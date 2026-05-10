// WP-09 — Idle fidgets.
//
// When she's been still for a while, pick a small involuntary action so the
// orb doesn't read as "paused video." Think: shifting weight on a couch,
// brushing hair back, a sigh. Nothing that demands attention — if a user
// catches one, it should feel like peripheral motion, not a show.
//
// Scheduler:
//   - Between fidgets: random gap in [20s, 60s].
//   - On any interaction (emotion change, drag, hover, summon), push +30s
//     onto the next-gap timer. She doesn't fidget while "engaged."
//   - Only ticks while visibility ∈ {'active', 'resting-aware'}.
//     Resting proper / ghost / hidden = fully still (she's asleep).
//   - Weighted pick across 7 fidgets. Low tier disables 3 of them.
//
// State handoff to the renderer:
//   The scheduler mutates `fidget` (a shared state object) — breath-rate
//   scalar, rotZ offset, contour band, accent hue shift, light-dir drift,
//   Y-bob (IPC to main). OrbScene reads these each frame and sums them with
//   other contributors. Scheduler never talks to THREE directly.
//
// All timings are numeric + mutable. No React, no DOM.

const MIN_GAP_MS = 20_000
const MAX_GAP_MS = 60_000
const INTERACTION_PUSH_MS = 30_000

const clamp = (v, lo, hi) => v < lo ? lo : v > hi ? hi : v
const easeInOutCubic = (t) => t < 0.5 ? 4*t*t*t : 1 - Math.pow(-2*t + 2, 3) / 2
const easeOutCubic = (t) => 1 - Math.pow(1 - t, 3)

// Weight table. Sums don't need to be 100 — picker normalizes.
// Rarer fidgets (double-breath, micro-bob) stay rare intentionally.
const FIDGET_WEIGHTS = {
  slowTilt:      25,
  breathPause:   25,
  contourPulse:  25,
  hueShift:      10,
  gazeDrift:      8,
  microBob:       4,
  doubleBreath:   3,
}

// Low-tier disables anything that touches shader uniforms she doesn't have
// budget for, plus the main-process bob (cheap, but window moves are costly
// on low-end displays).
const LOW_TIER_DISABLED = new Set(['contourPulse', 'microBob', 'doubleBreath'])

function pickFidget(rand, tier) {
  const entries = Object.entries(FIDGET_WEIGHTS).filter(([k]) =>
    tier !== 'low' || !LOW_TIER_DISABLED.has(k)
  )
  let total = 0
  for (const [, w] of entries) total += w
  let r = rand() * total
  for (const [k, w] of entries) {
    r -= w
    if (r <= 0) return k
  }
  return entries[0][0]
}

// Shared state. Renderer reads each field every frame; scheduler mutates.
// All fields are zero-at-rest so summing with other contributors is safe.
function createFidgetState() {
  return {
    // Extra seconds-per-breath-cycle multiplier. 1.0 = no change.
    breathRateMul: 1.0,
    // Extra hold at bottom of exhale (seconds). 0 at rest.
    breathHoldBottom: 0,
    // Z rotation offset (radians). Summed with drag rotZ + arrival rotZ.
    rotZ: 0,
    // Contour speed scalar. 1.0 = neutral.
    contourSpeedMul: 1.0,
    // Accent hue shift in degrees. Applied by renderer via HSL.
    accentHueShift: 0,
    // Light direction offset (unit vector). At rest (0,0,0) = use default.
    lightOffsetX: 0,
    lightOffsetY: 0,
    // Contour highlight band — 0..1 position along surfaceDist, and intensity.
    highlightBand: 0.5,
    highlightIntensity: 0,  // 0 = disabled
    // Current fidget name (null = idle). For debug / telemetry.
    current: null,
  }
}

// Each fidget is a function (state, t) => boolean; returns false when done.
// `t` is seconds since the fidget started. Pure: no DOM, no IPC.
const FIDGETS = {
  // 1. Slow tilt — small rotZ ±0.12 over 1.8s, hold 300ms, return.
  // Contour speed dip 20% during the hold (she's "leaning into a thought").
  slowTilt: {
    duration: 3.3,  // 1.8 tilt + 0.3 hold + 1.2 return
    apply(state, t, ctx) {
      const dir = ctx.dir  // ±1 set at trigger
      if (t < 1.8) {
        const u = easeInOutCubic(t / 1.8)
        state.rotZ = 0.12 * dir * u
        state.contourSpeedMul = 1.0 - 0.20 * u
      } else if (t < 2.1) {
        state.rotZ = 0.12 * dir
        state.contourSpeedMul = 0.80
      } else {
        const u = easeInOutCubic((t - 2.1) / 1.2)
        state.rotZ = 0.12 * dir * (1 - u)
        state.contourSpeedMul = 0.80 + 0.20 * u
      }
      return t < 3.3
    },
  },

  // 2. Breath pause — hold bottom of exhale 1.5s. The shader's breath driver
  // reads `breathHoldBottom`; during the hold we freeze phase near 1.0 (fully
  // exhaled), so the sphere stops pulsing for a visible beat.
  breathPause: {
    duration: 1.5,
    apply(state, t) {
      state.breathHoldBottom = t < 1.5 ? 1.5 - t : 0
      return t < 1.5
    },
  },

  // 3. Contour pulse — brighten one UV band for 700ms. Band position is
  // picked at trigger; intensity curves 0→1→0 across duration.
  contourPulse: {
    duration: 0.7,
    apply(state, t, ctx) {
      state.highlightBand = ctx.band
      const u = t / 0.7
      state.highlightIntensity = Math.sin(u * Math.PI) * 0.8
      return t < 0.7
    },
  },

  // 4. Accent hue micro-shift — ±5° over 1.2s, hold 400ms, return.
  hueShift: {
    duration: 2.8,
    apply(state, t, ctx) {
      const dir = ctx.dir
      if (t < 1.2) {
        state.accentHueShift = 5 * dir * easeInOutCubic(t / 1.2)
      } else if (t < 1.6) {
        state.accentHueShift = 5 * dir
      } else {
        const u = easeInOutCubic((t - 1.6) / 1.2)
        state.accentHueShift = 5 * dir * (1 - u)
      }
      return t < 2.8
    },
  },

  // 5. Gaze drift — light direction wanders over 2.5s, returns.
  // Small offsets: ±0.25 in x/y so specular highlight moves a few pixels.
  gazeDrift: {
    duration: 2.5,
    apply(state, t, ctx) {
      const u = t / 2.5
      // Smooth there-and-back via sin(π·u).
      const arc = Math.sin(u * Math.PI)
      state.lightOffsetX = ctx.dx * arc
      state.lightOffsetY = ctx.dy * arc
      return t < 2.5
    },
  },

  // 6. Micro-bob — window Y +3px then return. Uses IPC to main since window
  // position lives there. 900ms total. Scheduler fires the IPC at t=0; the
  // shared state doesn't carry any local contribution for this one.
  microBob: {
    duration: 0.9,
    trigger(ctx) {
      try {
        // Preload exposes this via orbAPI (see preload.cjs WP-09 entry).
        if (typeof window !== 'undefined' && window.orbAPI?.fidgetBob) {
          window.orbAPI.fidgetBob()
        }
      } catch (_) {}
    },
    apply(_state, t) {
      return t < 0.9
    },
  },

  // 7. Double breath — two quick shallow inhales. Breath rate spikes 3× for
  // 600ms, returns to 1× over 200ms. Rare: reads as a quick sigh.
  doubleBreath: {
    duration: 0.8,
    apply(state, t) {
      if (t < 0.6) {
        state.breathRateMul = 3.0
      } else {
        state.breathRateMul = 3.0 - 2.0 * ((t - 0.6) / 0.2)
      }
      return t < 0.8
    },
  },
}

export function createFidgetScheduler(opts = {}) {
  const {
    getActive = () => true,
    getTier = () => 'mid',
    rand = Math.random,
  } = opts

  const state = createFidgetState()

  // Internal scheduler clock.
  let running = false
  let nextAt = 0        // perf.now() timestamp of next fidget
  let currentName = null
  let currentStartedAt = 0
  let currentCtx = null
  let forceBypassActive = false  // dev: forceFire sets this so step doesn't kill on ghost visibility

  function scheduleNext() {
    const gap = MIN_GAP_MS + rand() * (MAX_GAP_MS - MIN_GAP_MS)
    nextAt = performance.now() + gap
  }

  function start() {
    if (running) return
    running = true
    scheduleNext()
  }

  function stop() {
    running = false
    currentName = null
    // Reset shared state so no lingering fidget contribution bleeds through
    // after stop (e.g., visibility flipped to 'resting').
    Object.assign(state, createFidgetState())
  }

  // Call when user interacts with the orb. Pushes next fidget out so she
  // doesn't fidget while the user is actively looking at her.
  function pushInteraction() {
    if (!running) return
    nextAt = Math.max(nextAt, performance.now() + INTERACTION_PUSH_MS)
  }

  function triggerFidget() {
    const tier = getTier()
    const name = pickFidget(rand, tier)
    const def = FIDGETS[name]
    if (!def) { scheduleNext(); return }
    currentName = name
    currentStartedAt = performance.now()
    // Build per-trigger context (direction, band, etc.).
    currentCtx = {
      dir: rand() < 0.5 ? -1 : 1,
      band: rand(),
      dx: (rand() - 0.5) * 0.5,
      dy: (rand() - 0.5) * 0.5,
    }
    state.current = name
    if (def.trigger) def.trigger(currentCtx)
  }

  function step() {
    if (!running) return state
    if (!getActive() && !forceBypassActive) {
      // Visibility dropped mid-fidget. Reset and wait for re-start.
      if (currentName) {
        currentName = null
        Object.assign(state, createFidgetState())
      }
      return state
    }
    const now = performance.now()
    if (currentName) {
      const def = FIDGETS[currentName]
      const tSec = (now - currentStartedAt) / 1000
      // Reset state deltas before applying so fidget owns its own contribution.
      state.breathRateMul = 1.0
      state.breathHoldBottom = 0
      state.rotZ = 0
      state.contourSpeedMul = 1.0
      state.accentHueShift = 0
      state.lightOffsetX = 0
      state.lightOffsetY = 0
      state.highlightIntensity = 0
      const alive = def.apply(state, tSec, currentCtx)
      if (!alive) {
        // Fidget done — clear and schedule next.
        currentName = null
        currentCtx = null
        state.current = null
        state.breathRateMul = 1.0
        state.breathHoldBottom = 0
        state.rotZ = 0
        state.contourSpeedMul = 1.0
        state.accentHueShift = 0
        state.lightOffsetX = 0
        state.lightOffsetY = 0
        state.highlightIntensity = 0
        forceBypassActive = false
        scheduleNext()
      }
    } else if (now >= nextAt) {
      triggerFidget()
    }
    return state
  }

  // Dev helper: force next fidget now (optional name override). Returns name.
  function forceFire(name) {
    if (!running) start()
    forceBypassActive = true
    if (name && FIDGETS[name]) {
      const def = FIDGETS[name]
      currentName = name
      currentStartedAt = performance.now()
      currentCtx = {
        dir: rand() < 0.5 ? -1 : 1,
        band: rand(),
        dx: (rand() - 0.5) * 0.5,
        dy: (rand() - 0.5) * 0.5,
      }
      state.current = name
      if (def.trigger) def.trigger(currentCtx)
    } else {
      triggerFidget()
    }
    return state.current
  }

  return { start, stop, step, pushInteraction, forceFire, _state: state }
}
