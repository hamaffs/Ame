import React, { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Calendar, Plus, Trash2 } from 'lucide-react'

/**
 * SchedulesPanel — shows scheduled tasks / reminders.
 *
 * Contract:
 *   socket.on('schedules_update', { schedules: [{id, when, text, recurring}] })
 *   socket.emit('schedule_add', { when, text, recurring })
 *   socket.emit('schedule_remove', { id })
 */
export default function SchedulesPanel({ open, onClose, socket }) {
  const [schedules, setSchedules] = useState([])
  const [draftText, setDraftText] = useState('')
  const [draftWhen, setDraftWhen] = useState('')

  useEffect(() => {
    if (!open || !socket) return
    const handler = (data) => {
      if (data && Array.isArray(data.schedules)) setSchedules(data.schedules)
      else if (Array.isArray(data)) setSchedules(data)
    }
    socket.on('schedules_update', handler)
    socket.emit('schedules_request')
    return () => { socket.off('schedules_update', handler) }
  }, [open, socket])

  const add = () => {
    if (!draftText.trim() || !socket) return
    socket.emit('schedule_add', { when: draftWhen, text: draftText, recurring: false })
    setDraftText(''); setDraftWhen('')
  }

  const remove = (id) => {
    if (!socket) return
    socket.emit('schedule_remove', { id })
    setSchedules((prev) => prev.filter((s) => s.id !== id))
  }

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
            display: 'flex', flexDirection: 'column',
          }}
        >
          <header style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '14px 16px',
            borderBottom: '1px solid var(--ame-border, #222)',
            color: 'var(--ame-text, #e5e5e5)',
          }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, letterSpacing: '0.18em', textTransform: 'uppercase' }}>
              <Calendar size={13} /> Schedules
            </span>
            <button onClick={onClose} className="btn-icon" aria-label="Close">
              <X size={14} />
            </button>
          </header>

          <div style={{ padding: 14, borderBottom: '1px solid var(--ame-border, #222)', display: 'flex', flexDirection: 'column', gap: 6 }}>
            <input
              value={draftText}
              onChange={(e) => setDraftText(e.target.value)}
              placeholder="Remind me to…"
              style={inputStyle}
            />
            <div style={{ display: 'flex', gap: 6 }}>
              <input
                value={draftWhen}
                onChange={(e) => setDraftWhen(e.target.value)}
                placeholder="when (e.g. tomorrow 9am)"
                style={{ ...inputStyle, flex: 1 }}
              />
              <button onClick={add} className="btn-icon" aria-label="Add">
                <Plus size={14} />
              </button>
            </div>
          </div>

          <div style={{ flex: 1, overflowY: 'auto', padding: 12, fontSize: 12, color: 'var(--ame-text, #e5e5e5)' }}>
            {schedules.length === 0 && (
              <div style={{ color: 'var(--ame-text-secondary, #888)' }}>No scheduled tasks.</div>
            )}
            {schedules.map((s) => (
              <div key={s.id} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '8px 10px',
                marginBottom: 6,
                borderRadius: 6,
                background: 'var(--ame-bg, #0a0a0c)',
                border: '1px solid var(--ame-border, #222)',
              }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 11, color: 'var(--ame-text-secondary, #888)' }}>
                    {s.when ? (typeof s.when === 'string' ? s.when : new Date(s.when).toLocaleString()) : '—'}
                    {s.recurring && <span style={{ marginLeft: 6, color: 'var(--ame-accent, #00d084)' }}>↻</span>}
                  </div>
                  <div style={{ marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.text}</div>
                </div>
                <button onClick={() => remove(s.id)} className="btn-icon" aria-label="Remove">
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  )
}

const inputStyle = {
  background: 'var(--ame-bg, #0a0a0c)',
  border: '1px solid var(--ame-border, #222)',
  color: 'var(--ame-text, #e5e5e5)',
  padding: '6px 8px',
  fontSize: 12,
  borderRadius: 4,
  outline: 'none',
}
