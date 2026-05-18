import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  publicDir: 'public',
  base: '/',
  // Optional: uncomment proxy if VITE_API_BASE points to local Flask (127.0.0.1:5000).
  // Default frontend uses Railway via VITE_API_BASE in .env.
  // server: {
  //   proxy: {
  //     '/api': { target: 'http://127.0.0.1:5000', changeOrigin: true },
  //     '/flask': {
  //       target: 'http://127.0.0.1:5000',
  //       changeOrigin: true,
  //       rewrite: (path) => path.replace(/^\/flask/, ''),
  //     },
  //   },
  // },
})
