import React, { useState, useEffect, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { io } from 'socket.io-client'
import {
  Mic, MicOff, Send, Settings, Wifi, WifiOff, Zap, Clock,
  Camera, Lock, VolumeX, MessageSquare, X,
  ArrowLeft, CheckCircle, XCircle, Loader2,
  Cpu, Eye, Calendar, HelpCircle
} from 'lucide-react'

import OrbScene       from './components/OrbScene.jsx'
import ToolsPanel     from './components/ToolsPanel.jsx'
import SettingsPanel  from './components/SettingsPanel.jsx'
import Toasts, { useToasts } from './components/Toasts.jsx'
import ChatHistory from './components/ChatHistory.jsx'
import SystemMonitor from './components/SystemMonitor.jsx'
import SchedulesPanel from './components/SchedulesPanel.jsx'
import WelcomePage    from './WelcomePage.jsx'
import { generateTheme, applyTheme } from './theme.js'

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8766'
const SOCKET_URL = BACKEND_URL
const MIN_RMS_UI = 800  // dot lights up above this level (0–32768 peak scale)

const TRANSLATIONS = {
  en: {
    idle: 'IDLE', listening: 'LISTENING', thinking: 'THINKING', speaking: 'SPEAKING', muted: 'MUTED',
    placeholder: "what's on your mind?", micOn: 'MIC ON', micOff: 'MIC OFF',
    online: 'online', offline: 'offline',
    voice: 'VOICE', takesEffect: 'takes effect on reconnect',
    language: 'LANGUAGE', responseStyle: 'RESPONSE STYLE',
    concise: 'Concise', balanced: 'Balanced', detailed: 'Detailed',
    themeColor: 'THEME COLOR', system: 'SYSTEM',
    model: 'model', version: 'version', voiceLabel: 'voice', back: 'back',
    sysPanel: 'SYS PANEL', session: 'SESSION',
    messages: 'messages', uptime: 'uptime',
    quickActions: 'QUICK ACTIONS',
    takeScreenshot: 'take screenshot', lockScreen: 'lock screen',
    muteVolume: 'mute volume', currentTime: 'current time', searchWeb: 'search web',
    capabilities: 'capabilities', agentLog: 'AGENT LOG', noActiveTasks: 'no active tasks',
    dir: 'ltr',
    // Settings page
    settings: 'Settings', settingsVoice: 'Voice', settingsLanguage: 'Language',
    settingsAppearance: 'Appearance', settingsAwareness: 'Awareness',
    settingsGoingDark: 'Going Dark', settingsAbout: 'About AMÉ',
    voiceDesc: 'Choose how AMÉ sounds and responds.', voiceModel: 'Voice model',
    languageDesc: 'Choose the language AMÉ speaks.', selectLanguage: 'Select language',
    appearanceDesc: 'Customize the look and feel.',
    awarenessDesc: 'Control what AMÉ pays attention to.',
    screenWatcher: 'Screen watcher', screenWatcherDesc: 'AMÉ quietly watches your screen and speaks up when something matters.',
    newsAwareness: 'News awareness', newsAwarenessDesc: 'AMÉ checks news about your interests when you open her.',
    memory: 'Memory', memoryDesc: 'AMÉ remembers things you tell her across conversations.',
    dangerZone: 'Danger zone', clearMemory: 'Clear all memory', clearMemoryConfirm: 'Are you sure you want to clear all memory? This cannot be undone.',
    goingDarkDesc: 'Double clap to summon AMÉ and trigger a custom action.',
    enableDoubleClap: 'Enable double clap', whatToDo: 'What to do',
    whatToDoDesc: "Tell AMÉ what to do when you clap — she'll figure out the rest.",
    save: 'Save', saved: 'Saved!',
    goingDarkExamples: 'Examples',
    aboutDesc: 'Your personal AI assistant.',
  },
  fr: {
    idle: 'REPOS', listening: 'ÉCOUTE', thinking: 'RÉFLEXION', speaking: 'PARLE', muted: 'MUET',
    placeholder: "qu'est-ce qui te passe par la tête?", micOn: 'MIC ON', micOff: 'MIC OFF',
    online: 'en ligne', offline: 'hors ligne',
    voice: 'VOIX', takesEffect: 'effectif à la reconnexion',
    language: 'LANGUE', responseStyle: 'STYLE DE RÉPONSE',
    concise: 'Concis', balanced: 'Équilibré', detailed: 'Détaillé',
    themeColor: 'COULEUR DU THÈME', system: 'SYSTÈME',
    model: 'modèle', version: 'version', voiceLabel: 'voix', back: 'retour',
    sysPanel: 'PANNEAU SYS', session: 'SESSION',
    messages: 'messages', uptime: 'durée',
    quickActions: 'ACTIONS RAPIDES',
    takeScreenshot: 'capture d\'écran', lockScreen: 'verrouiller',
    muteVolume: 'couper le son', currentTime: 'heure actuelle', searchWeb: 'rechercher',
    capabilities: 'capacités', agentLog: 'JOURNAL AGENT', noActiveTasks: 'aucune tâche active',
    dir: 'ltr',
    settings: 'Paramètres', settingsVoice: 'Voix', settingsLanguage: 'Langue',
    settingsAppearance: 'Apparence', settingsAwareness: 'Conscience',
    settingsGoingDark: 'Mode Sombre', settingsAbout: 'À propos',
    voiceDesc: 'Choisissez comment AMÉ parle et répond.', voiceModel: 'Modèle vocal',
    languageDesc: 'Choisissez la langue d\'AMÉ.', selectLanguage: 'Choisir la langue',
    appearanceDesc: 'Personnalisez l\'apparence.',
    awarenessDesc: 'Contrôlez ce qu\'AMÉ surveille.',
    screenWatcher: 'Surveillance écran', screenWatcherDesc: 'AMÉ surveille discrètement votre écran et intervient quand c\'est important.',
    newsAwareness: 'Actualités', newsAwarenessDesc: 'AMÉ vérifie les actualités sur vos centres d\'intérêt au démarrage.',
    memory: 'Mémoire', memoryDesc: 'AMÉ retient ce que vous lui dites entre les conversations.',
    dangerZone: 'Zone dangereuse', clearMemory: 'Effacer la mémoire', clearMemoryConfirm: 'Voulez-vous vraiment effacer toute la mémoire ? Cette action est irréversible.',
    goingDarkDesc: 'Double clap pour invoquer AMÉ et déclencher une action.',
    enableDoubleClap: 'Activer le double clap', whatToDo: 'Que faire',
    whatToDoDesc: 'Dites à AMÉ quoi faire quand vous clapez.',
    save: 'Enregistrer', saved: 'Enregistré !',
    goingDarkExamples: 'Exemples',
    aboutDesc: 'Votre assistante IA personnelle.',
  },
  ar: {
    idle: 'خامل', listening: 'يستمع', thinking: 'يفكر', speaking: 'يتحدث', muted: 'صامت',
    placeholder: 'شو ببالك؟', micOn: 'الميك شغال', micOff: 'الميك مغلق',
    online: 'متصل', offline: 'غير متصل',
    voice: 'الصوت', takesEffect: 'يسري عند إعادة الاتصال',
    language: 'اللغة', responseStyle: 'أسلوب الرد',
    concise: 'مختصر', balanced: 'متوازن', detailed: 'مفصّل',
    themeColor: 'لون الثيم', system: 'النظام',
    model: 'النموذج', version: 'الإصدار', voiceLabel: 'الصوت', back: 'رجوع',
    sysPanel: 'لوحة النظام', session: 'الجلسة',
    messages: 'رسائل', uptime: 'مدة التشغيل',
    quickActions: 'إجراءات سريعة',
    takeScreenshot: 'التقاط الشاشة', lockScreen: 'قفل الشاشة',
    muteVolume: 'كتم الصوت', currentTime: 'الوقت الحالي', searchWeb: 'بحث على الإنترنت',
    capabilities: 'القدرات', agentLog: 'سجل المهام', noActiveTasks: 'لا توجد مهام نشطة',
    dir: 'rtl',
    settings: 'الإعدادات', settingsVoice: 'الصوت', settingsLanguage: 'اللغة',
    settingsAppearance: 'المظهر', settingsAwareness: 'الوعي',
    settingsGoingDark: 'الوضع المظلم', settingsAbout: 'عن AMÉ',
    voiceDesc: 'اختر كيف تتحدث AMÉ وتستجيب.', voiceModel: 'نموذج الصوت',
    languageDesc: 'اختر اللغة التي تتحدث بها AMÉ.', selectLanguage: 'اختر اللغة',
    appearanceDesc: 'خصص المظهر والشكل.',
    awarenessDesc: 'تحكم فيما تنتبه إليه AMÉ.',
    screenWatcher: 'مراقبة الشاشة', screenWatcherDesc: 'AMÉ تراقب شاشتك بهدوء وتتدخل عندما يكون الأمر مهماً.',
    newsAwareness: 'الأخبار', newsAwarenessDesc: 'AMÉ تتحقق من الأخبار المتعلقة باهتماماتك عند فتحها.',
    memory: 'الذاكرة', memoryDesc: 'AMÉ تتذكر ما تخبرها به بين المحادثات.',
    dangerZone: 'منطقة الخطر', clearMemory: 'مسح الذاكرة', clearMemoryConfirm: 'هل أنت متأكد من مسح كل الذاكرة؟ لا يمكن التراجع.',
    goingDarkDesc: 'صفق مرتين لاستدعاء AMÉ وتشغيل إجراء مخصص.',
    enableDoubleClap: 'تفعيل التصفيق المزدوج', whatToDo: 'ماذا تفعل',
    whatToDoDesc: 'أخبر AMÉ ماذا تفعل عندما تصفق.',
    save: 'حفظ', saved: 'تم الحفظ!',
    goingDarkExamples: 'أمثلة',
    aboutDesc: 'مساعدتك الشخصية بالذكاء الاصطناعي.',
  },
  es: {
    idle: 'LISTO', listening: 'ESCUCHA', thinking: 'PENSANDO', speaking: 'HABLA', muted: 'MUTE',
    placeholder: '¿qué tienes en mente?', micOn: 'MIC ON', micOff: 'MIC OFF',
    online: 'en línea', offline: 'sin conexión',
    voice: 'VOZ', takesEffect: 'efectivo al reconectar',
    language: 'IDIOMA', responseStyle: 'ESTILO DE RESPUESTA',
    concise: 'Conciso', balanced: 'Equilibrado', detailed: 'Detallado',
    themeColor: 'COLOR DEL TEMA', system: 'SISTEMA',
    model: 'modelo', version: 'versión', voiceLabel: 'voz', back: 'volver',
    sysPanel: 'PANEL SYS', session: 'SESIÓN',
    messages: 'mensajes', uptime: 'tiempo activo',
    quickActions: 'ACCIONES RÁPIDAS',
    takeScreenshot: 'captura de pantalla', lockScreen: 'bloquear pantalla',
    muteVolume: 'silenciar', currentTime: 'hora actual', searchWeb: 'buscar en web',
    capabilities: 'capacidades', agentLog: 'REGISTRO AGENTE', noActiveTasks: 'sin tareas activas',
    dir: 'ltr',
    settings: 'Ajustes', settingsVoice: 'Voz', settingsLanguage: 'Idioma',
    settingsAppearance: 'Apariencia', settingsAwareness: 'Conciencia',
    settingsGoingDark: 'Modo Oscuro', settingsAbout: 'Sobre AMÉ',
    voiceDesc: 'Elige cómo suena y responde AMÉ.', voiceModel: 'Modelo de voz',
    languageDesc: 'Elige el idioma de AMÉ.', selectLanguage: 'Seleccionar idioma',
    appearanceDesc: 'Personaliza la apariencia.',
    awarenessDesc: 'Controla a qué presta atención AMÉ.',
    screenWatcher: 'Vigilante de pantalla', screenWatcherDesc: 'AMÉ observa tu pantalla discretamente e interviene cuando importa.',
    newsAwareness: 'Noticias', newsAwarenessDesc: 'AMÉ busca noticias sobre tus intereses al iniciar.',
    memory: 'Memoria', memoryDesc: 'AMÉ recuerda lo que le dices entre conversaciones.',
    dangerZone: 'Zona peligrosa', clearMemory: 'Borrar memoria', clearMemoryConfirm: 'Seguro que quieres borrar toda la memoria? No se puede deshacer.',
    goingDarkDesc: 'Doble palmada para invocar AMÉ y ejecutar una acción.',
    enableDoubleClap: 'Activar doble palmada', whatToDo: 'Qué hacer',
    whatToDoDesc: 'Dile a AMÉ qué hacer cuando aplaudas.',
    save: 'Guardar', saved: 'Guardado!',
    goingDarkExamples: 'Ejemplos',
    aboutDesc: 'Tu asistente personal de IA.',
  },
  de: {
    idle: 'BEREIT', listening: 'HÖRT ZU', thinking: 'DENKT', speaking: 'SPRICHT', muted: 'STUMM',
    placeholder: 'was hast du auf dem Herzen?', micOn: 'MIC AN', micOff: 'MIC AUS',
    online: 'online', offline: 'offline',
    voice: 'STIMME', takesEffect: 'wirkt nach Neuverbindung',
    language: 'SPRACHE', responseStyle: 'ANTWORTSTIL',
    concise: 'Kurz', balanced: 'Ausgewogen', detailed: 'Ausführlich',
    themeColor: 'DESIGNFARBE', system: 'SYSTEM',
    model: 'Modell', version: 'Version', voiceLabel: 'Stimme', back: 'zurück',
    sysPanel: 'SYS-PANEL', session: 'SITZUNG',
    messages: 'Nachrichten', uptime: 'Laufzeit',
    quickActions: 'SCHNELLAKTIONEN',
    takeScreenshot: 'Screenshot', lockScreen: 'Bildschirm sperren',
    muteVolume: 'Ton stumm', currentTime: 'aktuelle Uhrzeit', searchWeb: 'Web suchen',
    capabilities: 'Fähigkeiten', agentLog: 'AGENT-PROTOKOLL', noActiveTasks: 'keine aktiven Aufgaben',
    dir: 'ltr',
    settings: 'Einstellungen', settingsVoice: 'Stimme', settingsLanguage: 'Sprache',
    settingsAppearance: 'Erscheinung', settingsAwareness: 'Aufmerksamkeit',
    settingsGoingDark: 'Dunkel-Modus', settingsAbout: 'Über AMÉ',
    voiceDesc: 'Wähle wie AMÉ klingt und antwortet.', voiceModel: 'Stimmmodell',
    languageDesc: 'Wähle die Sprache von AMÉ.', selectLanguage: 'Sprache wählen',
    appearanceDesc: 'Passe das Aussehen an.',
    awarenessDesc: 'Steuere worauf AMÉ achtet.',
    screenWatcher: 'Bildschirmüberwachung', screenWatcherDesc: 'AMÉ beobachtet deinen Bildschirm und meldet sich wenn nötig.',
    newsAwareness: 'Nachrichten', newsAwarenessDesc: 'AMÉ prüft Nachrichten zu deinen Interessen beim Start.',
    memory: 'Gedächtnis', memoryDesc: 'AMÉ merkt sich was du ihr sagst.',
    dangerZone: 'Gefahrenzone', clearMemory: 'Gedächtnis löschen', clearMemoryConfirm: 'Bist du sicher? Dies kann nicht rückgängig gemacht werden.',
    goingDarkDesc: 'Doppelklatschen um AMÉ zu rufen und eine Aktion auszulösen.',
    enableDoubleClap: 'Doppelklatschen aktivieren', whatToDo: 'Was tun',
    whatToDoDesc: 'Sage AMÉ was sie tun soll wenn du klatschst.',
    save: 'Speichern', saved: 'Gespeichert!',
    goingDarkExamples: 'Beispiele',
    aboutDesc: 'Deine persönliche KI-Assistentin.',
  },
  ja: {
    idle: '待機', listening: '聴取中', thinking: '思考中', speaking: '発話中', muted: 'ミュート',
    placeholder: '何を考えてる？', micOn: 'マイクON', micOff: 'マイクOFF',
    online: 'オンライン', offline: 'オフライン',
    voice: '音声', takesEffect: '再接続時に有効',
    language: '言語', responseStyle: '返答スタイル',
    concise: '簡潔', balanced: 'バランス', detailed: '詳細',
    themeColor: 'テーマカラー', system: 'システム',
    model: 'モデル', version: 'バージョン', voiceLabel: '音声', back: '戻る',
    sysPanel: 'SYSパネル', session: 'セッション',
    messages: 'メッセージ', uptime: '稼働時間',
    quickActions: 'クイックアクション',
    takeScreenshot: 'スクリーンショット', lockScreen: '画面ロック',
    muteVolume: 'ミュート', currentTime: '現在時刻', searchWeb: 'ウェブ検索',
    capabilities: '機能', agentLog: 'エージェントログ', noActiveTasks: 'タスクなし',
    dir: 'ltr',
    settings: '設定', settingsVoice: '音声', settingsLanguage: '言語',
    settingsAppearance: '外観', settingsAwareness: '認識',
    settingsGoingDark: 'ダークモード', settingsAbout: 'AMÉについて',
    voiceDesc: 'AMÉの声と応答スタイルを選択。', voiceModel: '音声モデル',
    languageDesc: 'AMÉの言語を選択。', selectLanguage: '言語を選択',
    appearanceDesc: '見た目をカスタマイズ。',
    awarenessDesc: 'AMÉが注意を払う対象を制御。',
    screenWatcher: '画面監視', screenWatcherDesc: 'AMÉが画面を静かに監視し、重要な時に発言します。',
    newsAwareness: 'ニュース', newsAwarenessDesc: 'AMÉが起動時にあなたの興味に関するニュースをチェック。',
    memory: '記憶', memoryDesc: 'AMÉは会話間であなたの話を覚えています。',
    dangerZone: '危険ゾーン', clearMemory: '記憶を消去', clearMemoryConfirm: '本当に全ての記憶を消去しますか？元に戻せません。',
    goingDarkDesc: 'ダブルクラップでAMÉを呼び出しアクションを実行。',
    enableDoubleClap: 'ダブルクラップを有効化', whatToDo: '何をする',
    whatToDoDesc: 'クラップした時にAMÉに何をさせるか指定。',
    save: '保存', saved: '保存済み!',
    goingDarkExamples: '例',
    aboutDesc: 'あなたのパーソナルAIアシスタント。',
  },
}

const STATE_COLORS = {
  idle:      { color: 'var(--ame-accent)',       bg: 'var(--ame-accent-ghost)' },
  listening: { color: 'var(--ame-cyan)',          bg: 'var(--ame-cyan-dim)'    },
  thinking:  { color: 'var(--ame-amber)',         bg: 'var(--ame-amber-dim)'   },
  speaking:  { color: 'var(--ame-accent-light)',  bg: 'var(--ame-accent-ghost)'},
  muted:     { color: 'var(--ame-rose)',          bg: 'rgba(251,113,133,0.1)'  },
}

function getStateMeta(state, lang) {
  const strings = TRANSLATIONS[lang] || TRANSLATIONS.en
  const colors   = STATE_COLORS[state] || STATE_COLORS.idle
  return { label: strings[state] || strings.idle, ...colors }
}

const SUGGESTIONS = [
  { label: 'play some music',       send: 'I want to listen to some music' },
  { label: "what's happening?",     send: "What's happening in the world today?" },
  { label: 'take a screenshot',     send: 'Can you take a screenshot for me?' },
  { label: 'make me laugh',         send: 'Tell me something funny' },
]


// ── Sidebar text palette — all CSS variables ────────────────
const SB = {
  bg:      'var(--ame-sidebar-bg)',
  border:  '1px solid var(--ame-border-accent)',
  header:  'var(--ame-accent-light)',
  text:    'var(--ame-text)',
  dim:     'var(--ame-text-secondary)',
  ghost:   'var(--ame-text-ghost)',
  accent:  'var(--ame-accent)',
  accentL: 'var(--ame-accent-light)',
}

// parseMarkdown is imported from its own module for testability
import parseMarkdown from './parseMarkdown.js'

// ── Window size hook ────────────────────────────────────────
function useWindowSize() {
  const [width, setWidth] = useState(() => window.innerWidth || 800)
  useEffect(() => {
    const handler = () => setWidth(window.innerWidth)
    window.addEventListener('resize', handler)
    return () => window.removeEventListener('resize', handler)
  }, [])
  return width
}

// ── Format timestamp ────────────────────────────────────────
function formatTime(ts) {
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
}

// ── Typewriter hook ─────────────────────────────────────────
function useTypewriter(text, speed = 18) {
  const [displayed, setDisplayed] = useState('')
  const [done, setDone] = useState(true)
  useEffect(() => {
    if (!text) { setDisplayed(''); setDone(true); return }
    setDisplayed(''); setDone(false)
    let i = 0
    const iv = setInterval(() => {
      i++; setDisplayed(text.slice(0, i))
      if (i >= text.length) { clearInterval(iv); setDone(true) }
    }, speed)
    return () => clearInterval(iv)
  }, [text])
  return { displayed, done }
}

// ── Uptime counter ──────────────────────────────────────────
function UptimeCounter({ start }) {
  const [, tick] = useState(0)
  useEffect(() => { const iv = setInterval(() => tick(n => n + 1), 1000); return () => clearInterval(iv) }, [])
  const s = Math.floor((Date.now() - start) / 1000), m = Math.floor(s / 60), h = Math.floor(m / 60)
  return <span>{h > 0 ? `${h}h ${m % 60}m` : m > 0 ? `${m}m ${s % 60}s` : `${s}s`}</span>
}

// Detect RTL scripts (Arabic, Hebrew, Persian, etc.)
const isRTL = (text) => /[\u0600-\u06FF\u0590-\u05FF\u0750-\u077F]/.test(text)

// Helper to strip punctuation for robust deduplication
const stripPunc = (s) => s ? s.replace(/[.,!?]/g, '').replace(/\s+/g, ' ').trim() : ''

// ── Floating message — no bubbles ───────────────────────────
function Bubble({ msg, age, onWhyClick }) {
  // Hide empty messages
  if (!msg.text && msg.role !== 'screenshot') return null
  const isUser      = msg.role === 'user'
  const isSys       = msg.role === 'system'
  const isShot      = msg.role === 'screenshot'
  const isLive      = msg.live === true
  const isProactive = msg.proactive === true
  const isUrgent    = msg.proactiveMode === 'urgent'

  const ageFade = 1

  if (isShot) return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: ageFade, y: 0 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 4 }}
    >
      <div className="msg-ame msg-ame-final" style={{ padding: '8px' }}>
        <img
          src={`file:///${msg.text.replace(/\\/g, '/')}`}
          alt="Screenshot"
          style={{ maxWidth: 320, maxHeight: 200, borderRadius: 4, display: 'block', border: '1px solid var(--ame-border)' }}
        />
      </div>
      <span className="msg-ts" style={{ paddingLeft: 14 }}>{formatTime(msg.ts)}</span>
    </motion.div>
  )

  if (isSys) {
    if (msg.text.startsWith('Working on it:')) return null
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: ageFade * 0.6 }}
        style={{ textAlign: 'center', margin: '2px 0' }}
      >
        <span className="msg-system">{msg.text}</span>
      </motion.div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: ageFade, y: 0 }}
      transition={{ duration: 0.28, ease: 'easeOut' }}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: isUser ? 'flex-end' : 'flex-start',
        gap: 4,
      }}
    >
      {isUser ? (
        <div className="msg-user" dir="auto">{msg.text}</div>
      ) : isLive ? (
        <div className="msg-ame msg-ame-live" dir="auto">{msg.text}</div>
      ) : (
        <div
          className={`msg-ame msg-ame-final${isProactive ? (isUrgent ? ' msg-proactive msg-proactive-urgent' : ' msg-proactive') : ''}`}
          dir="auto"
          dangerouslySetInnerHTML={{ __html: parseMarkdown(msg.text) }}
        />
      )}
      <span className="msg-ts" style={{ paddingLeft: isUser ? 0 : 14, display: 'flex', alignItems: 'center', gap: 4 }} dir="auto">
        {isProactive && (
          <Eye size={9} style={{ color: isUrgent ? 'var(--ame-amber)' : 'var(--ame-accent)', opacity: 0.6 }} />
        )}
        {formatTime(msg.ts)}
        {isProactive && onWhyClick && (
          <button
            onClick={() => onWhyClick(msg.text)}
            style={{
              background: 'none', border: '1px solid var(--ame-accent-ghost)',
              borderRadius: 4, cursor: 'pointer', display: 'flex',
              alignItems: 'center', gap: 3, padding: '1px 6px', marginLeft: 4,
              color: 'var(--ame-accent-light)', fontFamily: 'var(--ame-mono)',
              fontSize: 9, letterSpacing: '0.04em',
              transition: 'border-color 0.2s, color 0.2s',
            }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--ame-accent)'; e.currentTarget.style.color = 'var(--ame-accent)' }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--ame-accent-ghost)'; e.currentTarget.style.color = 'var(--ame-accent-light)' }}
            title="Ask Amé why she said this"
          >
            <HelpCircle size={8} />
            Why?
          </button>
        )}
      </span>
    </motion.div>
  )
}

// ── Typing indicator — bouncing dots ─────────────────────────
function TypingDots() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      style={{ display: 'flex', alignItems: 'center', gap: 5, paddingLeft: 30, paddingTop: 8, paddingBottom: 8 }}
    >
      {[0, 1, 2].map(i => (
        <motion.span
          key={i}
          animate={{ opacity: [0.3, 1, 0.3] }}
          transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }}
          style={{
            width: 6, height: 6, borderRadius: '50%',
            background: 'var(--ame-accent)',
          }}
        />
      ))}
    </motion.div>
  )
}

// ═══════════════════════════════════════════════════════════
export default function App() {
  const windowWidth = useWindowSize()
  const [envReady, setEnvReady]         = useState(null)
  const [connected, setConnected]       = useState(false)
  const [connTimeout, setConnTimeout]   = useState(false)
  const [ameState, setAmeState]         = useState('idle')
  const [messages, setMessages]         = useState([])
  const [inputText, setInputText]       = useState('')
  const [isTyping, setIsTyping]         = useState(false)
  const [audioDevices, setAudioDevices] = useState({ inputs: [], outputs: [] })
  const [selectedMic, setSelectedMic]   = useState(null)
  const [sessionStart]                  = useState(Date.now())
  const [messageCount, setMsgCount]     = useState(0)
  const [agentActive, setAgentActive]   = useState(false)
  const agentActiveRef                  = useRef(false)
  const [isMicActive, setIsMicActive]   = useState(false)
  const [toolsOpen, setToolsOpen]       = useState(false)
  const [historyOpen, setHistoryOpen]   = useState(false)
  const [focusMode, setFocusMode]       = useState(false)
  const [sysMonitorOpen, setSysMonitorOpen] = useState(false)
  const [schedulesOpen, setSchedulesOpen] = useState(false)
  const { toasts, addToast, removeToast } = useToasts()
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [settingsTab, setSettingsTab]   = useState('voice')
  const [language, setLanguage]         = useState(() => localStorage.getItem('ame_language') || 'en')
  const [lastText, setLastText]         = useState('')
  const [activeProvider, setActiveProvider] = useState('Gemini Live')
  const [isOffline, setIsOffline]           = useState(false)
  const [isMuted, setIsMuted]           = useState(false)
  const [selectedVoice, setSelectedVoice]   = useState(() => localStorage.getItem('ame_voice') || 'Zephyr')
  const [responseStyle, setResponseStyle]   = useState(1)
  const [screenWatcherOn, setScreenWatcherOn] = useState(() => localStorage.getItem('ame_screen_watcher') !== 'false')
  const [codeAwarenessOn, setCodeAwarenessOn] = useState(() => localStorage.getItem('ame_code_awareness') !== 'false')
  const [accentColor, setAccentColor]       = useState(() => localStorage.getItem('ame_accent_color') || '#00d084')
  const [bgShade, setBgShade]               = useState(() => localStorage.getItem('ame_bg_shade') || 'black')
  const [theme, setTheme]                   = useState(() => generateTheme(localStorage.getItem('ame_accent_color') || '#00d084', localStorage.getItem('ame_bg_shade') || 'black'))
  const [micRms, setMicRms]                 = useState(0)   // 0–32768, for audio level meter
  const [chatVisible, setChatVisible]       = useState(() => localStorage.getItem('ame_chat_visible') !== 'false')
  const [chatUnread, setChatUnread]         = useState(false)
  const [clapEnabled, setClapEnabled]       = useState(() => localStorage.getItem('ame_clap_mode') === 'true')
  const [clapAction, setClapAction]         = useState(() => localStorage.getItem('ame_clap_action') || '')
  const [newsEnabled, setNewsEnabled]       = useState(() => localStorage.getItem('ame_news_enabled') !== 'false')
  const [memoryEnabled, setMemoryEnabled]   = useState(() => localStorage.getItem('ame_memory_enabled') !== 'false')
  const [permissionLevel, setPermissionLevel] = useState(() => localStorage.getItem('ame_permission_level') || 'high')

  const chatScrollRef    = useRef(null)
  const inputRef         = useRef(null)
  const socketRef        = useRef(null)
  const msgIdRef         = useRef(0)
  const msgSeqRef        = useRef(0)
  const languageRef      = useRef(language)
  // Watchdog: tracks last time a transcript arrived
  const lastTranscriptTs = useRef(0)
  const watchdogRef      = useRef(null)
  const liveAmeMsgId     = useRef(null)   // ID of the in-progress live AMÉ bubble
  const lastAmeFinalText = useRef('')     // last finalized ame text — for cross-event dedup
  const lastAmeFinalTs   = useRef(0)      // timestamp of last finalized ame text
  const chatVisibleRef   = useRef(chatVisible)
  const addToastRef      = useRef(addToast)
  useEffect(() => { languageRef.current = language }, [language])
  useEffect(() => { addToastRef.current = addToast }, [addToast])
  // Keep chatVisibleRef in sync with chatVisible state so socket listeners
  // (which close over the ref, not the state) always see the current value.
  useEffect(() => { chatVisibleRef.current = chatVisible }, [chatVisible])

  // Central helper: mark a new unread notification only when chat is hidden.
  // Uses a ref read (never stale) and a functional setter (never races).
  const markUnreadIfHidden = useCallback(() => {
    if (!chatVisibleRef.current) {
      setChatUnread(prev => prev ? prev : true)
    }
  }, [])

  const { displayed: twText, done: twDone } = useTypewriter(lastText)

  // Add a message bubble
  const addMsg = useCallback((role, text) => {
    const id = `m${++msgIdRef.current}`
    const seq = ++msgSeqRef.current
    const now = Date.now()
    markUnreadIfHidden()
    setMessages(prev => {
      // Don't add if same role+text exists in last 3 messages within 5 seconds
      for (let i = prev.length - 1; i >= Math.max(0, prev.length - 3); i--) {
        const m = prev[i]
        if (m.role === role && m.text === text && now - m.ts < 5000) return prev
      }
      return [...prev.slice(-80), { id, role, text, ts: now, seq }]
    })
    return id
  }, [])

  // ── Check setup status ───────────────────────────────────
  useEffect(() => {
    fetch(`${BACKEND_URL}/setup-status`)
      .then(r => r.json())
      .then(data => setEnvReady(data.configured !== false))
      .catch(() => setEnvReady(true))
  }, [])

  // ── Socket.IO ────────────────────────────────────────────
  const isValidUserMessage = (text) => {
    if (!text || text.trim().length === 0) return false
    const garbage = ['<noise>', '[noise]', '<ctrl', '[ctrl', '<key', '[key', '<unk>', '[unk]', '...']
    const lower = text.toLowerCase().trim()
    for (const g of garbage) { if (lower.includes(g)) return false }
    const words = lower.split(/\s+/)
    if (words.length === 1 && words[0].length < 3) return false
    return true
  }

  useEffect(() => {
    // Guard: never create a second socket if one already exists and is still
    // usable (e.g. React StrictMode double-invoke, rapid remount).
    // Check both existence and connection state — a disconnected ref should be
    // replaced, not reused, to avoid silently dropping all listeners.
    if (socketRef.current && (socketRef.current.connected || socketRef.current.active)) return
    // Clean up any stale disconnected socket before creating a new one
    if (socketRef.current) {
      socketRef.current.removeAllListeners()
      socketRef.current.disconnect()
      socketRef.current = null
    }

    const token = window.__ameSessionToken || ''
    const sock = io(SOCKET_URL, { transports: ['websocket'], reconnection: true, reconnectionDelay: 2000, auth: { token } })
    socketRef.current = sock

    const timeoutId = setTimeout(() => {
      if (!sock.connected) setConnTimeout(true)
    }, 20000)

    // Helper: register a listener with automatic cleanup of any previous one
    const on = (event, handler) => {
      sock.off(event)
      sock.on(event, handler)
    }

    on('connect', () => {
      clearTimeout(timeoutId); setConnected(true); setConnTimeout(false)
      setIsTyping(false); setAmeState('idle')
      sock.emit('get_audio_devices')
      sock.emit('set_language', { language: languageRef.current })
      // Sync saved voice preference on (re)connect
      const savedVoice = localStorage.getItem('ame_voice') || 'Zephyr'
      sock.emit('set_voice', { voice: savedVoice })
      // Sync screen watcher preference from localStorage
      const swPref = localStorage.getItem('ame_screen_watcher') !== 'false'
      sock.emit('set_screen_watcher', { enabled: swPref })
      // Sync code awareness preference
      const cwPref = localStorage.getItem('ame_code_awareness') !== 'false'
      sock.emit('set_code_awareness', { enabled: cwPref })
      // Sync clap mode preference + action
      const clapPref = localStorage.getItem('ame_clap_mode') === 'true'
      const clapAct = localStorage.getItem('ame_clap_action') || ''
      sock.emit('set_clap_mode', { enabled: clapPref, action: clapAct })
      // Sync permission mode
      sock.emit('set_permission_level', { level: localStorage.getItem('ame_permission_level') || 'high' })
      
      const controller = new AbortController()
      setTimeout(() => controller.abort(), 5000)
      fetch(`${BACKEND_URL}/health`, { signal: controller.signal }).then(r => r.json()).then(d => { if (d.provider) setActiveProvider(d.provider); if (d.offline !== undefined) setIsOffline(d.offline) }).catch(() => {})
    })
    on('disconnect', () => {
      setConnected(false); setIsTyping(false); setAmeState('idle')
      setConnTimeout(false)
      liveAmeMsgId.current  = null
    })

    on('user_speaking', () => setAmeState('listening'))
    on('ame_speaking', () => setAmeState('speaking'))

    on('ame_done_speaking', () => {
      setIsTyping(false)
      setAmeState('idle')
    })

    // Barge-in: user interrupted AMÉ mid-speech
    on('ame_interrupted', () => {
      setAmeState('listening')
      setIsTyping(false)
      // Promote any live AMÉ bubble to final as-is (partial response)
      if (liveAmeMsgId.current) {
        setMessages(prev => prev.map(m =>
          m.id === liveAmeMsgId.current ? { ...m, live: false } : m
        ))
        liveAmeMsgId.current = null
      }
    })

    on('user_transcript_canceled', () => {
      setMessages(prev => {
        let next = prev.filter(m => m.id !== 'user-current')
        const now = Date.now()
        return next.filter(m => !(m.id.startsWith('u_stale_') && now - m.ts < 60000))
      })
    })

    on('state_change', ({ state }) => {
      setAmeState(state)
      // When AMÉ starts speaking, the user's turn is definitively over.
      // Finalize any live user bubble that wasn't promoted by user_transcript.
      // We only do this on 'speaking' — NOT on 'idle', because idle fires after
      // ame_done_speaking which often arrives right before user_transcript does,
      // causing user_transcript to find no 'user-current' and create a duplicate bubble.
      if (state === 'speaking') {
        setMessages(prev => {
          const idx = prev.findIndex(m => m.id === 'user-current')
          if (idx >= 0) {
            const updated = [...prev]
            // Renamed to u_stale so user_transcript fallback can find it via stale bubble lookup
            updated[idx] = { ...updated[idx], id: `u_stale_${Date.now()}`, live: false }
            return updated
          }
          return prev
        })
      }
    })

    on('wake_word_detected', () => {
      setIsMicActive(true); setAmeState('listening')
      setTimeout(() => setIsMicActive(false), 2000)
    })

    // user_transcript_partial — live typing as user speaks (mirrors AMÉ's streaming)
    // Uses static ID 'user-current' so only ONE live user bubble exists at a time.
    on('user_transcript_partial', ({ text }) => {
      if (!text || !text.trim()) return
      // Filter noise: must contain at least one real word (letter/digit character)
      if (!/[a-zA-Z0-9\u00C0-\u024F\u0600-\u06FF]/.test(text)) return
      lastTranscriptTs.current = Date.now()
      markUnreadIfHidden()
      // New user turn starting — clear any stale AMÉ bubble ref so the next
      // AMÉ response creates a fresh bubble instead of updating the old one.
      liveAmeMsgId.current = null
      setMessages(prev => {
        const idx = prev.findIndex(m => m.id === 'user-current')
        if (idx >= 0) {
          const updated = [...prev]
          updated[idx] = { ...updated[idx], text }
          return updated
        }
        return [...prev.slice(-80), { id: 'user-current', role: 'user', text, ts: Date.now(), live: true, seq: ++msgSeqRef.current }]
      })
    })

    // user_transcript — final corrected text at turn_complete. Promotes the live bubble.
    on('user_transcript', ({ text }) => {
      if (!text || !text.trim()) return
      if (!/[a-zA-Z0-9\u00C0-\u024F\u0600-\u06FF]/.test(text)) return
      lastTranscriptTs.current = Date.now()
      markUnreadIfHidden()
      const now = Date.now()
      const permId = `u_${now}_${Math.random().toString(36).slice(2, 7)}`
      setMessages(prev => {
        const idx = prev.findIndex(m => m.id === 'user-current')
        if (idx >= 0) {
          // Always replace with final corrected text — STT may have corrected partial
          const updated = [...prev]
          updated[idx] = { ...updated[idx], id: permId, text: text, live: false, ts: now }
          return updated
        }
        // Look for a recently staled bubble to update instead of creating duplicate
        let recentStale = -1
        for (let i = prev.length - 1; i >= 0; i--) {
          if (
            prev[i].role === 'user' &&
            prev[i].id && prev[i].id.startsWith('u_stale_') &&
            (now - prev[i].ts) < 300000
          ) { recentStale = i; break }
        }
        if (recentStale >= 0) {
          const updated = [...prev]
          updated[recentStale] = { ...updated[recentStale], id: permId, text: text, live: false, ts: now }
          return updated
        }
      // Check if duplicate of any recent permanent user msg
        const trimmed = stripPunc(text.toLowerCase())
      let isDupe = false
        for (let i = prev.length - 1; i >= Math.max(0, prev.length - 5); i--) {
        const m = prev[i]
        if (m.role === 'user' && m.id !== 'user-current' && !m.id.startsWith('u_stale_') && m.text) {
          const prevTrimmed = stripPunc(m.text.toLowerCase())
          if (prevTrimmed === trimmed || (trimmed.length > 12 && (prevTrimmed.includes(trimmed) || trimmed.includes(prevTrimmed)))) {
            isDupe = true; break;
          }
          }
        }
      if (isDupe) {
        // Vaporize the orphaned live/stale bubble that was forming this ghost echo
        return prev.filter(m => m.id !== 'user-current' && !(m.id.startsWith('u_stale_') && stripPunc(m.text?.toLowerCase()) === trimmed))
      }
        return [...prev.slice(-80), { id: permId, role: 'user', text, ts: now, seq: ++msgSeqRef.current }]
      })
      setMsgCount(c => c + 1)
    })

    // ── Shared dedup: reject ame text that matches recent final ──
    const isAmeDupe = (text) => {
      if (!text) return false
      const t = text.trim().toLowerCase()
      const prev = lastAmeFinalText.current.trim().toLowerCase()
      if (!prev) return false
      const age = Date.now() - lastAmeFinalTs.current
      if (age > 12000) return false  // stale

      const tClean = stripPunc(t)
      const prevClean = stripPunc(prev)

      // Exact or substring match at any age (ignoring punctuation)
      if (tClean === prevClean || (tClean.length > 12 && (tClean.includes(prevClean) || prevClean.includes(tClean)))) return true

      // Within 3s of a final, block short texts (< 80 chars) that share significant overlap
      // This catches reworded confirmations like "Done!" then "Done, music paused."
      if (age < 3000 && t.length < 80) {
        const prevWords = new Set(prevClean.split(' ').filter(w => w.length > 2))
        const curWords = tClean.split(' ').filter(w => w.length > 2)
        if (prevWords.size > 0 && curWords.length > 0) {
          const overlap = curWords.filter(w => prevWords.has(w)).length
          if (overlap / curWords.length > 0.4) return true
        }
      }
      return false
    }
    const markAmeFinal = (text) => {
      if (text) {
        lastAmeFinalText.current = text
        lastAmeFinalTs.current = Date.now()
      }
    }

    // ame_response_chunk — streaming chunks + final promotion, single event.
    // final:true promotes the live bubble to permanent (markdown rendered).
    on('ame_response_chunk', ({ text, final: isFinal }) => {
      if (isFinal) {
        if (liveAmeMsgId.current) {
          const finalId = liveAmeMsgId.current
          liveAmeMsgId.current = null
          setMessages(prev => {
            const msg = prev.find(m => m.id === finalId)
            const finalText = text || (msg && msg.text) || ''

              // If fully assembled text is a duplicate, vaporize the bubble entirely
              if (isAmeDupe(finalText)) {
                return prev.filter(m => m.id !== finalId)
              }

            markAmeFinal(finalText)
            return prev.map(m => m.id === finalId ? { ...m, text: finalText || m.text, live: false } : m)
          })
        } else if (text) {
          // No live bubble — this final might be a duplicate turn_complete.
          // Guard with isAmeDupe BEFORE creating the bubble, then mark final
          // so concurrent chunks can't slip a duplicate through.
            if (isAmeDupe(text)) return
          markAmeFinal(text)
            const id = `m${++msgIdRef.current}`
            setMessages(prev => {
              const trimmed = stripPunc(text.toLowerCase())
              for (let i = prev.length - 1; i >= Math.max(0, prev.length - 5); i--) {
                const m = prev[i]
                if (m.role === 'ame' && m.text) {
                  const mt = stripPunc(m.text.toLowerCase())
                  if (mt === trimmed || (trimmed.length > 12 && (mt.includes(trimmed) || trimmed.includes(mt)))) return prev
                }
              }
              return [...prev.slice(-80), { id, role: 'ame', text, ts: Date.now(), live: false, seq: ++msgSeqRef.current }]
            })
        }
        setIsTyping(false)
        agentActiveRef.current = false
        setAgentActive(false)
        return
      }
      if (!text) return
      if (!liveAmeMsgId.current) {
        // Skip if this is a duplicate of a just-finalized message
        if (isAmeDupe(text)) return
        const id = `m${++msgIdRef.current}`
        liveAmeMsgId.current = id
        markUnreadIfHidden()
        setMessages(prev => [...prev.slice(-80), { id, role: 'ame', text, ts: Date.now(), live: true, seq: ++msgSeqRef.current }])
        setMsgCount(c => c + 1)
      } else {
        setMessages(prev => prev.map(m =>
          m.id === liveAmeMsgId.current ? { ...m, text } : m
        ))
      }
    })

    // ame_response — kept for agent fallback path
    on('ame_response', ({ text }) => {
      if (!text || isAmeDupe(text)) return
      setMessages(prev => {
          const trimmed = stripPunc(text.toLowerCase())
        for (let i = prev.length - 1; i >= Math.max(0, prev.length - 5); i--) {
          const m = prev[i]
          if (m.role === 'ame' && m.text) {
              const mTrimmed = stripPunc(m.text.toLowerCase())
              if (mTrimmed === trimmed || (trimmed.length > 12 && (mTrimmed.includes(trimmed) || trimmed.includes(mTrimmed)))) return prev
          }
        }
        const id = `m${++msgIdRef.current}`
        markUnreadIfHidden()
        return [...prev.slice(-80), { id, role: 'ame', text, ts: Date.now(), seq: ++msgSeqRef.current }]
      })
      markAmeFinal(text)
      setMsgCount(c => c + 1)
      setIsTyping(false)
      agentActiveRef.current = false
      setAgentActive(false)
    })

    // assistant_message — error/reconnect notices and agent task speak callbacks
    on('assistant_message', ({ text }) => {
      if (!text || isAmeDupe(text)) return
      setMessages(prev => {
          const trimmed = stripPunc(text.toLowerCase())
        for (let i = prev.length - 1; i >= Math.max(0, prev.length - 5); i--) {
          const m = prev[i]
          if (m.role === 'ame' && m.text) {
              const mTrimmed = stripPunc(m.text.toLowerCase())
              if (mTrimmed === trimmed || (trimmed.length > 12 && (mTrimmed.includes(trimmed) || trimmed.includes(mTrimmed)))) return prev
          }
        }
        const id = `m${++msgIdRef.current}`
        markUnreadIfHidden()
        return [...prev.slice(-80), { id, role: 'ame', text, ts: Date.now(), seq: ++msgSeqRef.current }]
      })
      markAmeFinal(text)
      setMsgCount(c => c + 1)
      setIsTyping(false)
      agentActiveRef.current = false
      setAgentActive(false)
    })

    on('ame_split_bubble', () => {
      // Previously this reset liveAmeMsgId.current to null, which caused the
      // post-tool response to open a brand-new bubble — making the UI look
      // fragmented (pre-tool text in one bubble, confirmation in another).
      // We intentionally do nothing here: the existing live bubble stays open
      // and the post-tool text simply continues appending to it, keeping the
      // response seamless. The bubble is finalized normally at ame_response_chunk
      // with final:true.
    })

    on('tool_executing', ({ action }) => {
      agentActiveRef.current = true
      setAgentActive(true)
      setAmeState('thinking')
    })

    on('provider_changed', ({ provider, offline }) => {
      setActiveProvider(provider)
      setIsOffline(!!offline)
    })
    on('screenshot_taken', ({ path }) => {
      addMsg('screenshot', path)
      addToastRef.current('screenshot', 'Screenshot captured')
    })

    // Proactive screen watcher — AMÉ noticed something on the screen
    on('proactive_message', ({ text, mode }) => {
      if (!text) return
      // Strip any leftover URGENT:/PASSIVE: prefix from the display text
      let cleanText = text
      if (/^(URGENT|PASSIVE)\s*:\s*/i.test(cleanText)) {
        cleanText = cleanText.replace(/^(URGENT|PASSIVE)\s*:\s*/i, '')
      }
      
      // Strip any "Reasoning:" or extra lines the AI tries to sneak in
      cleanText = cleanText.split('\n')[0].trim()

      if (!cleanText) return
      const id = `m${++msgIdRef.current}`
      setMessages(prev => [...prev.slice(-80), {
        id, role: 'ame', text: cleanText, ts: Date.now(), seq: ++msgSeqRef.current,
        proactive: true,
        proactiveMode: mode || 'passive',   // 'urgent' or 'passive'
      }])
      setMsgCount(c => c + 1)
      addToastRef.current(mode === 'urgent' ? 'warning' : 'proactive', cleanText)
    })
    on('error',            ({ message }) => {
      addMsg('system', `Error: ${message}`)
      addToastRef.current('warning', message)
    })
    on('audio_devices',    ({ inputs, outputs }) => setAudioDevices({ inputs: inputs || [], outputs: outputs || [] }))
    on('session_dropped', () => {
      setAmeState('idle')
      setIsTyping(false)
      liveAmeMsgId.current  = null
      addToastRef.current('warning', 'Session dropped \u2014 reconnecting...')
    })
    on('focus_summary', ({ summary, count, messages }) => {
      if (summary) addToastRef.current('info', summary)
    })
    // Double clap detected — bring window to front
    on('dark_mode_triggered', () => {
      window.electronAPI?.focus()
      addToastRef.current('clap', 'Double clap detected')
    })
    // After dark mode actions complete — minimize so opened apps are visible
    on('minimize_after_dark_mode', () => {
      setTimeout(() => window.electronAPI?.close(), 3000) // This now hides her entirely to the tray!
    })
    return () => {
      // Null the ref first so any in-flight handlers that read socketRef.current
      // see null immediately and don't attempt to re-use the dying socket.
      socketRef.current = null
      sock.removeAllListeners()
      sock.disconnect()
    }
  }, [])

  useEffect(() => {
    if (chatScrollRef.current) chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight
  }, [messages, isTyping, chatVisible])

  const resetToIdle = useCallback(() => {
    setAmeState('idle')
    setIsMicActive(false)
    setIsTyping(false)
    if (watchdogRef.current) { clearInterval(watchdogRef.current); watchdogRef.current = null }
  }, [])

  const triggerMic = useCallback(() => {
    socketRef.current?.emit('manual_listen')
    setIsMicActive(true)
    setAmeState('listening')
    lastTranscriptTs.current = Date.now()
    // Watchdog: if no transcript arrives within 10s, reset to idle (BUG 3)
    if (watchdogRef.current) clearInterval(watchdogRef.current)
    watchdogRef.current = setInterval(() => {
      const silent = Date.now() - lastTranscriptTs.current > 10000
      if (silent) resetToIdle()
    }, 2000)
  }, [resetToIdle])

  const toggleMute = useCallback(() => {
    const newMuted = !isMuted
    setIsMuted(newMuted)
    socketRef.current?.emit('set_mute', { muted: newMuted })
    setAmeState(newMuted ? 'muted' : 'listening')
  }, [isMuted])

  // Keydown shortcuts — defined after triggerMic/toggleMute so closures are valid
  useEffect(() => {
    const h = e => {
      if (e.code === 'Space' && !['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)) { e.preventDefault(); triggerMic() }
      if (e.code === 'F4') { e.preventDefault(); toggleMute() }
      if (e.code === 'F6') { e.preventDefault(); if (window.__exportOrbLogo) window.__exportOrbLogo(2048) }
      if (e.code === 'F7') { e.preventDefault(); if (window.__exportOrbGif) window.__exportOrbGif(512, 3, 25) }
    }
    window.addEventListener('keydown', h); return () => window.removeEventListener('keydown', h)
  }, [triggerMic, toggleMute])

  // Audio level meter — poll /audio-level every 200ms while connected
  useEffect(() => {
    if (!connected) return
    const id = setInterval(() => {
      const controller = new AbortController()
      setTimeout(() => controller.abort(), 2000)
      fetch(`${BACKEND_URL}/audio-level`, { signal: controller.signal })
        .then(r => r.json())
        .then(d => setMicRms(d.rms || 0))
        .catch(() => {})
    }, 200)
    return () => clearInterval(id)
  }, [connected])

  const handleVoiceChange = v => {
    setSelectedVoice(v)
    localStorage.setItem('ame_voice', v)
    socketRef.current?.emit('set_voice', { voice: v })
  }

  const handleLanguageChange = code => {
    setLanguage(code)
    localStorage.setItem('ame_language', code)
    socketRef.current?.emit('set_language', { language: code })
    // Instruct the live session to switch response language immediately
    socketRef.current?.emit('set_language_instruction', { language: code })
  }

  // Generate full theme and apply all CSS variables whenever accent or shade changes
  useEffect(() => {
    const t = generateTheme(accentColor, bgShade)
    setTheme(t)
    applyTheme(t)
  }, [accentColor, bgShade])

  const handleAccentChange = (color) => {
    setAccentColor(color)
    localStorage.setItem('ame_accent_color', color)
  }

  const handleShadeChange = (shade) => {
    setBgShade(shade)
    localStorage.setItem('ame_bg_shade', shade)
  }

  const openSettings = () => {
    setSettingsOpen(true)
    setSettingsTab('voice')
  }

  const toggleChat = useCallback(() => {
    setChatVisible(prev => {
      const next = !prev
      localStorage.setItem('ame_chat_visible', String(next))
      if (next) {
        setChatUnread(false)
        // Scroll to bottom after chat becomes visible — rAF waits for paint
        requestAnimationFrame(() => {
          if (chatScrollRef.current) chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight
        })
      }
      return next
    })
  }, [])

  const sendMsg = useCallback(() => {
    const text = inputText.trim()
    if (!text || !connected) return
    setIsTyping(true); setAmeState('thinking')
    setInputText('')
    socketRef.current?.emit('user_message', { text, language: languageRef.current, style: responseStyle })
  }, [inputText, connected, responseStyle])

  const sendQuick = cmd => {
    if (!connected) return
    setIsTyping(true); setAmeState('thinking')
    socketRef.current?.emit('user_message', { text: cmd, language: languageRef.current, style: responseStyle })
  }

  const handleWhyClick = useCallback((proactiveText) => {
    if (!connected) return
    const snippet = proactiveText.length > 200 ? proactiveText.slice(0, 200) + '…' : proactiveText
    const whyMsg = `You just told me: "${snippet}"\n\nWhy? Explain what you noticed, why it matters, and what I should know about it. Teach me.`
    setIsTyping(true); setAmeState('thinking')
    socketRef.current?.emit('user_message', { text: whyMsg, language: languageRef.current, style: responseStyle })
  }, [connected, responseStyle])

  const meta = getStateMeta(ameState, language)
  const t = TRANSLATIONS[language] || TRANSLATIONS.en
  const hasMessages = messages.length > 0

  // Orb opacity based on state
  const orbOpacity = !ameState || ameState === 'idle' ? 0.18
    : ameState === 'speaking' ? 0.4
    : 0.3

  // ── Welcome / setup gate ─────────────────────────────────
  if (envReady === false) {
    return <WelcomePage onComplete={() => setEnvReady(true)} />
  }

  // ── Connection screen — shown while waiting or after timeout ──
  if (!connected) {
    return (
      <div style={{
        position: 'fixed', inset: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'var(--ame-bg)', flexDirection: 'column', gap: 16,
      }}>
        <div className="bg-scanlines" />
        <div style={{ position: 'relative', zIndex: 10, textAlign: 'center' }}>
          {connTimeout ? (
            <>
              <WifiOff size={36} style={{ color: 'var(--ame-rose)', marginBottom: 16 }} />
              <h2 style={{ fontSize: 16, fontWeight: 600, fontFamily: 'var(--ame-mono)', color: 'var(--ame-text)', marginBottom: 8, letterSpacing: '0.1em' }}>
                CONNECTION FAILED
              </h2>
              <p style={{ fontSize: 12, fontFamily: 'var(--ame-mono)', color: 'var(--ame-text-tertiary)', marginBottom: 20, lineHeight: 1.8 }}>
                backend is taking longer than expected — retrying...
              </p>
              <button
                className="btn-ghost"
                onClick={() => { setConnTimeout(false); socketRef.current?.connect() }}
              >
                retry now
              </button>
            </>
          ) : (
            <>
              <Loader2 size={36} style={{ color: 'var(--ame-accent)', marginBottom: 16, animation: 'spin 1s linear infinite' }} />
              <h2 style={{ fontSize: 16, fontWeight: 600, fontFamily: 'var(--ame-mono)', color: 'var(--ame-text)', marginBottom: 8, letterSpacing: '0.1em' }}>
                CONNECTING
              </h2>
              <p style={{ fontSize: 12, fontFamily: 'var(--ame-mono)', color: 'var(--ame-text-tertiary)', lineHeight: 1.8 }}>
                starting up...
              </p>
            </>
          )}
        </div>
      </div>
    )
  }

  // ── Portal layer — rendered directly on document.body,
  //    completely outside the app layout tree so no parent
  //    overflow/transform can ever affect position:fixed ──────
  const portalLayer = createPortal(
    <>
      {/* placeholder — orb moved into app tree for correct z-index stacking */}

      {/* Orb rings — hidden in orb mode (orb mode has its own effects) */}
      {chatVisible && ameState === 'listening' && (
        <><div className="orb-pulse-ring" /><div className="orb-pulse-ring" /></>
      )}
      {chatVisible && ameState === 'thinking' && (
        <><div className="orb-thinking-arc" /><div className="orb-thinking-arc" /></>
      )}

      {/* Tools backdrop */}
      <div
        onClick={() => setToolsOpen(false)}
        style={{
          position: 'fixed', inset: 0,
          background: 'rgba(0,0,0,0.75)',
          backdropFilter: 'blur(8px)',
          WebkitBackdropFilter: 'blur(8px)',
          zIndex: 90,
          display: toolsOpen ? 'block' : 'none',
        }}
      />

      {/* ══════ SETTINGS PAGE (full screen) ══════ */}
      <AnimatePresence>
        {settingsOpen && (
          <SettingsPanel
            settingsTab={settingsTab} setSettingsTab={setSettingsTab} setSettingsOpen={setSettingsOpen}
            t={t}
            selectedVoice={selectedVoice} handleVoiceChange={handleVoiceChange}
            responseStyle={responseStyle} setResponseStyle={setResponseStyle} socketRef={socketRef}
            language={language} handleLanguageChange={handleLanguageChange}
            accentColor={accentColor} handleAccentChange={handleAccentChange} bgShade={bgShade} handleShadeChange={handleShadeChange}
            chatVisible={chatVisible} toggleChat={toggleChat}
            screenWatcherOn={screenWatcherOn} setScreenWatcherOn={setScreenWatcherOn}
            codeAwarenessOn={codeAwarenessOn} setCodeAwarenessOn={setCodeAwarenessOn}
            newsEnabled={newsEnabled} setNewsEnabled={setNewsEnabled}
            memoryEnabled={memoryEnabled} setMemoryEnabled={setMemoryEnabled}
            setMessages={setMessages} setMsgCount={setMsgCount}
            permissionLevel={permissionLevel} setPermissionLevel={setPermissionLevel}
            clapEnabled={clapEnabled} setClapEnabled={setClapEnabled} clapAction={clapAction} setClapAction={setClapAction}
            activeProvider={activeProvider} sessionStart={sessionStart}
          />
        )}
      </AnimatePresence>
    </>,
    document.body
  )

  return (
    <>
      {portalLayer}

    <div style={{ position: 'fixed', inset: 0, display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--ame-bg)' }}>

      {/* Background layers */}
      <div className="bg-scanlines" />

      {/* Orb — fades in/out with AnimatePresence so unmount is animated */}
      <AnimatePresence>
        {(!chatVisible || !isMuted) && (
          <motion.div
            key="orb"
            initial={{ opacity: 0, scale: 0.88 }}
            animate={{
              opacity: !chatVisible ? 1 : (ameState === 'idle' ? 0.6 : 1),
              scale: !chatVisible ? 1.18 : 1,
            }}
            exit={{ opacity: 0, scale: 0.88 }}
            transition={{ duration: 0.5, ease: [0.4, 0, 0.2, 1] }}
            style={{
              position: 'fixed',
              top: '50%',
              left: '50%',
              x: '-50%',
              y: '-50%',
              width: 380,
              height: 380,
              zIndex: chatVisible ? 1 : 5,
              pointerEvents: 'none',
            }}
          >
            <OrbScene
              state={ameState}
              size={380}
              accentColor={accentColor}
              orbMode={!chatVisible}
            />
            {!chatVisible && ameState === 'listening' && (
              <>
                <div className="orb-mode-glow-listening" />
                <div className="orb-mode-glow-listening" />
              </>
            )}
            {!chatVisible && ameState === 'speaking' && (
              <div className="orb-mode-glow-speaking" />
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Orb-mode state label — visible only when chat is hidden, below the orb */}
      <div className="orb-mode-state" style={{
        top: 'calc(50% + 230px)',
        opacity: chatVisible ? 0 : 1,
        transition: 'opacity 0.4s cubic-bezier(0.4, 0, 0.2, 1) 0.15s',
      }}>
        <span className="orb-mode-state-label" style={{
          color: isMuted ? 'var(--ame-rose)' : meta.color,
        }}>
          {isMuted ? t.muted : meta.label}
        </span>
      </div>

      {/* ── Title bar ────────────────────────────────────────── */}
      <div className="titlebar">
        {/* Left: brand */}
        <div className="titlebar-nodrag" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span className="titlebar-brand">AMÉ</span>
        </div>

        {/* Center: state label + mute badge */}
        <div className="titlebar-state">
          <div className="status-dot" style={{ background: isMuted ? 'var(--ame-rose)' : meta.color }} />
          <span className="titlebar-state-label" style={{ color: isMuted ? 'var(--ame-rose)' : meta.color }}>
            {isMuted ? t.muted : meta.label}
          </span>
          {isMuted && (
            <span style={{
              fontSize: 9, fontFamily: 'var(--ame-mono)', letterSpacing: '0.1em',
              color: 'var(--ame-rose)', background: 'var(--ame-rose-dim)',
              borderRadius: 4, padding: '2px 6px', marginLeft: 6,
            }}>
              F4
            </span>
          )}
        </div>

        {/* Right: conn + settings + win controls */}
        <div className="titlebar-nodrag" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginRight: 6 }}>
            {connected
              ? <Wifi size={11} style={{ color: isOffline ? 'var(--ame-amber)' : 'var(--ame-green)' }} />
              : <WifiOff size={11} style={{ color: 'var(--ame-rose)' }} />}
            <span style={{ fontFamily: 'var(--ame-mono)', fontSize: 10, color: connected ? (isOffline ? 'var(--ame-amber)' : 'var(--ame-text-tertiary)') : 'var(--ame-rose)', letterSpacing: '0.05em' }}>
              {connected ? (isOffline ? 'OFFLINE' : t.online) : t.offline}
            </span>
          </div>
          <button className="btn-icon" style={{ position: 'relative' }}
            onClick={toggleChat}
            title={chatVisible ? 'Hide chat' : 'Show chat'}>
            <MessageSquare size={13} style={{ opacity: chatVisible ? 1 : 0.4 }} />
            {chatUnread && !chatVisible && (
              <span style={{
                position: 'absolute', top: 3, right: 3,
                width: 6, height: 6, borderRadius: '50%',
                background: 'var(--ame-accent)',
                boxShadow: '0 0 6px var(--ame-accent)',
              }} />
            )}
          </button>
          <button className="btn-icon"
            onClick={() => setHistoryOpen(h => !h)}
            title="Chat history">
            <Clock size={13} />
          </button>
          <button className="btn-icon" style={{
            background: focusMode ? 'var(--ame-accent-ghost)' : 'transparent',
            position: 'relative',
          }}
            onClick={() => {
              const next = !focusMode
              setFocusMode(next)
              socketRef.current?.emit('set_focus_mode', { enabled: next })
            }}
            title={focusMode ? 'Exit focus mode' : 'Enter focus mode'}>
            <Eye size={13} style={{ color: focusMode ? 'var(--ame-accent)' : undefined }} />
            {focusMode && <div style={{
              position: 'absolute', top: 2, right: 2,
              width: 5, height: 5, borderRadius: '50%',
              background: 'var(--ame-accent)',
              boxShadow: '0 0 6px var(--ame-accent)',
              animation: 'pulse 2s infinite',
            }} />}
          </button>
          <button className="btn-icon" style={{ background: sysMonitorOpen ? 'var(--ame-accent-ghost)' : 'transparent' }}
            onClick={() => setSysMonitorOpen(v => !v)}
            title="System monitor">
            <Cpu size={13} style={{ color: sysMonitorOpen ? 'var(--ame-accent)' : undefined }} />
          </button>
          <button className="btn-icon" style={{ background: schedulesOpen ? 'var(--ame-accent-ghost)' : 'transparent' }}
            onClick={() => setSchedulesOpen(v => !v)}
            title="Schedules">
            <Calendar size={13} style={{ color: schedulesOpen ? 'var(--ame-accent)' : undefined }} />
          </button>
          <button className="btn-icon"
            onClick={openSettings}>
            <Settings size={13} />
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginLeft: 4 }}>
            <button
              onClick={() => window.electronAPI?.minimize()}
              style={{
                width: 28, height: 28, borderRadius: '50%',
                border: 'none',
                background: 'transparent', color: 'var(--ame-text-secondary)',
                cursor: 'pointer', display: 'flex',
                alignItems: 'center', justifyContent: 'center', fontSize: 14,
              }}
              onMouseEnter={e => { e.currentTarget.style.background = 'var(--ame-bg-hover)'; e.currentTarget.style.color = 'var(--ame-text)'; }}
              onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--ame-text-secondary)'; }}
            >─</button>
            <button
              onClick={() => window.electronAPI?.close()}
              style={{
                width: 28, height: 28, borderRadius: '50%',
                border: 'none',
                background: 'transparent', color: 'var(--ame-text-secondary)',
                cursor: 'pointer', display: 'flex',
                alignItems: 'center', justifyContent: 'center', fontSize: 14,
              }}
              onMouseEnter={e => { e.currentTarget.style.background = 'var(--ame-rose-dim)'; e.currentTarget.style.color = 'var(--ame-rose)'; }}
              onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--ame-text-secondary)'; }}
            >✕</button>
          </div>
        </div>
      </div>

      {/* ── Main content — full screen, orb centered behind ─────── */}
      <div style={{
        flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden',
        position: 'relative', zIndex: 10,
        opacity: chatVisible ? 1 : 0,
        transform: chatVisible ? 'translateY(0)' : 'translateY(30px)',
        pointerEvents: chatVisible ? undefined : 'none',
        transition: 'opacity 0.3s cubic-bezier(0.4, 0, 0.2, 1), transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
      }}>

        {/* Chat area — full width, scrollable, solid bubbles over orb */}
        <div ref={chatScrollRef} className="chat-area" style={{
          flex: 1, overflowY: 'auto',
        }}>
          {!hasMessages && !isTyping ? (
            <div className="empty-state">
              <div style={{
                fontFamily: 'var(--ame-mono)', fontSize: 11,
                letterSpacing: '0.2em', color: 'var(--ame-text-tertiary)',
                textTransform: 'uppercase', marginBottom: 8,
              }}>
                speak a command or type below
              </div>
              <div style={{
                width: 48, height: 1,
                background: 'linear-gradient(90deg, transparent, var(--ame-accent), transparent)',
                marginBottom: 12,
              }} />
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, justifyContent: 'center' }}>
                {SUGGESTIONS.map(s => (
                  <button key={s.label} className="suggestion-chip" onClick={() => sendQuick(s.send)}>
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <AnimatePresence initial={false}>
              <MemoizedMessageList messages={messages} onWhyClick={handleWhyClick} />
              {isTyping && <TypingDots key="typing" />}
            </AnimatePresence>
          )}
        </div>

        {/* Input bar */}
        <div className="input-bar">
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <button
              className={`mic-btn ${!isMuted ? 'active' : ''}`}
              onClick={toggleMute}
              title={isMuted ? 'Turn on voice' : 'Turn off voice'}
              style={{ opacity: isMuted ? 0.45 : 1, transition: 'opacity 0.3s ease' }}
            >
              {isMuted ? <MicOff size={16} /> : <Mic size={16} />}
            </button>
            {/* Audio level ring — pulses with mic input when voice is on */}
            {!isMuted && connected && (
              <div style={{
                position: 'absolute', inset: -3, borderRadius: '50%',
                border: `2px solid var(--ame-accent)`,
                opacity: Math.min(micRms / 3000, 1),
                transform: `scale(${1 + Math.min(micRms / 20000, 0.4)})`,
                pointerEvents: 'none', transition: 'transform 80ms, opacity 80ms',
              }} />
            )}
          </div>
          <div className="chat-input-wrap">
            <input
              ref={inputRef}
              className="chat-input"
              dir="auto"
              value={inputText}
              onChange={e => setInputText(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMsg() } }}
              placeholder={t.placeholder}
            />
          </div>
          <AnimatePresence>
            {inputText.trim() && (
              <motion.button
                initial={{ opacity: 0, scale: 0.7 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.7 }}
                transition={{ duration: 0.15 }}
                className="send-btn"
                onClick={sendMsg}
                disabled={!connected}
              >
                <Send size={15} />
              </motion.button>
            )}
          </AnimatePresence>
        </div>

        {/* Status line */}
        <div className="status-line">
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Cpu size={10} style={{ opacity: 0.6, color: isOffline ? 'var(--ame-amber)' : undefined }} />
            <span style={{ color: isOffline ? 'var(--ame-amber)' : 'var(--ame-text-tertiary)', fontWeight: 500 }}>{activeProvider}</span>
            <span style={{
              fontSize: 9, fontFamily: 'var(--ame-mono)', letterSpacing: '0.08em',
              color: isMuted ? 'var(--ame-rose)' : 'var(--ame-text-ghost)',
              background: isMuted ? 'var(--ame-rose-dim)' : 'transparent',
              borderRadius: 4, padding: '2px 6px', cursor: 'pointer', marginLeft: 8
            }} onClick={toggleMute} title="F4 to toggle mute">
              {isMuted ? t.micOff : t.micOn}
            </span>
            {/* Audio level dot — pulses with mic input (BUG 1 diagnostics) */}
            {!isMuted && connected && (
              <span title={`Mic level: ${Math.round(micRms)}`} style={{
                display: 'inline-block', width: 6, height: 6, borderRadius: '50%',
                background: micRms > MIN_RMS_UI ? 'var(--ame-accent)' : 'var(--ame-border)',
                boxShadow: micRms > MIN_RMS_UI ? '0 0 4px var(--ame-accent)' : 'none',
                transition: 'background 150ms, box-shadow 150ms',
              }} />
            )}
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Clock size={10} style={{ opacity: 0.6 }} />
            <UptimeCounter start={sessionStart} />
            <span style={{ opacity: 0.5, marginLeft: 6 }}>{messageCount} msg</span>
          </span>
        </div>
      </div>

      <ToolsPanel open={toolsOpen} onClose={() => setToolsOpen(false)} socket={socketRef.current} />
      <ChatHistory open={historyOpen} onClose={() => setHistoryOpen(false)} socket={socketRef.current} />
      <SystemMonitor open={sysMonitorOpen} onClose={() => setSysMonitorOpen(false)} socket={socketRef.current} />
      <SchedulesPanel open={schedulesOpen} onClose={() => setSchedulesOpen(false)} socket={socketRef.current} />
      <Toasts toasts={toasts} removeToast={removeToast} />
    </div>
    </>
  )
}

const MemoizedMessageList = React.memo(({ messages, onWhyClick }) => {
  const sorted = [...messages].sort((a, b) => (a.seq || 0) - (b.seq || 0))
  const total = sorted.length
  return (
    <>{sorted.map((m, i) => <Bubble key={m.id} msg={m} age={total - 1 - i} onWhyClick={onWhyClick} />)}</>
  )
})
