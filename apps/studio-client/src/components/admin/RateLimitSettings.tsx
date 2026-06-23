// ============================================================================
// component >> RateLimitSettings.tsx
// project >> SupremeAI 2.0
// purpose >> Rate limiting
// module >> src
// ============================================================================
interface RateLimitConfig {
  tenant_id: string;
  billing_tier: string;
  requests_per_minute: number;
  max_tokens_per_day: number;
  custom_limits: Record<string, any>;
  admin_override: boolean;
}

const TIER_OPTIONS = ['free', 'pro', 'enterprise'] as const;
const TIER_LIMITS: Record<string, Partial<RateLimitConfig>> = {
  free: { requests_per_minute: 60, max_tokens_per_day: 100000 },
  pro: { requests_per_minute: 500, max_tokens_per_day: 50000 },
  enterprise: { requests_per_minute: 2000, max_tokens_per_day: 500000 },
};

export function RateLimitSettings({ tenantId }: { tenantId: string }) {
  const [config, setConfig] = useState<RateLimitConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [overrideReason, setOverrideReason] = useState('');

  const fetchConfig = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/tools/tenant-limits/${tenantId}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('access_token') || ''}` },
      });
      if (res.ok) {
        const data = await res.json();
        setConfig(data);
      }
    } catch (err) {
      console.error('Failed to fetch rate limit config', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchConfig(); }, [tenantId]);

  const handleTierChange = async (tier: string) => {
    if (!config) return;
    setSaving(true);
    try {
      await fetch(`/api/tools/tenant-limits/${tenantId}/tier`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('access_token') || ''}`,
        },
        body: JSON.stringify({ billing_tier: tier }),
      });
      setConfig({ ...config, billing_tier: tier, ...TIER_LIMITS[tier as keyof typeof TIER_LIMITS] });
    } catch (err) {
      console.error('Failed to update tier', err);
    } finally {
      setSaving(false);
    }
  };

  const handleAdminOverride = async () => {
    if (!config) return;
    setSaving(true);
    try {
      const res = await fetch(`/api/tools/tenant-limits/${tenantId}/override`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('access_token') || ''}`,
        },
        body: JSON.stringify({ admin_override: !config.admin_override, reason: overrideReason || 'Admin override' }),
      });
      if (res.ok) {
        setConfig({ ...config, admin_override: !config.admin_override });
        setOverrideReason('');
      }
    } catch (err) {
      console.error('Override failed', err);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="p-4 text-slate-400 font-mono text-sm">Loading rate limit config…</div>;
  }

  if (!config) {
    return (
      <div className="p-4 bg-red-900/30 border border-red-800 rounded-lg text-red-300 font-mono text-sm">
        Failed to load rate limit configuration.
        <button onClick={fetchConfig} className="ml-4 underline">Retry</button>
      </div>
    );
  }

  return (
    <div className="p-6 bg-[#0c0d12]/90 border border-slate-900 rounded-xl font-sans">
      <h3 className="text-xs font-bold text-slate-300 mb-4 uppercase tracking-wider font-mono">
        ⚡ TENANT RATE LIMITS
      </h3>

      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-[10px] text-slate-400 font-mono uppercase mb-1">Billing Tier</label>
            <select
              value={config.billing_tier}
              onChange={(e) => handleTierChange(e.target.value)}
              disabled={saving}
              className="w-full bg-slate-900 border border-slate-800 rounded px-3 py-2 text-sm text-slate-200 font-mono disabled:opacity-50"
            >
              {TIER_OPTIONS.map((tier) => (
                <option key={tier} value={tier}>{tier.toUpperCase()}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[10px] text-slate-400 font-mono uppercase mb-1">RPM Limit</label>
            <div className="bg-slate-900 border border-slate-800 rounded px-3 py-2 text-sm text-slate-200 font-mono">
              {config.requests_per_minute}
            </div>
          </div>

          <div>
            <label className="block text-[10px] text-slate-400 font-mono uppercase mb-1">Max Tokens / Day</label>
            <div className="bg-slate-900 border border-slate-800 rounded px-3 py-2 text-sm text-slate-200 font-mono">
              {config.max_tokens_per_day.toLocaleString()}
            </div>
          </div>

          <div>
            <label className="block text-[10px] text-slate-400 font-mono uppercase mb-1">Custom Limits (JSON)</label>
            <textarea
              value={JSON.stringify(config.custom_limits, null, 2)}
              onChange={(e) => {
                try {
                  setConfig({ ...config, custom_limits: JSON.parse(e.target.value) });
                } catch { /* ignore invalid JSON */ }
              }}
              rows={3}
              className="w-full bg-slate-900 border border-slate-800 rounded px-3 py-2 text-sm text-slate-200 font-mono"
              placeholder='{"max_file_size_mb": 50}'
            />
          </div>
        </div>

        <div className="border-t border-slate-800 pt-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-bold text-slate-300">Admin Override</p>
              <p className="text-[10px] text-slate-500 font-mono">
                {config.admin_override ? 'Active — rate limits suspended' : 'Inactive — normal limits apply'}
              </p>
            </div>
            <button
              onClick={handleAdminOverride}
              disabled={saving}
              className={`px-4 py-2 rounded text-xs font-bold font-mono disabled:opacity-50 ${
                config.admin_override
                  ? 'bg-red-900/50 text-red-300 border border-red-800'
                  : 'bg-blue-900/50 text-blue-300 border border-blue-800'
              }`}
            >
              {config.admin_override ? 'Revoke Override' : 'Grant Override'}
            </button>
          </div>
          {config.admin_override && (
            <div className="mt-3">
              <input
                type="text"
                value={overrideReason}
                onChange={(e) => setOverrideReason(e.target.value)}
                placeholder="Override reason (required for audit log)"
                className="w-full bg-slate-900 border border-slate-800 rounded px-3 py-2 text-sm text-slate-200 font-mono"
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
