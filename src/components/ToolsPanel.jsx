import React, { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Zap, Activity } from 'lucide-react'

/**
 * ToolsPanel — overlay showing active agent tasks and tool capabilities.
 *
 * Contract:
 *   socket.on('agent_log', { entries: [{ ts, level, message, tool }] })
 *   socket.on('tools_list', { tools: [{ name, description, enabled }] })
 */
export default function ToolsPanel({ open, onClose, socket }) {
  const [log,   setLog]   = useState([])
  const [tools, setTools] = useState([])

  useEffect(() => {
    if (!open || !socket) return
    const logHandler = (data) => {
      if (data && Array.isArray(data.entries)) setLog(data.entries.slice(-50))
      else if (Array.isArray(data)) setLog(data.slice(-50))
    }
    const toolsHandler = (data) => {
      if (data && Array.isArray(data.tools)) setTools(data.tools)
      else if (Array.isArray(data)) setTools(data)
    }
    socket.on('agent_log', logHandler)
    socket.on('tools_list', toolsHandler)
    socket.emit('tools_request')
    return () => {
      socket.off('agent_log', logHandler)
      socket.off('tools_list', toolsHandler)
    }
  }, [open, socket])

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 20 }}
          transition={{ duration: 0.2 }}
          style={{
            position: 'fixed',
            top: '50%', left: '50%',
            transform: 'translate(-50%, -50%)',
            width: 'min(560px, 92vw)',
            maxHeight: '78vh',
            zIndex: 95,
            background: 'var(--ame-bg-card, #111)',
            border: '1px solid var(--ame-border, #222)',
            borderRadius: 10,
            display: 'flex', flexDirection: 'column',
            color: 'var(--ame-text, #e5e5e5)',
          }}
        >
          <header style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '14px 16px',
            borderBottom: '1px solid var(--ame-border, #222)',
          }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, letterSpacing: '0.18em', textTransform: 'uppercase' }}>
              <Zap size={13} /> Tools &amp; agent log
            </span>
            <button onClick={onClose} className="btn-icon" aria-label="Close">
              <X size={14} />
            </button>
          </header>

          <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
            <section style={{ flex: 1, padding: 14, overflowY: 'auto', borderRight: '1px solid var(--ame-border, #222)' }}>
              <div style={{ fontSize: 10, letterSpacing: '0.18em', color: 'var(--ame-text-secondary, #888)', marginBottom: 8 }}>
                CAPABILITIES
              </div>
              {tools.length === 0 && (
                <div style={{ fontSize: 12, color: 'var(--ame-text-secondary, #888)' }}>No tool list received yet.</div>
              )}
              {tools.map((t) => (
                <div key={t.name} style={{ padding: '6px 0', borderBottom: '1px solid var(--ame-border, #222)' }}>
                  <div style={{ fontSize: 12 }}>{t.name}</div>
                  {t.description && (
                    <div style={{ fontSize: 11, color: 'var(--ame-text-secondary, #888)', marginTop: 2 }}>{t.description}</div>
                  )}
                </div>
              ))}
            </section>

            <section style={{ flex: 1.4, padding: 14, overflowY: 'auto' }}>
              <div style={{ fontSize: 10, letterSpacing: '0.18em', color: 'var(--ame-text-secondary, #888)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                <Activity size={11} /> AGENT LOG
              </div>
              {log.length === 0 && (
                <div style={{ fontSize: 12, color: 'var(--ame-text-secondary, #888)' }}>No activity.</div>
              )}
              {log.slice().reverse().map((e, i) => (
                <div key={i} style={{ padding: '4px 0', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }}>
                  <span style={{ color: 'var(--ame-text-secondary, #888)' }}>
                    {e.ts ? new Date(e.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }) : ''}
                  </span>
                  {e.tool && <span style={{ marginLeft: 6, color: 'var(--ame-accent, #00d084)' }}>[{e.tool}]</span>}
                  <span style={{ marginLeft: 6 }}>{e.message}</span>
                </div>
              ))}
            </section>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
