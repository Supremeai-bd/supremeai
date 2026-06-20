interface HeaderProps {
  currentTab: 'customer' | 'admin';
  setCurrentTab: (tab: 'customer' | 'admin') => void;
}

export function Header({ currentTab, setCurrentTab }: HeaderProps) {
  return (
    <div className="h-14 flex-shrink-0 bg-[#06080d]/80 backdrop-blur-md border-b border-[rgba(0,243,255,0.15)] flex items-center justify-between px-6 z-20">
      <div className="flex items-center gap-3">
        <span className="text-2xl drop-shadow-[0_0_10px_#00f3ff]">🔱</span>
        <span className="font-bold tracking-widest text-lg font-['Space_Grotesk'] text-white">
          SUPREME<span className="text-[#00f3ff]">AI</span>
        </span>
        <span className="hidden sm:inline-flex items-center gap-2 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-cyan-950/50 text-[#00f3ff] border border-cyan-800/40">
          <span className="w-1.5 h-1.5 rounded-full bg-[#00f3ff] animate-pulse"></span>
          NEURAL LINK ACTIVE
        </span>
      </div>

      {/* Global tab switch */}
      <div className="flex bg-[#0f121d] rounded-lg p-1 border border-slate-800">
        <button 
          onClick={() => { setCurrentTab('customer'); window.location.hash = ''; }}
          className={`px-4 py-1.5 text-xs font-semibold rounded-md transition-all duration-300 ${currentTab === 'customer' ? 'bg-[#00f3ff]/20 text-[#00f3ff] border border-[#00f3ff]/30' : 'text-slate-400 hover:text-white'}`}
        >
          Operator Studio
        </button>
        <button 
          onClick={() => { setCurrentTab('admin'); window.location.hash = 'admin'; }}
          className={`px-4 py-1.5 text-xs font-semibold rounded-md transition-all duration-300 ${currentTab === 'admin' ? 'bg-[#bc13fe]/20 text-[#bc13fe] border border-[#bc13fe]/30' : 'text-slate-400 hover:text-white'}`}
        >
          God Control Center
        </button>
      </div>

      <div className="text-xs text-slate-400 font-mono hidden md:block">
        v2.0 (FastAPI Core)
      </div>
    </div>
  );
}
