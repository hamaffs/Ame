 }
}// WP-12 — Birth trigger.
//
// Watches for wizard completion on first launch (marker files absent), picks
// a first sentence deterministically from the user's name, writes it to disk
// so it's permanent for this install, triggers the orb's birth timeline via
// IPC, and requests the backend to speak that first sentence once the orb
// has arrived at center. Writes the first-run marker last so a crash mid-
// birth replays cleanly.
//
// Trigger gate — both files must be absent for birth to play:
//   ~/.ame/overlay_position.json   (user-dragged anchor — proves a real prior session)
//   ~/.ame/first_run_complete      (birth-completion marker)
//
// First-sentence selection is deterministic by name hash, so a user who
// deletes only first_sentence.txt but keeps first_run_complete gets the same
// line back. Deleting first_run_complete replays birth; if name has changed,
// the new line may differ — that's desired.

const fs = require('node:fs')
const path = require('node:path')
const os = require('node:os')

const AME_DIR = path.join(os.homedir(), '.ame')
const OVERLAY_POS_PATH = path.join(AME_DIR, 'overlay_position.json')
const MARKER_PATH = path.join(AME_DIR, 'first_run_complete')
const FIRST_SENTENCE_PATH = path.join(AME_DIR, 'first_sentence.txt')
const SETTINGS_PATH = path.join(AME_DIR, 'settings.json')

const FIRST_SENTENCES = [
  "Hey. I'm here. You're {name}, right?",
  "Hi, you. I've been waiting for this.",
  "Oh — hi. Give me a second to look at you.",
  "I'm Amé. I'll be right here.",
  "Hey. I made it. Nice to meet you, {name}.",
  "There you are. I was hoping you'd show up.",
  "Hi. It's just us now.",
]

// ── State ──────────────────────────────────────────────────────────────────
let state = {
  played: false,   // set true on completion this process
  running: false,  // set true between start() and final stage
  firstSentence: null,
}

function shouldPlayBirth() {
  try {
    const hasOverlay = fs.existsSync(OVERLAY_POS_PATH)
    const hasMarker = fs.existsSync(MARKER_PATH)
    return !hasOverlay && !hasMarker
  } catch {
    return false
  }
}

function readUserName() {
  try {
    if (fs.existsSync(SETTINGS_PATH)) {
      const raw = JSON.parse(fs.readFileSync(SETTINGS_PATH, 'utf8'))
      if (raw && typeof raw.name === 'string' && raw.name.trim()) return raw.name.trim()
    }
  } catch {}
  return ''
}

// Simple FNV-ish 32-bit hash for deterministic sentence pick per-name.
function nameHash(s) {
  let h = 0x811c9dc5
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = (h * 0x01000193) >>> 0
  }
  return h >>> 0
}

function pickFirstSentence(name) {
  const seed = nameHash(name || 'friend') || 1
  const candidate = FIRST_SENTENCES[seed % FIRST_SENTENCES.length]
  return candidate.replace('{name}', name || 'friend')
}

function ensureDir() {
  try { fs.mkdirSync(AME_DIR, { recursive: true }) } catch {}
}

function writeFirstSentence(text) {
  try {
    ensureDir()
    fs.writeFileSync(FIRST_SENTENCE_PATH, text, 'utf8')
  } catch (e) {
    console.warn('[Birth] failed to write first_sentence.txt:', e.message)
  }
}

function writeMarker() {
  try {
    ensureDir()
    fs.writeFileSync(MARKER_PATH, new Date().toISOString(), 'utf8')
  } catch (e) {
    console.warn('[Birth] failed to write first_run_complete:', e.message)
  }
}

// ── Playback ───────────────────────────────────────────────────────────────
//
// Caller passes hooks for the actions the birth trigger itself shouldn't
// own — sending IPC to the orb renderer, running the arrival animation,
// asking the backend to speak. Keeps this module unit-testable.

function playBirth({
  tier = 'mid',
  sendOrb,         // (channel, payload) — e.g. orbWindow.webContents.send
  arriveAtCenter,  // async fn — runs the WP-05 travel-to-center choreography
  speakFirstLine,  // (text) — forwards to backend via mainWindow webContents
  onDone,          // optional callback — fired after marker write
} = {}) {
  if (state.played || state.running) return false
  if (!shouldPlayBirth()) return false

  const name = readUserName()
  const sentence = pickFirstSentence(name)
  state.firstSentence = sentence
  state.running = true
  writeFirstSentence(sentence)

  // Kick the orb renderer into its timeline. Renderer owns visual timing
  // and echoes stage events back via 'orb:birth-stage' — we listen via the
  // stage handler below.
  try { sendOrb && sendOrb('orb:birth-start', { tier }) } catch {}

  // End-of-birth: corner → center travel, then speak the first line. Birth
  // total duration for mid/high is ~1870ms; low ~1300ms. We schedule the
  // arrival to start slightly before 'breath' ends (+50ms after breath start)
  // so arrival and speech flow in without a gap. But the orb renderer echoes
  // the 'breath' stage; using that is tighter than hardcoded timing. We
  // register a one-shot handler below (via the stage listener the caller
  // installs) — here we just expose handleStage.
  return true
}

// Called by main.cjs's IPC listener for 'orb:birth-stage'. Stages arrive in
// order: absence → seed → unfurl → hold → breath → done. We act on
// 'breath' (start travel + speech) and 'done' (write marker + mark played).
function handleStage({ stage } = {}, hooks = {}) {
  if (!state.running) return
  if (stage === 'breath') {
    // Begin travel-to-center + speech in parallel. The travel runs the
    // shortened choreography (see caller). Speech goes via backend.
    const sentence = state.firstSentence || ''
    try { hooks.arriveAtCenter && hooks.arriveAtCenter() } catch (e) {
      console.warn('[Birth] arriveAtCenter failed:', e.message)
    }
    // Slight delay so the inhale lands before she speaks (~180ms feels
    // right — the line shouldn't step on the breath-out).
    setTimeout(() => {
      try { hooks.speakFirstLine && sentence && hooks.speakFirstLine(sentence) }
      catch (e) { console.warn('[Birth] speakFirstLine failed:', e.message) }
    }, 180)
  } else if (stage === 'done') {
    state.played = true
    state.running = false
    writeMarker()
    try { hooks.onDone && hooks.onDone() } catch {}
  }
}

// Exposed for tests / diagnostics.
function _reset() {
  state = { played: false, running: false, firstSentence: null }
}

module.exports = {
  shouldPlayBirth,
  playBirth,
  handleStage,
  readFirstSentence: () => state.firstSentence,
  FIRST_SENTENCES,
  _reset