export function CommandCenter(): JSX.Element {
  return (
    <div className="flex-grow p-6 overflow-y-auto bg-[#030508]">
      <div className="flex items-center justify-between mb-6 pb-2 border-b border-[#00f3ff]/15">
        <h2 className="text-lg font-bold font-['Space_Grotesk'] tracking-widest text-[#00f3ff] uppercase">
          🔱 SUPREMEAI 2.0 SYSTEM STATUS & OVERVIEW
        </h2>
        <span className="text-xs px-3 py-1 rounded bg-[#00f3ff]/10 text-[#00f3ff] border border-[#00f3ff]/20 font-mono">
          SYNCED: 2026-06-20
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div className="bg-[#080b11]/80 backdrop-blur-md border border-[#00f3ff]/10 rounded-xl p-5 flex flex-col gap-4 shadow-[0_4px_20px_rgba(0,243,255,0.05)] hover:border-[#00f3ff]/30 transition-all duration-300">
          <div className="flex items-center justify-between">
            <span className="font-bold tracking-wider text-sm text-slate-200">সামগ্রিক অগ্রগতি (Progress)</span>
            <span className="text-[#00f3ff] font-bold text-sm">92%</span>
          </div>
          <div className="w-full bg-[#121622] rounded-full h-2 overflow-hidden border border-white/[0.04]">
            <div className="bg-gradient-to-r from-[#00f3ff] to-[#bc13fe] h-full" style={{ width: '92%' }}></div>
          </div>
          <div className="text-xs text-slate-400 leading-relaxed font-sans flex flex-col gap-2">
            <div>• <strong>GCP Cloud Run</strong>: Live & Routing active.</div>
            <div>• <strong>Firebase Hosting</strong>: React studio client deployed.</div>
            <div>• <strong>CI/CD</strong>: Unified single pipeline configured.</div>
            <div>• <strong>E2E Tests</strong>: Automated Firebase & VS Code runs passing.</div>
          </div>
        </div>

        <div className="bg-[#080b11]/80 backdrop-blur-md border border-[#00f3ff]/10 rounded-xl p-5 flex flex-col gap-4 shadow-[0_4px_20px_rgba(0,243,255,0.05)] hover:border-[#00f3ff]/30 transition-all duration-300">
          <div className="flex items-center justify-between">
            <span className="font-bold tracking-wider text-sm text-slate-200">টেস্ট সুইট (Test Matrix)</span>
            <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-emerald-950 text-emerald-400 border border-emerald-900">HEALTHY</span>
          </div>
          <div className="flex justify-around items-center py-2 bg-black/30 border border-slate-900 rounded-lg">
            <div className="text-center">
              <div className="text-lg font-bold text-white">127</div>
              <div className="text-[10px] text-slate-500 font-mono">TOTAL</div>
            </div>
            <div className="w-[1px] h-8 bg-slate-800"></div>
            <div className="text-center">
              <div className="text-lg font-bold text-emerald-400">125</div>
              <div className="text-[10px] text-emerald-500 font-mono">PASSED</div>
            </div>
            <div className="w-[1px] h-8 bg-slate-800"></div>
            <div className="text-center">
              <div className="text-lg font-bold text-yellow-400">2</div>
              <div className="text-[10px] text-yellow-500 font-mono">SKIPPED</div>
            </div>
          </div>
          <div className="text-xs text-slate-400 leading-relaxed font-sans">
            ২৪টি টেস্ট ফাইলে মোট ১২৭টি টেস্ট কেস সফলভাবে রান হয়েছে।
          </div>
        </div>

        <div className="bg-[#080b11]/80 backdrop-blur-md border border-[#00f3ff]/10 rounded-xl p-5 flex flex-col gap-4 shadow-[0_4px_20px_rgba(0,243,255,0.05)] hover:border-[#00f3ff]/30 transition-all duration-300">
          <div className="flex items-center justify-between">
            <span className="font-bold tracking-wider text-sm text-slate-200">এআই স্কিলস (Active Skills)</span>
            <span className="text-[#bc13fe] text-xs font-mono">ACTIVE</span>
          </div>
          <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto">
            {['multi_account_rotator', 'local_search_rag', 'docker_sandbox', 'cost_auditor', 'whisper_voice_handler', 'cot_reasoner', 'skill_loader', 'bengali_nlp'].map(skill => (
              <span key={skill} className="px-2 py-1 text-[10px] rounded bg-[#101424] text-slate-300 border border-slate-800 font-mono">
                {skill}
              </span>
            ))}
          </div>
        </div>

        <div className="bg-[#080b11]/80 backdrop-blur-md border border-[#00f3ff]/10 rounded-xl p-5 flex flex-col gap-4 shadow-[0_4px_20px_rgba(0,243,255,0.05)] hover:border-[#00f3ff]/30 transition-all duration-300">
          <div className="flex items-center justify-between">
            <span className="font-bold tracking-wider text-sm text-slate-200">ডিপেন্ডেন্সি (Dependencies)</span>
            <span className="text-indigo-400 text-xs font-mono">VERIFIED</span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs font-mono text-slate-400">
            <div>• fastapi & uvicorn</div>
            <div>• sentry-sdk</div>
            <div>• playwright</div>
            <div>• firebase-admin</div>
            <div>• easyocr</div>
            <div>• testing-library</div>
          </div>
        </div>

        <div className="bg-[#080b11]/80 backdrop-blur-md border border-[#00f3ff]/10 rounded-xl p-5 flex flex-col gap-4 shadow-[0_4px_20px_rgba(0,243,255,0.05)] hover:border-[#00f3ff]/30 transition-all duration-300">
          <div className="flex items-center justify-between">
            <span className="font-bold tracking-wider text-sm text-slate-200">পেন্ডিং কাজ (Manual Tasks)</span>
            <span className="text-yellow-400 text-xs font-mono">PENDING</span>
          </div>
          <div className="text-xs text-slate-400 leading-relaxed font-sans flex flex-col gap-2">
            <label className="flex items-center gap-2 cursor-pointer hover:text-white transition-colors">
              <input type="checkbox" disabled checked className="accent-[#00f3ff]" />
              <span className="line-through text-slate-500">GCP Run & Services Enablement</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer hover:text-white transition-colors">
              <input type="checkbox" disabled className="accent-[#00f3ff]" />
              <span>Supabase Shared DB & Upstash Redis</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer hover:text-white transition-colors">
              <input type="checkbox" disabled className="accent-[#00f3ff]" />
              <span>Cloudflare load balancer integration</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer hover:text-white transition-colors">
              <input type="checkbox" disabled className="accent-[#00f3ff]" />
              <span>Telegram/Discord Bot tokens config</span>
            </label>
          </div>
        </div>

        <div className="bg-[#080b11]/80 backdrop-blur-md border border-[#00f3ff]/10 rounded-xl p-5 flex flex-col gap-4 shadow-[0_4px_20px_rgba(0,243,255,0.05)] hover:border-[#00f3ff]/30 transition-all duration-300">
          <div className="flex items-center justify-between">
            <span className="font-bold tracking-wider text-sm text-slate-200">গিটহাব ও ডেপ্লয় (CI/CD)</span>
            <span className="text-purple-400 text-xs font-mono">CONFIGURED</span>
          </div>
          <div className="text-xs text-slate-400 leading-relaxed font-sans flex flex-col gap-2">
            <div>• <strong>Workflow</strong>: `.github/workflows/ci-cd.yml`</div>
            <div>• <strong>Strategy</strong>: Blue-Green staging deployment.</div>
            <div>• <strong>Fallback</strong>: Auto-rollback to stable version on error.</div>
            <div>• <strong>Local Cache</strong>: Playwright headless binaries resolved.</div>
          </div>
        </div>
      </div>
    </div>
  );
}
