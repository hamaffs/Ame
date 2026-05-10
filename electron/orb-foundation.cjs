,
}
// Orb foundation: state cache, home persistence, move-suppression guard.
// All orb-related state that needs to survive window recreate lives here.
//
// The state cache is replayed to the renderer after every recreate, so a
// crashed orb comes back as she was, not as a blank default.
//
// Home persistence is crash-tolerant: corrupt files fall back silently,
// missing files are fine, partial writes don't brick startup.

const fs = require('fs')
const path = require('path')
const os = require('os')

const AME_DIR = path.join(os.homedir(), '.ame')
const HOME_FILE = path.join(AME_DIR, 'overlay_position.json')
const CAPABILITY_FILE = path.join(AME_DIR, 'capability.json')

// ── State cache ────────────────────────────────────────────────────────────
// Single source of truth for what the orb "is" right now. Every IPC handler
// that forwards to the orb updates this first, so createOrbWindow can replay.

const orbStateCache = {
  state: 'idle',
  emotion: 'watching',
  accent: '#00d084',
  visibility: 'ghost',   // 'active' | 'resting' | 'resting-aware' | 'hidden' | 'ghost'
  micLevel: 0,
  dock: 'corner',
}

function setCache(key, value) {
  orbStateCache[key] = value
}

function getCache() {
  return orbStateCache
}

function replayStateToOrb(forwardFn) {
  // Called after createOrbWindow + did-finish-load. Sends every cached field
  // so the renderer boots into the correct state, not defaults.
  try {
    forwardFn('orb:state',   { state: orbStateCache.state })
    forwardFn('orb:emotion', { emotion: orbStateCache.emotion })
    forwardFn('orb:accent',  { color: orbStateCache.accent })
    forwardFn('orb:visibility', {
      state: orbStateCache.visibility,
      reason: 'recreate-replay',
    })
  } catch (_) {}
}

// ── Home persistence ───────────────────────────────────────────────────────

function ensureAmeDir() {
  try {
    if (!fs.existsSync(AME_DIR)) fs.mkdirSync(AME_DIR, { recursive: true })
  } catch (_) {}
}

function loadSavedHome() {
  try {
    if (!fs.existsSync(HOME_FILE)) return null
    const raw = fs.readFileSync(HOME_FILE, 'utf8')
    const data = JSON.parse(raw)
    if (typeof data?.x !== 'number' || typeof data?.y !== 'number') return null
    if (!Number.isFinite(data.x) || !Number.isFinite(data.y)) return null
    return { x: Math.round(data.x), y: Math.round(data.y), savedAt: data.savedAt || null }
  } catch (err) {
    console.warn('[Orb] saved home unreadable; falling back to default:', err?.message || err)
    return null
  }
}

function saveHome(x, y) {
  ensureAmeDir()
  console.log(`[Orb:saveHome] x=${x} y=${y} caller=${new Error().stack?.split('\n')[2]?.trim()}`)
  const data = {
    x: Math.round(x),
    y: Math.round(y),
    savedAt: new Date().toISOString(),
  }
  try {
    // Atomic-ish write: tmp then rename, so a crash mid-write doesn't leave
    // garbage in HOME_FILE (we'd rather lose this save than corrupt the file).
    const tmp = HOME_FILE + '.tmp'
    fs.writeFileSync(tmp, JSON.stringify(data, null, 2))
    fs.renameSync(tmp, HOME_FILE)
  } catch (err) {
    console.warn('[Orb] failed to save home:', err?.message || err)
  }
}

// ── Capability persistence ─────────────────────────────────────────────────
// Mirrored to ~/.ame/capability.json so main process knows the tier on boot
// (before the renderer has had a chance to probe). Cinema mode and cursor
// polling both care about this.

let _capabilityCache = null  // { detected, override, gates, savedAt }

const CAPABILITY_PROBE_VERSION = 2  // must match PROBE_VERSION in capability.js

function loadCapability() {
  if (_capabilityCache) return _capabilityCache
  try {
    if (!fs.existsSync(CAPABILITY_FILE)) return null
    const raw = fs.readFileSync(CAPABILITY_FILE, 'utf8')
    const data = JSON.parse(raw)
    if (data && typeof data === 'object') {
      // Stale schema? Ignore so the renderer re-probes with current logic.
      if (data.probeVersion !== CAPABILITY_PROBE_VERSION) return null
      _capabilityCache = data
      return data
    }
  } catch (err) {
    console.warn('[Capability] persisted file unreadable:', err?.message || err)
  }
  return null
}

function saveCapability(data) {
  ensureAmeDir()
  try {
    _capabilityCache = { ...data, savedAt: new Date().toISOString() }
    const tmp = CAPABILITY_FILE + '.tmp'
    fs.writeFileSync(tmp, JSON.stringify(_capabilityCache, null, 2))
    fs.renameSync(tmp, CAPABILITY_FILE)
  } catch (err) {
    console.warn('[Capability] save failed:', err?.message || err)
  }
}

function getCapabilityTier() {
  const c = loadCapability()
  if (!c) return 'low'  // conservative default
  if (c.override && c.override !== 'auto') return c.override
  return c.detected || 'low'
}

// ── Move-suppression flag ──────────────────────────────────────────────────
// Set true around every programmatic setPosition / setBounds call. Drag
// detection ignores 'move' events while this is true, so our own animations
// never self-anchor the orb.

let suppressMoveEvents = false
let suppressClearTimer = null

function beginProgrammaticMove(extraMs = 200) {
  suppressMoveEvents = true
  if (suppressClearTimer) clearTimeout(suppressClearTimer)
  suppressClearTimer = setTimeout(() => {
    suppressMoveEvents = false
    suppressClearTimer = null
  }, extraMs)
}

function endProgrammaticMove() {
  // Allow callers to explicitly end early. The timer keeps a safety net in
  // case the caller forgets — suppression auto-clears after 200ms.
  if (suppressClearTimer) {
    clearTimeout(suppressClearTimer)
    suppressClearTimer = null
  }
  suppressMoveEvents = false
}

function isProgrammaticMove() {
  return suppressMoveEvents
}

// ── Multi-display home clamp ───────────────────────────────────────────────
// If the saved point is inside a connected display, use it. If not (monitor
// unplugged), fall back to the default home on primary — but don't clear the
// saved point. User plugs the monitor back in, she returns next launch.

function isPointInAnyDisplay(point, allDisplays) {
  for (const d of allDisplays) {
    const wa = d.workArea
    if (point.x >= wa.x && point.x < wa.x + wa.width &&
        point.y >= wa.y && point.y < wa.y + wa.height) {
      return true
    }
  }
  return false
}

module.exports = {
  HOME_FILE,
  CAPABILITY_FILE,
  setCache,
  getCache,
  replayStateToOrb,
  loadSavedHome,
  saveHome,
  beginProgrammaticMove,
  endProgrammaticMove,
  isProgrammaticMove,
  isPointInAnyDisplay,
  loadCapability,
  saveCapability,
  getCapabilityTier