
})
/**
 * WP-06 — Bloom-from-within.
 *
 * When the orb is anchored at home, summoning/dismissing shouldn't travel —
 * she *gathers herself* in place. This module drives the three-stage timeline
 * (gather → resolve → settle on summon; disperse → implode → settle on dismiss)
 * and emits IPC so the renderer can sweep uCoreWave, spawn particles, and
 * run the high-tier chromatic aberration pass.
 *
 * No window position work here — she's already home. The renderer does all
 * visuals; main only drives timing + stage boundaries.
 *
 * Returns { cancel() } — cancel stops the timeline and emits
 * `orb:bloom-stage { stage: 'cancel', dir }` so the renderer clears uCoreWave.
 */

'use strict'

// ── Summon timeline (900ms) ───────────────────────────────────
// gather: contour noise unfurl + core wave starts sweeping center→rim
// resolve: opacity/scale overshoot + chromatic ab (high tier)
// settle: breath rate ramp to 1.6× baseline, decay begins
const BLOOM_IN_MS = Object.freeze({
  gather:  360,
  resolve: 320,
  settle:  220,
})
const BLOOM_IN_TOTAL = BLOOM_IN_MS.gather + BLOOM_IN_MS.resolve + BLOOM_IN_MS.settle

// ── Dismiss timeline (640ms) ──────────────────────────────────
// disperse: contour speed spike + particles fly outward + fresnel invert
// implode: scale 1.0→0.84, opacity 1.0→0.2, 80ms flash at end
// settle: breath rate to 0.4× baseline
const BLOOM_OUT_MS = Object.freeze({
  disperse: 260,
  implode:  260,
  settle:   120,
})
const BLOOM_OUT_TOTAL = BLOOM_OUT_MS.disperse + BLOOM_OUT_MS.implode + BLOOM_OUT_MS.settle

const EMIT_MS = 1000 / 60

function playBloom(opts) {
  const { dir, emit, tier, onDone } = opts
  const isIn = dir === 'in'
  const stages = isIn ? BLOOM_IN_MS : BLOOM_OUT_MS
  const total = isIn ? BLOOM_IN_TOTAL : BLOOM_OUT_TOTAL

  const stageNames = isIn
    ? ['gather', 'resolve', 'settle']
    : ['disperse', 'implode', 'settle']

  const boundaries = [
    stages[stageNames[0]],
    stages[stageNames[0]] + stages[stageNames[1]],
    stages[stageNames[0]] + stages[stageNames[1]] + stages[stageNames[2]],
  ]

  let cancelled = false
  let doneCalled = false
  let lastStage = null
  let timer = null
  const startT = Date.now()

  function stageEmit(stage, extra) {
    if (cancelled) return
    if (lastStage === stage) return
    lastStage = stage
    emit('orb:bloom-stage', Object.assign({
      stage,
      dir,
      tier,
      t: Date.now() - startT,
      total,
    }, extra || {}))
  }

  function finish() {
    if (doneCalled) return
    doneCalled = true
    if (timer) { clearInterval(timer); timer = null }
    if (typeof onDone === 'function') {
      try { onDone() } catch (_) {}
    }
  }

  function cancel() {
    if (cancelled) return
    cancelled = true
    if (timer) { clearInterval(timer); timer = null }
    try {
      emit('orb:bloom-stage', {
        stage: 'cancel',
        dir,
        tier,
        t: Date.now() - startT,
      })
    } catch (_) {}
    finish()
  }

  // Kick the first stage immediately so the renderer begins sweeping before
  // the timer fires. Critical for the bloom to feel synchronous with the
  // summon hotkey press.
  stageEmit(stageNames[0])

  timer = setInterval(() => {
    if (cancelled) return
    const elapsed = Date.now() - startT

    if (elapsed < boundaries[0]) {
      stageEmit(stageNames[0])
    } else if (elapsed < boundaries[1]) {
      stageEmit(stageNames[1])
    } else if (elapsed < boundaries[2]) {
      stageEmit(stageNames[2])
    }

    // Progress within the whole bloom (0..1). Renderer uses this to drive
    // uCoreWave sweep; main reports it so renderer can stay frame-aligned.
    const progress = Math.min(1, elapsed / total)
    emit('orb:bloom-progress', { dir, tier, progress })

    if (elapsed >= total) {
      // Final settle re-emit with `final: true` so renderer can snap any
      // lingering bloom uniforms back to neutral (prevents stuck core wave).
      try {
        emit('orb:bloom-stage', {
          stage: 'settle',
          dir,
          tier,
          t: elapsed,
          final: true,
        })
      } catch (_) {}
      finish()
    }
  }, EMIT_MS)

  return { cancel }
}

module.exports = {
  playBloom,
  BLOOM_IN_MS,
  BLOOM_OUT_MS,
  BLOOM_IN_TOTAL,
  BLOOM_OUT_TOTAL