interface LiveLogsProps {
  liveLogs: string[];
  setLiveLogs: (logs: string[]) => void;
}

export function LiveLogs({ liveLogs, setLiveLogs }: LiveLogsProps) {
  return (
    <div className="flex-grow flex flex-col bg-black/80 p-4 font-mono text-xs overflow-y-auto">
      <div className="flex justify-between items-center mb-3 pb-2 border-b border-slate-800">
        <span className="text-slate-400 font-bold uppercase tracking-wider text-[10px]">Real-time Live Stream (supremeai.log)</span>
        <button onClick={() => setLiveLogs([])} className="text-red-400 hover:text-red-300 font-bold text-[10px]">CLEAR SCREEN</button>
      </div>
      <div className="flex-grow flex flex-col gap-1 overflow-y-auto max-h-[70vh]">
        {liveLogs.length === 0 ?
          <div className="text-slate-500 italic">Listening for incoming server logs...</div>
          :
          liveLogs.map((log, idx) => (
            <div key={idx} className="text-[#00ff66] whitespace-pre-wrap">{log}</div>
          ))
        }
      </div>
    </div>
  );
}
