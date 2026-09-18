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

function AppRoutes() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) {
    return <Login />;
  }

  return (
    <Layout onLogout={() => {}}>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/crm" element={<CRM />} />
        <Route path="/hr" element={<HR />} />
        <Route path="/inventory" element={<Inventory />} />
        <Route path="/finance" element={<Finance />} />
        <Route path="/projects" element={<Projects />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/ai-chat" element={<AIChat />} />
        <Route path="/documents" element={<Documents />} />
        <Route path="/workflows" element={<Workflows />} />
        <Route path="/integrations" element={<Integrations />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/bulk-import" element={<BulkImportExport />} />
        <Route path="/migrations" element={<MigrationManager />} />
        <Route path="/permissions" element={<Permissions />} />
        <Route path="/llm-manager" element={<LLMManager />} />
        <Route path="/search" element={<Search />} />
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