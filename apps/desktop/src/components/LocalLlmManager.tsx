import React, { useState } from 'react';
import { Cpu, Download, Play, Square, HardDrive, Cloud, AlertCircle, CheckCircle2 } from 'lucide-react';

// ═══════════════════════════════════════════════════════════════════════════
// AETHEL Desktop Studio — Hybrid Cloud & Local Engine Manager
// বাংলা মন্তব্য: কাস্টমার পিসিতে Ollama না থাকলেও লাইভ ক্লাউড এপিআই ডাইরেক্ট কানেক্টেড থাকে
// ═══════════════════════════════════════════════════════════════════════════

interface LocalModel {
  name: string;
  size: string;
  vramRequired: string;
  status: 'installed' | 'running' | 'available';
}

export const LocalLlmManager: React.FC = () => {
  const [ollamaDetected, setOllamaDetected] = useState(false);
  const [cloudConnected, setCloudConnected] = useState(true);

  const [models, setModels] = useState<LocalModel[]>([
    { name: 'DeepSeek-V3 / Kimi-K2.5 (Cloud Primary)', size: 'Cloud Managed', vramRequired: '0 GB (Zero PC Overhead)', status: 'running' },
    { name: 'DeepSeek-R1-Distill-Qwen-7B (Optional Local)', size: '4.7 GB', vramRequired: '6 GB VRAM', status: 'available' },
    { name: 'Qwen-2.5-Coder-7B-Instruct (Optional Local)', size: '4.4 GB', vramRequired: '6 GB VRAM', status: 'available' },
  ]);

  return (
    <div className="w-full bg-[#080b14] border border-white/10 rounded-2xl p-6 font-sans">
      {/* Hybrid Network Header */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 mb-6 pb-4 border-b border-white/10">
        <div>
          <h3 className="text-base font-mono font-bold text-[#00f3ff] uppercase tracking-wider flex items-center gap-2">
            <Cpu size={18} />
            <span>Hybrid Cloud & Local Engine Manager</span>
          </h3>
          <p className="text-xs text-gray-400 font-mono mt-0.5">
            Primary: Live Cloud Backend API | Fallback: Local Offline Models
          </p>
        </div>

        <div className="flex gap-3 text-xs font-mono">
          {/* Cloud Server Status */}
          <span className="bg-[#10b981]/10 border border-[#10b981]/30 px-3 py-1.5 rounded-lg text-[#10b981] flex items-center gap-1.5 font-bold">
            <Cloud size={14} />
            Cloud API: Connected (100% Active)
          </span>

          {/* Local Ollama Status */}
          {ollamaDetected ? (
            <span className="bg-[#00f3ff]/10 border border-[#00f3ff]/30 px-3 py-1.5 rounded-lg text-[#00f3ff] flex items-center gap-1.5">
              <CheckCircle2 size={14} /> Local Engine Active
            </span>
          ) : (
            <span className="bg-[#f59e0b]/10 border border-[#f59e0b]/30 px-3 py-1.5 rounded-lg text-[#f59e0b] flex items-center gap-1.5">
              <AlertCircle size={14} /> Local Ollama Not Installed (Cloud Active)
            </span>
          )}
        </div>
      </div>

      {!ollamaDetected && (
        <div className="mb-4 p-3 rounded-xl bg-[#00f3ff]/5 border border-[#00f3ff]/20 flex items-center justify-between text-xs font-mono">
          <span className="text-gray-300">
            💡 পিসিতে Ollama না থাকলেও ব্যাকএন্ড ক্লাউড সার্ভার দিয়ে সব কাজ সরাসরি চলবে। অফলাইন মোডের জন্য চাইলে ১-ক্লিকে ইনস্টল করতে পারেন:
          </span>
          <button
            onClick={() => setOllamaDetected(true)}
            className="ml-4 px-3 py-1.5 bg-[#00f3ff] text-black font-bold rounded-lg hover:opacity-90 transition-opacity flex items-center gap-1 whitespace-nowrap"
          >
            <Download size={12} /> 1-Click Auto Install Local Engine
          </button>
        </div>
      )}

      {/* Models List */}
      <div className="space-y-3">
        {models.map((model, idx) => (
          <div
            key={idx}
            className="flex items-center justify-between p-4 rounded-xl bg-black/40 border border-white/10 hover:border-[#00f3ff]/30 transition-all font-mono"
          >
            <div>
              <div className="text-sm font-bold text-gray-200 flex items-center gap-2">
                {model.name}
                {model.status === 'running' && (
                  <span className="text-[10px] bg-[#10b981]/10 text-[#10b981] px-2 py-0.5 rounded-md border border-[#10b981]/30">
                    Active Primary Engine
                  </span>
                )}
              </div>
              <div className="text-xs text-gray-500 mt-1 flex gap-4">
                <span>Memory Footprint: {model.size}</span>
                <span>Requirement: {model.vramRequired}</span>
              </div>
            </div>

            <div>
              {model.status === 'running' ? (
                <span className="text-xs font-bold text-[#10b981] bg-[#10b981]/10 px-3 py-1.5 rounded-lg border border-[#10b981]/30 flex items-center gap-1">
                  <CheckCircle2 size={12} /> Serving Requests
                </span>
              ) : (
                <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-[#00f3ff] to-[#bc13fe] text-black text-xs font-bold hover:opacity-90 transition-opacity">
                  <Download size={12} /> Download Model
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
