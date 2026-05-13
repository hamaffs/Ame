import React, { useState } from 'react'
import { motion } from 'framer-motion'
import { Loader2, CheckCircle, XCircle } from 'lucide-react'

/**
 * First-run setup. App.jsx mounts this when `envReady === false` (the backend
 * told us no .env / API key is configured yet).
 *
 * Flow:
 *   1. Validate the key against the provider via POST /test-provider
 *   2. Persist via POST /setup
 *   3. Call onComplete() so App swaps back to the main UI
 *
 * Both endpoints require the session token (Authorization: Bearer <token>),
 * which Electron's preload exposes via window.electronAPI.getSessionToken().
 * When running in a plain browser tab (no Electron) the token is null and
 * the backend will 403 — that's expected; production use is through Electron.
 */
export default function WelcomePage({ onComplete }) {
  const [keys, setKeys] = useState({
    GOOGLE_AI_STUDIO_KEY: '',
    GROQ_API_KEY: '',
    name: '',
  })
  const [saving, setSaving] = useState(false)
  const [error,  setError]  = useState(null)

  const update = (k) => (e) => setKeys((prev) => ({ ...prev, [k]: e.target.value }))

  const submit = async () => {
    const hasKey = (keys.GOOGLE_AI_STUDIO_KEY || keys.GROQ_API_KEY || '').trim().length > 0
    if (!hasKey) {
      setError('Add at least one API key to continue.')
      return
    }
    setSaving(true); setError(null)

    try {
      const backend = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8766'

      // Grab the session token from the Electron preload bridge.
      let token = null
      try { token = await window.electronAPI?.getSessionToken?.() } catch (_) {}
      const auth = token ? { Authorization: `Bearer ${token}` } : {}

      // Step 1 — validate the key against the provider.
      const testRes = await fetch(`${backend}/test-provider`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...auth },
        body: JSON.stringify({
          GROQ_API_KEY: keys.GROQ_API_KEY.trim(),
          GOOGLE_AI_STUDIO_KEY: keys.GOOGLE_AI_STUDIO_KEY.trim(),
        }),
      })
      if (testRes.status === 403) {
        throw new Error('Backend rejected the request — session token missing. Launch Amé via Electron (`ame`), not the raw browser.')
      }
      if (!testRes.ok) {
        throw new Error(`Provider test failed: HTTP ${testRes.status}`)
      }
      const testJson = await testRes.json().catch(() => ({}))
      if (testJson.ok === false) {
        throw new Error(testJson.error || 'Key rejected by provider')
      }

      // Step 2 — persist into ~/.config/ame/.env (Linux) / %APPDATA%\ame\.env (Win).
      const saveRes = await fetch(`${backend}/setup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...auth },
        body: JSON.stringify({
          name: keys.name.trim(),
          provider: keys.GOOGLE_AI_STUDIO_KEY ? 'gemini' : 'groq',
          GROQ_API_KEY: keys.GROQ_API_KEY.trim(),
          GOOGLE_AI_STUDIO_KEY: keys.GOOGLE_AI_STUDIO_KEY.trim(),
        }),
      })
      if (!saveRes.ok) {
        const body = await saveRes.json().catch(() => ({}))
        throw new Error(body.message || `Save failed: HTTP ${saveRes.status}`)
      }

      // Let Electron know the wizard is complete (used to unlock the orb hotkey).
      try { window.electronAPI?.orbSend?.('wizard:complete') } catch (_) {}

      onComplete?.()
    } catch (e) {
      setError(e.message || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0,
      background: 'var(--ame-bg, #0a0a0c)',
      color: 'var(--ame-text, #e5e5e5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 24,
    }}>
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        style={{ width: 'min(440px, 100%)' }}
      >
        <h1 style={{ fontSize: 22, fontWeight: 500, margin: 0, letterSpacing: '0.04em' }}>Welcome to Amé</h1>
        <p style={{ marginTop: 8, fontSize: 13, color: 'var(--ame-text-secondary, #888)', lineHeight: 1.5 }}>
          Add at least one API key to get started. You can change these later in Settings.
        </p>

        <div style={{ marginTop: 24, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Field label="Your name (optional)"
                 hint="So Amé knows what to call you."
                 type="text"
                 value={keys.name}
                 onChange={update('name')} />
          <Field label="Google AI Studio / Gemini key (recommended)"
                 hint="From aistudio.google.com — drives Gemini Live voice and most tasks."
                 value={keys.GOOGLE_AI_STUDIO_KEY}
                 onChange={update('GOOGLE_AI_STUDIO_KEY')} />
          <Field label="Groq API key (optional)"
                 hint="Used as a faster fallback for some tasks."
                 value={keys.GROQ_API_KEY}
                 onChange={update('GROQ_API_KEY')} />
        </div>

        {error && (
          <div style={{ marginTop: 16, color: 'var(--ame-rose, #ff7a9b)', fontSize: 12, display: 'flex', alignItems: 'flex-start', gap: 6 }}>
            <XCircle size={13} style={{ marginTop: 2, flexShrink: 0 }} />
            <span>{error}</span>
          </div>
        )}

        <div style={{ marginTop: 24, display: 'flex', gap: 10 }}>
          <button
            className="btn-primary"
            disabled={saving}
            onClick={submit}
            style={{ display: 'flex', alignItems: 'center', gap: 8 }}
          >
            {saving ? <Loader2 size={13} className="spin" /> : <CheckCircle size={13} />}
            {saving ? 'Validating…' : 'Continue'}
          </button>
          <button
            className="btn-ghost"
            onClick={() => onComplete?.()}
            disabled={saving}
          >
            Skip for now
          </button>
        </div>

        <p style={{ marginTop: 18, fontSize: 11, color: 'var(--ame-text-ghost, #555)' }}>
          Keys are stored locally on this machine. On Linux, that's <code>~/.config/ame/.env</code>.
        </p>
      </motion.div>
    </div>
  )
}

function Field({ label, hint, value, onChange, type = 'password' }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <span style={{ fontSize: 11, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--ame-text-secondary, #888)' }}>{label}</span>
      <input
        type={type}
        value={value}
        onChange={onChange}
        placeholder={type === 'text' ? 'your name…' : 'paste key…'}
        style={{
          background: 'var(--ame-bg-card, #111)',
          border: '1px solid var(--ame-border, #222)',
          borderRadius: 4,
          color: 'var(--ame-text, #e5e5e5)',
          padding: '8px 10px',
          fontSize: 12,
          fontFamily: 'JetBrains Mono, monospace',
          outline: 'none',
        }}
      />
      {hint && <span style={{ fontSize: 11, color: 'var(--ame-text-ghost, #555)' }}>{hint}</span>}
    </label>
  )
}
