import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const target = loadEnv(mode, '.', '').VITE_BACKEND_PROXY_TARGET || 'http://localhost:8000'
  return {
    plugins: [react()],
    build: {
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes('/node_modules/react/') || id.includes('/node_modules/react-dom/')) return 'react'
            if (id.includes('/node_modules/recharts/')) return 'charts'
            if (id.includes('/node_modules/leaflet/') || id.includes('/node_modules/react-leaflet/')) return 'maps'
          },
        },
      },
    },
    server: { host: '0.0.0.0', port: 5173, proxy: { '/api': target, '/uploads': target } },
  }
})
