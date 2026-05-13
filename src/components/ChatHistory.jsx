import React, { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, MessageSquare } from 'lucide-react'

/**
 * ChatHistory drawer — shows past conversation sessions.
 *
 * Contract (best-effort, may need backend adjustment):
 *   socket.emit('chat_history_request')
 *   socket.on('chat_history', ({ sessions: [{ id, started_at, messages: [...] }] }))
 *
 * Props:
 *   - open: boolean
 *   - onClose: () => void
 *   - socket: socket.io client (may be null on first render)
 */
export default function ChatHistory({ open, onClose, socket }) {
  const [sessions, setSessions] = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading]   = useState(false)

  useEffect(() => {
    if (!open || !socket) return
    setLoading(true)
    const handler = (data) => {
      setLoading(false)
      if (data && Array.isArray(data.sessions)) setSessions(data.sessions)
      else if (Array.isArray(data)) setSessions(data)
    }
    socket.on('chat_history', handler)
    socket.emit('chat_history_request')
    return () => { socket.off('chat_history', handler) }
  }, [open, socket])

  return (
    <AnimatePresence>
      {open && (
        <motion.aside
          initial={{ x: '100%' }}
          animate={{ x: 0 }}
          exit={{ x: '100%' }}
          transition={{ type: 'spring', stiffness: 320, damping: 32 }}
          style={{
            position: 'fixed',
            top: 0, right: 0, bottom: 0,
            width: 360,
            zIndex: 80,
            background: 'var(--ame-bg-card, #111)',
            borderLeft: '1px solid var(--ame-border, #222)',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <header style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '14px 16px',
            borderBottom: '1px solid var(--ame-border, #222)',
            color: 'var(--ame-text, #e5e5e5)',
          }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, letterSpacing: '0.18em', textTransform: 'uppercase' }}>
              <MessageSquare size={13} /> Chat history
            </span>
            <button onClick={onClose} className="btn-icon" aria-label="Close">
              <X size={14} />
            </button>
          </header>

          <div style={{ flex: 1, overflowY: 'auto', padding: 12, fontSize: 12, color: 'var(--ame-text, #e5e5e5)' }}>
            {loading && <div style={{ color: 'var(--ame-text-secondary, #888)' }}>Loading…</div>}
            {!loading && sessions.length === 0 && (
              <div style={{ color: 'var(--ame-text-secondary, #888)' }}>No past sessions yet.</div>
            )}
            {sessions.map((s) => (
              <div
                key={s.id || s.started_at}
                onClick={() => setSelected(selected === s.id ? null : s.id)}
                style={{
                  padding: '8px 10px',
                  marginBottom: 6,
                  borderRadius: 6,
                  background: 'var(--ame-bg, #0a0a0c)',
                  border: '1px solid var(--ame-border, #222)',
                  cursor: 'pointer',
                }}
              >
                <div style={{ fontSize: 11, color: 'var(--ame-text-secondary, #888)' }}>
                  {s.started_at ? new Date(s.started_at).toLocaleString() : s.id}
                </div>
                <div style={{ marginTop: 4 }}>
                  {(s.messages?.[0]?.text || s.preview || '(empty)').slice(0, 80)}
                </div>
                {selected === s.id && Array.isArray(s.messages) && (
                  <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid var(--ame-border, #222)', display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {s.messages.map((m, i) => (
                      <div key={m.id || i} style={{ opacity: m.role === 'ame' ? 0.9 : 1 }}>
                        <span style={{ color: m.role === 'ame' ? 'var(--ame-accent, #00d084)' : 'var(--ame-text-secondary, #888)', marginRight: 6 }}>
                          {m.role === 'ame' ? 'AMÉ' : 'YOU'}
                        </span>
                        {m.text}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  )
}
