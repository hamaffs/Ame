import React, { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Cpu, Activity } from 'lucide-react'

/**
 * SystemMonitor drawer — live CPU / RAM / disk / network stats.
 *
 * Contract:
 *   socket.on('system_stats', { cpu_pct, mem_pct, disk_pct, net_kbps, processes })
 * Backend is expected to emit this periodically (e.g. every 2 s).
 */
export default function SystemMonitor({ open, onClose, socket }) {
  const [stats, setStats] = useState(null)

  useEffect(() => {
    if (!open || !socket) return
    const handler = (data) => setStats(data || null)
    socket.on('system_stats', handler)
    socket.emit('system_stats_subscribe')
    return () => {
      socket.off('system_stats', handler)
      socket.emit('system_stats_unsubscribe')
    }
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
            width: 320,
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
              <Cpu size={13} /> System
            </span>
            <button onClick={onClose} className="btn-icon" aria-label="Close">
              <X size={14} />
            </button>
          </header>

          <div style={{ padding: 16, fontSize: 12, color: 'var(--ame-text, #e5e5e5)', display: 'flex', flexDirection: 'column', gap: 14 }}>
            {!stats && (
              <div style={{ color: 'var(--ame-text-secondary, #888)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <Activity size={12} /> Waiting for backend…
              </div>
            )}
            {stats && (
              <>
                <Bar label="CPU"  pct={stats.cpu_pct ?? 0} />
                <Bar label="RAM"  pct={stats.mem_pct ?? 0} />
                <Bar label="DISK" pct={stats.disk_pct ?? 0} />
                <Row  label="NET" value={stats.net_kbps != null ? `${stats.net_kbps.toFixed(1)} kbps` : '—'} />
                {Array.isArray(stats.processes) && stats.processes.length > 0 && (
                  <div>
                    <div style={{ fontSize: 10, letterSpacing: '0.18em', color: 'var(--ame-text-secondary, #888)', marginBottom: 6 }}>
                      TOP PROCESSES
                    </div>
                    {stats.processes.slice(0, 8).map((p, i) => (
                      <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', fontSize: 11 }}>
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.name}</span>
                        <span style={{ color: 'var(--ame-text-secondary, #888)' }}>{p.cpu_pct?.toFixed?.(1) ?? p.cpu_pct}%</span>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  )
}

function Bar({ label, pct }) {
  const clamped = Math.max(0, Math.min(100, pct))
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
        <span style={{ letterSpacing: '0.18em', color: 'var(--ame-text-secondary, #888)' }}>{label}</span>
        <span>{clamped.toFixed(0)}%</span>
      </div>
      <div style={{ height: 4, background: 'var(--ame-bg, #0a0a0c)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{
          width: `${clamped}%`,
          height: '100%',
          background: clamped > 85 ? 'var(--ame-rose, #ff7a9b)' : 'var(--ame-accent, #00d084)',
          transition: 'width 0.3s ease',
        }} />
      </div>
    </div>
  )
}

function Row({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
      <span style={{ letterSpacing: '0.18em', color: 'var(--ame-text-secondary, #888)' }}>{label}</span>
      <span>{value}</span>
    </div>
  )
}
