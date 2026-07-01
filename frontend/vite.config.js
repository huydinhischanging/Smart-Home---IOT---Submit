import { defineConfig } from 'vite'
import fs from 'fs'
import path from 'path'

function tryRead(filePath) {
  return fs.existsSync(filePath) ? fs.readFileSync(filePath) : null
}

function resolveHttpsConfig() {
  const frontendKey = path.resolve(__dirname, 'key.pem')
  const frontendCert = path.resolve(__dirname, 'cert.pem')
  const backendKey = path.resolve(__dirname, '../backend/key.pem')
  const backendCert = path.resolve(__dirname, '../backend/cert.pem')

  const key = tryRead(frontendKey) || tryRead(backendKey)
  const cert = tryRead(frontendCert) || tryRead(backendCert)

  if (!key || !cert) {
    return false
  }

  return { key, cert }
}

export default defineConfig({
  server: {
    https: resolveHttpsConfig(),
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      // REST API
      '/api': {
        target:       'http://127.0.0.1:5000',
        changeOrigin: true,
        secure:       false,
      },
      // Socket.IO WebSocket
      '/socket.io': {
        target:       'http://127.0.0.1:5000',
        changeOrigin: true,
        secure:       false,
        ws:           true,   // ← forward WebSocket
      },
    },
  },
})
