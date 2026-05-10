,
}
/**
 * WP-05 — Arrival choreography.
 *
 * Replaces the single-tween travel path with a five-stage performance:
 *   Anticipate (90ms)  → renderer squashes, breath freezes
 *   Launch     (130ms) → scale punch, trails start, speed spikes
 *   Flight     (440ms) → setPosition interp + directional squash (renderer)
 *   Arrival    (220ms) → overshoot + touchdown squash + DOM ripple
 *   Settle     (320ms) → breath ramps to 1.6× and decays
 *
 * Stage boundaries emit IPC so the renderer can handle its own visual bits
 * (squash, trails, ripple, particles) — main only drives window position and
 * timing. All stage tween constants live here so the rest of main.cjs stays
 * focused on window/identity concerns.
 *
 * This module is drop-in replaceable for `travelOrbTo` in main.cjs. It
 * cancels cleanly on interruption (dismiss mid-flight → call `cancel()`
 * and the timeline stops, renderer gets a `cancel` stage event to clear
 * squash/trails/ripple state).
 */

'use strict'

// Stage durations (ms). Total = 1200ms pre-settle, settle is 320ms on top.
// The settle is emitted-only — no position work — so the caller can release
// the move-suppression lock at `settleStartMs` if it wants snappy anchoring.
const STAGE_MS = Object.freeze({
  anticipate: 90,
  launch: 130,
  flight: 440,
  arrival: 220,
  settle: 320,
})
// WP-13 — cross-display flight is 620ms (vs 440ms same-display) with a
// boundary-crossing keyframe at the display edge. Rest of the stage table
// stays identical so timelines remain drop-in compatible.
const CROSS_DISPLAY_FLIGHT_MS = 620
// Brief core-wave brighten at the boundary — reads as "stepping through".
// 120ms ease-in-out pulse centered on the boundary moment.
const BOUNDARY_PULSE_MS = 120
const TOTAL_MOVE_MS = STAGE_MS.anticipate + STAGE_MS.launch + STAGE_MS.flight + STAGE_MS.arrival
const TOTAL_MS = TOTAL_MOVE_MS + STAGE_MS.settle

// Arrival overshoot — wider than the legacy 14px so the bounce reads.
const ARRIVAL_OVERSHOOT_PX = 12

// Flight IPC emit rate. 60Hz = every ~16ms. Matches renderer frame so
// directional squash lerps in without double-sampling.
const FLIGHT_EMIT_MS = 1000 / 60

// WP-13 — cross-display detection + boundary-point computation.
//
// Returns { x, y, tAlongFlight } where (x,y) is the point on the shared
// display edge that the orb should cross, and tAlongFlight ∈ (0,1) is the
// normalized eased-progress at which the boundary pulse fires (proportional
// to linear distance from source to boundary along the straight-line path).
// Returns null when source + target are on the same display, when no `screen`
// API is available, or when no shared edge exists (orphaned displays).
function computeCrossDisplay(screenApi, from, to) {
  if (!screenApi || typeof screenApi.getAllDisplays !== 'function') return null
  let displays
  try { displays = screenApi.getAllDisplays() } catch { return null }
  if (!Array.isArray(displays) || displays.length < 2) return null
  const srcDisplay = displayContaining(displays, from)
  const dstDisplay = displayContaining(displays, to)
  if (!srcDisplay || !dstDisplay) return null
  if (srcDisplay.id === dstDisplay.id) return null
  // Intersect the source display's bounds with the src→dst line; the exit
  // point is the boundary. Clamp slightly inside the edge (4px) so Windows
  // doesn't route the window to a neighboring monitor a frame early.
  const exit = segmentExit(srcDisplay.bounds, from, to)
  if (!exit) return null
  const srcToExit = Math.hypot(exit.x - from.x, exit.y - from.y)
  const total = Math.hypot(to.x - from.x, to.y - from.y) || 1
  const tAlongFlight = Math.max(0.15, Math.min(0.85, srcToExit / total))
  return { x: Math.round(exit.x), y: Math.round(exit.y), tAlongFlight }
}

function displayContaining(displays, pt) {
  for (const d of displays) {
    const b = d.bounds
    if (pt.x >= b.x && pt.x < b.x + b.width && pt.y >= b.y && pt.y < b.y + b.height) return d
  }
  return null
}

// Segment/rect exit — walks the parametric line from `from` to `to` and
// returns the first point where it leaves `rect`. Assumes `from` is inside
// rect (caller guarantees via displayContaining).
function segmentExit(rect, from, to) {
  const dx = to.x - from.x
  const dy = to.y - from.y
  if (dx === 0 && dy === 0) return null
  const xMin = rect.x
  const xMax = rect.x + rect.width
  const yMin = rect.y
  const yMax = rect.y + rect.height
  let tExit = 1
  if (dx > 0) tExit = Math.min(tExit, (xMax - from.x) / dx)
  else if (dx < 0) tExit = Math.min(tExit, (xMin - from.x) / dx)
  if (dy > 0) tExit = Math.min(tExit, (yMax - from.y) / dy)
  else if (dy < 0) tExit = Math.min(tExit, (yMin - from.y) / dy)
  if (!(tExit > 0 && tExit <= 1)) return null
  return { x: from.x + dx * tExit, y: from.y + dy * tExit }
}

function easeInCubic(t) {
  return t * t * t
}
function easeOutCubic(t) {
  const inv = 1 - t
  return 1 - inv * inv * inv
}
function easeInOutCubic(t) {
  return t < 0.5
    ? 4 * t * t * t
    : 1 - Math.pow(-2 * t + 2, 3) / 2
}

/**
 * playArrival(opts)
 *
 * opts = {
 *   orbWindow,         // BrowserWindow
 *   from: {x, y},      // start position (orbWindow.getPosition())
 *   to: {x, y},        // target position
 *   emit,              // (channel, payload) => void — forwardToOrb
 *   beginProgrammaticMove, // (ms) => void — foundation suppression helper
 *   tier,              // 'low' | 'mid' | 'high'
 *   onDone,            // () => void — called after settle stage completes
 * }
 *
 * Returns { cancel() } — cancel stops the timeline and emits
 * `orb:arrival-stage { stage: 'cancel' }` so the renderer clears trails,
 * squash, and any in-flight ripple.
 */
function playArrival(opts) {
  const {
    orbWindow, from, to, emit, beginProgrammaticMove, tier, onDone,
    // WP-13: caller can inject `screen` from Electron so we detect cross-
    // display travel without importing electron at module-load time (keeps
    // this file unit-testable in pure Node).
    screen: screenApi = null,
  } = opts

  if (!orbWindow || orbWindow.isDestroyed()) {
    if (typeof onDone === 'function') onDone()
    return { cancel() {} }
  }

  const dx = to.x - from.x
  const dy = to.y - from.y
  const mag = Math.sqrt(dx * dx + dy * dy) || 1
  const nvx = dx / mag
  const nvy = dy / mag
  const overshootX = to.x + nvx * ARRIVAL_OVERSHOOT_PX
  const overshootY = to.y + nvy * ARRIVAL_OVERSHOOT_PX

  // WP-13: detect cross-display travel + compute boundary point.
  // If both source and target are on the same display, `cross` is null and
  // the rest of the flight path is identical to the single-display path.
  // Otherwise we use the longer flight duration and a two-segment path that
  // crosses the shared display edge (not a straight line through the dead
  // zone between bezels — that reads as teleport).
  const cross = computeCrossDisplay(screenApi, from, to)
  const flightMs = cross ? CROSS_DISPLAY_FLIGHT_MS : STAGE_MS.flight

  // Suppress drag-detection for the whole move + a small trailing buffer.
  // Settle has no position work, so we don't extend the window for it.
  const totalMoveMs = STAGE_MS.anticipate + STAGE_MS.launch + flightMs + STAGE_MS.arrival
  beginProgrammaticMove(totalMoveMs + 120)

  const startT = Date.now()
  let cancelled = false
  let lastStage = null
  let flightTimer = null
  let doneCalled = false

  // Stage boundaries as ms from startT.
  const anticipateEnd = STAGE_MS.anticipate
  const launchEnd     = anticipateEnd + STAGE_MS.launch
  const flightEnd     = launchEnd + flightMs
  const arrivalEnd    = flightEnd + STAGE_MS.arrival
  const settleEnd     = arrivalEnd + STAGE_MS.settle

  // WP-13 boundary timestamp. Emitted exactly once when the orb's eased
  // progress crosses the display boundary. Using eased progress (not linear
  // time) keeps the pulse aligned with where she visually is, which matters
  // because the flight uses ease-out so mid-time ≠ mid-distance.
  let boundaryEmitted = !cross
  const boundaryProgress = cross ? cross.tAlongFlight : null

  function stageEmit(stage, extra) {
    if (cancelled) return
    if (lastStage === stage) return
    lastStage = stage
    emit('orb:arrival-stage', Object.assign({
      stage,
      tier,
      t: Date.now() - startT,
      velocity: { x: nvx, y: nvy },
      speed: mag / Math.max(1, STAGE_MS.flight),  // px/ms
    }, extra || {}))
  }

  // Kick the first stage immediately so the renderer starts squashing
  // before the position timer fires. This keeps anticipation visible even
  // when the travel distance is small.
  stageEmit('anticipate')

  function finish() {
    if (doneCalled) return
    doneCalled = true
    if (flightTimer) { clearInterval(flightTimer); flightTimer = null }
    if (typeof onDone === 'function') {
      try { onDone() } catch (_) {}
    }
  }

  function cancel() {
    if (cancelled) return
    cancelled = true
    if (flightTimer) { clearInterval(flightTimer); flightTimer = null }
    try {
      emit('orb:arrival-stage', {
        stage: 'cancel',
        tier,
        t: Date.now() - startT,
      })
    } catch (_) {}
    finish()
  }

  flightTimer = setInterval(() => {
    if (cancelled) return
    if (!orbWindow || orbWindow.isDestroyed()) { cancel(); return }

    const elapsed = Date.now() - startT

    // Stage dispatch — emit boundaries exactly once.
    if (elapsed < anticipateEnd) {
      stageEmit('anticipate')
    } else if (elapsed < launchEnd) {
      stageEmit('launch')
    } else if (elapsed < flightEnd) {
      stageEmit('flight')
    } else if (elapsed < arrivalEnd) {
      stageEmit('arrival')
    } else if (elapsed < settleEnd) {
      stageEmit('settle')
    }

    // Position timeline — only stages 2..4 move the window. Anticipation
    // and settle are renderer-only visual events.
    let x = from.x, y = from.y
    if (elapsed < anticipateEnd) {
      // Hold — she's coiling, not moving yet.
      x = from.x
      y = from.y
    } else if (elapsed < launchEnd) {
      // Launch: begin moving 20% of the way toward overshoot with a snappy
      // ease-in — the explosive uncompress already sells the start, so the
      // position ramp is small here.
      const t = (elapsed - anticipateEnd) / STAGE_MS.launch
      const e = easeInCubic(t) * 0.2
      x = Math.round(from.x + (overshootX - from.x) * e)
      y = Math.round(from.y + (overshootY - from.y) * e)
    } else if (elapsed < flightEnd) {
      // Flight: bulk of the travel. Ease-out from the launch's 20% to full
      // overshoot so velocity is highest mid-flight (where trails read best)
      // and decelerates into arrival.
      const t = (elapsed - launchEnd) / flightMs
      const e = 0.2 + easeOutCubic(t) * 0.8
      if (cross) {
        // WP-13 two-segment path via the display-boundary point. Segment
        // split at `cross.tAlongFlight` — eased progress before that is
        // travel to boundary, after is boundary → overshoot. Same ease-out
        // curve applies continuously; only the endpoint changes at tCross.
        const tCross = cross.tAlongFlight
        if (e < tCross) {
          const seg = e / tCross
          x = Math.round(from.x + (cross.x - from.x) * seg)
          y = Math.round(from.y + (cross.y - from.y) * seg)
        } else {
          const seg = (e - tCross) / (1 - tCross)
          x = Math.round(cross.x + (overshootX - cross.x) * seg)
          y = Math.round(cross.y + (overshootY - cross.y) * seg)
        }
        // Boundary pulse — emit once when eased progress crosses tCross.
        if (!boundaryEmitted && e >= tCross) {
          boundaryEmitted = true
          try {
            emit('orb:arrival-stage', {
              stage: 'boundary',
              tier,
              t: elapsed,
              pulseMs: BOUNDARY_PULSE_MS,
              velocity: { x: nvx, y: nvy },
            })
          } catch (_) {}
        }
      } else {
        x = Math.round(from.x + (overshootX - from.x) * e)
        y = Math.round(from.y + (overshootY - from.y) * e)
      }
    } else if (elapsed < arrivalEnd) {
      // Arrival: pull back from overshoot to target.
      const t = (elapsed - flightEnd) / STAGE_MS.arrival
      const e = easeInOutCubic(t)
      x = Math.round(overshootX + (to.x - overshootX) * e)
      y = Math.round(overshootY + (to.y - overshootY) * e)
    } else {
      // Settle: position already at target; renderer does the visual settle.
      x = to.x
      y = to.y
    }

    if (elapsed <= arrivalEnd) {
      try { orbWindow.setPosition(x, y, false) } catch (_) {}
    }

    // End of timeline — emit settle once more then finish.
    if (elapsed >= settleEnd) {
      try { orbWindow.setPosition(to.x, to.y, false) } catch (_) {}
      // Final settle re-emit — guards against renderer missing the first
      // `settle` IPC due to subscription timing or any dropped event.
      // Without this the orb can stick in the arrival-stage squash shape.
      try {
        emit('orb:arrival-stage', {
          stage: 'settle',
          tier,
          t: elapsed,
          velocity: { x: nvx, y: nvy },
          final: true,
        })
      } catch (_) {}
      finish()
    }
  }, FLIGHT_EMIT_MS)

  return { cancel }
}

module.exports = {
  playArrival,
  STAGE_MS,
  TOTAL_MS,
  TOTAL_MOVE_MS,
  CROSS_DISPLAY_FLIGHT_MS,
  BOUNDARY_PULSE_MS,
  computeCrossDisplay