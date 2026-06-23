// ============================================================================
// component >> QuickPresets.tsx
// project >> SupremeAI 2.0
// purpose >> General utility
// module >> src
// ============================================================================
const PRESETS = [
  {
    title: 'Code Generator',
    description: 'Python binary search algorithm',
    prompt: 'Python binary search algorithm design',
  },
  {
    title: 'Translator',
    description: 'Translate to Bengali',
    prompt: "Translate 'Welcome to SupremeAI' to Bengali",
  },
  {
    title: 'Content Writer',
    description: 'Startup marketing email',
    prompt: 'Write a marketing email for an AI startup',
  },
];

export function QuickPresets({ onSelectPreset }: QuickPresetsProps) {
  return (
    <div className="w-72 flex-shrink-0 bg-[#08090d]/60 backdrop-blur-lg border-r border-[rgba(138,92,246,0.15)] flex flex-col p-4 z-10">
      <div className="text-[11px] uppercase tracking-[2px] text-[#bc13fe] font-semibold mb-3">
        Quick Presets
      </div>
      <div className="flex-grow overflow-y-auto flex flex-col gap-3">
        {PRESETS.map(preset => (
          <div
            key={preset.title}
            onClick={() => onSelectPreset(preset.prompt)}
            className="bg-white/[0.02] border border-white/[0.04] rounded-lg p-3 text-xs cursor-pointer hover:border-[#bc13fe]/30 hover:bg-[#bc13fe]/5 transition-all duration-300"
          >
            <strong className="text-[#f8f9fa] block mb-1">{preset.title}</strong>
            <span className="text-slate-400 text-[11px]">{preset.description}</span>
          </div>
        ))}
      </div>

      <div className="mt-4 p-3 bg-[#bc13fe]/5 border border-[#bc13fe]/20 rounded-lg flex items-center gap-3">
        <span className="w-2.5 h-2.5 rounded-full bg-[#bc13fe] animate-pulse"></span>
        <span className="text-xs font-semibold text-slate-300">Operator Core Ready</span>
      </div>
    </div>
  );
}
