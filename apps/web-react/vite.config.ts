import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // the gateway's CORS policy allows exactly http://localhost:5173: fail instead of moving to another port
  server: { port: 5173, strictPort: true },
})
