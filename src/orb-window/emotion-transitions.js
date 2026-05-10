// WP-08 — Emotion wave-sweep transitions.
//
// When emotion changes, crossfade old↔new params over 420ms. Renderer
// visualizes the crossfade as a wave sweeping across the orb surface, starting
// from the point on the orb nearest to the cursor (so the change flows *from*
// the user toward the opposite rim).
//
// What crossfades:
//   - accent color (shader `uColorBase` / line color)
//   - contour noise scale
//   - breath rate (JS — lerped in OrbScene animate loop via new target)
//   - fresnel intensity (shader, high tier only)
//
// Mid-transition retargets: the mix progress keeps its current 0..1 value,
// "old" becomes the currently-displayed interpolated state, "new" becomes the
// next emotion's params. The wave origin does NOT restart from 0 — it simply
// retargets. This way rapid emotion changes feel like a single continuous
// retargeting, not a flash of resets.
//
// All timing is numeric + mutable. No React, no DOM.

import * as THREE from 'three'

const DURATION_MS = 420

const clamp = (v, lo, hi) => v < lo ? lo : v > hi ? hi : v
const easeInOutCubic = (t) => t < 0.5 ? 4*t*t*t : 1 - Math.pow(-2*t + 2, 3) / 2

// Full emotion param table. Separate from EMOTION_CFG in OrbScene (which owns
// runtime mapping); this is the static material palette the sweep crossfades.
// Keep in sync with EMOTION_CFG entries.
export const EMOTION_PARAMS = {
  watching:  { accent: '#7dd3fc', noiseScale: 1.8, fresnel: 1.0 },
  curious:   { accent: '#a78bfa', noiseScale: 2.4, fresnel: 1.2 },
  holding:   { accent: '#fb7185', noiseScale: 1.4, fresnel: 0.85 },
  excited:   { accent: '#fbbf24', noiseScale: 2.8, fresnel: 1.3 },
  withdrawn: { accent: '#64748b', noiseScale: 1.2, fresnel: 0.7 },
  listening: { accent: '#22d3ee', noiseScale: 2.0, fresnel: 1.05 },
  thinking:  { accent: '#c084fc', noiseScale: 2.6, fresnel: 1.1 },
}

const DEFAULT_PARAMS = EMOTION_PARAMS.watching

export function getEmotionParams(name) {
  return EMOTION_PARAMS[name] || DEFAULT_PARAMS
}

// Parse "#rrggbb" → THREE.Color, cached.
const _colorCache = new Map()
function colorOf(hex) {
  let c = _colorCache.get(hex)
  if (!c) {
    c = new THREE.Color(hex)
    _colorCache.set(hex, c)
  }
  return c
}

export function createEmotionTransition(initialEmotion = 'watching') {
  const initial = getEmotionParams(initialEmotion)

  const state = {
    // When a transition is active: mix progresses 0→1 over DURATION_MS.
    // At rest (no transition): mix=0, oldParams === liveParams, newParams === liveParams.
    active: false,
    startedAt: 0,
    mix: 0,                      // 0..1 — eased progress through the crossfade

    // Param snapshots. `old` = state at trigger time. `live` = what we hand the
    // renderer each frame (old*(1-mix) + new*mix, done scalar-wise). `new` =
    // target emotion params.
    oldAccent: colorOf(initial.accent).clone(),
    newAccent: colorOf(initial.accent).clone(),
    liveAccent: colorOf(initial.accent).clone(),

    oldNoise: initial.noiseScale,
    newNoise: initial.noiseScale,
    liveNoise: initial.noiseScale,

    oldFresnel: initial.fresnel,
    newFresnel: initial.fresnel,
    liveFresnel: initial.fresnel,

    // Wave origin — unit vector on the orb surface where the sweep starts.
    // The renderer uses this with mesh-space normals to build the wavefront.
    // Defaults to +X (right side) so first trigger without a cursor hint
    // still has a sensible direction.
    waveOriginX: 1,
    waveOriginY: 0,
    waveOriginZ: 0,

    // For cue particle emit — consumers set a flag here and clear on read.
    cuePending: false,
    cueAccent: '#ffffff',

    // Current emotion name (for downstream code that wants it).
    emotion: initialEmotion,
  }

  // Trigger a new transition. `origin` is an optional {x, y, z} unit vector on
  // the orb surface where the wavefront starts. If null, keeps the last origin.
  // Called by the OrbWindow when the `emotion` prop changes.
  function trigger(nextEmotion, origin) {
    const next = getEmotionParams(nextEmotion)

    // Retarget: the current live interpolated values become the new "old"
    // anchor. This makes a second trigger mid-transition glide from where she
    // is right now, not snap back to the previous anchor.
    state.oldAccent.copy(state.liveAccent)
    state.oldNoise = state.liveNoise
    state.oldFresnel = state.liveFresnel

    state.newAccent.copy(colorOf(next.accent))
    state.newNoise = next.noiseScale
    state.newFresnel = next.fresnel

    if (origin) {
      const m = Math.hypot(origin.x || 0, origin.y || 0, origin.z || 0)
      if (m > 0.001) {
        state.waveOriginX = (origin.x || 0) / m
        state.waveOriginY = (origin.y || 0) / m
        state.waveOriginZ = (origin.z || 0) / m
      }
    }

    state.active = true
    state.startedAt = performance.now()
    state.mix = 0
    state.emotion = nextEmotion
    state.cuePending = true
    state.cueAccent = next.accent
  }

  // Call once per frame. Advances mix, updates live params, returns snapshot
  // the renderer applies to uniforms. No-op when inactive.
  function step() {
    if (state.active) {
      const age = performance.now() - state.startedAt
      const u = clamp(age / DURATION_MS, 0, 1)
      state.mix = easeInOutCubic(u)
      // Lerp live values. Color lerp is channel-wise (THREE.Color.lerpColors).
      state.liveAccent.lerpColors(state.oldAccent, state.newAccent, state.mix)
      state.liveNoise = state.oldNoise + (state.newNoise - state.oldNoise) * state.mix
      state.liveFresnel = state.oldFresnel + (state.newFresnel - state.oldFresnel) * state.mix
      if (u >= 1) {
        state.active = false
        state.mix = 0
        // Collapse old/new so next frame has clean anchors.
        state.oldAccent.copy(state.liveAccent)
        state.oldNoise = state.liveNoise
        state.oldFresnel = state.liveFresnel
      }
    }
    return state
  }

  function consumeCue() {
    if (!state.cuePending) return null
    state.cuePending = false
    return { accent: state.cueAccent, originX: state.waveOriginX, originY: state.waveOriginY }
  }

  return { trigger, step, consumeCue, _state: state }
}
