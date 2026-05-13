import React, { useCallback, useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { AlertTriangle, Camera, Info, Sparkles, X } from 'lucide-react'

const TOAST_DURATION_MS = 4500

const TOAST_TYPES = {
  screenshot: { icon: Camera,         accent: 'var(--ame-cyan, #4dd0ff)'  },
  warning:    { icon: AlertTriangle,  accent: 'var(--ame-amber, #ffb454)' },
  proactive:  { icon: Sparkles,       accent: 'var(--ame-accent, #00d084)' },
  info:       { icon: Info,           accent: 'var(--ame-accent-light, #1ee594)' },
  clap:       { icon: Sparkles,       accent: 'var(--ame-rose, #ff7a9b)' },
}

let _id = 0

export function useToasts() {
  const [toasts, setToasts] = useState([])

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const addToast = useCallback((type, message) => {
    const id = `t${++_id}`
    setToasts((prev) => [...prev.slice(-4), { id, type, message, ts: Date.now() }])
    setTimeout(() => removeToast(id), TOAST_DURATION_MS)
    return id
  }, [removeToast])

  return { toasts, addToast, removeToast }
}

export default function Toasts({ toasts, removeToast }) {
  return (
    <div
      style={{
        position: 'fixed',
        top: 16,
        right: 16,
        zIndex: 1000,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        pointerEvents: 'none',
      }}
    >
      <AnimatePresence>
        {toasts.map((t) => {
          const spec = TOAST_TYPES[t.type] || TOAST_TYPES.info
          const Icon = spec.icon
          return (
            <motion.div
              key={t.id}
              initial={{ opacity: 0, x: 24 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 24 }}
              transition={{ duration: 0.22 }}
              style={{
                pointerEvents: 'auto',
                minWidth: 240,
                maxWidth: 360,
                padding: '10px 12px',
                borderRadius: 8,
                background: 'var(--ame-bg-card, rgba(20,20,22,0.92))',
                border: `1px solid ${spec.accent}55`,
                boxShadow: `0 4px 24px ${spec.accent}22`,
                color: 'var(--ame-text, #e5e5e5)',
                display: 'flex',
                gap: 10,
                alignItems: 'flex-start',
                fontSize: 12,
              }}
            >
              <Icon size={14} style={{ color: spec.accent, marginTop: 2, flexShrink: 0 }} />
              <div style={{ flex: 1, lineHeight: 1.4 }}>{t.message}</div>
              <button
                onClick={() => removeToast(t.id)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--ame-text-secondary, #888)',
                  cursor: 'pointer',
                  padding: 0,
                  display: 'flex',
                }}
                aria-label="Dismiss"
              >
                <X size={12} />
              </button>
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}
