"""
SupremeAI 2.0 — API Key Management React Component
For Studio Admin Panel (React + Vite + Tailwind)
"""

# File: apps/studio-client/src/components/api-keys/ApiKeyManager.tsx

import React, { useState, useEffect, useCallback } from 'react';
import { 
  Key, Copy, Eye, EyeOff, RotateCcw, Trash2, 
  AlertTriangle, CheckCircle, BarChart3, Shield,
  Clock, Globe, Lock, ChevronDown, ChevronUp,
  Plus, X, RefreshCw, Filter, Search
} from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { api } from '@/lib/api';
import { toast } from 'sonner';
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, 
  Tooltip, ResponsiveContainer, AreaChart, Area 
} from 'recharts';

// Types
interface APIKey {
  id: string;
  name: string;
  description?: string;
  key_prefix: string;
  scopes: string[];
  rate_limit_rpm: number;
  rate_limit_rpd: number;
  monthly_quota: number;
  quota_used: number;
  quota_remaining: number;
  quota_usage_percent: number;
  expires_at: string | null;
  days_until_expiry: number | null;
  last_used_at: string | null;
  created_at: string;
  status: 'active' | 'revoked' | 'expired' | 'suspended';
  is_active: boolean;
  ip_whitelist: string[];
}

interface UsageStats {
  key_id: string;
  total_requests: number;
  total_tokens: number;
  total_cost_usd: number;
  avg_latency_ms: number | null;
  success_rate: number;
  top_endpoints: Array<{ endpoint: string; count: number; tokens: number }>;
  daily_usage: Array<{ date: string; requests: number; tokens: number; cost: number }>;
}

interface CreateKeyData {
  name: string;
  description?: string;
  scopes: string[];
  environment: 'live' | 'test' | 'dev';
  expires_in_days?: number;
  rate_limit_rpm?: number;
  rate_limit_rpd?: number;
  monthly_quota?: number;
  ip_whitelist?: string[];
}

const SCOPE_OPTIONS = [
  { value: 'inference', label: 'Inference', description: 'Call AI models' },
  { value: 'training', label: 'Training', description: 'Train custom models' },
  { value: 'admin', label: 'Admin', description: 'Manage keys and users' },
  { value: 'billing', label: 'Billing', description: 'View billing and usage' },
  { value: 'read_only', label: 'Read Only', description: 'View-only access' },
  { value: 'webhook', label: 'Webhook', description: 'Manage webhooks' },
];

const ENV_OPTIONS = [
  { value: 'live', label: 'Production', color: 'bg-green-500' },
  { value: 'test', label: 'Testing', color: 'bg-yellow-500' },
  { value: 'dev', label: 'Development', color: 'bg-blue-500' },
];

// ═══════════════════════════════════════════════════════════════
// Main Component
// ═══════════════════════════════════════════════════════════════

export const ApiKeyManager: React.FC = () => {
  const { user } = useAuth();
  const [keys, setKeys] = useState<APIKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedKey, setSelectedKey] = useState<APIKey | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showUsageModal, setShowUsageModal] = useState(false);
  const [showRotateConfirm, setShowRotateConfirm] = useState(false);
  const [showRevokeConfirm, setShowRevokeConfirm] = useState(false);
  const [newKeyData, setNewKeyData] = useState<CreateKeyData>({
    name: '',
    scopes: ['inference'],
    environment: 'live',
  });
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<string | null>(null);
  const [usageStats, setUsageStats] = useState<UsageStats | null>(null);
  const [usageLoading, setUsageLoading] = useState(false);
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedKey, setExpandedKey] = useState<string | null>(null);

  // Fetch keys on mount
  useEffect(() => {
    fetchKeys();
  }, []);

  const fetchKeys = async () => {
    try {
      setLoading(true);
      const response = await api.get('/api/v1/keys');
      setKeys(response.data.keys);
    } catch (error) {
      toast.error('Failed to load API keys');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateKey = async () => {
    try {
      const response = await api.post('/api/v1/keys', newKeyData);
      setNewlyCreatedKey(response.data.key);
      setKeys(prev => [response.data, ...prev]);
      toast.success('API key created successfully!');
      setShowCreateModal(false);
      setNewKeyData({ name: '', scopes: ['inference'], environment: 'live' });
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to create key');
    }
  };

  const handleRotateKey = async (keyId: string) => {
    try {
      const response = await api.post(`/api/v1/keys/${keyId}/rotate`);
      setNewlyCreatedKey(response.data.new_key);
      toast.success('Key rotated successfully!');
      fetchKeys();
      setShowRotateConfirm(false);
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to rotate key');
    }
  };

  const handleRevokeKey = async (keyId: string) => {
    try {
      await api.post(`/api/v1/keys/${keyId}/revoke`, { reason: 'User initiated revocation' });
      toast.success('Key revoked successfully');
      fetchKeys();
      setShowRevokeConfirm(false);
      setSelectedKey(null);
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to revoke key');
    }
  };

  const handleCopyKey = (key: string) => {
    navigator.clipboard.writeText(key);
    toast.success('Key copied to clipboard!');
  };

  const handleViewUsage = async (keyId: string) => {
    try {
      setUsageLoading(true);
      const response = await api.get(`/api/v1/keys/${keyId}/usage?days=30`);
      setUsageStats(response.data);
      setShowUsageModal(true);
    } catch (error) {
      toast.error('Failed to load usage stats');
    } finally {
      setUsageLoading(false);
    }
  };

  const filteredKeys = keys.filter(key => {
    if (filterStatus !== 'all' && key.status !== filterStatus) return false;
    if (searchQuery && !key.name.toLowerCase().includes(searchQuery.toLowerCase()) && 
        !key.key_prefix.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-green-100 text-green-800 border-green-200';
      case 'suspended': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'revoked': return 'bg-red-100 text-red-800 border-red-200';
      case 'expired': return 'bg-gray-100 text-gray-800 border-gray-200';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getQuotaColor = (percent: number) => {
    if (percent >= 100) return 'bg-red-500';
    if (percent >= 80) return 'bg-yellow-500';
    return 'bg-green-500';
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      {/* Header */}
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
              <Key className="w-8 h-8 text-indigo-600" />
              API Key Management
            </h1>
            <p className="text-gray-500 mt-1">Create, manage, and monitor your API keys</p>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
          >
            <Plus className="w-5 h-5" />
            Create New Key
          </button>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <StatCard 
            icon={<Key className="w-5 h-5" />} 
            label="Total Keys" 
            value={keys.length} 
            color="bg-blue-50 text-blue-600" 
          />
          <StatCard 
            icon={<CheckCircle className="w-5 h-5" />} 
            label="Active" 
            value={keys.filter(k => k.status === 'active').length} 
            color="bg-green-50 text-green-600" 
          />
          <StatCard 
            icon={<AlertTriangle className="w-5 h-5" />} 
            label="Suspended" 
            value={keys.filter(k => k.status === 'suspended').length} 
            color="bg-yellow-50 text-yellow-600" 
          />
          <StatCard 
            icon={<BarChart3 className="w-5 h-5" />} 
            label="Total Usage" 
            value={`${keys.reduce((acc, k) => acc + k.quota_used, 0).toLocaleString()} tokens`} 
            color="bg-purple-50 text-purple-600" 
          />
        </div>

        {/* Filters */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-6">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search keys..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
            </div>
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            >
              <option value="all">All Status</option>
              <option value="active">Active</option>
              <option value="suspended">Suspended</option>
              <option value="revoked">Revoked</option>
              <option value="expired">Expired</option>
            </select>
            <button
              onClick={fetchKeys}
              className="p-2 border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              <RefreshCw className="w-5 h-5 text-gray-600" />
            </button>
          </div>
        </div>

        {/* Keys List */}
        <div className="space-y-4">
          {loading ? (
            <div className="text-center py-12">
              <RefreshCw className="w-8 h-8 animate-spin text-indigo-600 mx-auto" />
              <p className="text-gray-500 mt-2">Loading keys...</p>
            </div>
          ) : filteredKeys.length === 0 ? (
            <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
              <Key className="w-12 h-12 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500">No API keys found</p>
              <button
                onClick={() => setShowCreateModal(true)}
                className="mt-3 text-indigo-600 hover:text-indigo-700 font-medium"
              >
                Create your first key
              </button>
            </div>
          ) : (
            filteredKeys.map(key => (
              <KeyCard 
                key={key.id}
                apiKey={key}
                isExpanded={expandedKey === key.id}
                onToggle={() => setExpandedKey(expandedKey === key.id ? null : key.id)}
                onRotate={() => { setSelectedKey(key); setShowRotateConfirm(true); }}
                onRevoke={() => { setSelectedKey(key); setShowRevokeConfirm(true); }}
                onViewUsage={() => handleViewUsage(key.id)}
              />
            ))
          )}
        </div>
      </div>

      {/* Create Key Modal */}
      {showCreateModal && (
        <CreateKeyModal
          data={newKeyData}
          onChange={setNewKeyData}
          onCreate={handleCreateKey}
          onClose={() => setShowCreateModal(false)}
        />
      )}

      {/* Newly Created Key Display */}
      {newlyCreatedKey && (
        <NewKeyDisplayModal
          key={newlyCreatedKey}
          onClose={() => setNewlyCreatedKey(null)}
          onCopy={() => handleCopyKey(newlyCreatedKey)}
        />
      )}

      {/* Usage Stats Modal */}
      {showUsageModal && usageStats && (
        <UsageStatsModal
          stats={usageStats}
          onClose={() => setShowUsageModal(false)}
        />
      )}

      {/* Rotate Confirmation */}
      {showRotateConfirm && selectedKey && (
        <ConfirmModal
          title="Rotate API Key"
          message={`Are you sure you want to rotate "${selectedKey.name}"? The old key will be immediately revoked.`}
          confirmText="Rotate"
          confirmColor="bg-yellow-600 hover:bg-yellow-700"
          onConfirm={() => handleRotateKey(selectedKey.id)}
          onClose={() => setShowRotateConfirm(false)}
        />
      )}

      {/* Revoke Confirmation */}
      {showRevokeConfirm && selectedKey && (
        <ConfirmModal
          title="Revoke API Key"
          message={`Are you sure you want to revoke "${selectedKey.name}"? This action cannot be undone.`}
          confirmText="Revoke"
          confirmColor="bg-red-600 hover:bg-red-700"
          onConfirm={() => handleRevokeKey(selectedKey.id)}
          onClose={() => setShowRevokeConfirm(false)}
        />
      )}
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════
// Sub-Components
// ═══════════════════════════════════════════════════════════════

const StatCard: React.FC<{ icon: React.ReactNode; label: string; value: string | number; color: string }> = 
  ({ icon, label, value, color }) => (
  <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
    <div className="flex items-center gap-3">
      <div className={`p-2 rounded-lg ${color}`}>{icon}</div>
      <div>
        <p className="text-sm text-gray-500">{label}</p>
        <p className="text-2xl font-bold text-gray-900">{value}</p>
      </div>
    </div>
  </div>
);

const KeyCard: React.FC<{
  apiKey: APIKey;
  isExpanded: boolean;
  onToggle: () => void;
  onRotate: () => void;
  onRevoke: () => void;
  onViewUsage: () => void;
}> = ({ apiKey, isExpanded, onToggle, onRotate, onRevoke, onViewUsage }) => {
  const envColor = ENV_OPTIONS.find(e => e.value === apiKey.key_prefix.split('_')[1])?.color || 'bg-gray-500';

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
      <div className="p-4 flex items-center gap-4">
        <div className={`w-2 h-12 rounded-full ${apiKey.is_active ? 'bg-green-500' : 'bg-gray-300'}`} />
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-gray-900">{apiKey.name}</h3>
            <span className={`px-2 py-0.5 text-xs font-medium rounded-full border ${getStatusColor(apiKey.status)}`}>
              {apiKey.status}
            </span>
            <span className={`w-2 h-2 rounded-full ${envColor}`} title="Environment" />
          </div>
          <p className="text-sm text-gray-500 font-mono mt-0.5">{apiKey.key_prefix}...</p>
          <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {apiKey.days_until_expiry !== null ? `${apiKey.days_until_expiry} days left` : 'No expiry'}
            </span>
            <span className="flex items-center gap-1">
              <BarChart3 className="w-3 h-3" />
              {apiKey.quota_used.toLocaleString()} / {apiKey.monthly_quota.toLocaleString()} tokens
            </span>
            {apiKey.last_used_at && (
              <span>Last used: {new Date(apiKey.last_used_at).toLocaleDateString()}</span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={onViewUsage} className="p-2 hover:bg-gray-100 rounded-lg" title="View Usage">
            <BarChart3 className="w-5 h-5 text-gray-600" />
          </button>
          {apiKey.status === 'active' && (
            <>
              <button onClick={onRotate} className="p-2 hover:bg-gray-100 rounded-lg" title="Rotate Key">
                <RotateCcw className="w-5 h-5 text-yellow-600" />
              </button>
              <button onClick={onRevoke} className="p-2 hover:bg-gray-100 rounded-lg" title="Revoke Key">
                <Trash2 className="w-5 h-5 text-red-600" />
              </button>
            </>
          )}
          <button onClick={onToggle} className="p-2 hover:bg-gray-100 rounded-lg">
            {isExpanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* Quota Bar */}
      <div className="px-4 pb-2">
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div 
            className={`h-2 rounded-full transition-all ${getQuotaColor(apiKey.quota_usage_percent)}`}
            style={{ width: `${Math.min(apiKey.quota_usage_percent, 100)}%` }}
          />
        </div>
        <p className="text-xs text-gray-500 mt-1">{apiKey.quota_usage_percent.toFixed(1)}% quota used</p>
      </div>

      {/* Expanded Details */}
      {isExpanded && (
        <div className="px-4 pb-4 border-t border-gray-100 pt-3">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <p className="text-gray-500">Scopes</p>
              <div className="flex flex-wrap gap-1 mt-1">
                {apiKey.scopes.map(s => (
                  <span key={s} className="px-2 py-0.5 bg-indigo-50 text-indigo-700 rounded text-xs">
                    {s}
                  </span>
                ))}
              </div>
            </div>
            <div>
              <p className="text-gray-500">Rate Limits</p>
              <p className="font-medium">{apiKey.rate_limit_rpm} RPM / {apiKey.rate_limit_rpd} RPD</p>
            </div>
            <div>
              <p className="text-gray-500">Created</p>
              <p className="font-medium">{new Date(apiKey.created_at).toLocaleDateString()}</p>
            </div>
            <div>
              <p className="text-gray-500">IP Whitelist</p>
              <p className="font-medium">{apiKey.ip_whitelist.length > 0 ? apiKey.ip_whitelist.join(', ') : 'None'}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const CreateKeyModal: React.FC<{
  data: CreateKeyData;
  onChange: (data: CreateKeyData) => void;
  onCreate: () => void;
  onClose: () => void;
}> = ({ data, onChange, onCreate, onClose }) => {
  const [step, setStep] = useState(1);

  const update = (field: keyof CreateKeyData, value: any) => {
    onChange({ ...data, [field]: value });
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="p-6 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-xl font-bold">Create New API Key</h2>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          {/* Step 1: Basic Info */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Key Name *</label>
            <input
              type="text"
              value={data.name}
              onChange={(e) => update('name', e.target.value)}
              placeholder="e.g., Production Inference Key"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <textarea
              value={data.description || ''}
              onChange={(e) => update('description', e.target.value)}
              placeholder="What is this key for?"
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {/* Environment */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Environment</label>
            <div className="flex gap-3">
              {ENV_OPTIONS.map(env => (
                <button
                  key={env.value}
                  onClick={() => update('environment', env.value)}
                  className={`flex-1 p-3 rounded-lg border-2 text-center transition-all ${
                    data.environment === env.value 
                      ? 'border-indigo-500 bg-indigo-50' 
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className={`w-3 h-3 rounded-full ${env.color} mx-auto mb-1`} />
                  <span className="text-sm font-medium">{env.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Scopes */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Permissions (Scopes)</label>
            <div className="space-y-2">
              {SCOPE_OPTIONS.map(scope => (
                <label key={scope.value} className="flex items-start gap-3 p-2 rounded-lg hover:bg-gray-50 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={data.scopes.includes(scope.value)}
                    onChange={(e) => {
                      const newScopes = e.target.checked
                        ? [...data.scopes, scope.value]
                        : data.scopes.filter(s => s !== scope.value);
                      update('scopes', newScopes);
                    }}
                    className="mt-1 w-4 h-4 text-indigo-600 rounded"
                  />
                  <div>
                    <p className="font-medium text-sm">{scope.label}</p>
                    <p className="text-xs text-gray-500">{scope.description}</p>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Advanced Options */}
          <div className="border-t border-gray-200 pt-4">
            <p className="text-sm font-medium text-gray-700 mb-3">Advanced Options</p>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Expires in (days)</label>
                <input
                  type="number"
                  value={data.expires_in_days || ''}
                  onChange={(e) => update('expires_in_days', e.target.value ? parseInt(e.target.value) : undefined)}
                  placeholder="Never"
                  min={1}
                  max={365}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Monthly Quota (tokens)</label>
                <input
                  type="number"
                  value={data.monthly_quota || ''}
                  onChange={(e) => update('monthly_quota', e.target.value ? parseInt(e.target.value) : undefined)}
                  placeholder="1,000,000"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Rate Limit (RPM)</label>
                <input
                  type="number"
                  value={data.rate_limit_rpm || ''}
                  onChange={(e) => update('rate_limit_rpm', e.target.value ? parseInt(e.target.value) : undefined)}
                  placeholder="60"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Rate Limit (RPD)</label>
                <input
                  type="number"
                  value={data.rate_limit_rpd || ''}
                  onChange={(e) => update('rate_limit_rpd', e.target.value ? parseInt(e.target.value) : undefined)}
                  placeholder="1000"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                />
              </div>
            </div>
          </div>
        </div>

        <div className="p-6 border-t border-gray-200 flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg">
            Cancel
          </button>
          <button
            onClick={onCreate}
            disabled={!data.name}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Create Key
          </button>
        </div>
      </div>
    </div>
  );
};

const NewKeyDisplayModal: React.FC<{
  key: string;
  onClose: () => void;
  onCopy: () => void;
}> = ({ key: apiKey, onClose, onCopy }) => {
  const [showKey, setShowKey] = useState(false);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6">
        <div className="text-center">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <CheckCircle className="w-8 h-8 text-green-600" />
          </div>
          <h2 className="text-xl font-bold mb-2">API Key Created!</h2>
          <p className="text-gray-500 mb-6">Copy this key now. You won't be able to see it again.</p>

          <div className="bg-gray-900 rounded-lg p-4 mb-4 relative">
            <code className="text-green-400 font-mono text-sm break-all">
              {showKey ? apiKey : apiKey.substring(0, 20) + '•'.repeat(apiKey.length - 20)}
            </code>
            <button
              onClick={() => setShowKey(!showKey)}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-white"
            >
              {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>

          <div className="flex gap-3 justify-center">
            <button
              onClick={() => { onCopy(); }}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
            >
              <Copy className="w-4 h-4" />
              Copy Key
            </button>
            <button onClick={onClose} className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">
              Done
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

const UsageStatsModal: React.FC<{
  stats: UsageStats;
  onClose: () => void;
}> = ({ stats, onClose }) => {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-4xl max-h-[90vh] overflow-y-auto">
        <div className="p-6 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-xl font-bold">Usage Statistics</h2>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6">
          {/* Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <StatCard icon={<BarChart3 className="w-5 h-5" />} label="Total Requests" value={stats.total_requests.toLocaleString()} color="bg-blue-50 text-blue-600" />
            <StatCard icon={<Key className="w-5 h-5" />} label="Total Tokens" value={stats.total_tokens.toLocaleString()} color="bg-purple-50 text-purple-600" />
            <StatCard icon={<Shield className="w-5 h-5" />} label="Success Rate" value={`${stats.success_rate}%`} color="bg-green-50 text-green-600" />
            <StatCard icon={<Globe className="w-5 h-5" />} label="Cost" value={`$${stats.total_cost_usd.toFixed(4)}`} color="bg-yellow-50 text-yellow-600" />
          </div>

          {/* Daily Usage Chart */}
          <div className="mb-6">
            <h3 className="font-semibold mb-3">Daily Usage (Last 30 Days)</h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={stats.daily_usage}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tickFormatter={(d) => new Date(d).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} />
                  <YAxis />
                  <Tooltip />
                  <Area type="monotone" dataKey="requests" stroke="#4f46e5" fill="#4f46e5" fillOpacity={0.1} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Top Endpoints */}
          <div>
            <h3 className="font-semibold mb-3">Top Endpoints</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left">Endpoint</th>
                    <th className="px-4 py-2 text-right">Requests</th>
                    <th className="px-4 py-2 text-right">Tokens</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.top_endpoints.map((ep, i) => (
                    <tr key={i} className="border-t border-gray-100">
                      <td className="px-4 py-2 font-mono text-xs">{ep.endpoint}</td>
                      <td className="px-4 py-2 text-right">{ep.count.toLocaleString()}</td>
                      <td className="px-4 py-2 text-right">{ep.tokens.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const ConfirmModal: React.FC<{
  title: string;
  message: string;
  confirmText: string;
  confirmColor: string;
  onConfirm: () => void;
  onClose: () => void;
}> = ({ title, message, confirmText, confirmColor, onConfirm, onClose }) => (
  <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
    <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
      <h2 className="text-xl font-bold mb-2">{title}</h2>
      <p className="text-gray-500 mb-6">{message}</p>
      <div className="flex justify-end gap-3">
        <button onClick={onClose} className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg">
          Cancel
        </button>
        <button onClick={onConfirm} className={`px-4 py-2 text-white rounded-lg ${confirmColor}`}>
          {confirmText}
        </button>
      </div>
    </div>
  </div>
);

export default ApiKeyManager;
