/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'ame-bg': 'var(--ame-bg)',
        'ame-surface': 'var(--ame-bg-card)',
        'ame-border': 'var(--ame-border)',
        'ame-accent': 'var(--ame-accent)',
        'ame-accent-light': 'var(--ame-accent-light)',
        'ame-green': 'var(--ame-green)',
        'ame-cyan': 'var(--ame-cyan)',
        'ame-amber': 'var(--ame-amber)',
        'ame-rose': 'var(--ame-rose)',
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      }
    },
  },
  plugins: [],
}
