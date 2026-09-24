import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // In development the API runs on :8000; the SPA calls /api/... and Vite forwards it.
    proxy: { '/api': 'http://localhost:8000' },
  },
  build: {
    // Built files are served by FastAPI from this directory (git-ignored).
    outDir: '../backend/src/kms/static',
    emptyOutDir: true,
  },
})
