// Orb-window renderer. Loaded by orb.html in a separate Electron BrowserWindow
// (transparent, always-on-top, click-through). Receives state/emotion/accent
// from main process via window.orbAPI (see electron/preload.cjs).
//
// Phase-1 scaffold: renders OrbScene at 140×140 and updates its props from
// the orb IPC channels. The orb-window/* helpers (birth, fidgets, drag
// physics, capability, emotion transitions) are left for a follow-up pass —
// they need IPC stage-events from main that we're not driving yet.

import React, { useEffect, useState } from 'react'
import ReactDOM from 'react-dom/client'
import OrbScene from './components/OrbScene.jsx'

function OrbApp() {
  const [state, setState]     = useState('idle')
  const [emotion, setEmotion] = useState('watching')
  const [accent, setAccent]   = useState('#00d084')

  useEffect(() => {
    if (!window.orbAPI) return
    const offState   = window.orbAPI.onState?.(s => s && setState(s))
    const offEmotion = window.orbAPI.onEmotion?.(e => e && setEmotion(e))
    const offAccent  = window.orbAPI.onAccent?.(c => c && setAccent(c))
    // Tell main process the orb renderer is up so the hotkey gate opens.
    try { window.orbAPI.reportBirthStage?.({ stage: 'ready' }) } catch (_) {}
    return () => {
      try { offState?.() } catch (_) {}
      try { offEmotion?.() } catch (_) {}
      try { offAccent?.() } catch (_) {}
    }
  }, [])

  // OrbScene reads `state` and `accentColor`; `emotion` is reserved for the
  // richer renderer to wire up later (subtle hue / breath-depth shifts).
  void emotion

  return (
    <div style={{ width: '100%', height: '100%' }}>
      <OrbScene state={state} size={140} accentColor={accent} orbMode={true} />
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('orb-root')).render(
  <OrbApp />
)
