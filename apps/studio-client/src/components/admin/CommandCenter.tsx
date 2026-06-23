// ============================================================================
// component >> CommandCenter.tsx
// project >> SupremeAI 2.0
// purpose >> General utility
// module >> src
// ============================================================================
import { Activity, DollarSign, Cpu, AlertTriangle, Zap, Shield } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

const requestData = [
  { time: '00:00', requests: 120 },
  { time: '04:00', requests: 80 },
  { time: '08:00', requests: 300 },
  { time: '12:00', requests: 450 },
  { time: '16:00', requests: 380 },
  { time: '20:00', requests: 250 },
  { time: '23:59', requests: 180 },
];

const providerData = [
  { name: 'OpenRouter', value: 45, color: '#00f3ff' },
  { name: 'Gemini', value: 25, color: '#bc13fe' },
  { name: 'Groq', value: 20, color: '#10b981' },
  { name: 'DeepSeek', value: 10, color: '#f59e0b' },
];

const alerts = [
  { id: 1, severity: 'warning', message: 'Latency spike on Groq (340ms)', time: '2m ago' },
  { id: 2, severity: 'danger', message: 'Rate limit approaching: OpenRouter 85%', time: '5m ago' },
  { id: 3, severity: 'info', message: 'New model version v2.1 deployed', time: '12m ago' },
  { id: 4, severity: 'warning', message: 'Redis memory usage at 78%', time: '18m ago' },
  { id: 5, severity: 'info', message: 'Daily backup completed successfully', time: '1h ago' },
];

const quickActions = [
  { label: 'Emergency Stop', icon: Shield, variant: 'danger' as const },
  { label: 'Scale to Max', icon: Zap, variant: 'purple' as const },
  { label: 'Purge Cache', icon: Activity, variant: 'info' as const },
  { label: 'Deploy Hotfix', icon: DollarSign, variant: 'success' as const },
];

const severityColors: Record<string, string> = {
  danger: 'text-red-400 border-red-900/50',
  warning: 'text-yellow-400 border-yellow-900/50',
  info: 'text-cyan-400 border-cyan-900/50',
};

export function CommandCenter() {
  return (
    <div className="flex-grow p-6 overflow-y-auto bg-[var(--background)] text-[var(--foreground)]">
      <div className="flex items-center justify-between mb-6 pb-2 border-b border-[var(--border-color)]">
        <h2 className="text-lg font-bold font-['Space_Grotesk'] tracking-widest text-[#00f3ff] uppercase">
          🖥️ Command Center
        </h2>
        <span className="text-xs px-3 py-1 rounded bg-emerald-950/40 text-emerald-400 border border-emerald-900 font-mono flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          ALL SYSTEMS OPERATIONAL
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
        {quickActions.map(action => (
          <button
            key={action.label}
            className={`flex items-center gap-3 p-3 rounded-lg border transition-all hover:scale-[1.02] ${
              action.variant === 'danger' ? 'border-red-900/50 text-red-400 hover:bg-red-950/30' :
              action.variant === 'purple' ? 'border-purple-900/50 text-purple-400 hover:bg-purple-950/30' :
              action.variant === 'success' ? 'border-emerald-900/50 text-emerald-400 hover:bg-emerald-950/30' :
              'border-cyan-900/50 text-cyan-400 hover:bg-cyan-950/30'
            }`}
          >
            <action.icon size={16} />
            <span className="text-xs font-bold font-mono uppercase">{action.label}</span>
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <Card title="Active Requests (24h)" banglaHint="গত ২৪ ঘণ্টায় আসা মোট রিকোয়েস্ট বা ট্রাফিকের গ্রাফিকাল রূপরেখা।" className="col-span-2">
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={requestData}>
              <defs>
                <linearGradient id="colorRequests" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#00f3ff" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#00f3ff" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <XAxis dataKey="time" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ backgroundColor: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: 8, color: 'var(--foreground)' }}
                labelStyle={{ color: '#00f3ff' }}
              />
              <Area type="monotone" dataKey="requests" stroke="#00f3ff" fillOpacity={1} fill="url(#colorRequests)" />
            </AreaChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Model Load Distribution" banglaHint="কোন এআই প্রোভাইডার (যেমন Gemini, Groq) কত শতাংশ রিকোয়েস্ট হ্যান্ডেল করছে।">
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={providerData}
                cx="50%"
                cy="50%"
                innerRadius={40}
                outerRadius={70}
                paddingAngle={5}
                dataKey="value"
              >
                {providerData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ backgroundColor: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: 8, color: 'var(--foreground)' }}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex flex-col gap-1.5 mt-2">
            {providerData.map(p => (
              <div key={p.name} className="flex items-center justify-between text-[10px] font-mono">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: p.color }} />
                  <span className="text-slate-400">{p.name}</span>
                </div>
                <span className="text-[var(--foreground)]">{p.value}%</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card title="Cost Burn Rate" banglaHint="বর্তমান ঘণ্টার খরচ এবং আনুমানিক মাসিক খরচের হিসাব।" className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-slate-400">
              <DollarSign size={14} />
              <span className="text-xs">Current Hour</span>
            </div>
            <span className="text-xl font-bold text-[var(--foreground)] font-mono">$2.40</span>
          </div>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-slate-400">
              <Cpu size={14} />
              <span className="text-xs">Projected Monthly</span>
            </div>
            <span className="text-xl font-bold text-[#00f3ff] font-mono">$1,720</span>
          </div>
          <div className="text-[10px] text-slate-500">Based on 720h average utilization</div>
        </Card>

        <Card title="System Heartbeat" banglaHint="গুরুত্বপূর্ণ সার্ভিসসমূহের রিয়েল-টাইম কানেক্টিভিটি স্ট্যাটাস।" className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <Activity size={16} className="text-emerald-400" />
            <div>
              <div className="text-xs text-slate-400">API Server</div>
              <div className="text-sm font-bold text-emerald-400 font-mono">99.98%</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Cpu size={16} className="text-[#00f3ff]" />
            <div>
              <div className="text-xs text-slate-400">Model Provider</div>
              <div className="text-sm font-bold text-[#00f3ff] font-mono">99.95%</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Activity size={16} className="text-emerald-400" />
            <div>
              <div className="text-xs text-slate-400">Database</div>
              <div className="text-sm font-bold text-emerald-400 font-mono">100%</div>
            </div>
          </div>
        </Card>

        <Card title="Recent Alerts" banglaHint="সিস্টেমের সাম্প্রতিক গুরুত্বপূর্ণ অ্যালার্ট এবং ওয়ার্নিং মেসেজ।">
          <div className="flex flex-col gap-2">
            {alerts.map(alert => (
              <div key={alert.id} className={`flex items-start gap-2 p-2 rounded border text-[11px] font-mono ${severityColors[alert.severity]}`}>
                <AlertTriangle size={12} className="mt-0.5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-[var(--foreground)] truncate">{alert.message}</div>
                  <div className="text-slate-500 text-[9px] mt-0.5">{alert.time}</div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
