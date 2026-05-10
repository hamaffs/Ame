import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

export default defineConfig({
  plugins: [react()],
  base: './',
  envDir: false,
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        orb:  resolve(__dirname, 'orb.html'),
      },
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    host: true,
    watch: {
      ignored: [
        '**/.env',
        '**/.env.*',
        '**/backend/**',
        '**/.ame/**',
        '**/pretrained_models/**',
        '**/output/**'
      ]
    }
  }
})
