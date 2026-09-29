import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import CRM from './pages/CRM';
import HR from './pages/HR';
import Inventory from './pages/Inventory';
import Finance from './pages/Finance';
import Projects from './pages/Projects';
import Reports from './pages/Reports';
import Analytics from './pages/Analytics';
import AIChat from './pages/AIChat';
import Documents from './pages/Documents';
import Workflows from './pages/Workflows';
import Integrations from './pages/Integrations';
import Settings from './pages/Settings';
import BulkImportExport from './pages/BulkImportExport';
import MigrationManager from './pages/MigrationManager';
import Permissions from './pages/Permissions';
import LLMManager from './pages/LLMManager';
import Search from './pages/Search';

// Role-based route guard
/**
 * Render children for an authenticated user whose legacy role is allowed.
 * Empty allowedRoles or '*' allows any authenticated role; matching ignores case.
 * Show a spinner while loading, redirect signed-out users to /login, and send
 * users with a disallowed role to /.
 */
function RequireRole({ children, allowedRoles = [] }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  // If no specific roles required, just check authenticated
  if (allowedRoles.length === 0) {
    return children;
  }

  // Check if user has one of the allowed roles
  const userRole = user?.role?.toLowerCase() || 'user';
  const hasAccess = allowedRoles.some(role => role.toLowerCase() === userRole || role === '*');

  if (!hasAccess) {
    return <Navigate to="/" replace />;
  }

  return children;
}

/** Render a loading state, login form, or the authenticated application routes. */
function AppRoutes() {
  const { user, loading, login, logout } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) {
    return <Login onLogin={login} />;
  }

  return (
    <Layout onLogout={logout}>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/login" element={<Login onLogin={login} />} />
        <Route path="/crm" element={<RequireRole><CRM /></RequireRole>} />
        <Route path="/hr" element={<RequireRole allowedRoles={['admin', 'superadmin', 'manager']}><HR /></RequireRole>} />
        <Route path="/inventory" element={<RequireRole><Inventory /></RequireRole>} />
        <Route path="/finance" element={<RequireRole allowedRoles={['admin', 'superadmin', 'manager']}><Finance /></RequireRole>} />
        <Route path="/projects" element={<RequireRole><Projects /></RequireRole>} />
        <Route path="/reports" element={<RequireRole allowedRoles={['admin', 'superadmin', 'manager']}><Reports /></RequireRole>} />
        <Route path="/analytics" element={<RequireRole allowedRoles={['admin', 'superadmin', 'manager']}><Analytics /></RequireRole>} />
        <Route path="/ai-chat" element={<RequireRole><AIChat /></RequireRole>} />
        <Route path="/documents" element={<RequireRole><Documents /></RequireRole>} />
        <Route path="/workflows" element={<RequireRole allowedRoles={['admin', 'superadmin', 'manager']}><Workflows /></RequireRole>} />
        <Route path="/integrations" element={<RequireRole allowedRoles={['admin', 'superadmin']}><Integrations /></RequireRole>} />
        <Route path="/settings" element={<RequireRole allowedRoles={['admin', 'superadmin']}><Settings /></RequireRole>} />
        <Route path="/bulk-import" element={<RequireRole allowedRoles={['admin', 'superadmin']}><BulkImportExport /></RequireRole>} />
        <Route path="/migrations" element={<RequireRole allowedRoles={['admin', 'superadmin']}><MigrationManager /></RequireRole>} />
        <Route path="/permissions" element={<RequireRole allowedRoles={['admin', 'superadmin']}><Permissions /></RequireRole>} />
        <Route path="/llm-manager" element={<RequireRole allowedRoles={['admin', 'superadmin']}><LLMManager /></RequireRole>} />
        <Route path="/search" element={<RequireRole><Search /></RequireRole>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}