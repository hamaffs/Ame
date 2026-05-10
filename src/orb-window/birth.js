// WP-12 — Birth timeline.
//
// One-shot state machine that drives the orb's first moment of visible life
// after a clean install. Stages, timings:
//
//   absence   0 ..  350ms  — orb fully invisible. Main window dims overlay.
//   seed      350 ..  650ms — 8px soft-white dot pulses 0→1→0.7. Not the orb.
//   unfurl    650 .. 1450ms — contour shader radial-reveal from center,
//                              noise scale ramps 0.1 → emotion-baseline.
//   hold     1450 .. 1650ms — full orb, holds still (anticipation).
//   breath   1650 .. 1870ms — first inhale (scale 1.0 → 1.04), core wave fires.
//   done     1870ms onward — birthT pinned at 1.0, first word travel + speech.
//
// Low tier compresses total duration to 1.5s: unfurl 500ms instead of 800ms,
// hold 120ms, breath 180ms. The seed + absence stay visible for humanity.
//
// Consumer reads { stage, seedOpacity, seedPulse, birthT, noiseScaleOverride,
// scalePulse, coreWavePulse } each frame. Birth owner (OrbWindow) also
// forwards `stage` events upward via IPC so main can trigger side-effects
// (travel to center at breath-end, backend first-sentence speech, marker
// write). Renderer never talks to main.

const TIMINGS = {
  high: { absence: 350, seed: 300, unfurl: 800, hold: 200, breath: 220 },
  mid:  { absence: 350, seed: 300, unfurl: 800, hold: 200, breath: 220 },
  low:  { absence: 300, seed: 240, unfurl: 500, hold: 120, breath: 180 },
}

const clamp01 = (v) => v < 0 ? 0 : v > 1 ? 1 : v
const easeOutCubic = (t) => 1 - Math.pow(1 - t, 3)
const easeInOutCubic = (t) => t < 0.5 ? 4*t*t*t : 1 - Math.pow(-2*t + 2, 3) / 2

export function createBirth({ onStage, tier = 'mid' } = {}) {
  const timings = TIMINGS[tier] || TIMINGS.mid
  const t0 = timings.absence
  const t1 = t0 + timings.seed
  const t2 = t1 + timings.unfurl
  const t3 = t2 + timings.hold
  const t4 = t3 + timings.breath
  const totalMs = t4

  const state = {
    running:    false,
    startAt:    0,
    stage:      'idle',   // 'idle' | 'absence' | 'seed' | 'unfurl' | 'hold' | 'breath' | 'done'
    seedOpacity: 0,       // 0..1, dot alpha for the DOM seed
    birthT:      1.0,     // radial reveal (0..1, 1 = full orb)
    noiseScaleOverride: null, // during unfurl only; null otherwise
    scalePulse:  0,       // additive scale offset (first inhale)
    coreWavePulse: 0,     // 0..1, reused by OrbScene's core wave uniform
  }

  let lastStageSent = 'idle'
  function emitStage(name) {
    if (name === lastStageSent) return
    lastStageSent = name
    try { onStage && onStage({ stage: name, tier, totalMs, now: performance.now() }) }
    catch {}
  }

  function start() {
    if (state.running) return
    state.running = true
    state.startAt = performance.now()
    state.stage = 'absence'
    state.seedOpacity = 0
    state.birthT = 0
    state.noiseScaleOverride = 0.1
    state.scalePulse = 0
    state.coreWavePulse = 0
    lastStageSent = 'idle'
    emitStage('absence')
  }

  function stop() {
    state.running = false
    state.stage = 'done'
    state.seedOpacity = 0
    state.birthT = 1.0
    state.noiseScaleOverride = null
    state.scalePulse = 0
    state.coreWavePulse = 0
  }

  function step(nowMs) {
    if (!state.running) return state
    const t = (nowMs ?? performance.now()) - state.startAt

    if (t < t0) {
      state.stage = 'absence'
      state.seedOpacity = 0
      state.birthT = 0
      state.noiseScaleOverride = 0.1
    } else if (t < t1) {
      // Seed: 0 → 1 → 0.7 over its window. Peaks at 50%.
      const k = (t - t0) / timings.seed
      const pulse = k < 0.5 ? (k / 0.5) : (1.0 - (k - 0.5) / 0.5 * 0.3)
      state.stage = 'seed'
      state.seedOpacity = clamp01(pulse)
      state.birthT = 0
      state.noiseScaleOverride = 0.1
      emitStage('seed')
    } else if (t < t2) {
      // Unfurl. Radial reveal + noise-scale ramp. Seed fades out quickly.
      const k = clamp01((t - t1) / timings.unfurl)
      const ek = easeOutCubic(k)
      state.stage = 'unfurl'
      // Seed fades to 0 in the first 30% of unfurl (smooth handoff).
      state.seedOpacity = clamp01(0.7 * (1.0 - k / 0.3))
      state.birthT = ek
      // Noise 0.1 → 1.8 (watching baseline) across unfurl. OrbScene lerps
      // this naturally back to CONTOUR_CFG baseline when we release (null).
      state.noiseScaleOverride = 0.1 + (1.8 - 0.1) * ek
      emitStage('unfurl')
    } else if (t < t3) {
      state.stage = 'hold'
      state.seedOpacity = 0
      state.birthT = 1.0
      state.noiseScaleOverride = null
      emitStage('hold')
    } else if (t < t4) {
      // First breath: inhale 1.0 → 1.04 over the window, core wave rides 0→1.
      const k = clamp01((t - t3) / timings.breath)
      const ek = easeInOutCubic(k)
      state.stage = 'breath'
      state.birthT = 1.0
      state.scalePulse = 0.04 * ek
      state.coreWavePulse = ek
      emitStage('breath')
    } else {
      state.stage = 'done'
      state.birthT = 1.0
      state.noiseScaleOverride = null
      state.scalePulse = 0
      state.coreWavePulse = 0
      state.running = false
      emitStage('done')
    }
    return state
  }

  return {
    start, stop, step, state,
    get isRunning() { return state.running },
    get totalMs() { return totalMs },
  }
}
