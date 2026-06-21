interface ConfigEditorProps {
  envConfig: Record<string, string>;
  setEnvConfig: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  handleSaveConfig: () => void;
}

export function ConfigEditor({ envConfig, setEnvConfig, handleSaveConfig }: ConfigEditorProps) {
  return (
    <div className="flex-grow bg-black/50 p-6 overflow-y-auto font-mono text-xs">
      <div className="flex justify-between items-center mb-4 pb-2 border-b border-slate-800">
        <h3 className="text-sm font-bold text-slate-200">⚙️ ENVIRONMENTAL CONFIGURATION</h3>
        <button
          onClick={handleSaveConfig}
          className="bg-emerald-500 hover:bg-emerald-400 text-black font-bold px-3 py-1.5 rounded transition-colors uppercase"
        >
          SAVE CONFIG
        </button>
      </div>

      <div className="flex flex-col gap-4">
        {Object.keys(envConfig).map(k => (
          <div key={k} className="flex flex-col md:flex-row md:items-center gap-2 bg-[#0c0d12] border border-slate-900 p-3 rounded-lg">
            <span className="font-bold text-slate-300 min-w-[200px] select-all">{k}</span>
            <input
              type={envConfig[k] === '********' ? 'password' : 'text'}
              value={envConfig[k]}
              onChange={e => {
                const val = e.target.value;
                setEnvConfig(prev => ({ ...prev, [k]: val }));
              }}
              className="flex-grow bg-[#06080b] border border-slate-800 rounded px-3 py-1 text-white outline-none focus:border-[#00f3ff] font-mono"
            />
          </div>
        ))}
      </div>
    </div>
  );
}
