interface HealthMapProps {
  healthMap: any;
}

export function HealthMap({ healthMap }: HealthMapProps) {
  return (
    <div className="flex-grow bg-black/50 p-6 overflow-y-auto font-mono text-xs">
      <h3 className="text-sm font-bold text-slate-200 mb-6 pb-2 border-b border-slate-800">📡 SYSTEM HEALTH MAP</h3>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-[#0c0d12] border border-slate-900 rounded-xl p-5 flex flex-col gap-3">
          <div className="flex justify-between items-center">
            <span className="font-bold text-white tracking-widest">GOOGLE CLOUD</span>
            <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-emerald-950 text-emerald-400 border border-emerald-900">ACTIVE</span>
          </div>
          <div className="text-slate-400 mt-2">Latency: {healthMap?.gcp?.latency || "42ms"}</div>
          <div className="text-slate-400">Region: {healthMap?.gcp?.region || "us-central1"}</div>
        </div>
        <div className="bg-[#0c0d12] border border-slate-900 rounded-xl p-5 flex flex-col gap-3">
          <div className="flex justify-between items-center">
            <span className="font-bold text-white tracking-widest">RAILWAY HOST</span>
            <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-emerald-950 text-emerald-400 border border-emerald-900">ACTIVE</span>
          </div>
          <div className="text-slate-400 mt-2">Latency: {healthMap?.railway?.latency || "78ms"}</div>
          <div className="text-slate-400">Region: {healthMap?.railway?.region || "eu-west"}</div>
        </div>
        <div className="bg-[#0c0d12] border border-slate-900 rounded-xl p-5 flex flex-col gap-3">
          <div className="flex justify-between items-center">
            <span className="font-bold text-white tracking-widest">RENDER DEPLOY</span>
            <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-yellow-950 text-yellow-400 border border-yellow-900">DEGRADED</span>
          </div>
          <div className="text-slate-400 mt-2">Latency: {healthMap?.render?.latency || "250ms"}</div>
          <div className="text-slate-400">Region: {healthMap?.render?.region || "singapore"}</div>
        </div>
      </div>
    </div>
  );
}
