import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev proxy: the SPA calls /api/* and Vite forwards to the FastAPI server on :8000.
// Keeps the frontend origin-clean and matches the CORS allow-list.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
