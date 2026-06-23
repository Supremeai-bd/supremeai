import { Card, Badge } from '../ui';
import { GitBranch, Play, RotateCcw, FlaskConical, CheckCircle2, AlertTriangle } from 'lucide-react';
import { useState } from 'react';

const PIPELINE_STAGES = [
  { id: 'build', name: 'Build', status: 'success', duration: '2m 34s' },
  { id: 'test', name: 'Test', status: 'success', duration: '5m 12s' },
  { id: 'lint', name: 'Lint', status: 'success', duration: '1m 05s' },
  { id: 'deploy-staging', name: 'Deploy Staging', status: 'success', duration: '3m 22s' },
  { id: 'e2e', name: 'E2E Tests', status: 'running', duration: '...' },
  { id: 'deploy-prod', name: 'Deploy Production', status: 'pending', duration: '-' },
];

interface FeatureFlag {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  rollout: number;
  environment: 'staging' | 'production';
}

const MOCK_FLAGS: FeatureFlag[] = [
  { id: '1', name: 'new_chat_ui', description: 'New chat interface with streaming', enabled: true, rollout: 25, environment: 'production' },
  { id: '2', name: 'rag_v2', description: 'Improved RAG retrieval algorithm', enabled: false, rollout: 0, environment: 'staging' },
  { id: '3', name: 'dark_mode', description: 'Dark mode toggle for all users', enabled: true, rollout: 100, environment: 'production' },
];

export function CICDVisualizer() {
  const [flags, setFlags] = useState<FeatureFlag[]>(MOCK_FLAGS);

  const toggleFlag = (id: string) => {
    setFlags(flags.map(f => (f.id === id ? { ...f, enabled: !f.enabled } : f)));
  };

  const updateRollout = (id: string, rollout: number) => {
    setFlags(flags.map(f => (f.id === id ? { ...f, rollout } : f)));
  };

  const statusConfig: Record<string, { variant: 'success' | 'warning' | 'info' | 'danger'; icon: typeof GitBranch }> = {
    success: { variant: 'success', icon: CheckCircle2 },
    running: { variant: 'warning', icon: Play },
    pending: { variant: 'info', icon: GitBranch },
    failed: { variant: 'danger', icon: AlertTriangle },
  };

  const handleDeploy = async () => {
    try {
      const API_BASE = import.meta.env.VITE_API_BASE || '';
      const res = await fetch(`${API_BASE}/admin-api/deploy`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('supremeai_admin_token') || 'supreme-god-password'}`
        }
      });
      if (res.ok) {
        const data = await res.json();
        alert(`✅ ${data.message || 'Deployment triggered successfully!'}`);
      } else {
        alert('❌ Deployment failed (unauthorized or server error).');
      }
    } catch (e: any) {
      alert(`❌ Deployment failed: ${e.message}`);
    }
  };

  return (
    <div className="flex-grow p-6 overflow-y-auto bg-[#030508]">
      <div className="flex items-center justify-between mb-6 pb-2 border-b border-[#00f3ff]/15">
        <h2 className="text-lg font-bold font-['Space_Grotesk'] tracking-widest text-[#00f3ff] uppercase">
          🚀 CI/CD & Deployment Control
        </h2>
        <div className="flex gap-2">
          <button className="flex items-center gap-2 px-3 py-1.5 rounded border border-slate-800 text-slate-400 hover:text-white text-[10px] font-bold font-mono uppercase transition-colors">
            <RotateCcw size={10} /> History
          </button>
          <button
            onClick={handleDeploy}
            className="flex items-center gap-2 px-3 py-1.5 rounded bg-[#00f3ff] text-black text-[10px] font-bold font-mono uppercase hover:bg-cyan-400 transition-colors"
          >
            <Play size={10} /> Deploy
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <Card title="Pipeline: main">
          <div className="flex flex-col gap-3">
            {PIPELINE_STAGES.map((stage, i) => {
              const config = statusConfig[stage.status];
              return (
                <div key={stage.id} className="flex items-center gap-3">
                  <div className="flex flex-col items-center">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                      stage.status === 'success' ? 'bg-emerald-950 text-emerald-400' :
                      stage.status === 'running' ? 'bg-yellow-950 text-yellow-400 animate-pulse' :
                      'bg-slate-800 text-slate-500'
                    }`}>
                      <config.icon size={14} />
                    </div>
                    {i < PIPELINE_STAGES.length - 1 && (
                      <div className="w-0.5 h-6 bg-slate-800" />
                    )}
                  </div>
                  <div className="flex-1 flex items-center justify-between">
                    <div>
                      <div className="text-xs font-bold text-white font-mono">{stage.name}</div>
                      <div className="text-[10px] text-slate-500 font-mono">{stage.duration}</div>
                    </div>
                    <Badge variant={config.variant}>{stage.status.toUpperCase()}</Badge>
                  </div>
                </div>
              );
            })}
          </div>
        </Card>

        <Card title="Feature Flags" icon={<FlaskConical size={14} />}>
          <div className="flex flex-col gap-3">
            {flags.map(flag => (
              <div key={flag.id} className="p-3 rounded-lg border border-slate-800 bg-slate-900/30">
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <div className="text-xs font-bold text-white font-mono">{flag.name}</div>
                    <div className="text-[10px] text-slate-500 mt-0.5">{flag.description}</div>
                  </div>
                  <button
                    onClick={() => toggleFlag(flag.id)}
                    className={`w-8 h-4 rounded-full transition-colors ${flag.enabled ? 'bg-[#00f3ff]' : 'bg-slate-700'}`}
                  >
                    <div className={`w-3 h-3 rounded-full bg-white transition-transform ${flag.enabled ? 'translate-x-4' : 'translate-x-0.5'}`} />
                  </button>
                </div>
                {flag.enabled && (
                  <div className="mt-2">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[10px] text-slate-400">Rollout</span>
                      <span className="text-[10px] text-white font-mono">{flag.rollout}%</span>
                    </div>
                    <div className="w-full bg-slate-800 rounded-full h-1">
                      <div className="h-full rounded-full bg-[#00f3ff]" style={{ width: `${flag.rollout}%` }} />
                    </div>
                    <div className="flex gap-1 mt-2">
                      <button onClick={() => updateRollout(flag.id, Math.max(0, flag.rollout - 10))} className="text-[9px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 hover:text-white">-10%</button>
                      <button onClick={() => updateRollout(flag.id, Math.min(100, flag.rollout + 10))} className="text-[9px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 hover:text-white">+10%</button>
                    </div>
                  </div>
                )}
                <div className="mt-2">
                  <Badge variant={flag.environment === 'production' ? 'success' : 'info'}>{flag.environment}</Badge>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
