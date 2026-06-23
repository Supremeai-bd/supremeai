// ============================================================================
// component >> CloudOrchestrator.tsx
// project >> SupremeAI 2.0
// purpose >> Cloud provider
// module >> src
// ============================================================================
import { Card, Badge, Skeleton } from '../ui';
import { Globe, HardDrive, Cpu, Network, RefreshCw } from 'lucide-react';

const CLOUD_PROVIDERS = [
  { id: 'gcp', name: 'Google Cloud Platform', color: '#4285f4', icon: Globe },
  { id: 'aws', name: 'AWS', color: '#ff9900', icon: Globe },
  { id: 'azure', name: 'Azure', color: '#0078d4', icon: Globe },
  { id: 'cloudflare', name: 'Cloudflare', color: '#f48120', icon: Network },
  { id: 'supabase', name: 'Supabase', color: '#3ecf8e', icon: HardDrive },
  { id: 'railway', name: 'Railway', color: '#0b0d0e', icon: Cpu },
  { id: 'render', name: 'Render', color: '#46a5f5', icon: Globe },
];

export function CloudOrchestrator() {
  const { data: health, isLoading } = useQuery({
    queryKey: ['cloud-health'],
    queryFn: () => fetch('/admin-api/health-map').then(r => r.json()),
  });

  const providerHealth = Object.entries(health || {}).map(([id, data]: [string, any]) => ({
    id,
    name: CLOUD_PROVIDERS.find(p => p.id === id)?.name || id,
    color: CLOUD_PROVIDERS.find(p => p.id === id)?.color || '#666',
    status: data.status === 'healthy' ? 'healthy' : data.status === 'degraded' ? 'degraded' : 'down',
    latency: data.latency,
    region: data.region,
  }));

  return (
    <div className="flex-grow p-6 overflow-y-auto bg-[#030508]">
      <div className="flex items-center justify-between mb-6 pb-2 border-b border-[#00f3ff]/15">
        <h2 className="text-lg font-bold font-['Space_Grotesk'] tracking-widest text-[#00f3ff] uppercase">
          ☁️ Cloud Orchestrator
        </h2>
        <button className="flex items-center gap-2 px-3 py-1.5 rounded border border-[#00f3ff]/30 text-[#00f3ff] hover:bg-[#00f3ff]/10 text-[10px] font-bold font-mono uppercase transition-colors">
          <RefreshCw size={10} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
        {isLoading ? (
          <><Skeleton className="h-32 w-full" /><Skeleton className="h-32 w-full" /><Skeleton className="h-32 w-full" /><Skeleton className="h-32 w-full" /></>
        ) : (
          providerHealth.map(p => (
            <Card key={p.id} title={p.name} icon={
              <span className="w-3 h-3 rounded-full" style={{ backgroundColor: p.color }} />
            }>
              <div className="flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-slate-400">Status</span>
                  <Badge variant={p.status === 'healthy' ? 'success' : p.status === 'degraded' ? 'warning' : 'danger'}>{p.status}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-slate-400">Latency</span>
                  <span className="text-xs font-bold text-white font-mono">{p.latency}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-slate-400">Region</span>
                  <span className="text-xs font-bold text-slate-300 font-mono">{p.region}</span>
                </div>
              </div>
            </Card>
          ))
        )}
      </div>

      <Card title="Resource Utilization">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <div className="text-[10px] text-slate-400 uppercase mb-2">CPU Usage</div>
            <div className="flex items-end gap-2">
              <span className="text-3xl font-bold text-white font-mono">42</span>
              <span className="text-sm text-slate-500 mb-1">%</span>
            </div>
            <div className="w-full bg-slate-800 rounded-full h-1.5 mt-2">
              <div className="h-full rounded-full bg-[#00f3ff]" style={{ width: '42%' }} />
            </div>
          </div>
          <div>
            <div className="text-[10px] text-slate-400 uppercase mb-2">Memory Usage</div>
            <div className="flex items-end gap-2">
              <span className="text-3xl font-bold text-white font-mono">68</span>
              <span className="text-sm text-slate-500 mb-1">%</span>
            </div>
            <div className="w-full bg-slate-800 rounded-full h-1.5 mt-2">
              <div className="h-full rounded-full bg-purple-500" style={{ width: '68%' }} />
            </div>
          </div>
          <div>
            <div className="text-[10px] text-slate-400 uppercase mb-2">Network I/O</div>
            <div className="flex items-end gap-2">
              <span className="text-3xl font-bold text-white font-mono">1.2</span>
              <span className="text-sm text-slate-500 mb-1">Gbps</span>
            </div>
            <div className="w-full bg-slate-800 rounded-full h-1.5 mt-2">
              <div className="h-full rounded-full bg-emerald-500" style={{ width: '35%' }} />
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
