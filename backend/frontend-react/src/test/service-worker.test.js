import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { runInNewContext } from 'node:vm'
import { beforeEach, expect, it, vi } from 'vitest'

const source = readFileSync(resolve('public/sw.js'), 'utf8')
let handlers, caches, fetch

beforeEach(() => {
  handlers = {}
  caches = { match: vi.fn(), open: vi.fn(), keys: vi.fn(), delete: vi.fn() }
  fetch = vi.fn()
  runInNewContext(source, {
    self: { addEventListener: (event, handler) => { handlers[event] = handler }, skipWaiting: vi.fn(), clients: { claim: vi.fn() } },
    caches, fetch,
  })
})

it.each([
  ['GET', 'https://example.invalid/api/v1/auth/me'],
  ['GET', 'https://example.invalid/api/v1/inventory/products?search=widget'],
  ['POST', 'https://example.invalid/assets/file'],
  ['PUT', 'https://example.invalid/assets/file'],
  ['DELETE', 'https://example.invalid/assets/file'],
])('does not intercept %s %s', (method, url) => {
  const event = { request: { method, url }, respondWith: vi.fn() }
  handlers.fetch(event)
  expect(event.respondWith).not.toHaveBeenCalled()
  expect(caches.match).not.toHaveBeenCalled()
  expect(fetch).not.toHaveBeenCalled()
})

it.each([true, false])('serves a static asset with cache hit=%s', async hit => {
  const cached = { body: 'cached' }
  const network = { body: 'network' }
  caches.match.mockResolvedValue(hit ? cached : undefined)
  fetch.mockResolvedValue(network)
  const request = { method: 'GET', url: 'https://example.invalid/assets/main.js' }
  const event = { request, respondWith: vi.fn() }
  handlers.fetch(event)
  await expect(event.respondWith.mock.calls[0][0]).resolves.toBe(hit ? cached : network)
  expect(caches.match).toHaveBeenCalledWith(request)
  if (hit) expect(fetch).not.toHaveBeenCalled()
  else expect(fetch).toHaveBeenCalledWith(request)
})
