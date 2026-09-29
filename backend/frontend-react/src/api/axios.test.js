import { afterEach, expect, it, vi } from 'vitest'

afterEach(() => vi.unstubAllEnvs())

it.each([
  ['', '/api/v1'],
  ['https://example.invalid/custom/api', 'https://example.invalid/custom/api'],
])('uses the expected API base for configuration %s', async (configured, expected) => {
  vi.resetModules()
  vi.stubEnv('VITE_API_URL', configured)
  const { default: api } = await import('./axios')
  expect(api.defaults.baseURL).toBe(expected)
})
