,
}
const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  onOrbUserSummoned: (cb) => {
    const h = (_e, p) => cb(p)
    ipcRenderer.on('orb:user-summoned', h)
    return () => ipcRenderer.removeListener('orb:user-summoned', h)
  },
  // WP-11 cinema mode: main.cjs emits on/off, chat renderer relays to backend.
  onCinemaMode: (cb) => {
    const h = (_e, p) => cb(p)
    ipcRenderer.on('cinema-mode', h)
    return () => ipcRenderer.removeListener('cinema-mode', h)
  },
  // WP-12 birth first sentence. Main emits with { text } during birth.
  // Chat renderer relays to backend via socket `speak_first_sentence`.
  onFirstSentence: (cb) => {
    const h = (_e, p) => cb(p)
    ipcRenderer.on('birth:first-sentence', h)
    return () => ipcRenderer.removeListener('birth:first-sentence', h)
  },
  minimize: () => ipcRenderer.send('minimize-window'),
  maximize: () => ipcRenderer.send('maximize-window'),
  close: () => ipcRenderer.send('close-window'),
  focus: () => ipcRenderer.send('focus-window'),
  getSessionToken: () => ipcRenderer.invoke('get-session-token'),
  checkAdmin: () => ipcRenderer.invoke('check-admin'),
  relaunchAdmin: () => ipcRenderer.send('relaunch-admin'),
  // ── Orb bridge (used by the main window to drive the orb window) ──
  orbSend: (channel, payload) => {
    const allowed = [
      'orb:state', 'orb:emotion', 'orb:accent', 'orb:cue', 'orb:travel',
      'orb:summon', 'orb:dismiss', 'orb:ready',
      'orb:mic-level', 'orb:force-fidget', 'wizard:complete',
    ]
    if (!allowed.includes(channel)) return
    ipcRenderer.send(channel, payload)
  },
})

// Consumed by the orb window (read-only mirror). Each `onX` returns an
// unsubscribe function.
contextBridge.exposeInMainWorld('orbAPI', {
  onState:   (cb) => {
    const h = (_e, p) => cb(p?.state)
    ipcRenderer.on('orb:state', h)
    return () => ipcRenderer.removeListener('orb:state', h)
  },
  onEmotion: (cb) => {
    const h = (_e, p) => cb(p?.emotion)
    ipcRenderer.on('orb:emotion', h)
    return () => ipcRenderer.removeListener('orb:emotion', h)
  },
  onAccent: (cb) => {
    const h = (_e, p) => cb(p?.color)
    ipcRenderer.on('orb:accent', h)
    return () => ipcRenderer.removeListener('orb:accent', h)
  },
  onCue: (cb) => {
    const h = (_e, p) => cb(p)
    ipcRenderer.on('orb:cue', h)
    return () => ipcRenderer.removeListener('orb:cue', h)
  },
  onTravel: (cb) => {
    const h = (_e, p) => cb(p)
    ipcRenderer.on('orb:travel', h)
    return () => ipcRenderer.removeListener('orb:travel', h)
  },
  onDock: (cb) => {
    const h = (_e, p) => cb(p?.dock)
    ipcRenderer.on('orb:dock', h)
    return () => ipcRenderer.removeListener('orb:dock', h)
  },
  onAnchored: (cb) => {
    const h = (_e, p) => cb(p)
    ipcRenderer.on('orb:anchored', h)
    return () => ipcRenderer.removeListener('orb:anchored', h)
  },
  // WP-03: unified visibility state. Receives { state, previous, reason,
  // durationMs, tier } — renderer drives scale/breath/contour locally.
  onVisibility: (cb) => {
    const h = (_e, p) => cb(p)
    ipcRenderer.on('orb:visibility', h)
    return () => ipcRenderer.removeListener('orb:visibility', h)
  },
  // WP-04: live mic amplitude (0..1), ~20Hz from the audio path. Drives
  // breath depth phase-lock when emotion === 'listening'.
  onMicLevel: (cb) => {
    const h = (_e, p) => cb(p)
    ipcRenderer.on('orb:mic-level', h)
    return () => ipcRenderer.removeListener('orb:mic-level', h)
  },
  // WP-05: arrival choreography stage events. Payload:
  //   { stage: 'anticipate'|'launch'|'flight'|'arrival'|'settle'|'cancel',
  //     tier, t, velocity: {x,y}, speed }
  // Renderer owns squash/trails/ripple based on stage. Every summon emits
  // these in order; dismiss-mid-summon emits `cancel` so the renderer can
  // clear trails + distortion immediately.
  onArrivalStage: (cb) => {
    const h = (_e, p) => cb(p)
    ipcRenderer.on('orb:arrival-stage', h)
    return () => ipcRenderer.removeListener('orb:arrival-stage', h)
  },
  // WP-06: bloom-from-within stage events. Payload:
  //   { stage: 'gather'|'resolve'|'settle'|'disperse'|'implode'|'cancel',
  //     dir: 'in'|'out', tier, t, total, final? }
  // `orb:bloom-progress` ticks at ~60Hz with { dir, tier, progress:0..1 } so
  // the renderer can drive the uCoreWave sweep frame-aligned without guessing
  // stage math itself.
  onBloomStage: (cb) => {
    const h = (_e, p) => cb(p)
    ipcRenderer.on('orb:bloom-stage', h)
    return () => ipcRenderer.removeListener('orb:bloom-stage', h)
  },
  onBloomProgress: (cb) => {
    const h = (_e, p) => cb(p)
    ipcRenderer.on('orb:bloom-progress', h)
    return () => ipcRenderer.removeListener('orb:bloom-progress', h)
  },
  // WP-09 dev: force-fire a fidget from main window DevTools.
  onForceFidget: (cb) => {
    const h = (_e, p) => cb(p)
    ipcRenderer.on('orb:force-fidget', h)
    return () => ipcRenderer.removeListener('orb:force-fidget', h)
  },
  // WP-10: light-direction cursor tracking. Payload { x, y } in normalized
  // screen-delta from orb center (~200px → 1.0). Renderer smooths + blends.
  onLightDir: (cb) => {
    const h = (_e, p) => cb(p)
    ipcRenderer.on('orb:light-dir', h)
    return () => ipcRenderer.removeListener('orb:light-dir', h)
  },
  // Orb window → main: user picked "Close" from the orb context menu.
  dismiss: () => ipcRenderer.send('orb:dismiss', { reason: 'context-menu' }),
  // Orb window → main: user picked "Chat" from the orb context menu.
  // Reuses the existing focus-window handler (shows + focuses mainWindow).
  openChat: () => ipcRenderer.send('focus-window'),
  // Capability probe — orb renderer reports detected tier + override.
  reportCapability: (payload) => ipcRenderer.send('orb:capability', payload),
  getCapability: () => ipcRenderer.invoke('orb:capability-get'),
  // Hit-region toggle: { hover: true } when pointer is over the orb's actual
  // body, { hover: false } when it leaves. Main process toggles mouse events.
  setHitRegion: (hover) => ipcRenderer.send('orb:hit-region', { hover: !!hover }),
  // Manual drag — the React renderer signals mousedown on the orb body, and
  // main process follows the cursor with setPosition until mouseup. Using a
  // custom drag instead of -webkit-app-region:drag so right-click events
  // can still reach React (drag regions swallow them at the OS level).
  dragStart: (offset) => ipcRenderer.send('orb:drag-start', offset),
  dragEnd:   () => ipcRenderer.send('orb:drag-end'),
  // WP-09 fidget: micro-bob the orb window ±3px Y as an idle gesture.
  fidgetBob: () => ipcRenderer.send('orb:fidget-bob'),
  // WP-12 birth: main → orb start signal. Payload { tier }. Orb constructs
  // its timeline, runs it, and echoes stage events back via reportBirthStage
  // so main can drive corner clamp, first-sentence speech, and marker write.
  onBirthStart: (cb) => {
    const h = (_e, p) => cb(p)
    ipcRenderer.on('orb:birth-start', h)
    return () => ipcRenderer.removeListener('orb:birth-start', h)
  },
  reportBirthStage: (payload) => ipcRenderer.send('orb:birth-stage', payload),