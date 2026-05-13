import React, { useState } from 'react'
import { motion } from 'framer-motion'
import { Loader2, CheckCircle, XCircle } from 'lucide-react'

/**
 * First-run setup. App.jsx mounts this when `envReady === false` (the backend
 * told us no .env / API key is configured yet). On submit we POST to the
 * backend `/env/save` endpoint, then call onComplete to swap back to App.
 */
export default function WelcomePage({ onComplete }) {
  const [keys, setKeys] = useState({
    GEMINI_API_KEY: '',
    GOOGLE_AI_STUDIO_KEY: '',
    GROQ_API_KEY: '',
  })
  const [saving, setSaving] = useState(false)
  const [error,  setError]  = useState(null)

  const update = (k) => (e) => setKeys((prev) => ({ ...prev, [k]: e.target.value }))

  const submit = async () => {
    const filled = Object.entries(keys).filter(([, v]) => v.trim().length > 0)
    if (filled.length === 0) {
      setError('Add at least one API key to continue.')
      return
    }
    setSaving(true); setError(null)
    try {
      const backend = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8766'
      const res = await fetch(`${backend}/env/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(Object.fromEntries(filled)),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
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
          <Field label="Gemini API key (recommended)"
                 hint="From aistudio.google.com — drives Gemini Live voice and most tasks."
                 value={keys.GEMINI_API_KEY}
                 onChange={update('GEMINI_API_KEY')} />
          <Field label="Google AI Studio key (alias)"
                 hint="Same key as Gemini; either field works."
                 value={keys.GOOGLE_AI_STUDIO_KEY}
                 onChange={update('GOOGLE_AI_STUDIO_KEY')} />
          <Field label="Groq API key (optional)"
                 hint="Used as a faster fallback for some tasks."
                 value={keys.GROQ_API_KEY}
                 onChange={update('GROQ_API_KEY')} />
        </div>

        {error && (
          <div style={{ marginTop: 16, color: 'var(--ame-rose, #ff7a9b)', fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
            <XCircle size={13} /> {error}
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
            {saving ? 'Saving…' : 'Continue'}
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

function Field({ label, hint, value, onChange }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <span style={{ fontSize: 11, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--ame-text-secondary, #888)' }}>{label}</span>
      <input
        type="password"
        value={value}
        onChange={onChange}
        placeholder="paste key…"
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
