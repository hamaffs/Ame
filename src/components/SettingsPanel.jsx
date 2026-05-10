import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ArrowLeft, Volume2, Globe, Sparkles, Eye, Lock, Zap, Bot,
  Cpu, Brain, Newspaper, ExternalLink, MessageCircle
} from 'lucide-react'

const GEMINI_VOICES = [
  'Achernar', 'Aoede', 'Autonoe', 'Callirrhoe', 'Despina', 'Erinome', 'Gacrux',
  'Kore', 'Laomedeia', 'Leda', 'Pulcherrima', 'Sulafat', 'Vindemiatrix', 'Zephyr',
]
const VOICE_INFO = {
  Achernar:     { tone: 'Soft',      desc: 'A calm whisper that puts you at ease' },
  Aoede:        { tone: 'Melodic',   desc: 'Like a late-night radio host who actually cares' },
  Autonoe:      { tone: 'Bright',    desc: 'Crisp energy that keeps you engaged' },
  Callirrhoe:   { tone: 'Easy-going',desc: 'The friend who never rushes you' },
  Despina:      { tone: 'Smooth',    desc: 'Effortlessly composed at all times' },
  Erinome:      { tone: 'Clear',     desc: 'Every word lands exactly where it should' },
  Gacrux:       { tone: 'Mature',    desc: 'Steady wisdom with a warm depth' },
  Kore:         { tone: 'Confident', desc: 'Knows what she wants to say and says it' },
  Laomedeia:    { tone: 'Upbeat',    desc: 'Brings sunshine to every conversation' },
  Leda:         { tone: 'Youthful',  desc: 'The voice of someone who listens first' },
  Pulcherrima:  { tone: 'Energetic', desc: 'Bold presence that commands attention' },
  Sulafat:      { tone: 'Warm',      desc: 'Like a cozy conversation by the fire' },
  Vindemiatrix: { tone: 'Gentle',    desc: 'A calming presence in any moment' },
  Zephyr:       { tone: 'Airy',      desc: 'Bright confidence with a light touch' },
}
const RESPONSE_STYLES = ['Concise', 'Balanced', 'Detailed']
const STYLE_INFO = {
  Concise:  'Short, direct answers. No fluff.',
  Balanced: 'A natural mix of detail and brevity.',
  Detailed: 'Thorough explanations with context.',
}
const LANGUAGES = [
  { code: 'en', flag: '🇬🇧', label: 'English',   native: 'English'  },
  { code: 'fr', flag: '🇫🇷', label: 'French',    native: 'Français' },
  { code: 'ar', flag: '🇸🇦', label: 'Arabic',    native: 'العربية'  },
  { code: 'es', flag: '🇪🇸', label: 'Spanish',   native: 'Español'  },
  { code: 'de', flag: '🇩🇪', label: 'German',    native: 'Deutsch'  },
  { code: 'ja', flag: '🇯🇵', label: 'Japanese',  native: '日本語'    },
]

function UptimeCounter({ start }) {
  const [, tick] = useState(0)
  useEffect(() => { const iv = setInterval(() => tick(n => n + 1), 1000); return () => clearInterval(iv) }, [])
  const s = Math.floor((Date.now() - start) / 1000), m = Math.floor(s / 60), h = Math.floor(m / 60)
  return <span>{h > 0 ? `${h}h ${m % 60}m` : m > 0 ? `${m}m ${s % 60}s` : `${s}s`}</span>
}

export default function SettingsPanel({
  settingsTab, setSettingsTab, setSettingsOpen,
  t,
  selectedVoice, handleVoiceChange,
  responseStyle, setResponseStyle, socketRef,
  language, handleLanguageChange,
  accentColor, handleAccentChange, bgShade, handleShadeChange,
  chatVisible, toggleChat,
  screenWatcherOn, setScreenWatcherOn,
  codeAwarenessOn, setCodeAwarenessOn,
  newsEnabled, setNewsEnabled,
  memoryEnabled, setMemoryEnabled,
  setMessages, setMsgCount,
  permissionLevel, setPermissionLevel,
  clapEnabled, setClapEnabled, clapAction, setClapAction,
  activeProvider, sessionStart,
}) {
  const [isAdmin, setIsAdmin] = useState(false)

  useEffect(() => {
    if (settingsTab === 'security') {
      window.electronAPI?.checkAdmin?.().then?.(res => setIsAdmin(res))
    }
  }, [settingsTab])

  return (
    <motion.div
      key="settings-page"
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.97 }}
      transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
      style={{
        position: 'fixed', inset: 0, zIndex: 100,
        background: 'var(--ame-bg)',
        display: 'flex', flexDirection: 'column',
      }}
    >
      {/* ── Settings header ── */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '20px 24px',
        borderBottom: '1px solid var(--ame-border-subtle)',
        flexShrink: 0,
        WebkitAppRegion: 'drag',
      }}>
        <button
          onClick={() => setSettingsOpen(false)}
          className="titlebar-nodrag"
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'var(--ame-text-secondary)', display: 'flex', alignItems: 'center', gap: 8,
            padding: '4px 8px', borderRadius: 8,
            transition: 'color 0.15s',
          }}
          onMouseEnter={e => e.currentTarget.style.color = 'var(--ame-accent-light)'}
          onMouseLeave={e => e.currentTarget.style.color = 'var(--ame-text-secondary)'}
        >
          <ArrowLeft size={16} />
          <span style={{ fontFamily: 'var(--ame-mono)', fontSize: 12, letterSpacing: '0.05em' }}>{t.back || 'Back'}</span>
        </button>
        <div style={{ flex: 1 }} />
        <span style={{ fontFamily: 'var(--ame-sans)', fontSize: 14, letterSpacing: '0.05em', color: 'var(--ame-text)', fontWeight: 500 }}>{t.settings || 'Settings'}</span>
        <div style={{ flex: 1 }} />
        <div style={{ width: 70 }} /> {/* balance the back button */}
      </div>

      {/* ── Two-column layout ── */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>

        {/* ── Left nav ── */}
        <nav style={{
          width: 220, flexShrink: 0,
          borderRight: '1px solid var(--ame-border-subtle)',
          padding: '24px 0',
          display: 'flex', flexDirection: 'column', gap: 2,
        }}>
          {[
            { id: 'voice',      icon: <Volume2 size={15} />,   label: t.settingsVoice || 'Voice' },
            { id: 'language',    icon: <Globe size={15} />,     label: t.settingsLanguage || 'Language' },
            { id: 'appearance',  icon: <Sparkles size={15} />,  label: t.settingsAppearance || 'Appearance' },
            { id: 'awareness',   icon: <Eye size={15} />,       label: t.settingsAwareness || 'Awareness' },
            { id: 'security',    icon: <Lock size={15} />,      label: 'Security' },
            { id: 'dark',        icon: <Zap size={15} />,       label: t.settingsGoingDark || 'Going Dark' },
            { id: 'about',       icon: <Bot size={15} />,       label: t.settingsAbout || 'About AMÉ' },
          ].map(tab => {
            const active = settingsTab === tab.id
            return (
              <button key={tab.id}
                onClick={() => setSettingsTab(tab.id)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 12,
                  padding: '10px 16px', margin: '0 12px',
                  borderRadius: 8, cursor: 'pointer',
                  border: 'none',
                  background: active ? 'var(--ame-bg-elevated)' : 'transparent',
                  color: active ? 'var(--ame-text)' : 'var(--ame-text-secondary)',
                  fontFamily: 'var(--ame-sans)', fontSize: 13, fontWeight: active ? 500 : 400,
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={e => { if (!active) e.currentTarget.style.background = 'rgba(255,255,255,0.03)' }}
                onMouseLeave={e => { if (!active) e.currentTarget.style.background = 'transparent' }}
              >
                {tab.icon}
                {tab.label}
              </button>
            )
          })}
        </nav>

        {/* ── Right content ── */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '32px 40px', maxWidth: 600 }}>

          {/* ═══ VOICE ═══ */}
          {settingsTab === 'voice' && (
            <motion.div key="voice" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
              <h2 style={{ fontFamily: 'var(--ame-sans)', fontSize: 20, fontWeight: 500, color: 'var(--ame-text)', marginBottom: 6 }}>{t.settingsVoice || 'Voice'}</h2>
              <p style={{ fontFamily: 'var(--ame-sans)', fontSize: 13, color: 'var(--ame-text-secondary)', marginBottom: 28, lineHeight: 1.6 }}>{t.voiceDesc || 'Choose how AMÉ sounds and responds.'}</p>

              <div style={{ fontSize: 11, fontFamily: 'var(--ame-mono)', color: 'var(--ame-text-secondary)', marginBottom: 12, letterSpacing: '0.1em', textTransform: 'uppercase' }}>{t.voiceModel || 'Voice model'}</div>

              {/* Selected voice preview */}
              {VOICE_INFO[selectedVoice] && (
                <div style={{
                  padding: '16px', borderRadius: 12, marginBottom: 16,
                  border: '1px solid var(--ame-border)',
                  background: 'var(--ame-accent-ghost)',
                  display: 'flex', alignItems: 'center', gap: 14,
                }}>
                  <div style={{
                    width: 32, height: 32, borderRadius: '50%',
                    background: 'var(--ame-accent)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                  }}>
                    <Volume2 size={14} style={{ color: '#000' }} />
                  </div>
                  <div>
                    <div style={{ fontFamily: 'var(--ame-mono)', fontSize: 14, fontWeight: 600, color: 'var(--ame-accent-light)', marginBottom: 2 }}>{selectedVoice}</div>
                    <div style={{ fontFamily: 'var(--ame-mono)', fontSize: 11, color: 'var(--ame-text-ghost)', lineHeight: 1.4 }}>{VOICE_INFO[selectedVoice]?.desc}</div>
                  </div>
                </div>
              )}

              {/* Voice grid */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8, marginBottom: 32 }}>
                {GEMINI_VOICES.map(v => {
                  const active = selectedVoice === v
                  const info = VOICE_INFO[v] || {}
                  return (
                    <button key={v}
                      onClick={() => handleVoiceChange(v)}
                      style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        padding: '10px 14px', borderRadius: 10, cursor: 'pointer',
                        border: `1px solid ${active ? 'var(--ame-accent)' : 'var(--ame-border-subtle)'}`,
                        background: active ? 'var(--ame-accent-ghost)' : 'var(--ame-bg-card)',
                        transition: 'all 0.15s ease',
                        textAlign: 'left',
                      }}
                      onMouseEnter={e => { if (!active) { e.currentTarget.style.borderColor = 'var(--ame-border)'; e.currentTarget.style.background = 'var(--ame-bg-hover)' } }}
                      onMouseLeave={e => { if (!active) { e.currentTarget.style.borderColor = active ? 'var(--ame-accent)' : 'var(--ame-border-subtle)'; e.currentTarget.style.background = active ? 'var(--ame-accent-ghost)' : 'var(--ame-bg-card)' } }}
                    >
                      <span style={{ fontFamily: 'var(--ame-mono)', fontSize: 13, fontWeight: active ? 600 : 400, color: active ? 'var(--ame-accent-light)' : 'var(--ame-text)' }}>{v}</span>
                      <span style={{ fontFamily: 'var(--ame-mono)', fontSize: 10, color: 'var(--ame-text-ghost)', opacity: 0.7 }}>{info.tone}</span>
                    </button>
                  )
                })}
              </div>
              <p style={{ fontFamily: 'var(--ame-mono)', fontSize: 10, color: 'var(--ame-text-ghost)', marginBottom: 28 }}>{t.takesEffect}</p>

              <div style={{ fontSize: 11, fontFamily: 'var(--ame-mono)', color: 'var(--ame-text-secondary)', marginBottom: 12, letterSpacing: '0.1em', textTransform: 'uppercase' }}>{t.responseStyle || 'Response style'}</div>
              <div style={{ display: 'flex', gap: 10 }}>
                {RESPONSE_STYLES.map((s, i) => {
                  const active = responseStyle === i
                  return (
                    <button key={s}
                      onClick={() => { const safeStyle = Math.max(0, Math.min(2, i)); setResponseStyle(safeStyle); socketRef.current?.emit('set_style', { style: safeStyle }) }}
                      style={{
                        flex: 1, padding: '16px 14px', borderRadius: 12, cursor: 'pointer',
                        border: `1px solid ${active ? 'var(--ame-accent)' : 'var(--ame-border-subtle)'}`,
                        background: active ? 'var(--ame-accent-ghost)' : 'var(--ame-bg-card)',
                        textAlign: 'center', transition: 'all 0.15s ease',
                      }}
                      onMouseEnter={e => { if (!active) { e.currentTarget.style.borderColor = 'var(--ame-border)'; e.currentTarget.style.background = 'var(--ame-bg-hover)' } }}
                      onMouseLeave={e => { if (!active) { e.currentTarget.style.borderColor = 'var(--ame-border-subtle)'; e.currentTarget.style.background = 'var(--ame-bg-card)' } }}
                    >
                      <div style={{ fontFamily: 'var(--ame-mono)', fontSize: 13, fontWeight: 600, color: active ? 'var(--ame-accent-light)' : 'var(--ame-text)', marginBottom: 6 }}>{s}</div>
                      <div style={{ fontFamily: 'var(--ame-mono)', fontSize: 10, color: 'var(--ame-text-ghost)', lineHeight: 1.4 }}>{STYLE_INFO[s]}</div>
                    </button>
                  )
                })}
              </div>

              {/* Admin Access Toggle */}
              <div style={{
                padding: '18px 20px', borderRadius: 12,
                border: '1px solid var(--ame-border-subtle)',
                background: 'var(--ame-bg-card)',
                marginTop: 24,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <Lock size={16} style={{ color: isAdmin ? 'var(--ame-green)' : 'var(--ame-accent-light)' }} />
                    <span style={{ fontFamily: 'var(--ame-mono)', fontSize: 13, fontWeight: 600, color: 'var(--ame-text)' }}>Admin Access (UAC)</span>
                  </div>
                  <button
                    onClick={() => {
                      if (!isAdmin) window.electronAPI?.relaunchAdmin?.()
                    }}
                    disabled={isAdmin}
                    style={{
                      padding: '6px 14px', borderRadius: 8,
                      border: `1px solid ${isAdmin ? 'var(--ame-green)' : 'var(--ame-accent)'}`,
                      background: isAdmin ? 'color-mix(in srgb, var(--ame-green) 15%, transparent)' : 'var(--ame-accent-ghost)',
                      color: isAdmin ? 'var(--ame-green)' : 'var(--ame-accent-light)',
                      cursor: isAdmin ? 'default' : 'pointer',
                      fontFamily: 'var(--ame-mono)', fontSize: 12, fontWeight: 600,
                      transition: 'all 0.2s',
                      opacity: isAdmin ? 0.7 : 1
                    }}
                  >
                    {isAdmin ? 'Granted' : 'Relaunch as Admin'}
                  </button>
                </div>
                <p style={{ fontFamily: 'var(--ame-mono)', fontSize: 11, color: 'var(--ame-text-ghost)', lineHeight: 1.6, margin: '8px 0 0' }}>
                  Grants AMÉ deep system access for cybersecurity scans and advanced file operations. Requires an application restart.
                </p>
              </div>
            </motion.div>
          )}

          {/* ═══ LANGUAGE ═══ */}
          {settingsTab === 'language' && (
            <motion.div key="language" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
              <h2 style={{ fontFamily: 'var(--ame-sans)', fontSize: 20, fontWeight: 500, color: 'var(--ame-text)', marginBottom: 6 }}>{t.settingsLanguage || 'Language'}</h2>
              <p style={{ fontFamily: 'var(--ame-sans)', fontSize: 13, color: 'var(--ame-text-secondary)', marginBottom: 28, lineHeight: 1.6 }}>{t.languageDesc || 'AMÉ will respond in the language you choose.'}</p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {LANGUAGES.map(lang => {
                  const active = language === lang.code
                  return (
                    <button key={lang.code}
                      onClick={() => handleLanguageChange(lang.code)}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 16,
                        padding: '16px 20px', borderRadius: 12, cursor: 'pointer',
                        border: `1px solid ${active ? 'var(--ame-accent)' : 'var(--ame-border-subtle)'}`,
                        background: active ? 'var(--ame-accent-ghost)' : 'var(--ame-bg-card)',
                        transition: 'all 0.15s ease', textAlign: 'left',
                      }}
                      onMouseEnter={e => { if (!active) { e.currentTarget.style.borderColor = 'var(--ame-border)'; e.currentTarget.style.background = 'var(--ame-bg-hover)' } }}
                      onMouseLeave={e => { if (!active) { e.currentTarget.style.borderColor = 'var(--ame-border-subtle)'; e.currentTarget.style.background = 'var(--ame-bg-card)' } }}
                    >
                      <span style={{ fontSize: 28 }}>{lang.flag}</span>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontFamily: 'var(--ame-mono)', fontSize: 14, fontWeight: 600, color: active ? 'var(--ame-accent-light)' : 'var(--ame-text)' }}>{lang.label}</div>
                        <div style={{ fontFamily: 'var(--ame-mono)', fontSize: 12, color: 'var(--ame-text-ghost)', marginTop: 2 }}>{lang.native}</div>
                      </div>
                      {active && <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--ame-accent)', boxShadow: '0 0 8px var(--ame-accent)', flexShrink: 0 }} />}
                    </button>
                  )
                })}
              </div>
            </motion.div>
          )}

          {/* ═══ APPEARANCE ═══ */}
          {settingsTab === 'appearance' && (
            <motion.div key="appearance" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
              <h2 style={{ fontFamily: 'var(--ame-sans)', fontSize: 20, fontWeight: 500, color: 'var(--ame-text)', marginBottom: 6 }}>{t.settingsAppearance || 'Appearance'}</h2>
              <p style={{ fontFamily: 'var(--ame-sans)', fontSize: 13, color: 'var(--ame-text-secondary)', marginBottom: 28, lineHeight: 1.6 }}>{t.appearanceDesc || 'Customize how AMÉ looks.'}</p>

              <div style={{ fontSize: 11, fontFamily: 'var(--ame-mono)', color: 'var(--ame-text-secondary)', marginBottom: 14, letterSpacing: '0.1em', textTransform: 'uppercase' }}>{t.themeColor || 'Theme color'}</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 14 }}>
                {[
                  { color: '#00d084', label: 'Green'  },
                  { color: '#6c63ff', label: 'Purple' },
                  { color: '#0ea5e9', label: 'Blue'   },
                  { color: '#22d3ee', label: 'Cyan'   },
                  { color: '#ef4444', label: 'Red'    },
                  { color: '#f97316', label: 'Orange' },
                  { color: '#ec4899', label: 'Pink'   },
                  { color: '#e2e8f0', label: 'White'  },
                ].map(({ color, label }) => (
                  <button
                    key={color} title={label}
                    onClick={() => handleAccentChange(color)}
                    style={{
                      width: 32, height: 32, borderRadius: '50%',
                      background: color,
                      border: accentColor === color ? '2px solid #ffffff' : '2px solid transparent',
                      outline: accentColor === color ? `2px solid ${color}` : 'none',
                      outlineOffset: 2,
                      cursor: 'pointer', padding: 0,
                      transition: 'all 0.15s ease',
                      boxShadow: accentColor === color ? `0 0 12px ${color}` : 'none',
                    }}
                  />
                ))}
              </div>
              <input
                type="color" value={accentColor}
                onChange={e => handleAccentChange(e.target.value)}
                title="Custom color"
                style={{
                  width: '100%', height: 36, borderRadius: 10,
                  border: '1px solid var(--ame-border-subtle)',
                  background: 'rgba(255,255,255,0.04)',
                  cursor: 'pointer', padding: '2px 4px',
                  marginBottom: 28,
                }}
              />

              <div style={{ fontSize: 11, fontFamily: 'var(--ame-mono)', color: 'var(--ame-text-secondary)', marginBottom: 14, letterSpacing: '0.1em', textTransform: 'uppercase' }}>{t.bgShade || 'Background shade'}</div>
              <div style={{ display: 'flex', gap: 10, marginBottom: 28 }}>
                {[
                  { id: 'black', label: 'Black', preview: '#0a0a0a' },
                  { id: 'grey',  label: 'Grey',  preview: '#3a3a3a' },
                  { id: 'white', label: 'White', preview: '#e8e8e8' },
                ].map(({ id, label, preview }) => (
                  <button key={id}
                    onClick={() => handleShadeChange(id)}
                    style={{
                      flex: 1, padding: '14px 12px', borderRadius: 12, cursor: 'pointer',
                      border: `1px solid ${bgShade === id ? 'var(--ame-accent)' : 'var(--ame-border-subtle)'}`,
                      background: bgShade === id ? 'var(--ame-accent-ghost)' : 'var(--ame-bg-card)',
                      textAlign: 'center', transition: 'all 0.15s ease',
                    }}
                  >
                    <div style={{
                      width: 28, height: 28, borderRadius: '50%', margin: '0 auto 8px',
                      background: preview,
                      border: '2px solid rgba(128,128,128,0.3)',
                    }} />
                    <div style={{ fontFamily: 'var(--ame-mono)', fontSize: 12, fontWeight: 600, color: bgShade === id ? 'var(--ame-accent-light)' : 'var(--ame-text)' }}>{label}</div>
                  </button>
                ))}
              </div>

              <div style={{ fontSize: 11, fontFamily: 'var(--ame-mono)', color: 'var(--ame-text-secondary)', marginBottom: 14, letterSpacing: '0.1em', textTransform: 'uppercase' }}>Display mode</div>
              <div style={{ display: 'flex', gap: 10 }}>
                {[
                  { id: 'chat', label: 'Chat mode', desc: 'Full conversation view with messages and input bar', active: chatVisible },
                  { id: 'orb',  label: 'Orb mode',  desc: 'Minimal view — just the orb and your voice', active: !chatVisible },
                ].map(mode => (
                  <button key={mode.id}
                    onClick={toggleChat}
                    style={{
                      flex: 1, padding: '18px 16px', borderRadius: 12, cursor: 'pointer',
                      border: `1px solid ${mode.active ? 'var(--ame-accent)' : 'var(--ame-border-subtle)'}`,
                      background: mode.active ? 'var(--ame-accent-ghost)' : 'var(--ame-bg-card)',
                      textAlign: 'left', transition: 'all 0.15s ease',
                    }}
                  >
                    <div style={{ fontFamily: 'var(--ame-mono)', fontSize: 13, fontWeight: 600, color: mode.active ? 'var(--ame-accent-light)' : 'var(--ame-text)', marginBottom: 6 }}>{mode.label}</div>
                    <div style={{ fontFamily: 'var(--ame-mono)', fontSize: 10, color: 'var(--ame-text-ghost)', lineHeight: 1.5 }}>{mode.desc}</div>
                  </button>
                ))}
              </div>
            </motion.div>
          )}

          {/* ═══ AWARENESS ═══ */}
          {settingsTab === 'awareness' && (
            <motion.div key="awareness" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
              <h2 style={{ fontFamily: 'var(--ame-sans)', fontSize: 20, fontWeight: 500, color: 'var(--ame-text)', marginBottom: 6 }}>{t.settingsAwareness || 'Awareness'}</h2>
              <p style={{ fontFamily: 'var(--ame-sans)', fontSize: 13, color: 'var(--ame-text-secondary)', marginBottom: 28, lineHeight: 1.6 }}>{t.awarenessDesc || 'Control what AMÉ pays attention to.'}</p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {/* Screen watcher */}
                <div style={{
                  padding: '18px 20px', borderRadius: 12,
                  border: '1px solid var(--ame-border-subtle)',
                  background: 'var(--ame-bg-card)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <Eye size={16} style={{ color: 'var(--ame-accent-light)' }} />
                      <span style={{ fontFamily: 'var(--ame-mono)', fontSize: 13, fontWeight: 600, color: 'var(--ame-text)' }}>{t.screenWatcher || 'Screen watcher'}</span>
                    </div>
                    <button
                      onClick={() => {
                        const next = !screenWatcherOn
                        setScreenWatcherOn(next)
                        localStorage.setItem('ame_screen_watcher', String(next))
                        socketRef.current?.emit('set_screen_watcher', { enabled: next })
                      }}
                      style={{
                        width: 42, height: 22, borderRadius: 11, padding: 0,
                        border: `1px solid ${screenWatcherOn ? 'var(--ame-accent)' : 'var(--ame-border-subtle)'}`,
                        background: screenWatcherOn ? 'var(--ame-accent-ghost)' : 'transparent',
                        cursor: 'pointer', position: 'relative', transition: 'all 0.2s',
                      }}
                    >
                      <div style={{
                        width: 16, height: 16, borderRadius: '50%',
                        background: screenWatcherOn ? 'var(--ame-accent)' : 'var(--ame-text-ghost)',
                        position: 'absolute', top: 2,
                        left: screenWatcherOn ? 22 : 2,
                        transition: 'all 0.2s',
                      }} />
                    </button>
                  </div>
                  <p style={{ fontFamily: 'var(--ame-mono)', fontSize: 11, color: 'var(--ame-text-ghost)', lineHeight: 1.6, margin: 0 }}>
                    {t.screenWatcherDesc || 'AMÉ quietly watches your screen and speaks up when something matters.'}
                  </p>
                </div>

                {/* Code awareness */}
                <div style={{
                  padding: '18px 20px', borderRadius: 12,
                  border: '1px solid var(--ame-border-subtle)',
                  background: 'var(--ame-bg-card)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <Cpu size={16} style={{ color: 'var(--ame-accent-light)' }} />
                      <span style={{ fontFamily: 'var(--ame-mono)', fontSize: 13, fontWeight: 600, color: 'var(--ame-text)' }}>Code awareness</span>
                    </div>
                    <button
                      onClick={() => {
                        const next = !codeAwarenessOn
                        setCodeAwarenessOn(next)
                        localStorage.setItem('ame_code_awareness', String(next))
                        socketRef.current?.emit('set_code_awareness', { enabled: next })
                      }}
                      style={{
                        width: 42, height: 22, borderRadius: 11, padding: 0,
                        border: `1px solid ${codeAwarenessOn ? 'var(--ame-accent)' : 'var(--ame-border-subtle)'}`,
                        background: codeAwarenessOn ? 'var(--ame-accent-ghost)' : 'transparent',
                        cursor: 'pointer', position: 'relative', transition: 'all 0.2s',
                      }}
                    >
                      <div style={{
                        width: 16, height: 16, borderRadius: '50%',
                        background: codeAwarenessOn ? 'var(--ame-accent)' : 'var(--ame-text-ghost)',
                        position: 'absolute', top: 2,
                        left: codeAwarenessOn ? 22 : 2,
                        transition: 'all 0.2s',
                      }} />
                    </button>
                  </div>
                  <p style={{ fontFamily: 'var(--ame-mono)', fontSize: 11, color: 'var(--ame-text-ghost)', lineHeight: 1.6, margin: 0 }}>
                    AMÉ scans your local code projects to help you debug and write code.
                  </p>
                </div>

                {/* News awareness */}
                <div style={{
                  padding: '18px 20px', borderRadius: 12,
                  border: '1px solid var(--ame-border-subtle)',
                  background: 'var(--ame-bg-card)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <Newspaper size={16} style={{ color: 'var(--ame-accent-light)' }} />
                      <span style={{ fontFamily: 'var(--ame-mono)', fontSize: 13, fontWeight: 600, color: 'var(--ame-text)' }}>{t.newsAwareness || 'News awareness'}</span>
                    </div>
                    <button
                      onClick={() => {
                        const next = !newsEnabled
                        setNewsEnabled(next)
                        localStorage.setItem('ame_news_enabled', String(next))
                        socketRef.current?.emit('set_news_enabled', { enabled: next })
                      }}
                      style={{
                        width: 42, height: 22, borderRadius: 11, padding: 0,
                        border: `1px solid ${newsEnabled ? 'var(--ame-accent)' : 'var(--ame-border-subtle)'}`,
                        background: newsEnabled ? 'var(--ame-accent-ghost)' : 'transparent',
                        cursor: 'pointer', position: 'relative', transition: 'all 0.2s',
                      }}
                    >
                      <div style={{
                        width: 16, height: 16, borderRadius: '50%',
                        background: newsEnabled ? 'var(--ame-accent)' : 'var(--ame-text-ghost)',
                        position: 'absolute', top: 2,
                        left: newsEnabled ? 22 : 2,
                        transition: 'all 0.2s',
                      }} />
                    </button>
                  </div>
                  <p style={{ fontFamily: 'var(--ame-mono)', fontSize: 11, color: 'var(--ame-text-ghost)', lineHeight: 1.6, margin: 0 }}>
                    {t.newsAwarenessDesc || 'AMÉ checks news about your interests when you open her.'}
                  </p>
                </div>

                {/* Memory */}
                <div style={{
                  padding: '18px 20px', borderRadius: 12,
                  border: '1px solid var(--ame-border-subtle)',
                  background: 'var(--ame-bg-card)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <Brain size={16} style={{ color: 'var(--ame-accent-light)' }} />
                      <span style={{ fontFamily: 'var(--ame-mono)', fontSize: 13, fontWeight: 600, color: 'var(--ame-text)' }}>{t.memory || 'Memory'}</span>
                    </div>
                    <button
                      onClick={() => {
                        const next = !memoryEnabled
                        setMemoryEnabled(next)
                        localStorage.setItem('ame_memory_enabled', String(next))
                        socketRef.current?.emit('set_memory_enabled', { enabled: next })
                      }}
                      style={{
                        width: 42, height: 22, borderRadius: 11, padding: 0,
                        border: `1px solid ${memoryEnabled ? 'var(--ame-accent)' : 'var(--ame-border-subtle)'}`,
                        background: memoryEnabled ? 'var(--ame-accent-ghost)' : 'transparent',
                        cursor: 'pointer', position: 'relative', transition: 'all 0.2s',
                      }}
                    >
                      <div style={{
                        width: 16, height: 16, borderRadius: '50%',
                        background: memoryEnabled ? 'var(--ame-accent)' : 'var(--ame-text-ghost)',
                        position: 'absolute', top: 2,
                        left: memoryEnabled ? 22 : 2,
                        transition: 'all 0.2s',
                      }} />
                    </button>
                  </div>
                  <p style={{ fontFamily: 'var(--ame-mono)', fontSize: 11, color: 'var(--ame-text-ghost)', lineHeight: 1.6, margin: 0 }}>
                    {t.memoryDesc || 'AMÉ remembers things you tell her across conversations.'}
                  </p>
                </div>
              </div>

              {/* Danger zone */}
              <div style={{ marginTop: 36, padding: '18px 20px', borderRadius: 12, border: '1px solid rgba(239, 68, 68, 0.3)', background: 'rgba(239, 68, 68, 0.04)' }}>
                <div style={{ fontSize: 11, fontFamily: 'var(--ame-mono)', color: 'var(--ame-rose)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 12 }}>{t.dangerZone || 'Danger zone'}</div>
                <button
                  onClick={() => {
                    if (window.confirm(t.clearMemoryConfirm || 'Are you sure you want to clear all memory? This cannot be undone.')) {
                      socketRef.current?.emit('clear_memory')
                      setMessages([])
                      setMsgCount(0)
                    }
                  }}
                  style={{
                    padding: '10px 20px', borderRadius: 8, cursor: 'pointer',
                    border: '1px solid var(--ame-rose)',
                    background: 'transparent',
                    color: 'var(--ame-rose)',
                    fontFamily: 'var(--ame-mono)', fontSize: 12,
                    transition: 'all 0.15s',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.background = 'rgba(239, 68, 68, 0.15)' }}
                  onMouseLeave={e => { e.currentTarget.style.background = 'transparent' }}
                >
                  {t.clearMemory || 'Clear all memory'}
                </button>
              </div>
            </motion.div>
          )}

          {/* ═══ SECURITY & PERMISSIONS ═══ */}
          {settingsTab === 'security' && (
            <motion.div key="security" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
              <h2 style={{ fontFamily: 'var(--ame-sans)', fontSize: 20, fontWeight: 500, color: 'var(--ame-text)', marginBottom: 6 }}>Security & Permissions</h2>
              <p style={{ fontFamily: 'var(--ame-sans)', fontSize: 13, color: 'var(--ame-text-secondary)', marginBottom: 28, lineHeight: 1.6 }}>Control what AMÉ is allowed to do on your PC.</p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {[
                  { id: 'low', label: 'Low (Safe Mode)', desc: 'AMÉ can search, play music, and open apps, but cannot write files, run terminal commands, or send emails.', color: 'var(--ame-green)' },
                  { id: 'medium', label: 'Medium (Guardian)', desc: 'AMÉ is proactive but requires your confirmation before doing anything permanent. (Coming soon)', color: 'var(--ame-amber)' },
                  { id: 'high', label: 'High (Autopilot)', desc: 'AMÉ has full autonomous access to write code, send emails, and run terminal commands.', color: 'var(--ame-rose)' }
                ].map(lvl => {
                  const active = permissionLevel === lvl.id
                  return (
                    <button key={lvl.id}
                      onClick={() => {
                        setPermissionLevel(lvl.id)
                        localStorage.setItem('ame_permission_level', lvl.id)
                        socketRef.current?.emit('set_permission_level', { level: lvl.id })
                      }}
                      style={{
                        padding: '16px 20px', borderRadius: 12, cursor: 'pointer', textAlign: 'left',
                        border: `1px solid ${active ? lvl.color : 'var(--ame-border-subtle)'}`,
                        background: active ? `color-mix(in srgb, ${lvl.color} 10%, transparent)` : 'var(--ame-bg-card)',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      <div style={{ fontFamily: 'var(--ame-mono)', fontSize: 14, fontWeight: 600, color: active ? lvl.color : 'var(--ame-text)', marginBottom: 6 }}>{lvl.label}</div>
                      <div style={{ fontFamily: 'var(--ame-mono)', fontSize: 11, color: 'var(--ame-text-ghost)', lineHeight: 1.5 }}>{lvl.desc}</div>
                    </button>
                  )
                })}
              </div>
            </motion.div>
          )}

          {/* ═══ GOING DARK ═══ */}
          {settingsTab === 'dark' && (
            <motion.div key="dark" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
              <h2 style={{ fontFamily: 'var(--ame-sans)', fontSize: 20, fontWeight: 500, color: 'var(--ame-text)', marginBottom: 6 }}>{t.settingsGoingDark || 'Going Dark'}</h2>
              <p style={{ fontFamily: 'var(--ame-sans)', fontSize: 13, color: 'var(--ame-text-secondary)', marginBottom: 28, lineHeight: 1.6 }}>{t.goingDarkDesc || 'Double clap to summon AMÉ. She greets you, then does whatever you configured.'}</p>

              {/* Enable toggle */}
              <div style={{
                padding: '18px 20px', borderRadius: 12,
                border: '1px solid var(--ame-border-subtle)',
                background: 'var(--ame-bg-card)',
                marginBottom: 24,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <Zap size={16} style={{ color: 'var(--ame-accent-light)' }} />
                    <span style={{ fontFamily: 'var(--ame-mono)', fontSize: 13, fontWeight: 600, color: 'var(--ame-text)' }}>{t.enableDoubleClap || 'Clap detection'}</span>
                  </div>
                  <button
                    onClick={() => {
                      const next = !clapEnabled
                      setClapEnabled(next)
                      localStorage.setItem('ame_clap_mode', String(next))
                      socketRef.current?.emit('set_clap_mode', { enabled: next, action: clapAction })
                    }}
                    style={{
                      width: 42, height: 22, borderRadius: 11, padding: 0,
                      border: `1px solid ${clapEnabled ? 'var(--ame-accent)' : 'var(--ame-border-subtle)'}`,
                      background: clapEnabled ? 'var(--ame-accent-ghost)' : 'transparent',
                      cursor: 'pointer', position: 'relative', transition: 'all 0.2s',
                    }}
                  >
                    <div style={{
                      width: 16, height: 16, borderRadius: '50%',
                      background: clapEnabled ? 'var(--ame-accent)' : 'var(--ame-text-ghost)',
                      position: 'absolute', top: 2,
                      left: clapEnabled ? 22 : 2,
                      transition: 'all 0.2s',
                    }} />
                  </button>
                </div>
                <p style={{ fontFamily: 'var(--ame-mono)', fontSize: 11, color: 'var(--ame-text-ghost)', lineHeight: 1.6, margin: '8px 0 0' }}>
                  Double clap near your mic to summon AMÉ.
                </p>
              </div>

              {/* Action field */}
              <div style={{ fontSize: 11, fontFamily: 'var(--ame-mono)', color: 'var(--ame-text-secondary)', marginBottom: 10, letterSpacing: '0.1em', textTransform: 'uppercase' }}>{t.whatToDo || 'What to do'}</div>
              <p style={{ fontFamily: 'var(--ame-mono)', fontSize: 11, color: 'var(--ame-text-ghost)', marginBottom: 12, lineHeight: 1.6 }}>
                {t.whatToDoDesc || "Tell AMÉ what to do when you clap — she'll figure out the rest."}
              </p>
              <input
                type="text" value={clapAction}
                onChange={e => setClapAction(e.target.value)}
                placeholder="open Oracle VirtualBox and play Highway to Hell"
                style={{
                  width: '100%', padding: '12px 14px', borderRadius: 10,
                  background: 'var(--ame-bg-card)',
                  border: '1px solid var(--ame-border-subtle)',
                  color: 'var(--ame-text)', fontFamily: 'var(--ame-mono)', fontSize: 13,
                  outline: 'none', transition: 'border-color 0.15s',
                  boxSizing: 'border-box', marginBottom: 20,
                }}
                onFocus={e => e.target.style.borderColor = 'var(--ame-accent)'}
                onBlur={e => e.target.style.borderColor = 'var(--ame-border-subtle)'}
              />

              {/* Save button */}
              <button
                onClick={() => {
                  localStorage.setItem('ame_clap_action', clapAction)
                  socketRef.current?.emit('set_clap_mode', { enabled: clapEnabled, action: clapAction })
                }}
                style={{
                  padding: '11px 28px', borderRadius: 10, cursor: 'pointer',
                  border: '1px solid var(--ame-accent)',
                  background: 'var(--ame-accent-ghost)',
                  color: 'var(--ame-accent-light)',
                  fontFamily: 'var(--ame-mono)', fontSize: 13, fontWeight: 600,
                  letterSpacing: '0.05em',
                  transition: 'all 0.15s',
                }}
                onMouseEnter={e => { e.currentTarget.style.background = 'var(--ame-accent)'; e.currentTarget.style.color = '#000' }}
                onMouseLeave={e => { e.currentTarget.style.background = 'var(--ame-accent-ghost)'; e.currentTarget.style.color = 'var(--ame-accent-light)' }}
              >
                {t.save || 'Save'}
              </button>

              <div style={{ marginTop: 24, padding: '14px 16px', borderRadius: 10, border: '1px solid var(--ame-border-subtle)', background: 'var(--ame-bg-card)' }}>
                <div style={{ fontFamily: 'var(--ame-mono)', fontSize: 10, color: 'var(--ame-text-ghost)', lineHeight: 1.7 }}>
                  {t.goingDarkExamples || 'Examples'}:<br />
                  "open Oracle VirtualBox and start Kali Linux"<br />
                  "play Highway to Hell and open VS Code"<br />
                  "open Spotify and lock the screen"
                </div>
              </div>
            </motion.div>
          )}

          {/* ═══ ABOUT ═══ */}
          {settingsTab === 'about' && (
            <motion.div key="about" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
              <h2 style={{ fontFamily: 'var(--ame-sans)', fontSize: 20, fontWeight: 500, color: 'var(--ame-text)', marginBottom: 6 }}>{t.settingsAbout || 'About AMÉ'}</h2>
              <p style={{ fontFamily: 'var(--ame-sans)', fontSize: 13, color: 'var(--ame-text-secondary)', marginBottom: 28, lineHeight: 1.6 }}>{t.aboutDesc || 'Your personal AI assistant.'}</p>

              <div style={{
                padding: '20px', borderRadius: 12,
                border: '1px solid var(--ame-border-subtle)',
                background: 'var(--ame-bg-card)',
                marginBottom: 24,
              }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  {[
                    { label: 'Version',  value: 'AMÉ 3.0' },
                    { label: 'Model',    value: activeProvider },
                    { label: 'Voice',    value: selectedVoice },
                    { label: 'Session',  value: <UptimeCounter start={sessionStart} /> },
                  ].map(({ label, value }) => (
                    <div key={label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontFamily: 'var(--ame-mono)', fontSize: 12, color: 'var(--ame-text-secondary)' }}>{label}</span>
                      <span style={{ fontFamily: 'var(--ame-mono)', fontSize: 12, color: 'var(--ame-accent-light)' }}>{value}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div style={{
                padding: '20px', borderRadius: 12,
                border: '1px solid var(--ame-border-subtle)',
                background: 'var(--ame-bg-card)',
                marginBottom: 24,
              }}>
                <p style={{ fontFamily: 'var(--ame-mono)', fontSize: 12, color: 'var(--ame-text-secondary)', lineHeight: 1.8, margin: 0 }}>
                  AMÉ started as a simple idea: what if your computer actually listened?
                  Not just to commands, but to context. She watches your screen, hears your voice,
                  plays your music, and tries to be genuinely useful — not a chatbot in a box,
                  but something closer to a presence. She's still learning, still rough around
                  the edges. But she's here, and she's paying attention.
                </p>
              </div>

              <div style={{ display: 'flex', gap: 10 }}>
                <button
                  onClick={() => window.open('https://github.com', '_blank')}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '10px 18px', borderRadius: 10, cursor: 'pointer',
                    border: '1px solid var(--ame-border-subtle)',
                    background: 'var(--ame-bg-card)',
                    color: 'var(--ame-text-secondary)',
                    fontFamily: 'var(--ame-mono)', fontSize: 12,
                    transition: 'all 0.15s',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--ame-accent)'; e.currentTarget.style.color = 'var(--ame-accent-light)' }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--ame-border-subtle)'; e.currentTarget.style.color = 'var(--ame-text-secondary)' }}
                >
                  <ExternalLink size={14} />
                  GitHub
                </button>
                <button
                  onClick={() => window.open('mailto:feedback@ame.app', '_blank')}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '10px 18px', borderRadius: 10, cursor: 'pointer',
                    border: '1px solid var(--ame-border-subtle)',
                    background: 'var(--ame-bg-card)',
                    color: 'var(--ame-text-secondary)',
                    fontFamily: 'var(--ame-mono)', fontSize: 12,
                    transition: 'all 0.15s',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--ame-accent)'; e.currentTarget.style.color = 'var(--ame-accent-light)' }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--ame-border-subtle)'; e.currentTarget.style.color = 'var(--ame-text-secondary)' }}
                >
                  <MessageCircle size={14} />
                  Feedback
                </button>
              </div>
            </motion.div>
          )}

        </div>
      </div>
    </motion.div>
  )
}
