import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig(async ({ command }) => {
  const plugins = [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: false,
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg}'],
        runtimeCaching: [],
        cleanupOutdatedCaches: true,
      },
    }),
  ]

  // The interceptor is development-only and lives outside the frontend
  // Docker build context. Load it only for the Vite dev server so production
  // image builds remain self-contained.
  if (command === 'serve') {
    const { jevInterceptPlugin } = await import(
      '../../.opencode/skills/jev-intercept/scripts/frontend_intercept.js'
    )
    plugins.push(jevInterceptPlugin())
  }

  return {
    plugins,
    server: {
      port: 3000,
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
          ws: true,
        },
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: false,
    },
  }
})
