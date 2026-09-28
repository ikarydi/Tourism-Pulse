import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        // Charting and map libraries change far less often than app code:
        // separate files let browsers keep them cached across releases.
        manualChunks(id: string) {
          if (!id.includes('node_modules')) return undefined
          if (/[\\/](@observablehq|d3-[^\\/]+|d3|interval-tree-1d|isoformat)[\\/]/.test(id)) return 'charts'
          if (/[\\/](leaflet|react-leaflet|@react-leaflet)[\\/]/.test(id)) return 'maps'
          if (/[\\/](react|react-dom|scheduler)[\\/]/.test(id)) return 'react'
          return undefined
        },
      },
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
