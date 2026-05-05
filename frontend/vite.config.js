import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    // Ensure pdfjs-dist is pre-bundled so the worker URL resolves correctly
    include: ["pdfjs-dist"],
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
        // Do NOT rewrite — backend routes already include /api prefix
        // e.g. /api/documents/... → http://localhost:8000/api/documents/...
      },
    },
  },
})