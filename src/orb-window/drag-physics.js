// WP-07 — Drag physics.
//
// Creature-being-held feel layered on top of the WP-02 native window drag.
// Main process owns window position; this module owns the VISUAL transform
// (scale, tilt) of the orb body inside the window.
//
// Four stages:
//   1. Grab   (180ms) — startle pulse: 1.0 → 1.06 → 1.0
//   2. Resist (first 50ms of motion) — critically-damped spring lags behind
//      cursor briefly (stiffness 420, damping 28), then tightens (stiffness 900)
//   3. Follow (steady-state) — velocity-driven tilt + squash
//        rotZ   = clamp(vx * 0.0012, ±0.15)
//        scaleX = 1 + |v|*0.0006 along velocity
//        scaleY = 1 − |v|*0.0004 orthogonal, clamped ±8%
//      Velocity smoothed 60ms EMA.
//   4. Release (340ms) — underdamped wobble (stiffness 180, damping 10, one
//      overshoot), resolves to rest.
//
// All state is numeric + mutable; caller reads per-frame and applies to the
// scene. No React, no DOM.

const clamp = (v, lo, hi) => v < lo ? lo : v > hi ? hi : v

const STARTLE_MS   = 180
const RESIST_MS    = 50
const RELEASE_MS   = 340
const VELOCITY_TAU = 60  // ms EMA window

// Spring constants — see stage docs above.
const K_RESIST_EARLY = 420
const D_RESIST_EARLY = 28
const K_RESIST_LATE  = 900
const D_RESIST_LATE  = 60   // critically damped for late-resist
const K_RELEASE      = 180
const D_RELEASE      = 10

export function createDragPhysics() {
  // Mutable frame state. The renderer reads these after calling step().
  const state = {
    active: false,
    startedAt: 0,
    releasedAt: 0,
    // Velocity EMA (pixels per ms).
    vx: 0,
    vy: 0,
    // Last cursor sample for velocity derivation.
    lastX: 0,
    lastY: 0,
    lastT: 0,
    // Spring output — scale is a multiplier around 1.0.
    scale: 1.0,
    scaleVel: 0,
    rotZ: 0,
    rotZVel: 0,
    // Velocity-driven targets (follow stage). scaleAlong/Ortho project onto
    // scaleX/scaleY via velocity direction in the caller.
    scaleAlong: 1.0,
    scaleOrtho: 1.0,
    dirX: 1,
    dirY: 0,
  }

  function grab(x, y) {
    state.active = true
    state.startedAt = performance.now()
    state.releasedAt = 0
    state.lastX = x
    state.lastY = y
    state.lastT = state.startedAt
    state.vx = 0
    state.vy = 0
  }

  function move(x, y) {
    if (!state.active) return
    const t = performance.now()
    const dt = Math.max(1, t - state.lastT)
    const instVx = (x - state.lastX) / dt
    const instVy = (y - state.lastY) / dt
    const alpha = 1 - Math.exp(-dt / VELOCITY_TAU)
    state.vx += (instVx - state.vx) * alpha
    state.vy += (instVy - state.vy) * alpha
    state.lastX = x
    state.lastY = y
    state.lastT = t
  }

  function release() {
    if (!state.active) return
    state.active = false
    state.releasedAt = performance.now()
  }

  // Critically/underdamped spring step. Returns new (v, vel).
  function springStep(v, vel, target, k, d, dt) {
    const a = -k * (v - target) - d * vel
    const newVel = vel + a * dt
    const newV = v + newVel * dt
    return [newV, newVel]
  }

  // Call each animation frame. dtMs = frame delta in ms. Returns snapshot
  // the caller uses to update scene transforms. All outputs are deterministic
  // functions of state; caller is free to skip frames.
  function step(dtMs) {
    const dt = Math.min(0.05, dtMs / 1000)  // clamp to 50ms to survive hitches
    const now = performance.now()

    // Drive targets based on stage.
    let targetScale = 1.0
    let targetRot   = 0
    let kScale = K_RESIST_LATE
    let dScale = D_RESIST_LATE
    let kRot   = K_RESIST_LATE
    let dRot   = D_RESIST_LATE

    if (state.active) {
      const age = now - state.startedAt
      // Startle pulse — cosine bump in first STARTLE_MS.
      if (age < STARTLE_MS) {
        const u = age / STARTLE_MS
        // 0 → peak at 0.5 → 0. peak = 0.06 (scale 1.06).
        targetScale = 1.0 + 0.06 * Math.sin(u * Math.PI)
      }

      // Follow stage — velocity-driven tilt + squash.
      const speed = Math.hypot(state.vx, state.vy)  // px/ms
      if (age >= RESIST_MS && speed > 0) {
        const speedPxPerS = speed * 1000
        // Rotation: lean into motion. vx is px/ms → 0.0012 from plan targets
        // px/s scale, so multiply accordingly.
        targetRot = clamp(state.vx * 1000 * 0.0012 * 0.001, -0.15, 0.15)
        // Directional squash. Cache normalized direction for caller.
        const nx = state.vx / speed
        const ny = state.vy / speed
        state.dirX = nx
        state.dirY = ny
        const along = clamp(1 + speedPxPerS * 0.0006 * 0.001, 0.92, 1.08)
        const ortho = clamp(1 - speedPxPerS * 0.0004 * 0.001, 0.92, 1.08)
        state.scaleAlong += (along - state.scaleAlong) * 0.25
        state.scaleOrtho += (ortho - state.scaleOrtho) * 0.25
      } else {
        state.scaleAlong += (1.0 - state.scaleAlong) * 0.25
        state.scaleOrtho += (1.0 - state.scaleOrtho) * 0.25
      }

      // Early-resist uses a softer spring so she lags the startle / target.
      if (age < RESIST_MS) {
        kScale = K_RESIST_EARLY
        dScale = D_RESIST_EARLY
        kRot   = K_RESIST_EARLY
        dRot   = D_RESIST_EARLY
      }
    } else if (state.releasedAt > 0) {
      const rel = now - state.releasedAt
      if (rel < RELEASE_MS + 200) {
        // Underdamped wobble — targets are neutral (1.0, 0), spring parameters
        // produce a single overshoot before settling.
        kScale = K_RELEASE
        dScale = D_RELEASE
        kRot   = K_RELEASE
        dRot   = D_RELEASE
      } else {
        state.releasedAt = 0
      }
      state.scaleAlong += (1.0 - state.scaleAlong) * 0.2
      state.scaleOrtho += (1.0 - state.scaleOrtho) * 0.2
    }

    ;[state.scale, state.scaleVel] = springStep(
      state.scale, state.scaleVel, targetScale, kScale, dScale, dt)
    ;[state.rotZ, state.rotZVel] = springStep(
      state.rotZ, state.rotZVel, targetRot, kRot, dRot, dt)

    return {
      active:     state.active,
      scale:      state.scale,
      rotZ:       state.rotZ,
      scaleAlong: state.scaleAlong,
      scaleOrtho: state.scaleOrtho,
      dirX:       state.dirX,
      dirY:       state.dirY,
      age:        state.active ? (now - state.startedAt) : 0,
    }
  }

  return { grab, move, release, step, _state: state }
}
