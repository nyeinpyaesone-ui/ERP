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

it('renders route content passed by the application router', () => {
  useAuth.mockReturnValue({ user: { name: 'Alex', email: 'alex@example.com' }, logout: vi.fn() })
  render(
    <MemoryRouter initialEntries={['/crm']}>
      <Layout><h1>CRM route content</h1></Layout>
    </MemoryRouter>,
  )
  expect(screen.getByRole('main')).toContainElement(
    screen.getByRole('heading', { name: 'CRM route content' }),
  )
})

it('exposes accessible mobile navigation controls and active route state', () => {
  useAuth.mockReturnValue({ user: { name: 'Alex' }, logout: vi.fn() })
  render(
    <MemoryRouter initialEntries={['/crm']}>
      <Layout />
    </MemoryRouter>,
  )

  const openButton = screen.getByRole('button', { name: 'Open navigation menu' })
  expect(openButton).toHaveAttribute('aria-expanded', 'false')
  expect(screen.getByRole('link', { name: 'CRM' })).toHaveAttribute('aria-current', 'page')

  fireEvent.click(openButton)
  expect(openButton).toHaveAttribute('aria-expanded', 'true')
  fireEvent.click(screen.getByRole('button', { name: 'Close navigation menu' }))
  expect(openButton).toHaveAttribute('aria-expanded', 'false')
})

it('logs out through auth context, closes the menu and navigates to login', () => {
  const logout = vi.fn()
  useAuth.mockReturnValue({ user: { name: 'Alex', email: 'alex@example.com' }, logout })
  render(<MemoryRouter initialEntries={['/crm']}><Layout /><Location /></MemoryRouter>)
  fireEvent.click(screen.getByRole('button', { name: /Alex/ }))
  expect(screen.getByRole('menu', { name: 'User account' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('menuitem', { name: 'Sign out' }))
  expect(logout).toHaveBeenCalledOnce()
  expect(screen.getByTestId('location')).toHaveTextContent('/login')
  expect(screen.queryByRole('menu')).not.toBeInTheDocument()
})
