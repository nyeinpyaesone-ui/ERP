import React, { useCallback, useEffect, useState } from 'react';
import {
  Plug,
  Webhook,
  Plus,
  Trash2,
  Send,
  History,
  Slack,
  MessageCircle,
  Zap,
  RefreshCw,
} from 'lucide-react';
import api from '../api/axios';

const emptyWebhook = { name: '', url: '', events: '', secret: '' };

export default function Integrations() {
  const [integrations, setIntegrations] = useState([]);
  const [webhooks, setWebhooks] = useState([]);
  const [activeTab, setActiveTab] = useState('integrations');
  const [form, setForm] = useState(emptyWebhook);
  const [showCreate, setShowCreate] = useState(false);
  const [deliveries, setDeliveries] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const loadData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [integrationResponse, webhookResponse] = await Promise.all([
        api.get('/integrations/integrations'),
        api.get('/integrations/webhooks'),
      ]);
      setIntegrations(integrationResponse.data);
      setWebhooks(webhookResponse.data);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Unable to load integrations.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const createWebhook = async (event) => {
    event.preventDefault();
    setError('');
    const events = form.events.split(',').map((item) => item.trim()).filter(Boolean);
    if (!events.length) {
      setError('Add at least one event name.');
      return;
    }
    try {
      const payload = {
        name: form.name.trim(),
        url: form.url.trim(),
        events,
        ...(form.secret ? { secret: form.secret } : {}),
      };
      await api.post('/integrations/webhooks', payload);
      setForm(emptyWebhook);
      setShowCreate(false);
      await loadData();
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Webhook could not be created.');
    }
  };

  const testWebhook = async (id) => {
    setError('');
    try {
      const response = await api.post(`/integrations/webhooks/${id}/test`, {});
      setError(response.data.status === 'delivered'
        ? 'Test delivery succeeded.'
        : 'Test delivery failed. Check delivery history for details.');
      await loadDeliveries(id);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Webhook test failed.');
    }
  };

  const disableWebhook = async (id) => {
    if (!window.confirm('Disable this webhook? Its delivery history will be retained.')) return;
    setError('');
    try {
      await api.delete(`/integrations/webhooks/${id}`);
      await loadData();
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Webhook could not be disabled.');
    }
  };

  const loadDeliveries = async (id) => {
    setError('');
    try {
      const response = await api.get(`/integrations/webhooks/${id}/deliveries`);
      setDeliveries((current) => ({ ...current, [id]: response.data }));
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Unable to load delivery history.');
    }
  };

  const getProviderIcon = (provider) => {
    if (provider === 'slack') return <Slack className="w-5 h-5" />;
    if (provider === 'teams') return <MessageCircle className="w-5 h-5" />;
    if (provider === 'zapier') return <Zap className="w-5 h-5" />;
    return <Plug className="w-5 h-5" />;
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
          <Plug className="w-8 h-8 text-indigo-600" /> Integrations
        </h1>
        <button onClick={loadData} className="p-2 rounded-lg hover:bg-gray-100" aria-label="Refresh integrations">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {error && (
        <div role="status" className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          {error}
        </div>
      )}

      <div className="flex gap-1 mb-6 bg-gray-100 p-1 rounded-lg w-fit">
        {[{ id: 'integrations', label: 'Services', icon: Plug }, { id: 'webhooks', label: 'Webhooks', icon: Webhook }].map((tab) => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-md font-medium transition-all ${activeTab === tab.id ? 'bg-white text-indigo-600 shadow-xs' : 'text-gray-600'}`}>
            <tab.icon className="w-4 h-4" />{tab.label}
          </button>
        ))}
      </div>

      {loading && <p className="text-sm text-gray-500 mb-4">Loading…</p>}

      {activeTab === 'integrations' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {integrations.map((integration) => (
            <div key={integration.id} className="card p-5">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 bg-indigo-100 rounded-lg flex items-center justify-center text-indigo-600">
                  {getProviderIcon(integration.provider)}
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">{integration.name}</h3>
                  <p className="text-xs text-gray-500 capitalize">{integration.provider}</p>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${integration.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'}`}>
                  {integration.is_active ? 'Connected' : 'Disconnected'}
                </span>
                {integration.last_sync && <p className="text-xs text-gray-400">Last sync: {new Date(integration.last_sync).toLocaleDateString()}</p>}
              </div>
            </div>
          ))}
          {!loading && integrations.length === 0 && (
            <div className="col-span-full text-center py-12 text-gray-500">
              <Plug className="w-12 h-12 mx-auto mb-3 text-gray-300" />
              <p>No integrations configured yet.</p>
            </div>
          )}
        </div>
      )}

      {activeTab === 'webhooks' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button onClick={() => setShowCreate((visible) => !visible)}
              className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-white hover:bg-indigo-700">
              <Plus className="w-4 h-4" /> Add webhook
            </button>
          </div>

          {showCreate && (
            <form onSubmit={createWebhook} className="card p-5 space-y-3">
              <h2 className="font-semibold text-gray-900">New outbound webhook</h2>
              <label className="block text-sm">Name
                <input required maxLength={255} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="mt-1 w-full rounded border p-2" />
              </label>
              <label className="block text-sm">HTTPS destination URL
                <input required type="url" value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })}
                  placeholder="https://hooks.example.com/erp" className="mt-1 w-full rounded border p-2" />
              </label>
              <label className="block text-sm">Events (comma-separated)
                <input required value={form.events} onChange={(e) => setForm({ ...form, events: e.target.value })}
                  placeholder="invoice.created, deal.won" className="mt-1 w-full rounded border p-2" />
              </label>
              <label className="block text-sm">Signing secret (optional; at least 16 characters)
                <input type="password" minLength={16} maxLength={255} autoComplete="new-password"
                  value={form.secret} onChange={(e) => setForm({ ...form, secret: e.target.value })}
                  className="mt-1 w-full rounded border p-2" />
              </label>
              <p className="text-xs text-gray-500">
                The destination host must be explicitly allowlisted by the server administrator. The signing secret is write-only and is never returned by the API.
              </p>
              <div className="flex justify-end gap-2">
                <button type="button" onClick={() => setShowCreate(false)} className="rounded border px-3 py-2">Cancel</button>
                <button type="submit" className="rounded bg-indigo-600 px-3 py-2 text-white">Save webhook</button>
              </div>
            </form>
          )}

          {webhooks.map((webhook) => (
            <div key={webhook.id} className="card p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3">
                    <Webhook className="w-5 h-5 text-indigo-600" />
                    <h3 className="font-semibold text-gray-900">{webhook.name}</h3>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${webhook.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'}`}>
                      {webhook.is_active ? 'Active' : 'Disabled'}
                    </span>
                  </div>
                  <p className="text-sm text-gray-500 font-mono mt-1 truncate">{webhook.url}</p>
                  <div className="flex flex-wrap gap-2 mt-2">
                    {webhook.events?.map((eventName) => (
                      <span key={eventName} className="px-2 py-1 bg-gray-100 rounded text-xs text-gray-600">{eventName}</span>
                    ))}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={() => testWebhook(webhook.id)} disabled={!webhook.is_active}
                    className="inline-flex items-center gap-1 p-2 hover:bg-gray-100 rounded-lg text-indigo-600 disabled:opacity-40" title="Send test">
                    <Send className="w-4 h-4" /><span className="text-xs">Test</span>
                  </button>
                  <button onClick={() => loadDeliveries(webhook.id)}
                    className="inline-flex items-center gap-1 p-2 hover:bg-gray-100 rounded-lg text-gray-600" title="Delivery history">
                    <History className="w-4 h-4" /><span className="text-xs">History</span>
                  </button>
                  {webhook.is_active && (
                    <button onClick={() => disableWebhook(webhook.id)}
                      className="p-2 hover:bg-red-50 text-red-500 rounded-lg" title="Disable webhook">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
              {deliveries[webhook.id] && (
                <div className="mt-4 border-t pt-3">
                  <h4 className="text-sm font-semibold mb-2">Recent deliveries</h4>
                  {deliveries[webhook.id].length === 0 ? (
                    <p className="text-sm text-gray-500">No delivery attempts recorded.</p>
                  ) : (
                    <ul className="space-y-2">
                      {deliveries[webhook.id].map((delivery) => (
                        <li key={delivery.id} className="flex flex-wrap justify-between gap-2 text-sm">
                          <span>{delivery.event} · {delivery.status} · HTTP {delivery.response_status ?? '—'}</span>
                          <time className="text-gray-500">{delivery.created_at ? new Date(delivery.created_at).toLocaleString() : ''}</time>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>
          ))}
          {!loading && webhooks.length === 0 && !showCreate && (
            <div className="text-center py-12 text-gray-500">No webhooks configured yet.</div>
          )}
        </div>
      )}
    </div>
  );
}
