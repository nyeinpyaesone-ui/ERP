import React, { useState } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, Users, Package, DollarSign, Briefcase,
  BarChart2, MessageSquare, FileText, GitBranch,
  Settings, Database, Zap, Shield, Search, LogOut,
  Menu, X, ChevronDown, Building2, HelpCircle
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'CRM', href: '/crm', icon: Users },
  { name: 'HR', href: '/hr', icon: Building2 },
  { name: 'Inventory', href: '/inventory', icon: Package },
  { name: 'Finance', href: '/finance', icon: DollarSign },
  { name: 'Projects', href: '/projects', icon: Briefcase },
  { name: 'Reports', href: '/reports', icon: BarChart2 },
  { name: 'Analytics', href: '/analytics', icon: BarChart2 },
  { name: 'AI Chat', href: '/ai-chat', icon: MessageSquare },
  { name: 'Documents', href: '/documents', icon: FileText },
  { name: 'Workflows', href: '/workflows', icon: GitBranch },
  { name: 'Integrations', href: '/integrations', icon: Zap },
  { name: 'Settings', href: '/settings', icon: Settings },
  { name: 'Bulk Import', href: '/bulk-import', icon: Database },
  { name: 'Migrations', href: '/migrations', icon: Database },
  { name: 'Permissions', href: '/permissions', icon: Shield },
  { name: 'LLM Manager', href: '/llm-manager', icon: HelpCircle },
  { name: 'Search', href: '/search', icon: Search },
];

export default function Layout({ onLogout }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const { user } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    onLogout?.();
    navigate('/login');
    setUserMenuOpen(false);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-64 bg-white border-r border-gray-200 transform transition-transform duration-200 lg:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="flex items-center justify-between h-16 px-4 border-b border-gray-200">
            <h1 className="text-xl font-bold text-blue-600">ERP SOLUTION</h1>
            <button
              className="lg:hidden p-2 rounded text-gray-500 hover:text-gray-700"
              onClick={() => setSidebarOpen(false)}
            >
              <X className="w-6 h-6" />
            </button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
            {navigation.map((item) => (
              <NavLink
                key={item.name}
                to={item.href}
                className={({ isActive }) =>
                  `flex items-center px-3 py-2.5 text-sm font-medium rounded-lg transition-colors ${
                    isActive
                      ? 'bg-blue-50 text-blue-700'
                      : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                  }`
                }
                onClick={() => setSidebarOpen(false)}
              >
                <item.icon className="w-5 h-5 mr-3 flex-shrink-0" />
                {item.name}
              </NavLink>
            ))}
          </nav>

          {/* Footer */}
          <div className="p-4 border-t border-gray-200">
            <p className="text-xs text-gray-500 text-center">v2.2.0</p>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="lg:pl-64">
        {/* Top bar */}
        <header className="sticky top-0 z-30 bg-white border-b border-gray-200">
          <div className="flex items-center justify-between h-16 px-4 sm:px-6 lg:px-8">
            <button
              className="lg:hidden p-2 rounded text-gray-500 hover:text-gray-700 hover:bg-gray-100"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu className="w-6 h-6" />
            </button>

            <div className="flex-1 lg:flex-none" />

            <div className="flex items-center gap-4">
              {/* User menu */}
              <div className="relative">
                <button
                  onClick={() => setUserMenuOpen(!userMenuOpen)}
                  className="flex items-center gap-2 p-2 rounded-lg hover:bg-gray-100"
                >
                  <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
                    <span className="text-sm font-medium text-blue-700">
                      {user?.name?.[0] || 'U'}
                    </span>
                  </div>
                  <span className="hidden sm:block text-sm font-medium text-gray-700">
                    {user?.name || 'User'}
                  </span>
                  <ChevronDown className="w-4 h-4 text-gray-500" />
                </button>

                {userMenuOpen && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setUserMenuOpen(false)} />
                    <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-50">
                      <div className="px-4 py-2 border-b border-gray-200">
                        <p className="text-sm font-medium text-gray-900">{user?.name || 'User'}</p>
                        <p className="text-xs text-gray-500">{user?.email || 'user@example.com'}</p>
                      </div>
                      <button
                        onClick={handleLogout}
                        className="w-full flex items-center gap-2 px-4 py-2 text-sm text-red-600 hover:bg-red-50"
                      >
                        <LogOut className="w-4 h-4" />
                        Sign out
                      </button>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}