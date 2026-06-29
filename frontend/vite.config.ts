import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      // Forward AI-service calls (and the backend's authed /api/v1/*
      // routes) to the local docker-compose services so the dev server
      // on :5173 can be used without going through nginx on :8082.
      //
      // Both `/ai/...` (when callers pass the bare path) and
      // `/api/v1/ai/...` (when callers pass the same path with
      // axios's `baseURL: /api/v1` prefix) must reach the AI
      // service — otherwise `usePipelineAnalyze` returns 404
      // because the Go backend has no `/api/v1/ai/...` routes.
      //
      // The AI-service target uses `host.docker.internal` (or
      // `ai-service`, the docker-compose service name) because
      // `localhost` inside the frontend container points at the
      // container itself, not the host. Docker Desktop / WSL2
      // resolve `host.docker.internal`; on Linux compose networks
      // the service name is the canonical DNS name.
      '/ai/': {
        target: 'http://ai-service:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/ai\//, '/api/'),
      },
      '/api/v1/ai/': {
        target: 'http://ai-service:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/v1\/ai\//, '/api/'),
      },
      '/api/v1/': {
        target: 'http://backend:8080',
        changeOrigin: true,
      },
    },
  },
})