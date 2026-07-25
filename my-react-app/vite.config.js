import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  publicDir: 'public',
  base: '/',
  server: {
    proxy: {
      '/api': { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/uploads': { target: 'http://127.0.0.1:5000', changeOrigin: true },
      // Socket.IO WebSocket handshake — same-origin via proxy avoids CORS issues.
      '/socket.io': { target: 'http://127.0.0.1:5000', ws: true, changeOrigin: true },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          stripe: ['@stripe/stripe-js', '@stripe/react-stripe-js'],
          'socket-io': ['socket.io-client'],
          motion: ['framer-motion'],
        },
      },
    },
  },
})
