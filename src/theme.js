/**
 * Amé Theme System
 * generateTheme(hex) → full theme object from a single base color
 * applyTheme(theme)  → writes all CSS variables to :root
 */

/** Convert hex #rrggbb to { h, s, l } (0-360, 0-100, 0-100) */
function hexToHsl(hex) {
  let r = parseInt(hex.slice(1, 3), 16) / 255
  let g = parseInt(hex.slice(3, 5), 16) / 255
  let b = parseInt(hex.slice(5, 7), 16) / 255

  const max = Math.max(r, g, b), min = Math.min(r, g, b)
  let h, s
  const l = (max + min) / 2

  if (max === min) {
    h = s = 0
  } else {
    const d = max - min
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
    switch (max) {
      case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break
      case g: h = ((b - r) / d + 2) / 6; break
      case b: h = ((r - g) / d + 4) / 6; break
    }
  }
  return { h: h * 360, s: s * 100, l: l * 100 }
}

/** hsl(h, s%, l%) string */
function hsl(h, s, l) {
  return `hsl(${Math.round(h)}, ${Math.round(s)}%, ${Math.round(l)}%)`
}

/** hsl(h, s%, l%, a) string */
function hsla(h, s, l, a) {
  return `hsla(${Math.round(h)}, ${Math.round(s)}%, ${Math.round(l)}%, ${a})`
}

/** Shade presets – controls background lightness & saturation offsets */
const SHADE_PRESETS = {
  black: { bgBase: 4,  bgStep: 3, sat: 1.0 },   // original near-black
  grey:  { bgBase: 14, bgStep: 3, sat: 0.5 },   // softer mid-dark grey
  white: { bgBase: 90, bgStep: -3, sat: 0.3 },  // light mode
}

/**
 * Generate a full Amé theme from a single hex accent color.
 * shade = 'black' | 'grey' | 'white' – controls background brightness.
 */
export function generateTheme(hex, shade = 'black') {
  if (!hex || !/^#[0-9A-Fa-f]{6}$/.test(hex)) return generateTheme('#00d084', shade)
  const { h, s } = hexToHsl(hex)
  const p = SHADE_PRESETS[shade] || SHADE_PRESETS.black
  const isLight = shade === 'white'
  const bSat = (v) => Math.round(v * p.sat)  // scale saturation for shade

  // Background lightness levels derived from shade preset
  const bgL0 = p.bgBase
  const bgL1 = p.bgBase + p.bgStep
  const bgL2 = p.bgBase + p.bgStep * 2
  const bgL3 = p.bgBase + p.bgStep * 0.7
  const bgL4 = p.bgBase + p.bgStep * 1.5

  return {
    // ── Backgrounds ──────────────────────────────────────────
    bgMain:     hsl(h, bSat(20), bgL0),
    bgElevated: hsl(h, bSat(25), bgL1),
    bgSubtle:   hsl(h, bSat(20), bgL2),
    bgCard:     hsl(h, bSat(28), bgL3),
    bgHover:    hsl(h, bSat(22), bgL4),

    // ── Accent ───────────────────────────────────────────────
    accent:      hex,
    accentLight: hsl(h, Math.min(s, 80), isLight ? 40 : 72),
    accentDim:   hsl(h, Math.min(s, 80), isLight ? 55 : 30),
    accentGhost: hsla(h, Math.min(s, 80), isLight ? 45 : 55, isLight ? 0.10 : 0.08),
    accentGlow:  hsla(h, Math.min(s, 80), isLight ? 45 : 55, 0.30),

    // ── Borders ───────────────────────────────────────────────
    border:       hsla(h, 30, isLight ? 40 : 60, isLight ? 0.12 : 0.07),
    borderSubtle: hsla(h, 30, isLight ? 40 : 60, isLight ? 0.06 : 0.03),
    borderAccent: hsla(h, Math.min(s, 80), isLight ? 45 : 55, isLight ? 0.25 : 0.28),

    // ── Text ──────────────────────────────────────────────────
    textPrimary:   hsl(h, 15, isLight ? 12 : 92),
    textSecondary: hsl(h, 20, isLight ? 35 : 68),
    textTertiary:  hsl(h, 15, isLight ? 55 : 48),
    textGhost:     hsl(h, 20, isLight ? 72 : 35),

    // ── Chat bubbles ──────────────────────────────────────────
    ameBubbleBg:     hsl(h, bSat(35), bgL3),
    ameBubbleText:   hsl(h, 15, isLight ? 12 : 90),

    // ── Sidebar ───────────────────────────────────────────────
    sidebarBg:     hsla(h, bSat(28), bgL3, 0.97),

    // ── Input bar ─────────────────────────────────────────────
    inputBarBg:    hsl(h, bSat(22), bgL0 + (isLight ? -2 : 1)),
    inputBarGlass: hsla(h, bSat(22), isLight ? 96 : bgL0 + 2, isLight ? 0.6 : 0.65),

    // ── Orb colors ────────────────────────────────────────────
    orbIdle:         hex,
    orbIdleCore:     hsl(h, 60, isLight ? 92 : 5),
    orbSpeaking:     hex,
    orbSpeakingCore: hsl(h, 60, isLight ? 92 : 5),
    // Listening (cyan) and thinking (amber) never change
    orbListening:    '#22d3ee',
    orbThinking:     '#fbbf24',

    // ── Scanline overlay ──────────────────────────────────────
    scanlineColor: shade === 'black' ? 'rgba(0,0,0,0.08)' : 'transparent',
    shadowColor: isLight ? 'rgba(0,0,0,0.08)' : shade === 'grey' ? 'rgba(0,0,0,0.25)' : 'rgba(0,0,0,0.5)',
  }
}

/** Write every theme key as a CSS variable on :root */
export function applyTheme(theme) {
  const root = document.documentElement.style
  root.setProperty('--ame-bg',            theme.bgMain)
  root.setProperty('--ame-bg-subtle',     theme.bgSubtle)
  root.setProperty('--ame-bg-card',       theme.bgCard)
  root.setProperty('--ame-bg-elevated',   theme.bgElevated)
  root.setProperty('--ame-bg-hover',      theme.bgHover)

  root.setProperty('--ame-accent',        theme.accent)
  root.setProperty('--ame-accent-light',  theme.accentLight)
  root.setProperty('--ame-accent-dim',    theme.accentDim)
  root.setProperty('--ame-accent-ghost',  theme.accentGhost)
  root.setProperty('--ame-accent-glow',   theme.accentGlow)

  root.setProperty('--ame-border',        theme.border)
  root.setProperty('--ame-border-subtle', theme.borderSubtle)
  root.setProperty('--ame-border-accent', theme.borderAccent)

  root.setProperty('--ame-text',          theme.textPrimary)
  root.setProperty('--ame-text-secondary',theme.textSecondary)
  root.setProperty('--ame-text-tertiary', theme.textTertiary)
  root.setProperty('--ame-text-ghost',    theme.textGhost)

  root.setProperty('--ame-bubble-bg',       theme.ameBubbleBg)
  root.setProperty('--ame-bubble-text',     theme.ameBubbleText)
  root.setProperty('--ame-orb-idle',        theme.orbIdle)
  root.setProperty('--ame-orb-idle-core',   theme.orbIdleCore)
  root.setProperty('--ame-orb-speaking',    theme.orbSpeaking)
  root.setProperty('--ame-orb-speaking-core', theme.orbSpeakingCore)
  root.setProperty('--ame-sidebar-bg',    theme.sidebarBg)
  root.setProperty('--ame-input-bar-bg',  theme.inputBarBg)
  root.setProperty('--ame-input-bar-glass', theme.inputBarGlass)
  root.setProperty('--ame-scanline-color', theme.scanlineColor)
  root.setProperty('--ame-shadow-color',   theme.shadowColor)
}
