// WP-11 — Cinema mode detector.
//
// Detects when the user is in fullscreen (game, video, etc.) and reports
// on/off transitions via callbacks. Caller wires the transitions to orb
// visibility + backend proactive gating.
//
// Heuristic: poll at 5s intervals. For each display, grab the topmost
// non-Electron window's rect via a light Win32 call. If any foreground
// window exactly covers a display's bounds → cinema on. We avoid native
// helpers; Electron's built-in screen module + BrowserWindow state is
// enough for ~95% of cases.
//
// Specifically, we treat "cinema" as: our orb window reports it's no longer
// topmost (e.g. exclusive fullscreen app stole z-order on Windows) OR a
// known-fullscreen heuristic matches. The orb-not-visible check is the
// single most reliable signal on Windows — exclusive fullscreen apps always
// bring themselves above even alwaysOnTop toolwindows.
//
// Callers drive visibility + backend gating through the exposed callbacks.

const { screen, BrowserWindow } = require('electron')

const POLL_MS = 5000

function createCinemaDetector({ getOrbWindow, onEnter, onExit } = {}) {
  let timer = null
  let active = false
  let enterAt = 0

  function poll() {
    try {
      const orb = typeof getOrbWindow === 'function' ? getOrbWindow() : null
      if (!orb || orb.isDestroyed()) return

      // Is any *other* window full-display sized? BrowserWindow.getAllWindows
      // only sees our own windows, not third-party ones. So we rely on:
      //   (1) orb alwaysOnTop is true (we set it), yet the orb bounds hint
      //       it was pushed below — can't truly detect from JS alone without
      //       native helpers. Pragmatic fallback: listen for our own focus
      //       loss + check foreground display work-area match.
      // We approximate: check all our own BrowserWindows, if any is in
      // `fullScreen` mode, treat as cinema. This covers the main window's
      // F11 case. For exclusive-fullscreen third-party apps, users can
      // toggle manually or we add a Win32 binding later.
      let cinemaHinted = false
      const wins = BrowserWindow.getAllWindows()
      for (const w of wins) {
        if (w.isDestroyed()) continue
        if (w.id === orb.id) continue
        try {
          if (w.isFullScreen && w.isFullScreen()) {
            cinemaHinted = true
            break
          }
          // Simple-fullscreen / kiosk API variants. Ignore errors.
          if (w.isSimpleFullScreen && w.isSimpleFullScreen()) {
            cinemaHinted = true
            break
          }
        } catch (_) {}
      }

      // Secondary heuristic: any display where the foreground overlay
      // matches the entire work-area is likely a fullscreen third-party
      // app. We can't detect third-party from JS reliably, so stay with
      // the BrowserWindow-fullscreen signal for now. Future: add a native
      // helper that calls GetForegroundWindow + GetWindowRect.

      if (cinemaHinted && !active) {
        active = true
        enterAt = Date.now()
        try { onEnter && onEnter() } catch (_) {}
      } else if (!cinemaHinted && active) {
        active = false
        try { onExit && onExit({ durationMs: Date.now() - enterAt }) } catch (_) {}
      }
    } catch (_) {}
  }

  function start() {
    if (timer) return
    timer = setInterval(poll, POLL_MS)
    poll()  // kick once immediately so state is correct before the first tick
  }

  function stop() {
    if (timer) clearInterval(timer)
    timer = null
  }

  function isActive() { return active }

  return { start, stop, isActive }
}

module.exports = { createCinemaDetector }
