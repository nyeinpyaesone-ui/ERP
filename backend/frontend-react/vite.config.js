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

  // The Jev-Intercept plugin is optional and lives outside the normal frontend
  // build context. CI/test runners do not have this repo-root helper installed,
  // so Vitest and build validation should never fail just because it is absent.
  const isVitestRun = !!process.env.VITEST

  if (command === 'serve' && !isVitestRun) {
    const interceptorPath = [
      resolve(process.cwd(), '../../.opencode/skills/jev-intercept/scripts/frontend_intercept.js'),
      resolve(process.cwd(), '.opencode/skills/jev-intercept/scripts/frontend_intercept.js'),
    ].find(existsSync)

    if (interceptorPath) {
      const interceptorUrl = pathToFileURL(interceptorPath).href
      const { jevInterceptPlugin } = await import(interceptorUrl)
      plugins.push(jevInterceptPlugin())
    } else {
      console.warn('Skipping Jev-Intercept dev plugin: not found in the current workspace.')
    }
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
