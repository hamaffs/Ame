import { defineConfig } from 'vite'

export default defineConfig({
  test: {
    include: ['src/**/*.test.js'],
    // S-9: DOMPurify needs a DOM to operate on — give tests jsdom.
    environment: 'jsdom',
  },
})
