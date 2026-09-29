import React from 'react'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuth } from './contexts/AuthContext'
import App from './App'

vi.mock('./contexts/AuthContext', () => ({
  AuthProvider: ({ children }) => children,
  useAuth: vi.fn(),
}))
// Isolate route policy from page API requests and layout rendering.
vi.mock('./components/Layout', () => ({ default: ({ children }) => <main>{children}</main> }))
vi.mock('./pages/Dashboard', () => ({ default: () => <h1>Dashboard page</h1> }))
vi.mock('./pages/CRM', () => ({ default: () => <h1>CRM page</h1> }))
vi.mock('./pages/HR', () => ({ default: () => <h1>HR page</h1> }))
vi.mock('./pages/Inventory', () => ({ default: () => <h1>Inventory page</h1> }))
vi.mock('./pages/Finance', () => ({ default: () => <h1>Finance page</h1> }))
vi.mock('./pages/Projects', () => ({ default: () => <h1>Projects page</h1> }))
vi.mock('./pages/Reports', () => ({ default: () => <h1>Reports page</h1> }))
vi.mock('./pages/Analytics', () => ({ default: () => <h1>Analytics page</h1> }))
vi.mock('./pages/AIChat', () => ({ default: () => <h1>AIChat page</h1> }))
vi.mock('./pages/Documents', () => ({ default: () => <h1>Documents page</h1> }))
vi.mock('./pages/Workflows', () => ({ default: () => <h1>Workflows page</h1> }))
vi.mock('./pages/Integrations', () => ({ default: () => <h1>Integrations page</h1> }))
vi.mock('./pages/Settings', () => ({ default: () => <h1>Settings page</h1> }))
vi.mock('./pages/BulkImportExport', () => ({ default: () => <h1>BulkImportExport page</h1> }))
vi.mock('./pages/MigrationManager', () => ({ default: () => <h1>MigrationManager page</h1> }))
vi.mock('./pages/Permissions', () => ({ default: () => <h1>Permissions page</h1> }))
vi.mock('./pages/LLMManager', () => ({ default: () => <h1>LLMManager page</h1> }))
vi.mock('./pages/Search', () => ({ default: () => <h1>Search page</h1> }))
vi.mock('./pages/Login', () => ({ default: () => <h1>Login page</h1> }))

function Location() {
  return <output data-testid="location">{useLocation().pathname}</output>
}
function visit(path) {
  return render(<MemoryRouter initialEntries={[path]}><App /><Location /></MemoryRouter>)
}
beforeEach(() => {
  useAuth.mockReturnValue({ user: { role: 'user' }, loading: false, login: vi.fn(), logout: vi.fn() })
})

const restrictedRoutes = [
  ['/hr', 'HR', 'manager'], ['/finance', 'Finance', 'manager'],
  ['/reports', 'Reports', 'manager'], ['/analytics', 'Analytics', 'manager'],
  ['/workflows', 'Workflows', 'manager'], ['/integrations', 'Integrations', 'admin'],
  ['/settings', 'Settings', 'admin'], ['/bulk-import', 'BulkImportExport', 'admin'],
  ['/migrations', 'MigrationManager', 'admin'], ['/permissions', 'Permissions', 'admin'],
  ['/llm-manager', 'LLMManager', 'admin'],
]

describe('route authorization', () => {
  it('waits for authentication before rendering any page', () => {
    useAuth.mockReturnValue({ user: null, loading: true })
    visit('/hr')
    expect(screen.queryByRole('heading')).not.toBeInTheDocument()
  })

  it('shows login to an unauthenticated visitor', () => {
    useAuth.mockReturnValue({ user: null, loading: false })
    visit('/hr')
    expect(screen.getByRole('heading', { name: 'Login page' })).toBeInTheDocument()
  })

  it.each(restrictedRoutes)('denies ordinary users access to %s', (path, page) => {
    visit(path)
    expect(screen.getByRole('heading', { name: 'Dashboard page' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: `${page} page` })).not.toBeInTheDocument()
    expect(screen.getByTestId('location')).toHaveTextContent(/^\/$/)
  })

  it.each(restrictedRoutes)('allows the required role at %s', (path, page, role) => {
    useAuth.mockReturnValue({ user: { role }, loading: false })
    visit(path)
    expect(screen.getByRole('heading', { name: `${page} page` })).toBeInTheDocument()
  })

  it.each(['admin', 'superadmin', 'ADMIN', 'SuperAdmin'])('accepts %s case-insensitively', role => {
    useAuth.mockReturnValue({ user: { role }, loading: false })
    visit('/permissions')
    expect(screen.getByRole('heading', { name: 'Permissions page' })).toBeInTheDocument()
  })

  it.each(['manager', 'viewer', undefined])('denies role %s access to admin settings', role => {
    useAuth.mockReturnValue({ user: { role }, loading: false })
    visit('/settings')
    expect(screen.getByRole('heading', { name: 'Dashboard page' })).toBeInTheDocument()
  })

  it.each([['/crm', 'CRM'], ['/inventory', 'Inventory'], ['/projects', 'Projects'],
    ['/ai-chat', 'AIChat'], ['/documents', 'Documents'], ['/search', 'Search']])(
    'allows an authenticated user at %s', (path, page) => {
      visit(path)
      expect(screen.getByRole('heading', { name: `${page} page` })).toBeInTheDocument()
    },
  )

  it('redirects unknown routes home', () => {
    visit('/unknown')
    expect(screen.getByRole('heading', { name: 'Dashboard page' })).toBeInTheDocument()
    expect(screen.getByTestId('location')).toHaveTextContent(/^\/$/)
  })
})
