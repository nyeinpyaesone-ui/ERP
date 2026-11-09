import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'
import { existsSync } from 'node:fs'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

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
    // Keep this import out of esbuild's static dependency graph: the plugin
    // lives at the repository root, outside this package's Docker context.
    // Resolve both common working directories used by local development.
    const interceptorPath = [
      resolve(process.cwd(), '../../.opencode/skills/jev-intercept/scripts/frontend_intercept.js'),
      resolve(process.cwd(), '.opencode/skills/jev-intercept/scripts/frontend_intercept.js'),
    ].find(existsSync)

    if (!interceptorPath) {
      throw new Error('Jev-Intercept dev plugin not found from the current working directory')
    }

    const interceptorUrl = pathToFileURL(interceptorPath).href
    const { jevInterceptPlugin } = await import(interceptorUrl)
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
