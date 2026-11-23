import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { expect, it, vi } from 'vitest'
import { useAuth } from '../contexts/AuthContext'
import Layout from './Layout'

vi.mock('../contexts/AuthContext', () => ({ useAuth: vi.fn() }))

function Location() {
  return <output data-testid="location">{useLocation().pathname}</output>
}

it('logs out through auth context, closes the menu and navigates to login', () => {
  const logout = vi.fn()
  useAuth.mockReturnValue({ user: { name: 'Alex', email: 'alex@example.com' }, logout })
  render(<MemoryRouter initialEntries={['/crm']}><Layout /><Location /></MemoryRouter>)
  fireEvent.click(screen.getByRole('button', { name: /Alex/ }))
  fireEvent.click(screen.getByRole('button', { name: 'Sign out' }))
  expect(logout).toHaveBeenCalledOnce()
  expect(screen.getByTestId('location')).toHaveTextContent('/login')
  expect(screen.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument()
})
