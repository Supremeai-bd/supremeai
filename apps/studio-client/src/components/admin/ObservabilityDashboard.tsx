// ============================================================================
// component >> ObservabilityDashboard.tsx
// project >> SupremeAI 2.0
// purpose >> Dashboards
// module >> src
// ============================================================================
import { Card, Badge } from '../ui';
import { AlertTriangle, TrendingUp } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';

const latencyData = [
  { time: '10:00', p50: 200, p95: 450, p99: 900 },
  { time: '11:00', p50: 210, p95: 470, p99: 920 },
  { time: '12:00', p50: 240, p95: 510, p99: 980 },
  { time: '13:00', p50: 220, p95: 480, p99: 940 },
  { time: '14:00', p50: 190, p95: 420, p99: 850 },
  { time: '15:00', p50: 180, p95: 400, p99: 820 },
];

const endpointErrors = [
  { endpoint: '/api/chat', errors: 12, total: 1240 },
  { endpoint: '/api/tts', errors: 3, total: 450 },
  { endpoint: '/api/embed', errors: 0, total: 890 },
  { endpoint: '/api/skill', errors: 7, total: 320 },
];

export function ObservabilityDashboard() {
  const [range, setRange] = useState<'1h' | '6h' | '24h' | '7d'>('6h');

  return (
    <div className="flex-grow p-6 overflow-y-auto bg-[var(--background)] text-[var(--foreground)]">
      <div className="flex items-center justify-between mb-6 pb-2 border-b border-[var(--border-color)]">
        <h2 className="text-lg font-bold font-['Space_Grotesk'] tracking-widest text-[#00f3ff] uppercase">
          📊 Observability & Intelligence
        </h2>
        <div className="flex gap-1">
          {(['1h', '6h', '24h', '7d'] as const).map(r => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={`px-2 py-1 text-[10px] font-bold rounded font-mono transition-colors ${
                range === r ? 'bg-[#00f3ff]/20 text-[#00f3ff]' : 'text-slate-400 hover:text-[var(--foreground)]'
              }`}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <Card title="QPS" banglaHint="প্রতি সেকেন্ডে মোট রিকোয়েস্ট বা কুয়েরির সংখ্যা।">
          <div className="text-2xl font-bold text-[var(--foreground)] font-mono">142</div>
          <div className="text-[10px] text-emerald-400 font-mono flex items-center gap-1">
            <TrendingUp size={10} /> +12% from last hour
          </div>
        </Card>
        <Card title="P50 Latency" banglaHint="৫০% রিকোয়েস্টের গড় প্রসেসিং সময় বা লেটেন্সি।">
          <div className="text-2xl font-bold text-[var(--foreground)] font-mono">180ms</div>
          <div className="text-[10px] text-emerald-400 font-mono flex items-center gap-1">
            <TrendingUp size={10} /> -5% improvement
          </div>
        </Card>
        <Card title="P99 Latency" banglaHint="৯৯% রিকোয়েস্টের সর্বোচ্চ প্রসেসিং সময় বা লেটেন্সি।">
          <div className="text-2xl font-bold text-[#00f3ff] font-mono">820ms</div>
          <div className="text-[10px] text-yellow-400 font-mono">Above threshold (800ms)</div>
        </Card>
        <Card title="Error Rate" banglaHint="মোট রিকোয়েস্টের সাপেক্ষে ফেইল হওয়া এরর পার্সেন্টেজ।">
          <div className="text-2xl font-bold text-emerald-400 font-mono">2.1%</div>
          <div className="text-[10px] text-slate-500 font-mono">Within acceptable range</div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <Card title="Latency Percentiles" banglaHint="ভিন্ন ভিন্ন পার্সেন্টাইলের (P50, P95, P99) লেটেন্সি চার্ট।">
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={latencyData}>
              <XAxis dataKey="time" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ backgroundColor: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: 8, color: 'var(--foreground)' }} />
              <Area type="monotone" dataKey="p50" stroke="#10b981" fillOpacity={0} strokeWidth={2} />
              <Area type="monotone" dataKey="p95" stroke="#f59e0b" fillOpacity={0} strokeWidth={2} />
              <Area type="monotone" dataKey="p99" stroke="#ef4444" fillOpacity={0} strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Endpoint Error Breakdown" banglaHint="নির্দিষ্ট এপিআই এন্ডপয়েন্ট ভিত্তিক এরর কাউন্ট বিবরণ।">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={endpointErrors}>
              <XAxis dataKey="endpoint" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ backgroundColor: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: 8, color: 'var(--foreground)' }} />
              <Bar dataKey="errors" fill="#ef4444" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <Card title="Recent Alerts & Incidents" banglaHint="সাম্প্রতিক ঘটে যাওয়া অ্যালার্ট, ওয়ার্নিং এবং রিস্টোরেশন স্ট্যাটাস।">
        <div className="flex flex-col gap-2">
          {[
            { severity: 'warning', msg: 'High P99 latency detected on /api/chat', time: '3m ago', status: 'Investigating' },
            { severity: 'danger', msg: 'Memory usage exceeded 85% on GCP Cloud Run', time: '12m ago', status: 'Resolved' },
            { severity: 'info', msg: 'Deployment v2.1.4 completed successfully', time: '45m ago', status: 'Completed' },
          ].map((alert, i) => (
            <div key={i} className="flex items-center gap-4 p-3 rounded-lg border border-[var(--border-color)] bg-[var(--alert-bg)]">
              <AlertTriangle size={14} className={
                alert.severity === 'danger' ? 'text-red-400' :
                alert.severity === 'warning' ? 'text-yellow-400' : 'text-[#00f3ff]'
              } />
              <div className="flex-1">
                <div className="text-xs text-[var(--foreground)] font-mono">{alert.msg}</div>
                <div className="text-[10px] text-slate-500 mt-0.5">{alert.time}</div>
              </div>
              <Badge variant={alert.status === 'Resolved' || alert.status === 'Completed' ? 'success' : 'warning'}>
                {alert.status}
              </Badge>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

