import React from 'react'
import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import api from '../api/axios'
import { AuthProvider, useAuth } from './AuthContext'

vi.mock('../api/axios', () => ({ default: { get: vi.fn(), post: vi.fn() } }))

const user = { id: 7, full_name: 'Alex', role: 'user' }
const wrapper = ({ children }) => <AuthProvider>{children}</AuthProvider>

async function renderAuth() {
  const hook = renderHook(() => useAuth(), { wrapper })
  await waitFor(() => expect(hook.result.current.loading).toBe(false))
  return hook
}

beforeEach(() => {
  vi.resetAllMocks()
  localStorage.clear()
  api.post.mockResolvedValue({ data: { access_token: 'synthetic-token', user } })
})

describe('authentication requests', () => {
  it.each([
    { username: 'alex+test@example.com', password: 'a&b=+ c' },
    { email: 'alex+test@example.com', password: 'a&b=+ c' },
  ])('sends OAuth form data for $username$email and saves the session', async (credentials) => {
    const { result } = await renderAuth()
    let loggedIn
    await act(async () => { loggedIn = await result.current.login(credentials) })

    const [url, body, options] = api.post.mock.calls[0]
    expect(url).toBe('/auth/login')
    expect(body).toBeInstanceOf(URLSearchParams)
    expect(Object.fromEntries(new URLSearchParams(body.toString()))).toEqual({
      username: 'alex+test@example.com', password: 'a&b=+ c',
    })
    expect(options.headers['Content-Type']).toBe('application/x-www-form-urlencoded')
    expect(loggedIn).toEqual(user)
    expect(result.current.user).toEqual(user)
    expect(localStorage.getItem('token')).toBe('synthetic-token')
  })

  it('prefers username over email for form login', async () => {
    const { result } = await renderAuth()
    await act(async () => {
      await result.current.login({ username: 'preferred', email: 'fallback@example.com', password: 'password' })
    })
    expect(api.post.mock.calls[0][0]).toBe('/auth/login')
    expect(api.post.mock.calls[0][1].get('username')).toBe('preferred')
  })

  it('waits for JSON registration before logging in with the registered email', async () => {
    let finishRegistration
    api.post.mockReturnValueOnce(new Promise(resolve => { finishRegistration = resolve }))
    const { result } = await renderAuth()
    let pending
    act(() => {
      pending = result.current.login({ email: 'alex@example.com', password: 'password', full_name: 'Alex', role: 'superadmin' })
    })
    expect(api.post).toHaveBeenCalledWith('/auth/register', {
      email: 'alex@example.com', password: 'password', full_name: 'Alex',
    })
    await act(async () => { finishRegistration({}); await pending })
    expect(api.post.mock.calls[1][1].get('username')).toBe('alex@example.com')
    expect(result.current.user).toEqual(user)
  })

  it.each(['registration', 'login'])('propagates a failed %s without storing a session', async (phase) => {
    const error = new Error('rejected')
    const credentials = { email: 'alex@example.com', password: 'password' }
    if (phase === 'registration') {
      credentials.full_name = 'Alex'
      api.post.mockRejectedValue(error)
    } else {
      api.post.mockRejectedValue(error)
    }
    const { result } = await renderAuth()
    await act(async () => { await expect(result.current.login(credentials)).rejects.toBe(error) })
    expect(result.current.user).toBeNull()
    expect(localStorage.getItem('token')).toBeNull()
  })

  it('does not retain a session when login after successful registration fails', async () => {
    api.post.mockResolvedValueOnce({ data: user })
    api.post.mockRejectedValue(new Error('login failed'))
    const { result } = await renderAuth()
    await act(async () => {
      await expect(result.current.login({ email: 'alex@example.com', password: 'password', full_name: 'Alex' })).rejects.toThrow('login failed')
    })
    expect(api.post).toHaveBeenCalledTimes(2)
    expect(result.current.user).toBeNull()
    expect(localStorage.getItem('token')).toBeNull()
  })

  it('clears both token and user on logout after login', async () => {
    const { result } = await renderAuth()
    await act(async () => { await result.current.login({ username: 'alex', password: 'password' }) })
    act(() => result.current.logout())
    expect(result.current.user).toBeNull()
    expect(localStorage.getItem('token')).toBeNull()
  })
})
