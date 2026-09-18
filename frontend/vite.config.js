import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  return {
    plugins: [react()],
    optimizeDeps: {
      // Ensure pdfjs-dist is pre-bundled so the worker URL resolves correctly
      include: ["pdfjs-dist"],
    },
    server: {
      port: 5173,
      proxy: {
        // Same-origin in dev: auth cookies and CSRF work without any CORS setup.
        // Backend routes already start with /api/v1, so no path rewrite.
        '/api': {
          target: env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000',
          changeOrigin: true,
          secure: false,
        },
      },
    },
  }
})
