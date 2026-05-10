r }
const { app, BrowserWindow, ipcMain, dialog, Tray, Menu, nativeImage, screen, globalShortcut } = require('electron')
const path = require('path')
const { spawn } = require('child_process')

const fs = require('fs')
const orbFoundation = require('./orb-foundation.cjs')
const orbChoreography = require('./orb-choreography.cjs')
const cinemaMode = require('./cinema-mode.cjs')
const birthTrigger = require('./birth-trigger.cjs')
const orbBloom = require('./orb-bloom.cjs')

const isDev = !app.isPackaged
let mainWindow
let orbWindow = null
let orbTravelTimer = null
let backendProcess
let tray = null
let sessionToken = null
let splashWindow = null

// ── Desktop Orb window config ───────────────────────────────────────────────
const ORB_CORNER_SIZE = 140        // width/height when docked in corner
const ORB_SUMMONED_W = 380         // width when summoned to top (tight, unobtrusive)
const ORB_SUMMONED_H = 220         // height when summoned
const ORB_MARGIN_X = 24            // right-edge distance when at default home
const ORB_MARGIN_BOTTOM = 80       // bottom-edge distance (sits above taskbar per brief)
const ORB_MARGIN = 24              // legacy alias (kept for any lingering references)
const ORB_TOP_MARGIN = 14          // distance from top of screen when summoned
const ORB_TRAVEL_MS = 600          // travel duration across the screen
const ORB_ARRIVAL_OVERSHOOT = 14   // px past target before settling
const ORB_ARRIVAL_SETTLE_MS = 180  // overshoot-settle duration
const ORB_CORNER_OPACITY = 0.10    // 10% ghost presence in corner (unanchored)
const ORB_SUMMONED_OPACITY = 1.00  // full presence when summoned
const ORB_OPACITY_TWEEN_MS = 450   // fade duration
const ORB_DRAG_ANCHOR_THRESHOLD = 8 // px — drag further than this to anchor

// Dock state (authoritative). 'corner' | 'top'
let orbDock = 'corner'
let orbOpacityTimer = null
let orbReady = false  // gates hotkey until wizard/welcome is past

// Cursor-proximity poller. Flips click-through based on whether the cursor
// is inside the orb's interactive hit zone. Necessary because mouseenter
// from the renderer can't bootstrap itself — a click-through window never
// receives pointer events, so the renderer has no way to say "now I'm hot."
// Main process polls instead, which works in every dock state.
let orbCursorPollTimer = null
let orbIsInteractive = false  // mirrors setIgnoreMouseEvents(false) state
const ORB_CURSOR_POLL_MS = 60       // ~16Hz — cheap, plenty responsive
const ORB_HIT_RADIUS_CORNER = 56    // orb visual is ~78px, window is 140×140
const ORB_HIT_RADIUS_TOP = 56       // same visual size when summoned

// Anchoring: true once user has dragged her further than threshold. Seeded
// from ~/.ame/overlay_position.json on boot, then maintained at runtime.
let hasUserAnchored = false
let lastKnownOrbPosition = { x: 0, y: 0 }  // tracks every programmatic setPosition

// ── WP-03 Visibility state machine ─────────────────────────────────────────
// Four states: 'active' (summoned, full), 'resting' (anchored+dismissed,
// 20%), 'hidden' (× clicked, off-screen), 'ghost' (unanchored default, 10%).
// All transitions go through setOrbVisibility. The 'ghost' default preserves
// existing charm for users who never drag her.
let orbVisibility = 'ghost'
// Pre-wake baseline — the state we return to when cursor-proximity
// awareness decays. Always one of the four canonical states.
let orbBaselineVisibility = 'ghost'

const ORB_VISIBILITY_OPACITY = {
  active: 1.00,
  resting: 0.20,
  hidden: 0.00,
  ghost: 0.10,
  // Sub-state used by proximity wake — not a baseline, just a transient.
  'resting-aware': 0.40,
}
const ORB_VISIBILITY_MS = {
  'resting->active': 500,
  'active->resting': 400,
  'hidden->active': 600,
  'active->hidden': 350,
  'ghost->active': 600,
  'active->ghost': 450,
  'resting->resting-aware': 260,
  'resting-aware->resting': 420,
  // Fallback for any other pair.
  default: 400,
}

// Off-screen stash point for 'hidden'. Just outside the primary display —
// a 1×1 window so the OS can't route stray input to it.
const ORB_HIDDEN_SIZE = 1

// Cursor-proximity wake (resting → resting-aware).
const ORB_PROXIMITY_POLL_MS = 100     // 10Hz per spec
const ORB_PROXIMITY_RADIUS = 80
const ORB_PROXIMITY_AWARE_MS = 2000   // hold resting-aware this long before decay
let orbProximityTimer = null
let orbProximityDecayTimer = null

// Idle auto-dismiss. When she goes idle while docked at top and nothing
// happens for this long, she drifts back to the corner on her own.
const ORB_IDLE_DISMISS_MS = 12_000
let orbIdleTimer = null
let lastOrbState = 'idle'

function findPython() {
  const { execSync } = require('child_process')
  const os = require('os')
  const settingsPath = path.join(os.homedir(), '.ame', 'settings.json')

  // 1. Check settings.json first (survives UAC elevation env reset)
  try {
    if (fs.existsSync(settingsPath)) {
      const settings = JSON.parse(fs.readFileSync(settingsPath, 'utf8'))
      if (settings.python_path && fs.existsSync(settings.python_path)) {
        return settings.python_path
      }
    }
  } catch (e) {}

  // 2. Candidates in priority order — skip the Windows Store stub
  const localAppData = process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local')
  const candidates = [
    process.env.AME_PYTHON,                                                        // user override
    path.join(localAppData, 'Programs', 'Python', 'Python313', 'python.exe'),
    path.join(localAppData, 'Programs', 'Python', 'Python312', 'python.exe'),
    path.join(localAppData, 'Programs', 'Python', 'Python311', 'python.exe'),
    path.join(localAppData, 'Programs', 'Python', 'Python310', 'python.exe'),
    'C:\\Python312\\python.exe',
    'C:\\Python311\\python.exe',
  ]
  let foundPath = null
  for (const p of candidates) {
    if (p && fs.existsSync(p)) { foundPath = p; break }
  }
  
  // 3. Last resort: ask 'where python' and skip the WindowsApps stub
  if (!foundPath) {
    try {
      const lines = execSync('where python', { encoding: 'utf8' }).split('\n').map(l => l.trim()).filter(Boolean)
      for (const line of lines) {
        if (!line.toLowerCase().includes('windowsapps')) { foundPath = line; break }
      }
    } catch (_) {}
  }
  
  const pythonExe = foundPath || 'python'

  // 4. Persist the found path for next time (critical for UAC restart)
  if (pythonExe !== 'python') {
    try {
      const dir = path.dirname(settingsPath)
      if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
      let settings = {}
      if (fs.existsSync(settingsPath)) settings = JSON.parse(fs.readFileSync(settingsPath, 'utf8'))
      settings.python_path = pythonExe
      fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2))
    } catch (e) {}
  }

  return pythonExe
}

function killPortSync(port) {
  const { execSync } = require('child_process')
  try {
    // Find PIDs using the port, then kill them
    const result = execSync(`netstat -ano | findstr :${port}`, { encoding: 'utf8' })
    const pids = new Set()
    for (const line of result.split('\n')) {
      const m = line.trim().match(/\s(\d+)$/)
      if (m) pids.add(m[1])
    }
    for (const pid of pids) {
      try { execSync(`taskkill /F /PID ${pid}`, { encoding: 'utf8' }) } catch (_) {}
    }
    if (pids.size > 0) console.log(`[Backend] Cleared ${pids.size} process(es) on port ${port}`)
  } catch (_) {
    // Port was free — nothing to kill
  }
}

// ── First-run dependency installer ──────────────────────────────────────────

const DEPS_MARKER = path.join(require('os').homedir(), '.ame', 'deps-installed')
const REQUIREMENTS = path.join(__dirname, '..', 'requirements.txt')

function depsInstalled() {
  if (!fs.existsSync(REQUIREMENTS)) return true  // no requirements file = nothing to install
  if (!fs.existsSync(DEPS_MARKER)) return false
  // Re-install if requirements.txt is newer than the marker
  const reqMtime = fs.statSync(REQUIREMENTS).mtimeMs
  const markerMtime = fs.statSync(DEPS_MARKER).mtimeMs
  return markerMtime >= reqMtime
}

function pickRandomOrbPath() {
  try {
    const idx = Math.floor(Math.random() * 6) + 1
    const gifPath = path.join(__dirname, '..', 'assets', 'splash', `ame-orb${idx}.gif`)
    if (!fs.existsSync(gifPath)) return null
    return gifPath
  } catch (_) {
    return null
  }
}

function writeTempSplashHtml(html, name) {
  const os = require('os')
  const dir = path.join(os.tmpdir(), 'ame-splash')
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
  const file = path.join(dir, name)
  fs.writeFileSync(file, html, 'utf8')
  return file
}

function createSplashWindow() {
  splashWindow = new BrowserWindow({
    width: 420, height: 260,
    frame: false, resizable: false,
    transparent: true, alwaysOnTop: true,
    skipTaskbar: true,
    webPreferences: { nodeIntegration: false, contextIsolation: true },
  })

  const orbPath = pickRandomOrbPath()
  const orbMarkup = orbPath
    ? `<img src="file:///${orbPath.replace(/\\/g, '/')}" class="orb-img" alt="" />`
    : `<div class="ring"></div><div class="orb"></div>`

  const html = `<!DOCTYPE html>
<html><head><style>
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: -apple-system, 'Segoe UI', system-ui, sans-serif;
    background: rgba(9, 9, 11, 0.96);
    color: #e5e5e5;
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    height: 100vh;
    border-radius: 16px;
    border: 1px solid rgba(255,255,255,0.06);
    -webkit-app-region: drag;
    gap: 22px;
  }
  .orb-wrap {
    position: relative;
    width: 110px; height: 110px;
    display: flex; align-items: center; justify-content: center;
  }
  .orb-img {
    width: 110px; height: 110px;
    object-fit: cover;
    mix-blend-mode: lighten;
    filter: contrast(1.08) saturate(1.15) brightness(1.05);
    animation: float 4s ease-in-out infinite;
    pointer-events: none;
    user-select: none;
    -webkit-mask-image: radial-gradient(circle at 50% 50%, rgba(0,0,0,1) 38%, rgba(0,0,0,0.85) 46%, rgba(0,0,0,0) 50%);
            mask-image: radial-gradient(circle at 50% 50%, rgba(0,0,0,1) 38%, rgba(0,0,0,0.85) 46%, rgba(0,0,0,0) 50%);
  }
  .orb {
    width: 56px; height: 56px;
    border-radius: 50%;
    background:
      radial-gradient(circle at 35% 30%, rgba(255,255,255,0.18), rgba(255,255,255,0) 55%),
      radial-gradient(circle at 50% 50%, #2a2a2e 0%, #161618 70%);
    box-shadow: inset 0 0 16px rgba(0,0,0,0.55);
    animation: float 4s ease-in-out infinite;
  }
  .ring {
    position: absolute; inset: 0;
    border-radius: 50%;
    border: 1px solid rgba(255,255,255,0.05);
    animation: spin 18s linear infinite;
  }
  @keyframes float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-2px); } }
  @keyframes spin { to { transform: rotate(360deg); } }
  h2 {
    margin: 0;
    font-size: 11px;
    letter-spacing: 0.42em;
    text-transform: uppercase;
    font-weight: 500;
    color: #fafafa;
  }
  #status {
    font-size: 11px;
    color: #888;
    text-align: center;
    padding: 0 20px;
    letter-spacing: 0.04em;
    font-family: 'SF Mono', 'JetBrains Mono', Consolas, monospace;
  }
  .bar-bg {
    width: 280px;
    height: 2px;
    background: rgba(255,255,255,0.06);
    border-radius: 1px;
    overflow: hidden;
  }
  .bar-fg {
    height: 100%;
    width: 0%;
    background: rgba(255,255,255,0.7);
    border-radius: 1px;
    transition: width 0.3s ease;
  }
  .stack {
    display: flex; flex-direction: column; align-items: center; gap: 12px;
  }
</style></head><body>
  <div class="orb-wrap">
    ${orbMarkup}
  </div>
  <div class="stack">
    <h2>Amé</h2>
    <div id="status">preparing your companion...</div>
    <div class="bar-bg"><div class="bar-fg" id="bar"></div></div>
  </div>
  <script>
    window.updateProgress = (pct, msg) => {
      document.getElementById('bar').style.width = pct + '%';
      if (msg) document.getElementById('status').textContent = msg;
    };
  </script>
</body></html>`

  const splashFile = writeTempSplashHtml(html, 'splash-deps.html')
  splashWindow.loadFile(splashFile)
  return splashWindow
}

async function installDeps() {
  if (depsInstalled()) return true
  if (app.isPackaged && findBundledBackend()) return true  // bundled mode — no pip needed

  const pythonExe = findPython()
  console.log('[Setup] First run detected — installing Python dependencies...')

  createSplashWindow()

  return new Promise((resolve) => {
    const pip = spawn(pythonExe, ['-m', 'pip', 'install', '-r', REQUIREMENTS, '--quiet'], {
      cwd: path.join(__dirname, '..'),
      env: { ...process.env },
    })

    let lineCount = 0
    const totalEstimate = 27  // approximate number of packages

    pip.stdout.on('data', (data) => {
      const lines = data.toString().split('\n').filter(Boolean)
      lineCount += lines.length
      const pct = Math.min(95, Math.round((lineCount / totalEstimate) * 80))
      if (splashWindow && !splashWindow.isDestroyed()) {
        splashWindow.webContents.executeJavaScript(
          `window.updateProgress(${pct}, "Installing packages... (${lineCount}/${totalEstimate})")`
        ).catch(() => {})
      }
      console.log(`[Setup] ${data.toString().trim()}`)
    })

    pip.stderr.on('data', (data) => {
      const text = data.toString().trim()
      // pip writes progress to stderr — don't treat as error
      if (text) console.log(`[Setup] ${text}`)
    })

    pip.on('close', (code) => {
      if (code === 0) {
        console.log('[Setup] Dependencies installed successfully')
        // Write marker
        const markerDir = path.dirname(DEPS_MARKER)
        if (!fs.existsSync(markerDir)) fs.mkdirSync(markerDir, { recursive: true })
        fs.writeFileSync(DEPS_MARKER, new Date().toISOString())

        if (splashWindow && !splashWindow.isDestroyed()) {
          splashWindow.webContents.executeJavaScript(
            `window.updateProgress(100, "Ready!")`
          ).catch(() => {})
          setTimeout(() => {
            if (splashWindow && !splashWindow.isDestroyed()) splashWindow.close()
            splashWindow = null
          }, 800)
        }
        resolve(true)
      } else {
        console.error(`[Setup] pip install failed with code ${code}`)
        if (splashWindow && !splashWindow.isDestroyed()) {
          splashWindow.webContents.executeJavaScript(
            `window.updateProgress(0, "Install failed — check console. Continuing anyway...")`
          ).catch(() => {})
          setTimeout(() => {
            if (splashWindow && !splashWindow.isDestroyed()) splashWindow.close()
            splashWindow = null
          }, 3000)
        }
        resolve(false)
      }
    })
  })
}

// ── Ollama auto-spawn ──────────────────────────────────────────────────────
// Amé's router prefers local Gemma 4 for memory extraction, intent gate,
// news filter, etc. If the user has Ollama installed but hasn't manually
// started it, we boot `ollama serve` in the background so the local tier
// comes online automatically. If Ollama isn't installed, this is a no-op
// and the router transparently falls through to Gemini Flash Lite.

let ollamaProcess = null

function ollamaIsUp(timeoutMs = 800) {
  return new Promise((resolve) => {
    const http = require('http')
    const req = http.get('http://127.0.0.1:11434/api/tags', (res) => {
      res.resume()
      resolve(res.statusCode === 200)
    })
    req.on('error', () => resolve(false))
    req.setTimeout(timeoutMs, () => { req.destroy(); resolve(false) })
  })
}

async function startOllama() {
  if (await ollamaIsUp()) {
    console.log('[Ollama] already running — skipping auto-spawn')
    return
  }

  // Spawn detached so it survives quick Amé restarts, but track the pid so
  // we can kill it on clean exit if we were the ones who started it.
  try {
    ollamaProcess = spawn('ollama', ['serve'], {
      detached: true,
      stdio: 'ignore',
      windowsHide: true,
    })
    ollamaProcess.on('error', (err) => {
      // ENOENT → Ollama isn't installed. Silent fallback; router handles it.
      if (err && err.code === 'ENOENT') {
        console.log('[Ollama] not installed — local Gemma tier disabled, router will use cloud')
      } else {
        console.log(`[Ollama] spawn error: ${err.message}`)
      }
      ollamaProcess = null
    })
    ollamaProcess.unref()
    console.log('[Ollama] spawned — waiting for API to come online...')
  } catch (e) {
    console.log(`[Ollama] spawn failed: ${e.message}`)
    return
  }

  // Poll up to 10s for the API to answer. Typical cold start is 1–3s.
  const deadline = Date.now() + 10000
  while (Date.now() < deadline) {
    if (await ollamaIsUp()) {
      console.log('[Ollama] online at http://127.0.0.1:11434')
      return
    }
    await new Promise(r => setTimeout(r, 500))
  }
  console.log('[Ollama] did not respond within 10s — continuing, router will retry later')
}

function findBundledBackend() {
  const candidates = [
    // Packaged: extraResources lands here
    path.join(process.resourcesPath, 'ame-backend', 'ame-backend.exe'),
    // Dev/unpacked fallback
    path.join(__dirname, '..', 'dist', 'ame-backend', 'ame-backend.exe'),
    path.join(__dirname, '..', 'ame-backend', 'ame-backend.exe'),
  ]
  for (const p of candidates) {
    if (fs.existsSync(p)) return p
  }
  return null
}

function startBackend() {
  // Kill any leftover backend from a previous session
  killPortSync(8766)

  const bundledExe = app.isPackaged ? findBundledBackend() : null

  if (bundledExe) {
    // ── Bundled mode: launch ame-backend.exe directly ──
    console.log(`[Backend] Using bundled exe: ${bundledExe}`)
    backendProcess = spawn(bundledExe, [], {
      cwd: path.dirname(bundledExe),  // ← use the exe's own folder
      env: { ...process.env }
    })
  } else {
    // ── Dev mode: launch via Python interpreter ──
    const backendPath = path.join(__dirname, '..', 'backend', 'server.py')
    const pythonExe = findPython()
    console.log(`[Backend] Using Python: ${pythonExe}`)

    // Ensure Python's own directory is in PATH so it can find python311.dll
    // and any native extension DLLs (PortAudio, etc). Electron can strip PATH.
    const pythonDir = path.dirname(pythonExe)
    const pythonScripts = path.join(pythonDir, 'Scripts')
    const envPath = [pythonDir, pythonScripts, process.env.PATH || ''].join(path.delimiter)

    // -u forces unbuffered stdout/stderr. Without it, Python block-buffers
    // background-thread prints when stdout is a pipe (Electron child),
    // which hides Tier 2/3 boot logs and ContextEngine decisions for
    // minutes. PYTHONUNBUFFERED is belt-and-braces for any subprocess or
    // C-extension that might bypass Python's own buffer.
    backendProcess = spawn(pythonExe, ['-u', backendPath], {
      cwd: path.join(__dirname, '..'),
      env: { ...process.env, PATH: envPath, PYTHONUNBUFFERED: '1' }
    })
  }

  backendProcess.stdout.on('data', (data) => {
    const line = data.toString()
    console.log(`[Backend] ${line}`)
    // Capture session token from backend stdout
    const tokenMatch = line.match(/SESSION_TOKEN=(\S+)/)
    if (tokenMatch) {
      sessionToken = tokenMatch[1]
      console.log('[Backend] Session token captured')
      // Backend is ready — swap loading screen for the real React app
      loadApp()
    }
  })
  backendProcess.stderr.on('data', (data) => console.error(`[Backend] ${data}`))
  backendProcess.on('close', (code) => console.log(`[Backend] exited with code ${code}`))
}

// ── Orb window: transparent always-on-top companion ────────────────────────

function orbDefaultHome() {
  // Bottom-right of primary display's work area. 24px from right edge,
  // 80px from bottom (sits just above the taskbar per the M2 brief).
  const display = screen.getPrimaryDisplay()
  const wa = display.workArea
  return {
    x: wa.x + wa.width  - ORB_CORNER_SIZE - ORB_MARGIN_X,
    y: wa.y + wa.height - ORB_CORNER_SIZE - ORB_MARGIN_BOTTOM,
  }
}

function orbHomePosition() {
  // Returns the orb's home: saved position if present AND inside a connected
  // display, else the default bottom-right. Critical for multi-monitor
  // disconnect handling — we don't clear the saved point if the monitor is
  // missing, we just temporarily fall back.
  const saved = orbFoundation.loadSavedHome()
  if (saved) {
    const all = screen.getAllDisplays()
    if (orbFoundation.isPointInAnyDisplay(saved, all)) {
      console.log(`[Orb] using saved home x=${saved.x} y=${saved.y}`)
      return { x: saved.x, y: saved.y }
    }
    console.log(`[Orb] saved home (${saved.x},${saved.y}) offscreen; using default until monitor returns`)
  }
  const def = orbDefaultHome()
  console.log(`[Orb] no saved home; using default x=${def.x} y=${def.y}`)
  return def
}

// Legacy name kept as alias for any call sites not yet migrated.
function orbCornerPosition() { return orbHomePosition() }

function orbTopCenterPosition() {
  const display = screen.getPrimaryDisplay()
  const wa = display.workArea
  return {
    x: wa.x + Math.round((wa.width - ORB_SUMMONED_W) / 2),
    y: wa.y + ORB_TOP_MARGIN,
  }
}

function createOrbWindow() {
  if (orbWindow && !orbWindow.isDestroyed()) return orbWindow

  // Seed anchor state from disk on every createOrbWindow call (not just first
  // boot). If the process was running and the orb got recreated mid-session,
  // we still respect any saved anchor.
  const savedHome = orbFoundation.loadSavedHome()
  hasUserAnchored = !!savedHome

  const home = orbHomePosition()
  lastKnownOrbPosition = { x: home.x, y: home.y }
  const savedDebug = orbFoundation.loadSavedHome()
  console.log(`[Orb] createOrbWindow: home=(${home.x},${home.y}) saved=${savedDebug ? `(${savedDebug.x},${savedDebug.y})` : 'none'} anchored=${hasUserAnchored}`)

  orbWindow = new BrowserWindow({
    width: ORB_CORNER_SIZE,
    height: ORB_CORNER_SIZE,
    x: home.x,
    y: home.y,
    frame: false,
    transparent: true,
    resizable: false,
    // Tool window (WS_EX_TOOLWINDOW on Windows) — removes orb from taskbar,
    // Alt+Tab, and Task View at the OS level. Combined with skipTaskbar:true
    // and focusable:false, she is OS-invisible as a "window" while still
    // being rendered. This is the "one program, two surfaces" identity.
    type: 'toolbar',
    movable: true,               // WP-02: user can drag her; anchoring logic lives on 'move'
    minimizable: false,
    maximizable: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    focusable: false,
    hasShadow: false,
    show: false,
    backgroundColor: '#00000000',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.cjs'),
    },
  })

  // Float above fullscreen apps too.
  try { orbWindow.setAlwaysOnTop(true, 'screen-saver') } catch (_) {}
  try { orbWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true }) } catch (_) {}

  // Click-through while docked in corner. Gets toggled off during summon so
  // the × button becomes interactive at top.
  orbWindow.setIgnoreMouseEvents(true, { forward: true })
  try { orbWindow.setOpacity(ORB_CORNER_OPACITY) } catch (_) {}

  if (isDev) {
    const http = require('http')
    const tryLoad = () => {
      http.get('http://localhost:5173/orb.html', (res) => {
        console.log(`[Orb] vite responded ${res.statusCode}, calling loadURL`)
        if (orbWindow && !orbWindow.isDestroyed()) {
          orbWindow.loadURL('http://localhost:5173/orb.html')
            .then(() => console.log('[Orb] loadURL resolved'))
            .catch(err => console.error('[Orb] loadURL failed:', err?.message || err))
        }
      }).on('error', (err) => {
        console.log(`[Orb] vite not ready (${err.code || err.message}), retrying...`)
        setTimeout(tryLoad, 300)
      })
    }
    tryLoad()
  } else {
    orbWindow.loadFile(path.join(__dirname, '..', 'dist', 'orb.html'))
  }

  orbWindow.webContents.on('console-message', (_e, level, message, line, source) => {
    console.log(`[Orb console] ${message} (${source}:${line})`)
  })
  // Renderer crash recovery: null the window so next summon recreates it.
  // The state cache (orb-foundation) preserves emotion/accent/etc so she
  // returns as she was, not as a blank default.
  orbWindow.webContents.on('render-process-gone', (_e, details) => {
    console.error(`[Orb] renderer crashed:`, details)
    try { if (orbWindow && !orbWindow.isDestroyed()) orbWindow.destroy() } catch (_) {}
    orbWindow = null
    if (orbTravelTimer) { clearInterval(orbTravelTimer); orbTravelTimer = null }
    if (orbOpacityTimer) { clearInterval(orbOpacityTimer); orbOpacityTimer = null }
    stopOrbCursorPoll()
    stopOrbProximityPoll()
  })

  // Suppress the Windows native system menu (Restore/Move/Size/Minimize/
  // Maximize/Close). With manual drag (no -webkit-app-region:drag anywhere),
  // the OS shouldn't fire it — but we keep the suppression as defense in
  // depth in case any affordance still triggers it.
  orbWindow.webContents.on('system-context-menu', (e) => {
    e.preventDefault()
  })

  // Intercept any close attempt — the orb should NEVER natively close. The
  // tool-window flag + focusable:false should prevent this in normal use,
  // but defense in depth: if some OS affordance or edge case fires it, we
  // route to dismissOrb instead.
  orbWindow.on('close', (e) => {
    if (!app.isQuitting) {
      e.preventDefault()
      try { dismissOrb('close-event') } catch (_) {}
    }
  })

  // ── WP-02: drag-to-anchor detection ───────────────────────────────────
  // Windows fires 'move' continuously during a drag. We debounce to the end
  // of the gesture, then check whether it was a programmatic move (our own
  // animations) or a real user drag. Real drags > threshold → anchor.
  //
  // `lastKnownOrbPosition` is updated by every programmatic setPosition. On
  // debounced move-end we compute delta vs. that reference, not vs. the
  // previous frame, so micro-jitters during animation don't false-positive.
  let moveDebounceTimer = null
  const handleMoveEnd = () => {
    moveDebounceTimer = null
    if (!orbWindow || orbWindow.isDestroyed()) return
    if (orbFoundation.isProgrammaticMove()) return  // our animation — ignore

    const [x, y] = orbWindow.getPosition()
    const dx = x - lastKnownOrbPosition.x
    const dy = y - lastKnownOrbPosition.y
    const dist = Math.sqrt(dx * dx + dy * dy)

    if (dist < ORB_DRAG_ANCHOR_THRESHOLD) return  // tiny drag, ignore

    // Real user drag. Update anchor. Normalize summoned-width drags to
    // corner-equivalent top-left so next summon re-centers on the same body.
    lastKnownOrbPosition = { x, y }
    hasUserAnchored = true
    let homeX = x
    let homeY = y
    if (orbDock === 'top') {
      homeX = x + Math.round((ORB_SUMMONED_W - ORB_CORNER_SIZE) / 2)
    }
    orbFoundation.saveHome(homeX, homeY)
    console.log(`[Orb] anchored at x=${homeX} y=${homeY} (drag Δ=${Math.round(dist)}px, dock=${orbDock})`)

    // Let the renderer react (WP-06 adds an "accepted" pulse animation).
    forwardToOrb('orb:anchored', { x: homeX, y: homeY, previouslyAnchored: true })
  }

  orbWindow.on('move', () => {
    if (moveDebounceTimer) clearTimeout(moveDebounceTimer)
    moveDebounceTimer = setTimeout(handleMoveEnd, 150)
  })

  // `ready-to-show` is unreliable on transparent + focusable:false windows on
  // Windows. Use `did-finish-load` instead, which always fires.
  orbWindow.webContents.once('did-finish-load', () => {
    if (orbWindow && !orbWindow.isDestroyed()) {
      orbWindow.showInactive()
      const [x, y] = orbWindow.getPosition()
      console.log(`[Orb] shown at x=${x} y=${y} visible=${orbWindow.isVisible()}`)
      // Replay cached state so a recreated orb comes back as she was.
      orbFoundation.replayStateToOrb(forwardToOrb)
      // Seed WP-03 visibility baseline. Anchored users boot into 'resting'
      // (they've dragged her somewhere specific — she's asleep there, not
      // the default ghost). Unanchored users boot into 'ghost'. Either way,
      // the opacity is set directly (no tween) for the initial render.
      const initialVis = hasUserAnchored ? 'resting' : 'ghost'
      orbVisibility = initialVis
      orbBaselineVisibility = initialVis
      orbFoundation.setCache('visibility', initialVis)
      try { orbWindow.setOpacity(ORB_VISIBILITY_OPACITY[initialVis]) } catch (_) {}
      forwardToOrb('orb:visibility', {
        state: initialVis, previous: null, reason: 'boot', durationMs: 0,
        tier: orbFoundation.getCapabilityTier(),
      })
      if (initialVis === 'resting' && orbFoundation.getCapabilityTier() !== 'low') {
        startOrbProximityPoll()
      }
      // Start the cursor-proximity poller — this is what toggles click-through
      // so the user can actually interact with her.
      startOrbCursorPoll()
    }
  })
  orbWindow.webContents.on('did-fail-load', (_e, code, desc, url) => {
    console.error(`[Orb] load failed ${code} ${desc} ${url}`)
  })

  orbWindow.on('closed', () => {
    orbWindow = null
    if (orbTravelTimer) { clearInterval(orbTravelTimer); orbTravelTimer = null }
    stopOrbCursorPoll()
    stopOrbProximityPoll()
  })

  return orbWindow
}

// Wait for the orb renderer to be ready. Used by summonOrb when it has to
// recreate the window — we don't want to send IPC into a dead renderer.
function waitForOrbReady(timeoutMs = 3000) {
  return new Promise((resolve) => {
    if (!orbWindow || orbWindow.isDestroyed()) return resolve(false)
    if (!orbWindow.webContents.isLoading()) return resolve(true)
    const timer = setTimeout(() => resolve(false), timeoutMs)
    orbWindow.webContents.once('did-finish-load', () => {
      clearTimeout(timer); resolve(true)
    })
  })
}

function easeInOutCubic(t) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2
}

// Cursor-over-orb detection. The orb window is transparent and click-through
// by default, so renderer mouseenter can't fire. Main process watches the
// cursor and toggles setIgnoreMouseEvents when the pointer enters/leaves the
// orb's circular hit zone.
function isCursorOverOrb() {
  if (!orbWindow || orbWindow.isDestroyed()) return false
  try {
    const cursor = screen.getCursorScreenPoint()
    const [wx, wy] = orbWindow.getPosition()
    const [ww, wh] = orbWindow.getSize()
    // Center of the orb visual in screen coords. OrbWindow.jsx centers the
    // orb horizontally and offsets 6px from the top of the window.
    // OrbScene sits at top:6 inside the window in both dock modes, so the
    // orb center is the same formula regardless of whether she's in corner
    // or summoned at top.
    const ORB_VISUAL = 78
    const cx = wx + ww / 2
    const cy = wy + 6 + ORB_VISUAL / 2
    const radius = orbDock === 'top' ? ORB_HIT_RADIUS_TOP : ORB_HIT_RADIUS_CORNER
    const dx = cursor.x - cx
    const dy = cursor.y - cy
    return (dx * dx + dy * dy) <= radius * radius
  } catch (_) {
    return false
  }
}

// WP-10: light-dir cursor tracking. Same poll reads cursor, computes delta
// from orb center in screen coords, emits `orb:light-dir { x, y }` to
// renderer. Skipped on low tier (cheap per-tick but less payoff).
// Throttled to every 3rd tick (so ~20Hz if main poll is 60Hz).
let _lightDirTickCounter = 0
function startOrbCursorPoll() {
  if (orbCursorPollTimer) return
  orbCursorPollTimer = setInterval(() => {
    if (!orbWindow || orbWindow.isDestroyed()) {
      stopOrbCursorPoll()
      return
    }
    const inside = isCursorOverOrb()
    if (inside !== orbIsInteractive) {
      orbIsInteractive = inside
      try { orbWindow.setIgnoreMouseEvents(!inside, { forward: true }) } catch (_) {}
    }
    // WP-10 light-dir emit. Tier gate + throttle.
    _lightDirTickCounter++
    if (_lightDirTickCounter >= 3) {
      _lightDirTickCounter = 0
      try {
        const tier = orbFoundation.getCapabilityTier()
        if (tier !== 'low') {
          const cursor = screen.getCursorScreenPoint()
          const [wx, wy] = orbWindow.getPosition()
          const [ww] = orbWindow.getSize()
          const ORB_VISUAL = 78
          const cx = wx + ww / 2
          const cy = wy + 6 + ORB_VISUAL / 2
          // Deltas in screen px; normalize by a soft scale so 200px maps ~1.0.
          const dx = (cursor.x - cx) / 200
          const dy = (cursor.y - cy) / 200
          forwardToOrb('orb:light-dir', { x: dx, y: dy })
        }
      } catch (_) {}
    }
  }, ORB_CURSOR_POLL_MS)
}

function stopOrbCursorPoll() {
  if (orbCursorPollTimer) {
    clearInterval(orbCursorPollTimer)
    orbCursorPollTimer = null
  }
  orbIsInteractive = false
}

// WP-05: active arrival choreography handle. `travelOrbTo` cancels any
// in-flight choreography before starting a new one so dismiss-mid-summon
// retargets smoothly instead of two timelines fighting the window position.
let activeChoreography = null
// WP-06: active bloom-from-within handle. Cancels on dismiss-mid-summon etc.
let activeBloom = null

// WP-06: run the bloom-from-within timeline in place. No window position
// work — caller already asserted orb is at home. Cancels any prior bloom
// or choreography first to avoid double-timelines fighting the uniforms.
function playBloomAt(dir, onDone) {
  if (!orbWindow || orbWindow.isDestroyed()) {
    if (typeof onDone === 'function') onDone()
    return
  }
  if (activeBloom) {
    try { activeBloom.cancel() } catch (_) {}
    activeBloom = null
  }
  if (activeChoreography) {
    try { activeChoreography.cancel() } catch (_) {}
    activeChoreography = null
  }
  activeBloom = orbBloom.playBloom({
    dir,
    emit: forwardToOrb,
    tier: orbFoundation.getCapabilityTier(),
    onDone: () => {
      activeBloom = null
      if (typeof onDone === 'function') {
        try { onDone() } catch (_) {}
      }
    },
  })
}

function travelOrbTo(target) {
  if (!orbWindow || orbWindow.isDestroyed()) return
  if (orbTravelTimer) { clearInterval(orbTravelTimer); orbTravelTimer = null }
  if (activeChoreography) {
    try { activeChoreography.cancel() } catch (_) {}
    activeChoreography = null
  }

  const [startX, startY] = orbWindow.getPosition()

  activeChoreography = orbChoreography.playArrival({
    orbWindow,
    from: { x: startX, y: startY },
    to: target,
    emit: forwardToOrb,
    beginProgrammaticMove: (ms) => orbFoundation.beginProgrammaticMove(ms),
    tier: orbFoundation.getCapabilityTier(),
    // WP-13: inject `screen` so the choreography module can detect cross-
    // display travel and route the path via the shared display boundary.
    screen,
    onDone: () => {
      lastKnownOrbPosition = { x: target.x, y: target.y }
      activeChoreography = null
    },
  })
}

// ── WP-03 Visibility transitions ───────────────────────────────────────────
// Single entry point for visibility changes. Handles opacity tween, 'hidden'
// off-screen stashing, proximity-poll lifecycle, and renderer IPC. All
// visibility changes go through here — no other code should call
// orbWindow.setOpacity or reposition for hide purposes directly.

function getVisibilityDurationMs(from, to) {
  return ORB_VISIBILITY_MS[`${from}->${to}`] || ORB_VISIBILITY_MS.default
}

function setOrbVisibility(next, reason) {
  if (!orbWindow || orbWindow.isDestroyed()) return
  if (!(next in ORB_VISIBILITY_OPACITY)) {
    console.warn(`[Orb] setOrbVisibility: unknown state "${next}"`)
    return
  }
  const prev = orbVisibility
  if (prev === next) return
  orbVisibility = next
  // Only update baseline for canonical states; 'resting-aware' is transient.
  if (next !== 'resting-aware') orbBaselineVisibility = next
  orbFoundation.setCache('visibility', next)

  const fromOpacity = ORB_VISIBILITY_OPACITY[prev] ?? 0
  const toOpacity = ORB_VISIBILITY_OPACITY[next] ?? 0
  const ms = getVisibilityDurationMs(prev, next)

  console.log(`[Orb] visibility ${prev} → ${next} (${ms}ms, reason=${reason || 'n/a'})`)

  // If we're leaving 'hidden', bring the window back on-screen at its home
  // BEFORE tweening opacity (so the fade-in plays at the right spot).
  //
  // BUT: when the caller is summonOrb (orbDock is 'top'), summonOrb already
  // positioned the window at the correct summon anchor (home.x - 120, to
  // body-center it). Calling setBounds here with home.x would undo that and
  // cause a ~120px rightward glitch. Only re-home when docking as corner.
  if (prev === 'hidden' && next !== 'hidden' && orbDock !== 'top') {
    try {
      const home = orbHomePosition()
      const size = { width: ORB_CORNER_SIZE, height: ORB_CORNER_SIZE }
      orbFoundation.beginProgrammaticMove(Math.max(300, ms))
      orbWindow.setBounds({ x: home.x, y: home.y, ...size }, false)
      lastKnownOrbPosition = { x: home.x, y: home.y }
    } catch (_) {}
  }

  tweenOpacity(fromOpacity, toOpacity, ms)

  // If we're entering 'hidden', stash off-screen AFTER the fade completes.
  // Zero opacity is the visible effect; off-screen is belt-and-suspenders
  // so no stray input reaches a 0-opacity window.
  if (next === 'hidden') {
    setTimeout(() => {
      if (!orbWindow || orbWindow.isDestroyed()) return
      if (orbVisibility !== 'hidden') return  // state changed mid-tween
      try {
        // Park at (−10, −10) with a 1×1 footprint. Works cross-display.
        orbFoundation.beginProgrammaticMove(400)
        orbWindow.setBounds({ x: -10, y: -10, width: ORB_HIDDEN_SIZE, height: ORB_HIDDEN_SIZE }, false)
        lastKnownOrbPosition = { x: -10, y: -10 }
        orbWindow.setIgnoreMouseEvents(true, { forward: true })
      } catch (_) {}
    }, ms + 20)
  }

  // Proximity poll lifecycle — only runs while baseline is 'resting'.
  // Tier-gated: 'low' skips the 10Hz main-process poll (per plan: weak
  // CPUs shouldn't do this).
  if (next === 'resting' && orbFoundation.getCapabilityTier() !== 'low') {
    startOrbProximityPoll()
  } else if (next !== 'resting' && next !== 'resting-aware') {
    stopOrbProximityPoll()
  }

  forwardToOrb('orb:visibility', {
    state: next,
    previous: prev,
    reason: reason || null,
    durationMs: ms,
    tier: orbFoundation.getCapabilityTier(),
  })
}

// Cursor within ORB_PROXIMITY_RADIUS of orb center? Mirror of the WP-02
// hit-test formula but with a bigger radius — this is wake-awareness, not
// click interaction.
function isCursorNearOrb() {
  if (!orbWindow || orbWindow.isDestroyed()) return false
  try {
    const cursor = screen.getCursorScreenPoint()
    const [wx, wy] = orbWindow.getPosition()
    const [ww] = orbWindow.getSize()
    const ORB_VISUAL = 78
    const cx = wx + ww / 2
    const cy = wy + 6 + ORB_VISUAL / 2
    const dx = cursor.x - cx
    const dy = cursor.y - cy
    return (dx * dx + dy * dy) <= ORB_PROXIMITY_RADIUS * ORB_PROXIMITY_RADIUS
  } catch (_) {
    return false
  }
}

function startOrbProximityPoll() {
  if (orbProximityTimer) return
  orbProximityTimer = setInterval(() => {
    if (!orbWindow || orbWindow.isDestroyed()) {
      stopOrbProximityPoll()
      return
    }
    // Only meaningful while in 'resting' baseline. If something pushed us
    // into 'active'/'hidden'/'ghost' mid-poll, stop.
    if (orbBaselineVisibility !== 'resting') {
      stopOrbProximityPoll()
      return
    }
    const near = isCursorNearOrb()
    if (near && orbVisibility === 'resting') {
      setOrbVisibility('resting-aware', 'proximity-wake')
      scheduleProximityDecay()
    }
    // If we're already 'resting-aware' and cursor left the radius, let the
    // decay timer handle the fade — don't thrash.
  }, ORB_PROXIMITY_POLL_MS)
}

function stopOrbProximityPoll() {
  if (orbProximityTimer) {
    clearInterval(orbProximityTimer)
    orbProximityTimer = null
  }
  if (orbProximityDecayTimer) {
    clearTimeout(orbProximityDecayTimer)
    orbProximityDecayTimer = null
  }
}

// After ORB_PROXIMITY_AWARE_MS of being 'resting-aware', decay back to
// 'resting'. Re-arms on each proximity hit so continuous hover extends it.
function scheduleProximityDecay() {
  if (orbProximityDecayTimer) clearTimeout(orbProximityDecayTimer)
  orbProximityDecayTimer = setTimeout(() => {
    orbProximityDecayTimer = null
    if (orbVisibility === 'resting-aware' && orbBaselineVisibility === 'resting') {
      setOrbVisibility('resting', 'proximity-decay')
    }
  }, ORB_PROXIMITY_AWARE_MS)
}

function tweenOpacity(from, to, ms) {
  if (!orbWindow || orbWindow.isDestroyed()) return
  if (orbOpacityTimer) { clearInterval(orbOpacityTimer); orbOpacityTimer = null }
  // Use the window's *current* opacity as the start value. summonOrb sets
  // opacity 0 before resizing (to mask a Windows/DWM reflow glitch), so the
  // tween should fade in from 0 rather than snapping up to the prev state's
  // canonical opacity for one frame.
  let actualFrom = from
  try { actualFrom = orbWindow.getOpacity() } catch (_) {}
  const startT = Date.now()
  orbOpacityTimer = setInterval(() => {
    if (!orbWindow || orbWindow.isDestroyed()) {
      clearInterval(orbOpacityTimer); orbOpacityTimer = null; return
    }
    const elapsed = Date.now() - startT
    const t = Math.min(1, elapsed / ms)
    const v = actualFrom + (to - actualFrom) * easeInOutCubic(t)
    try { orbWindow.setOpacity(v) } catch (_) {}
    if (t >= 1) { clearInterval(orbOpacityTimer); orbOpacityTimer = null }
  }, 1000 / 60)
}

async function summonOrb(reason) {
  // Self-heal: if the orb window is gone (crash, force-close, never created),
  // recreate it at last home. summonOrb should NEVER fail silently because the
  // window doesn't exist — that's how users "lose her for good," which is a
  // promise we made not to break.
  if (!orbWindow || orbWindow.isDestroyed()) {
    console.log(`[Orb] summon triggered recreate (reason=${reason})`)
    createOrbWindow()
    // Wait for the renderer to boot before sending state. If it times out,
    // we still try — replayStateToOrb is defensive.
    await waitForOrbReady(3000)
  }

  if (!orbWindow || orbWindow.isDestroyed()) {
    console.warn(`[Orb] summon failed — recreate did not produce a window`)
    return
  }
  // WP-03: if she's currently 'hidden' (close-menu stashed her off-screen),
  // summoning should wake her back up even if dock state says 'top'. The
  // "already summoned, no-op" short-circuit only applies when she's actually
  // visible — otherwise the user can't recover her.
  if (orbDock === 'top' && orbVisibility !== 'hidden') return
  orbDock = 'top'
  if (orbIdleTimer) { clearTimeout(orbIdleTimer); orbIdleTimer = null }
  console.log(`[Orb] summon (reason=${reason}) anchored=${hasUserAnchored}`)

  // Explicit user-summon should clear the proactive cooldown. The main window
  // holds the socket, so we round-trip through it.
  if ((reason === 'hotkey' || reason === 'voice-regex') && mainWindow && !mainWindow.isDestroyed()) {
    try { mainWindow.webContents.send('orb:user-summoned', { reason }) } catch (_) {}
  }

  // WP-06: anchored summon skips travel and plays bloom-from-within in place.
  // She's already at home; the ceremonial flight is gone. We still resize the
  // window, but keep her centered on her anchor point.
  const useBloom = hasUserAnchored
  const target = useBloom ? null : orbTopCenterPosition()

  try { orbWindow.setFocusable(true) } catch (_) {}

  if (useBloom) {
    // Resize around SAVED HOME body center — canonical truth, not
    // getPosition() which drifts with every resize cycle. Saved home = corner
    // window top-left (140×140). Body center relative to that = (70, 45).
    try {
      const ORB_VISUAL = 78
      const BODY_Y_OFFSET = 6 + ORB_VISUAL / 2  // 45
      const home = orbHomePosition()
      const bodyCenterX = home.x + Math.round(ORB_CORNER_SIZE / 2)
      const bodyCenterY = home.y + BODY_Y_OFFSET
      const nx = bodyCenterX - Math.round(ORB_SUMMONED_W / 2)
      const ny = bodyCenterY - BODY_Y_OFFSET
      const [preX, preY] = orbWindow.getPosition()
      const [preW, preH] = orbWindow.getSize()
      console.log(`[Orb:summon] pre=(${preX},${preY}) size=(${preW}x${preH}) home=(${home.x},${home.y}) bodyCenter=(${bodyCenterX},${bodyCenterY}) → newBounds=(${nx},${ny},${ORB_SUMMONED_W}x${ORB_SUMMONED_H})`)
      orbFoundation.beginProgrammaticMove(200)
      // Resize on an INVISIBLE window — then fade opacity back in after the
      // window manager + renderer have both caught up to the new bounds.
      // Without this, Windows/DWM paints 1–2 frames where window size and
      // renderer left:50% layout are out of sync, flashing the orb body
      // left or right before it settles. setOpacity(0) lasts through the
      // resize; setOrbVisibility('active') below tweens from 0 to 1.0.
      try { orbWindow.setOpacity(0) } catch (_) {}
      orbWindow.setBounds({ x: nx, y: ny, width: ORB_SUMMONED_W, height: ORB_SUMMONED_H }, false)
      lastKnownOrbPosition = { x: nx, y: ny }
    } catch (_) {}
    playBloomAt('in')
  } else {
    // Unanchored: original ceremonial travel to top-center.
    try {
      const [cx, cy] = orbWindow.getPosition()
      orbFoundation.beginProgrammaticMove(300)
      orbWindow.setBounds({ x: cx, y: cy, width: ORB_SUMMONED_W, height: ORB_SUMMONED_H }, false)
      lastKnownOrbPosition = { x: cx, y: cy }
    } catch (_) {}
    travelOrbTo(target)
  }

  // Click-through enabled AFTER the resize. Setting setIgnoreMouseEvents
  // before setBounds can trigger a Windows DWM re-anchor on the transparent
  // toolbar window, contributing to horizontal glitches during summon.
  try { orbWindow.setIgnoreMouseEvents(true, { forward: true }) } catch (_) {}

  // WP-03: visibility is authoritative. setOrbVisibility handles the
  // opacity tween + renderer IPC + proximity-poll teardown in one place.
  setOrbVisibility('active', `summon:${reason || 'n/a'}`)

  orbFoundation.setCache('dock', 'top')
  forwardToOrb('orb:dock', { dock: 'top', reason })
  forwardToOrb('orb:travel', { to: 'center', reason })
}

function dismissOrb(reason) {
  if (!orbWindow || orbWindow.isDestroyed()) return
  // Already at rest? Context-menu Close on an already-resting orb should
  // still hide her; any other dismiss on a corner-docked orb is a no-op.
  if (orbDock === 'corner') {
    const isExplicitClose = reason === 'context-menu' || reason === 'close-button' || reason === 'close-event'
    if (isExplicitClose && orbVisibility !== 'hidden') {
      setOrbVisibility('hidden', `dismiss:${reason}`)
    }
    return
  }
  orbDock = 'corner'
  if (orbIdleTimer) { clearTimeout(orbIdleTimer); orbIdleTimer = null }
  console.log(`[Orb] dismiss (reason=${reason}) anchored=${hasUserAnchored}`)

  // WP-06: anchored dismiss plays bloom-out in place — no travel back home,
  // she's already home. Unanchored dismiss keeps the ceremonial travel.
  // Explicit-close (×/context-menu) always travels to hidden regardless.
  const isExplicitClose = reason === 'context-menu' || reason === 'close-button' || reason === 'close-event'
  const useBloom = hasUserAnchored && !isExplicitClose
  const target = useBloom ? null : orbHomePosition()

  if (useBloom) {
    // Bloom out in place. Dismiss returns to saved home exactly (140×140).
    // Using saved home directly removes any drift from round-trip resize math.
    try {
      const home = orbHomePosition()
      const [preX, preY] = orbWindow.getPosition()
      const [preW, preH] = orbWindow.getSize()
      console.log(`[Orb:dismiss] pre=(${preX},${preY}) size=(${preW}x${preH}) home=(${home.x},${home.y}) → newBounds=(${home.x},${home.y},${ORB_CORNER_SIZE}x${ORB_CORNER_SIZE})`)
      orbFoundation.beginProgrammaticMove(200)
      // Same opacity mask trick as summon — hide during the 380→140 resize
      // so any DWM/reflow frame-mismatch isn't visible. setOrbVisibility
      // below tweens opacity back to the dismiss target.
      try { orbWindow.setOpacity(0) } catch (_) {}
      orbWindow.setBounds({ x: home.x, y: home.y, width: ORB_CORNER_SIZE, height: ORB_CORNER_SIZE }, false)
      lastKnownOrbPosition = { x: home.x, y: home.y }
    } catch (_) {}
    playBloomAt('out')
  } else {
    travelOrbTo(target)
  }

  // WP-03: context-menu "Close" (or × equivalents) → 'hidden' (fully
  // off-screen, re-summon brings her back). Any other dismiss path →
  // 'resting' when anchored, 'ghost' when unanchored.
  const dismissTo = isExplicitClose
    ? 'hidden'
    : (hasUserAnchored ? 'resting' : 'ghost')
  setOrbVisibility(dismissTo, `dismiss:${reason || 'n/a'}`)

  // Resize AFTER travel completes (unanchored path only — bloom already
  // resized around anchor above).
  if (!useBloom) {
    setTimeout(() => {
      if (!orbWindow || orbWindow.isDestroyed()) return
      try {
        orbFoundation.beginProgrammaticMove(200)
        orbWindow.setBounds({
          x: target.x, y: target.y,
          width: ORB_CORNER_SIZE, height: ORB_CORNER_SIZE,
        }, false)
        lastKnownOrbPosition = { x: target.x, y: target.y }
      } catch (_) {}
      try { orbWindow.setIgnoreMouseEvents(true, { forward: true }) } catch (_) {}
      try { orbWindow.setFocusable(false) } catch (_) {}
    }, ORB_TRAVEL_MS + ORB_ARRIVAL_SETTLE_MS + 20)
  } else {
    try { orbWindow.setIgnoreMouseEvents(true, { forward: true }) } catch (_) {}
    try { orbWindow.setFocusable(false) } catch (_) {}
  }

  orbFoundation.setCache('dock', 'corner')
  forwardToOrb('orb:dock', { dock: 'corner', reason })
  forwardToOrb('orb:travel', { to: 'corner', reason })
}

function toggleOrbDock(reason) {
  if (orbDock === 'corner') summonOrb(reason || 'toggle')
  else dismissOrb(reason || 'toggle')
}

// Back-compat: existing `orb:travel { to: 'center'|'corner' }` routes through
// summon/dismiss so the auto-travel ripout in App.jsx doesn't need to know
// about the new channels and backend `orb_travel` tool calls still work.
function handleOrbTravel(payload) {
  const to = payload?.to
  if (!orbWindow || orbWindow.isDestroyed()) return
  if (to === 'center') summonOrb(payload?.reason || 'travel')
  else if (to === 'corner') dismissOrb(payload?.reason || 'travel')
}

function forwardToOrb(channel, payload) {
  if (!orbWindow || orbWindow.isDestroyed()) return
  try { orbWindow.webContents.send(channel, payload) } catch (_) {}
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 780,
    minWidth: 900,
    minHeight: 600,
    frame: false,
    show: false,
    icon: path.join(__dirname, '..', 'assets', 'ame-orb.ico'),
    backgroundColor: '#080c14',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.cjs')
    }
  })

  // Show a lightweight loading screen immediately — no more black screen.
  // IMPORTANT: -webkit-app-region: drag was previously on body here. That
  // CSS persists as a window-level drag region after Vite loads the real
  // app, turning every click into a drag-window-start. We now scope the
  // drag region to a tiny 28px strip at the top only, so the wizard and
  // the rest of the UI receive real click events.
  const orbPathMain = pickRandomOrbPath()
  const orbMarkupMain = orbPathMain
    ? `<img src="file:///${orbPathMain.replace(/\\/g, '/')}" class="orb-img" alt="" />`
    : `<div class="ring outer"></div><div class="ring"></div><div class="orb"></div>`

  const loadingHtml = `<!DOCTYPE html>
<html><head><style>
  * { margin:0; padding:0; box-sizing:border-box; }
  html, body {
    background: #09090b; color: #e5e5e5;
    font-family: -apple-system, 'Segoe UI', system-ui, sans-serif;
    height: 100vh; overflow: hidden;
    -webkit-app-region: no-drag;
  }
  .dragbar {
    position: fixed; top: 0; left: 0; right: 0; height: 28px;
    -webkit-app-region: drag;
    z-index: 10;
  }
  .center {
    position: absolute; inset: 0;
    display: flex; align-items: center; justify-content: center;
    -webkit-app-region: no-drag;
    flex-direction: column; gap: 28px;
  }
  .orb-wrap {
    position: relative;
    width: 160px; height: 160px;
    display: flex; align-items: center; justify-content: center;
  }
  .orb-img {
    width: 160px; height: 160px;
    object-fit: cover;
    mix-blend-mode: lighten;
    filter: contrast(1.08) saturate(1.15) brightness(1.05);
    animation: float 4.2s ease-in-out infinite;
    pointer-events: none;
    user-select: none;
    -webkit-mask-image: radial-gradient(circle at 50% 50%, rgba(0,0,0,1) 38%, rgba(0,0,0,0.85) 46%, rgba(0,0,0,0) 50%);
            mask-image: radial-gradient(circle at 50% 50%, rgba(0,0,0,1) 38%, rgba(0,0,0,0.85) 46%, rgba(0,0,0,0) 50%);
  }
  .orb {
    width: 78px; height: 78px;
    border-radius: 50%;
    background:
      radial-gradient(circle at 35% 30%, rgba(255,255,255,0.18), rgba(255,255,255,0) 55%),
      radial-gradient(circle at 60% 70%, rgba(255,255,255,0.05), rgba(255,255,255,0) 60%),
      radial-gradient(circle at 50% 50%, #2a2a2e 0%, #161618 70%);
    box-shadow:
      inset 0 0 22px rgba(0,0,0,0.55),
      0 0 30px rgba(255,255,255,0.04);
    animation: float 4.2s ease-in-out infinite;
  }
  .ring {
    position: absolute; inset: 0;
    border-radius: 50%;
    border: 1px solid rgba(255,255,255,0.06);
    animation: spin 14s linear infinite;
  }
  .ring.outer { inset: -10px; border-color: rgba(255,255,255,0.04); animation-duration: 22s; animation-direction: reverse; }
  @keyframes float {
    0%, 100% { transform: translateY(0) scale(1); }
    50%      { transform: translateY(-3px) scale(1.015); }
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .label {
    text-align: center;
  }
  .title {
    font-size: 11px; font-weight: 500; letter-spacing: 0.42em;
    color: #fafafa;
    text-transform: uppercase;
  }
  .status {
    font-size: 11px; color: #6b6b70; letter-spacing: 0.06em;
    margin-top: 14px; min-height: 1em;
    transition: opacity 0.4s ease;
    font-family: 'SF Mono', 'JetBrains Mono', Consolas, monospace;
  }
</style></head><body>
  <div class="dragbar"></div>
  <div class="center">
    <div class="orb-wrap">
      ${orbMarkupMain}
    </div>
    <div class="label">
      <div class="title">Amé</div>
      <div class="status" id="status">initializing</div>
    </div>
  </div>
  <script>
    const tips = [
      'initializing',
      'tuning the orb',
      'tip — press F4 to mute',
      'tip — Ctrl+K opens the command palette',
      'tip — double-clap to summon me',
      'warming the voice channel',
      'reading the room',
      'tip — I remember between conversations',
      'aligning the ambient layer',
      'tip — orb mode hides the chat for focus',
    ];
    let i = 0;
    const el = document.getElementById('status');
    setInterval(() => {
      i = (i + 1) % tips.length;
      el.style.opacity = '0';
      setTimeout(() => { el.textContent = tips[i]; el.style.opacity = '0.7'; }, 240);
    }, 1800);
  </script>
</body></html>`

  const loadingFile = writeTempSplashHtml(loadingHtml, 'splash-main.html')
  mainWindow.loadFile(loadingFile)
  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
    mainWindow.focus()
  })
  // Safety: if ready-to-show is delayed, show anyway after 1.2s
  setTimeout(() => {
    if (mainWindow && !mainWindow.isDestroyed() && !mainWindow.isVisible()) {
      mainWindow.show()
      mainWindow.focus()
    }
  }, 1200)

  mainWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault()
      mainWindow.hide()
    }
  })
}

function loadApp() {
  // Swap the loading screen for the real React app once backend is ready
  if (!mainWindow || mainWindow.isDestroyed()) return

  if (isDev) {
    const http = require('http')
    const pollVite = () => {
      http.get('http://localhost:5173', (res) => {
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.loadURL('http://localhost:5173')
        }
      }).on('error', () => {
        setTimeout(pollVite, 300)
      })
    }
    pollVite()
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'))
  }
}

// WP-11: cinema-mode state. Snapshots visibility at entry, restores on exit.
let preCinemaState = null
const cinemaDetector = cinemaMode.createCinemaDetector({
  getOrbWindow: () => orbWindow,
  onEnter: () => {
    console.log('[Cinema] fullscreen detected → orb hidden')
    preCinemaState = orbBaselineVisibility || orbVisibility || 'resting'
    try { setOrbVisibility('hidden', 'cinema-on') } catch (_) {}
    try {
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('cinema-mode', { on: true })
      }
    } catch (_) {}
  },
  onExit: ({ durationMs }) => {
    console.log(`[Cinema] fullscreen exited after ${durationMs}ms → orb restored`)
    const restore = preCinemaState || 'resting'
    preCinemaState = null
    try { setOrbVisibility(restore, 'cinema-off') } catch (_) {}
    try {
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('cinema-mode', { on: false })
      }
    } catch (_) {}
  },
})

app.whenReady().then(async () => {
  await installDeps()
  createWindow()   // Show loading screen immediately — no more black screen
  createOrbWindow()  // Persistent desktop orb — lives alongside the main window

  // V1.3 — Multi-monitor robustness. Without these listeners, plugging or
  // unplugging a display while Amé is running leaves the orb orphaned on
  // a missing monitor (or stranded in dead space) until the next restart.
  // On any display change, we re-resolve home and snap the orb back if its
  // current position is no longer inside any connected display.
  const handleDisplayChange = (reason) => {
    try {
      if (!orbWindow || orbWindow.isDestroyed()) return
      const all = screen.getAllDisplays()
      const bounds = orbWindow.getBounds()
      const orbPoint = { x: bounds.x, y: bounds.y }
      if (orbFoundation.isPointInAnyDisplay(orbPoint, all)) {
        // Orb is still on a real display — leave it alone, even if the
        // user just plugged in a new one. Don't yank her around.
        return
      }
      // Orb is orphaned. Re-resolve home (which will fall back to default
      // on the current primary if the saved monitor is gone) and snap.
      const home = orbHomePosition()
      orbFoundation.beginProgrammaticMove(300)
      orbWindow.setBounds({ x: home.x, y: home.y, width: bounds.width, height: bounds.height }, false)
      console.log(`[Orb] display change (${reason}) — orphaned orb snapped to (${home.x},${home.y})`)
    } catch (err) {
      console.warn('[Orb] display change handler failed:', err?.message || err)
    }
  }
  screen.on('display-added', () => handleDisplayChange('added'))
  screen.on('display-removed', () => handleDisplayChange('removed'))
  screen.on('display-metrics-changed', () => handleDisplayChange('metrics-changed'))

  cinemaDetector.start()  // WP-11
  startOllama()    // Fire-and-forget: boot local Gemma tier if Ollama is installed
  startBackend()   // Backend boots in background; loadApp() called when token is captured

  // System Tray Setup
  const iconPath = path.join(__dirname, '..', 'assets', 'ame-orb.ico')
  tray = new Tray(nativeImage.createFromPath(iconPath).resize({ width: 16, height: 16 }))

  const contextMenu = Menu.buildFromTemplate([
    { label: 'Show Amé', click: () => mainWindow?.show() },
    { type: 'separator' },
    { label: 'Quit', click: () => {
        app.isQuitting = true
        if (backendProcess) backendProcess.kill()
        if (ollamaProcess) { try { ollamaProcess.kill() } catch (_) {} }
        if (orbWindow && !orbWindow.isDestroyed()) orbWindow.destroy()
        app.quit()
    }}
  ])

  tray.setToolTip('Amé Assistant')
  tray.setContextMenu(contextMenu)

  tray.on('click', () => mainWindow?.show())

  // Global hotkey for summon/dismiss. Gated on orbReady so it doesn't fire
  // during wizard/welcome. Fallback to Ctrl+Alt+A if Ctrl+Shift+Space is taken.
  const primaryAccel = 'CommandOrControl+Shift+Space'
  const fallbackAccel = 'CommandOrControl+Alt+A'
  const onHotkey = () => { if (orbReady) toggleOrbDock('hotkey') }
  let ok = false
  try { ok = globalShortcut.register(primaryAccel, onHotkey) } catch (_) { ok = false }
  if (!ok) {
    console.log(`[Orb] ${primaryAccel} unavailable, falling back to ${fallbackAccel}`)
    try { globalShortcut.register(fallbackAccel, onHotkey) } catch (_) {}
  } else {
    console.log(`[Orb] hotkey registered: ${primaryAccel}`)
  }
})

app.on('will-quit', () => {
  try { globalShortcut.unregisterAll() } catch (_) {}
})

app.on('before-quit', () => {
  app.isQuitting = true
  if (orbTravelTimer) { clearInterval(orbTravelTimer); orbTravelTimer = null }
  if (orbOpacityTimer) { clearInterval(orbOpacityTimer); orbOpacityTimer = null }
  if (orbIdleTimer) { clearTimeout(orbIdleTimer); orbIdleTimer = null }
  if (orbWindow && !orbWindow.isDestroyed()) {
    try { orbWindow.destroy() } catch (_) {}
    orbWindow = null
  }
})

app.on('window-all-closed', () => {
  if (backendProcess) backendProcess.kill()
  if (ollamaProcess) { try { ollamaProcess.kill() } catch (_) {} }
  if (process.platform !== 'darwin') app.quit()
})

// ── Orb IPC bridge: main window → main process → orb window ────────────────
// The main window owns the Socket.IO connection. It forwards state/emotion/
// cue/travel over IPC, and we rebroadcast to the orb window.
ipcMain.on('orb:state',   (_ev, payload) => {
  const s = payload?.state || 'idle'
  orbFoundation.setCache('state', s)
  forwardToOrb('orb:state', payload)
  lastOrbState = s
  // Active states cancel any pending auto-dismiss.
  const active = (s === 'thinking' || s === 'speaking' || s === 'listening')
  if (active) {
    if (orbIdleTimer) { clearTimeout(orbIdleTimer); orbIdleTimer = null }
  } else if (orbDock === 'top') {
    // Idle/muted while summoned — start (or restart) the idle watchdog.
    if (orbIdleTimer) clearTimeout(orbIdleTimer)
    orbIdleTimer = setTimeout(() => {
      if (orbDock === 'top' && (lastOrbState === 'idle' || lastOrbState === 'muted')) {
        dismissOrb('idle-timeout')
      }
      orbIdleTimer = null
    }, ORB_IDLE_DISMISS_MS)
  }
})
ipcMain.on('orb:emotion', (_ev, payload) => {
  if (payload?.emotion) orbFoundation.setCache('emotion', payload.emotion)
  forwardToOrb('orb:emotion', payload)
})
// WP-04: live mic amplitude. Forwarded 1:1 — the renderer EMAs it. Keep
// this cheap; do NOT cache to disk or dedupe, it's a realtime stream.
ipcMain.on('orb:mic-level', (_ev, payload) => {
  forwardToOrb('orb:mic-level', payload)
})
ipcMain.on('orb:accent',  (_ev, payload) => {
  if (payload?.color) orbFoundation.setCache('accent', payload.color)
  forwardToOrb('orb:accent',  payload)
})
ipcMain.on('orb:cue',     (_ev, payload) => forwardToOrb('orb:cue',     payload))
ipcMain.on('orb:travel',  (_ev, payload) => handleOrbTravel(payload))
ipcMain.on('orb:summon',  (_ev, payload) => summonOrb(payload?.reason || 'ipc'))
ipcMain.on('orb:dismiss', (_ev, payload) => dismissOrb(payload?.reason || 'ipc'))
ipcMain.on('orb:ready',   () => { orbReady = true })

// WP-12: wizard completion → birth trigger. Main window emits this right
// after WelcomePage.onComplete fires (envReady transition). We wait 400ms so
// the wizard→chat transition settles, then call playBirth which no-ops unless
// marker files are absent. Detected tier comes from the saved capability
// record (renderer writes it on first probe).
function triggerBirthFromWizard() {
  if (!birthTrigger.shouldPlayBirth()) return
  let tier = 'mid'
  try {
    const cap = orbFoundation.loadCapability()
    if (cap && cap.detected) tier = cap.detected
  } catch {}
  setTimeout(() => {
    if (!orbWindow || orbWindow.isDestroyed()) return
    birthTrigger.playBirth({
      tier,
      sendOrb: (ch, p) => {
        try { orbWindow.webContents.send(ch, p) } catch (e) {
          console.warn('[Birth] sendOrb failed:', e.message)
        }
      },
      arriveAtCenter: () => {
        try { summonOrb('birth') } catch (e) {
          console.warn('[Birth] summon failed:', e.message)
        }
      },
      speakFirstLine: (text) => {
        try {
          if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('birth:first-sentence', { text })
          }
        } catch (e) {
          console.warn('[Birth] speakFirstLine relay failed:', e.message)
        }
      },
    })
  }, 400)
}

ipcMain.on('wizard:complete', () => {
  console.log('[Birth] wizard:complete received')
  triggerBirthFromWizard()
})

// WP-12: stage echoes from orb renderer. Drive side-effects (travel, speech,
// marker write) via the trigger module's handleStage.
ipcMain.on('orb:birth-stage', (_ev, payload) => {
  try {
    birthTrigger.handleStage(payload || {}, {
      arriveAtCenter: () => { try { summonOrb('birth-breath') } catch (_) {} },
      speakFirstLine: (text) => {
        try {
          if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('birth:first-sentence', { text })
          }
        } catch (_) {}
      },
      onDone: () => { console.log('[Birth] complete — marker written') },
    })
  } catch (e) {
    console.warn('[Birth] handleStage error:', e.message)
  }
})

// Hit-region: renderer tells us when the pointer is over the orb's actual
// body (vs. the transparent padding). When pointer leaves the orb, we let
// clicks pass through to whatever's underneath. When it enters, we capture.
// This is what makes the summoned 380×220 window NOT block clicks on the
// user's desktop icons next to the orb.
// hit-region IPC is now a no-op — main process polls cursor position
// directly (startOrbCursorPoll). Kept receivable for preload-API
// compatibility, but the renderer's mouseenter events can't drive this
// because a click-through window never gets pointer events in the first
// place. Leaving the channel silent avoids fighting the poller.
ipcMain.on('orb:hit-region', () => { /* no-op; see startOrbCursorPoll */ })

// ── Manual drag ────────────────────────────────────────────────────────────
// Replaces -webkit-app-region:drag, which eats right-click at the OS level
// (that's why the native system menu kept appearing — drag regions are
// treated like a title bar). Renderer sends drag-start on mousedown with
// the cursor offset inside the orb; main process then polls the cursor and
// follows it with setPosition until drag-end.
let orbDragTimer = null

let orbDragOffset = null       // cursor→window-top-left offset, captured once
let orbDragStartWinPos = null  // window pos at drag start (for end-of-drag anchor delta)

function startOrbDrag(_offset) {
  if (!orbWindow || orbWindow.isDestroyed()) return
  if (orbDragTimer) { clearInterval(orbDragTimer); orbDragTimer = null }

  // Compute a fixed offset from cursor → window top-left at drag start.
  // Each tick we re-target window to cursor - offset. Offset is captured ONCE
  // in DIP space and never recomputed, so DPI quantization errors can't
  // compound over the drag — every frame re-derives the target from scratch
  // relative to the live cursor, not from deltas against a stale baseline.
  //
  // Previous delta-from-start approach (startPos + (cursor - startCursor))
  // suffered compounding drift during motion because every tick
  // re-read getCursorScreenPoint() and DIP rounding of large deltas
  // accumulated. Direct cursor-minus-offset has no accumulation.
  try {
    const b0 = orbWindow.getBounds()
    const c0 = screen.getCursorScreenPoint()
    orbDragOffset = { x: c0.x - b0.x, y: c0.y - b0.y }
    orbDragStartWinPos = { x: b0.x, y: b0.y }
  } catch (_) {
    orbDragOffset = null
    orbDragStartWinPos = null
  }

  // Pause cursor-proximity poller during drag so it doesn't fight
  // the drag-follow loop over setIgnoreMouseEvents state.
  stopOrbCursorPoll()
  stopOrbProximityPoll()
  // Disable click-through WITHOUT forward. `forward:true` re-sends mouse
  // events to the window below, which on Windows can subtly shift cursor
  // reporting during drag. During an active drag we want exclusive cursor
  // ownership — no forwarding.
  try { orbWindow.setIgnoreMouseEvents(false) } catch (_) {}
  orbFoundation.beginProgrammaticMove(10_000)

  // Dedup consecutive identical targets. Calling setPosition with the same
  // coords on fractional-DPI displays can slide the window 1 physical pixel
  // per frame because SetWindowPos round-trip isn't identity.
  let lastCmdX = null
  let lastCmdY = null
  // Pin window size on every drag tick. DWM on transparent toolwindow
  // was inflating width/height by 1px per frame when setPosition was used —
  // 60 frames later the window had grown ~60px, and the orb (centered via
  // left:50%) appeared to drift right as the window expanded rightward
  // past the cursor. Using setBounds with explicit width/height forces
  // Windows to hold the size constant.
  const pinnedW = orbDock === 'top' ? ORB_SUMMONED_W : ORB_CORNER_SIZE
  const pinnedH = orbDock === 'top' ? ORB_SUMMONED_H : ORB_CORNER_SIZE
  orbDragTimer = setInterval(() => {
    if (!orbWindow || orbWindow.isDestroyed()) { endOrbDrag(); return }
    if (!orbDragOffset) return
    try {
      const cursor = screen.getCursorScreenPoint()
      const x = Math.round(cursor.x - orbDragOffset.x)
      const y = Math.round(cursor.y - orbDragOffset.y)
      if (x === lastCmdX && y === lastCmdY) return
      lastCmdX = x
      lastCmdY = y
      orbWindow.setBounds({ x, y, width: pinnedW, height: pinnedH }, false)
      lastKnownOrbPosition = { x, y }
    } catch (_) {}
  }, 1000 / 60)
}

function endOrbDrag() {
  if (orbDragTimer) { clearInterval(orbDragTimer); orbDragTimer = null }
  orbDragOffset = null
  orbFoundation.endProgrammaticMove()
  if (!orbWindow || orbWindow.isDestroyed()) return
  // Anchor decision: compare final position against where the drag began.
  // A drag that moves further than ORB_DRAG_ANCHOR_THRESHOLD counts as an
  // intentional placement — save it as home.
  try {
    const [x, y] = orbWindow.getPosition()
    if (orbDragStartWinPos) {
      const dx = x - orbDragStartWinPos.x
      const dy = y - orbDragStartWinPos.y
      const dist = Math.sqrt(dx * dx + dy * dy)
      if (dist >= ORB_DRAG_ANCHOR_THRESHOLD) {
        hasUserAnchored = true
        // If she was dragged while summoned (380 wide), the saved home
        // must be the corner-equivalent top-left so the next summon
        // recomputes the body center correctly. Otherwise summon reads
        // the 380-window top-left as if it were a 140-window top-left,
        // then re-centers and shifts the orb 120px to the left.
        // BODY_Y_OFFSET matches between sizes (both use ORB_VISUAL=78),
        // so only x needs translation.
        let homeX = x
        let homeY = y
        if (orbDock === 'top') {
          homeX = x + Math.round((ORB_SUMMONED_W - ORB_CORNER_SIZE) / 2)
        }
        orbFoundation.saveHome(homeX, homeY)
        console.log(`[Orb] anchored at x=${homeX} y=${homeY} (drag Δ=${Math.round(dist)}px, dock=${orbDock})`)
        forwardToOrb('orb:anchored', { x: homeX, y: homeY, previouslyAnchored: true })
      } else {
        console.log(`[Orb] drag too small (Δ=${Math.round(dist)}px), not anchoring`)
      }
    }
  } catch (_) {}
  orbDragStartWinPos = null
  startOrbCursorPoll()
}

// WP-09 dev: forward force-fidget from main window DevTools to orb window.
ipcMain.on('orb:force-fidget', (_ev, payload) => forwardToOrb('orb:force-fidget', payload))

ipcMain.on('orb:drag-start', (_ev, offset) => startOrbDrag(offset))
ipcMain.on('orb:drag-end',   () => endOrbDrag())

// WP-09 fidget: micro-bob. Nudge orb window +3px Y, return after 450ms.
// Uses beginProgrammaticMove so the move-suppression guard ignores these
// setBounds calls (prevents our own animation from self-anchoring home).
// Rate-limited to one bob per 800ms so a malicious/buggy renderer can't
// spam window moves.
let _lastBobAt = 0
ipcMain.on('orb:fidget-bob', () => {
  if (!orbWindow || orbWindow.isDestroyed()) return
  const now = Date.now()
  if (now - _lastBobAt < 800) return
  _lastBobAt = now
  try {
    const b = orbWindow.getBounds()
    orbFoundation.beginProgrammaticMove(500)
    orbWindow.setBounds({ x: b.x, y: b.y + 3, width: b.width, height: b.height }, false)
    setTimeout(() => {
      if (!orbWindow || orbWindow.isDestroyed()) return
      orbFoundation.beginProgrammaticMove(200)
      orbWindow.setBounds({ x: b.x, y: b.y, width: b.width, height: b.height }, false)
    }, 450)
  } catch (_) {}
})

// Capability probe: orb renderer measures hardware on first boot, reports
// back so main process can persist and use the tier for its own decisions
// (cursor polling cadence, cinema-mode frequency, future orchestration).
ipcMain.on('orb:capability', (_ev, payload) => {
  if (!payload) return
  try {
    orbFoundation.saveCapability(payload)
    console.log(`[Capability] tier=${payload.detected}${payload.override && payload.override !== 'auto' ? ' override=' + payload.override : ''}`)
  } catch (err) {
    console.warn('[Capability] save error:', err?.message || err)
  }
})
ipcMain.handle('orb:capability-get', () => {
  try { return orbFoundation.loadCapability() } catch { return null }
})

ipcMain.handle('get-session-token', () => sessionToken)

ipcMain.handle('check-admin', () => {
  try {
    require('child_process').execSync('net session', { stdio: 'ignore' })
    return true
  } catch (e) {
    return false
  }
})

ipcMain.on('relaunch-admin', () => {
  const args = process.argv.slice(1).filter(a => a !== '--tried-admin')
  if (args.length > 0 && args[0] === '.') {
    args[0] = process.cwd()
  }
  args.push('--tried-admin')

  const { spawn } = require('child_process')
  const argsList = args.map(a => `'${a.replace(/'/g, "''")}'`).join(', ')
  const cwd = process.cwd()
  const psCommand = `Start-Process -FilePath '${process.execPath}' -ArgumentList ${argsList} -WorkingDirectory '${cwd}' -Verb RunAs`

  const ps = spawn('powershell.exe', ['-NoProfile', '-WindowStyle', 'Hidden', '-Command', psCommand])
  ps.on('close', (code) => {
    if (code === 0) app.quit()
  })
})

ipcMain.on('minimize-window', () => mainWindow?.minimize())
ipcMain.on('maximize-window', () => {
  if (mainWindow?.isMaximized()) mainWindow.unmaximize()
  else mainWindow?.maximize()
})
ipcMain.on('close-window', () => {
  mainWindow?.hide()
})
ipcMain.on('focus-window', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore()
    mainWindow.focus()
  }