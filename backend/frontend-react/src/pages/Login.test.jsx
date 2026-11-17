import React from 'react'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuth } from '../contexts/AuthContext'
import Login from './Login'

vi.mock('../contexts/AuthContext', () => ({ useAuth: vi.fn() }))
const login = vi.fn()

beforeEach(() => {
  login.mockReset()
  useAuth.mockReturnValue({ login })
})

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<h1>Dashboard destination</h1>} />
      </Routes>
    </MemoryRouter>,
  )
}

function enterCredentials() {
  fireEvent.change(screen.getByPlaceholderText('you@company.com'), { target: { value: 'alex@example.com' } })
  fireEvent.change(screen.getByPlaceholderText('••••••••'), { target: { value: 'password' } })
}

describe('Login', () => {
  it('waits for authentication, disables submission, then navigates home', async () => {
    let finish
    login.mockReturnValue(new Promise(resolve => { finish = resolve }))
    renderLogin()
    enterCredentials()
    const button = screen.getByRole('button', { name: 'Sign In' })
    fireEvent.click(button)
    expect(login).toHaveBeenCalledWith({ username: 'alex@example.com', password: 'password' })
    expect(button).toBeDisabled()
    expect(screen.queryByText('Dashboard destination')).not.toBeInTheDocument()
    await act(async () => finish({ id: 7 }))
    expect(await screen.findByText('Dashboard destination')).toBeInTheDocument()
  })

  it('registers through the auth context including full name', async () => {
    login.mockResolvedValue({ id: 7 })
    renderLogin()
    fireEvent.click(screen.getByRole('button', { name: "Don't have an account? Register" }))
    enterCredentials()
    fireEvent.change(screen.getByPlaceholderText('John Doe'), { target: { value: 'Alex User' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create Account' }))
    expect(login).toHaveBeenCalledWith({ email: 'alex@example.com', password: 'password', full_name: 'Alex User' })
    expect(await screen.findByText('Dashboard destination')).toBeInTheDocument()
  })

  it.each([
    [{ response: { data: { detail: 'Account disabled' } } }, 'Account disabled'],
    [new Error('offline'), 'Authentication failed'],
  ])('shows authentication failure and allows retry', async (error, message) => {
    login.mockRejectedValueOnce(error).mockResolvedValueOnce({ id: 7 })
    renderLogin()
    enterCredentials()
    fireEvent.click(screen.getByRole('button', { name: 'Sign In' }))
    expect(await screen.findByText(message)).toBeInTheDocument()
    expect(screen.queryByText('Dashboard destination')).not.toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('button', { name: 'Sign In' })).toBeEnabled())
    fireEvent.click(screen.getByRole('button', { name: 'Sign In' }))
    expect(await screen.findByText('Dashboard destination')).toBeInTheDocument()
    expect(login).toHaveBeenCalledTimes(2)
  })
})
