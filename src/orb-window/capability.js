// Capability probe + quality tier.
//
// Runs once on the orb renderer's first boot per install (cached after).
// Detects hardware class and picks a tier: 'low' | 'mid' | 'high'.
// Every later waypoint imports `tier` and gates effects accordingly, so the
// same source code runs great on a ThinkPad and a gaming desktop.
//
// Gate table (what each tier enables):
//   framerate:      60 / 60 / 120
//   contourLines:    8 / 12 /  16
//   microTremors:   off / on /  on
//   motionTrails:    2 /  4 /   8   (ghost samples behind orb in flight)
//   idleParticles:   0 /  4 /   8   (max in-flight)
//   waveSweep:    color/color+noise/ full (color+noise+fresnel wave)
//   backdropFX:    off / off /  on  (chromatic ab, lens distort)
//   cursorPoll:    off /20Hz / 20Hz (for light-dir tracking)
//   proxWake:      off / on /  on   (cursor-proximity resting wake)
//
// The probe is defensive: any failure falls back to 'low' (never 'high', so
// a bad probe never over-commits a weak GPU). Override file takes precedence
// over probe so the user always wins.

// Storage keys piggyback on the existing IPC bridge's file API via the main
// process. The orb renderer can't touch `~/.ame/` directly (sandboxed), so we
// defer persistence to main via a new IPC channel. For tier-on-boot speed we
// also mirror to localStorage so we don't re-probe on every window load.

const LS_KEY = 'ame.capability.v2'   // bump to invalidate old bad detections

// ── Tier gate tables — canonical source of truth ───────────────────────────

export const TIER_GATES = {
  low: {
    framerate: 60,
    contourLines: 8,
    microTremors: false,
    motionTrails: 2,
    idleParticles: 0,
    waveSweep: 'color',
    backdropFX: false,
    cursorPoll: false,
    proxWake: false,
    fidgets: ['tilt', 'breathPause', 'contourPulse'],   // subtle-only
    chromaticAb: false,
    birthMs: 1500,
  },
  mid: {
    framerate: 60,
    contourLines: 12,
    microTremors: true,
    motionTrails: 4,
    idleParticles: 4,
    waveSweep: 'color+noise',
    backdropFX: false,
    cursorPoll: true,
    proxWake: true,
    fidgets: ['tilt', 'breathPause', 'contourPulse', 'accentShift', 'microBob', 'gazeDrift'],
    chromaticAb: false,
    birthMs: 2000,
  },
  high: {
    framerate: 120,
    contourLines: 16,
    microTremors: true,
    motionTrails: 8,
    idleParticles: 8,
    waveSweep: 'full',
    backdropFX: true,
    cursorPoll: true,
    proxWake: true,
    fidgets: ['tilt', 'breathPause', 'contourPulse', 'accentShift', 'microBob', 'gazeDrift', 'doubleBreath'],
    chromaticAb: true,
    birthMs: 2000,
  },
}

// ── Runtime state ──────────────────────────────────────────────────────────

let _detected = null   // the tier the probe actually detected
let _override = null   // user override, if any ('auto' means use detected)
let _gates = TIER_GATES.low  // default until probe completes — cautious floor

export function getTier() {
  if (_override && _override !== 'auto' && TIER_GATES[_override]) return _override
  return _detected || 'low'
}

export function getGates() {
  return _gates
}

export function setOverride(value) {
  // 'auto' | 'low' | 'mid' | 'high'
  _override = value
  _gates = TIER_GATES[getTier()] || TIER_GATES.low
  persist()
}

// ── Probe ──────────────────────────────────────────────────────────────────
// Returns a Promise<tier>. Runs WebGL renderer detection + a short framerate
// benchmark. Guaranteed to resolve within ~700ms even on a bad environment.

export async function probeCapability(opts = {}) {
  const force = !!opts.force

  // 1. Load cached result unless forced.
  if (!force) {
    const cached = loadCached()
    if (cached) {
      _detected = cached.detected
      _override = cached.override || null
      _gates = TIER_GATES[getTier()] || TIER_GATES.low
      return getTier()
    }
  }

  let detected = 'low'

  try {
    const gpuClass = detectGpuClass()          // 'weak' | 'mid' | 'strong'
    const refreshHz = detectRefreshRate()      // 60 | 90 | 120 | 144 | ...
    const fps = await measureFps(600)          // avg fps over 600ms, capped at refreshHz

    // Classify. We're conservative — promote to 'high' only when *all*
    // signals agree. One weak signal pulls us down a tier. A bad probe
    // (exception, NaN, etc) falls through to 'low' by default.
    if (gpuClass === 'strong' && refreshHz >= 120 && fps >= 110) {
      detected = 'high'
    } else if (gpuClass !== 'weak' && fps >= 55) {
      detected = 'mid'
    } else {
      detected = 'low'
    }
    console.log(`[Capability] probe gpu=${gpuClass} refreshHz=${refreshHz} fps=${fps} tier=${detected}`)
  } catch (err) {
    console.warn('[Capability] probe failed, falling back to low:', err?.message || err)
    detected = 'low'
  }

  _detected = detected
  _gates = TIER_GATES[getTier()] || TIER_GATES.low

  persist()

  // Let main process know — cinema-mode polling and cursor tracking both
  // need the tier to decide their own cadence.
  try {
    if (window.orbAPI?.reportCapability) {
      window.orbAPI.reportCapability({ detected, override: _override, gates: _gates })
    }
  } catch (_) {}

  return getTier()
}

// ── Detection helpers ──────────────────────────────────────────────────────

function detectGpuClass() {
  // Parse the WEBGL_debug_renderer_info string. Integrated iGPUs generally
  // have 'Intel', 'AMD Radeon Graphics' (integrated), 'Apple' (M-series is
  // strong, but we don't ship Mac yet). We're pessimistic — unknown strings
  // → 'mid' not 'strong'.
  let canvas, gl
  try {
    canvas = document.createElement('canvas')
    gl = canvas.getContext('webgl2') || canvas.getContext('webgl')
    if (!gl) return 'weak'
    const dbg = gl.getExtension('WEBGL_debug_renderer_info')
    if (!dbg) return 'mid'  // can't tell → cautious mid
    const renderer = gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) || ''
    const s = String(renderer).toLowerCase()

    // Strong signals — high-end discrete GPUs.
    if (/rtx\s*[234]0[6789]0|rtx\s*[234]0[6789]0\s*ti|geforce.*[234]0[6789]0|radeon.*rx\s*[67]\d\d\d|arc\s*a[57]\d\d/.test(s)) {
      return 'strong'
    }
    // Mid signals — dedicated GPUs that aren't top-tier but handle shaders fine.
    // GTX 1050/1060/1650/1660, RTX 2050/3050, Radeon RX 5500/5600, older Arc.
    if (/gtx\s*(1050|1060|1070|1080|1650|1660|1080)|rtx\s*(2050|3050)|radeon.*rx\s*(550|560|570|580|590|5300|5500|5600|6400|6500)|arc\s*a[34]\d\d|nvidia.*geforce/.test(s)) {
      return 'mid'
    }
    // Weak signals — known integrated lines.
    if (/intel.*(hd|uhd|iris xe|uhd graphics)|amd.*radeon graphics|vega.*[358]|ryzen.*graphics/.test(s)) {
      return 'weak'
    }
    // Unknown → mid. Safer default than 'strong'.
    return 'mid'
  } catch {
    return 'weak'
  } finally {
    try {
      if (gl && gl.getExtension) {
        const lose = gl.getExtension('WEBGL_lose_context')
        if (lose) lose.loseContext()
      }
    } catch (_) {}
  }
}

function detectRefreshRate() {
  // Best-effort. `window.screen` doesn't expose refresh reliably in Electron,
  // so we sample rAF timestamps. Good enough to distinguish 60 from 120+.
  // Called synchronously during probe; measureFps handles the async sampling.
  return _lastMeasuredRefresh || 60
}

let _lastMeasuredRefresh = 60

function measureFps(durationMs = 600) {
  return new Promise((resolve) => {
    const samples = []
    let last = performance.now()
    const start = last
    let rafId = 0
    const tick = (now) => {
      const dt = now - last
      last = now
      if (dt > 0 && dt < 100) samples.push(1000 / dt)  // ignore huge gaps (tab throttle)
      if (now - start < durationMs) {
        rafId = requestAnimationFrame(tick)
      } else {
        cancelAnimationFrame(rafId)
        if (samples.length === 0) return resolve(60)
        // Median is more stable than mean (ignores single-frame hitches).
        samples.sort((a, b) => a - b)
        const median = samples[Math.floor(samples.length / 2)]
        // Also infer refresh ceiling — max sustained fps ≈ display refresh.
        const top = Math.max(...samples.slice(-Math.min(10, samples.length)))
        _lastMeasuredRefresh = top >= 110 ? 120 : top >= 85 ? 90 : 60
        resolve(Math.round(median))
      }
    }
    rafId = requestAnimationFrame(tick)
  })
}

// ── Persistence (localStorage mirror + main-process file) ──────────────────

const PROBE_VERSION = 2  // bump when classification logic changes

function loadCached() {
  try {
    const raw = localStorage.getItem(LS_KEY)
    if (!raw) return null
    const data = JSON.parse(raw)
    if (!data || !TIER_GATES[data.detected]) return null
    if (data.probeVersion !== PROBE_VERSION) return null  // re-probe on upgrade
    return data
  } catch {
    return null
  }
}

function persist() {
  try {
    const data = {
      detected: _detected,
      override: _override,
      probeVersion: PROBE_VERSION,
      savedAt: new Date().toISOString(),
    }
    localStorage.setItem(LS_KEY, JSON.stringify(data))
    // Mirror to main process — survives localStorage wipe, available on boot
    // before the renderer probes.
    if (window.orbAPI?.reportCapability) {
      window.orbAPI.reportCapability(data)
    }
  } catch (_) {}
}
