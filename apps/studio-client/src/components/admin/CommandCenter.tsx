import { useEffect, useState, useMemo } from 'react';
import ReactFlow, {
  Background,
  useNodesState,
  useEdgesState,
  MarkerType,
} from 'reactflow';
import 'reactflow/dist/style.css';
import './AethelCoreStyles.css';
import { 
  Cpu, 
  Terminal, 
  Activity, 
  DollarSign, 
  Layers, 
  Volume2,
  ShieldAlert
} from 'lucide-react';
import AethelNode from './AethelNode';
import { GlassmorphicPanel } from './GlassmorphicPanel';
import { ConsentMatrixModal } from './ConsentMatrixModal';

// বাংলা মন্তব্য: লাইভ রিকোয়েস্ট ফিডের জন্য ডামি ডেটা ডিক্লেয়ার করা হচ্ছে
const initialFeed = [
  { id: 1, user: "User_942", request: "Check patient record anomalies", agent: "Medical Agent", status: "RESOLVED", time: "10s ago" },
  { id: 2, user: "User_108", request: "Audit smart contract at 0x71a...", agent: "Legal Agent", status: "PROCESSING", time: "Just now" },
  { id: 3, user: "System_Daemon", request: "Verify 6-layer hallucination limits", agent: "Firewall Agent", status: "NOMINAL", time: "1m ago" },
];

export function CommandCenter() {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges] = useEdgesState([]);
  const [activeModel, setActiveModel] = useState("Gemini-2.5-Flash");
  const [systemLoad, setSystemLoad] = useState(38);
  const [pingStatus, setPingStatus] = useState<Record<string, number>>({ OpenRouter: 45, Groq: 28, DeepSeek: 110 });
  const [liveLogs, setLiveLogs] = useState<string[]>([
    "[SYSTEM] Initiating Aethel Core visual telemetry...",
    "[SECURITY] 6-layer Hallucination Defense status: ACTIVE",
    "[MESH] GCP Cloud Run node load balanced successfully.",
  ]);
  const feed = initialFeed;
  const [voiceOverrideActive, setVoiceOverrideActive] = useState(false);
  
  // Consent Matrix state
  const [consentModalOpen, setConsentModalOpen] = useState(false);

  // Custom node types for ReactFlow
  const nodeTypes = useMemo(() => ({ aethel: AethelNode }), []);

  // বাংলা মন্তব্য: রিয়েল-টাইম ডাটা সিমুলেশনের জন্য টাইমার সেটআপ করা হচ্ছে
  useEffect(() => {
    const interval = setInterval(() => {
      setSystemLoad(prev => Math.min(Math.max(prev + Math.floor(Math.random() * 7) - 3, 20), 85));
      setPingStatus({
        OpenRouter: Math.floor(Math.random() * 20) + 35,
        Groq: Math.floor(Math.random() * 15) + 20,
        DeepSeek: Math.floor(Math.random() * 40) + 90,
      });

      const logs = [
        `[METRICS] Latency check completed: OpenRouter ${Math.floor(Math.random() * 20) + 35}ms.`,
        `[EVOLUTION] Generated skill optimizer checkpoint...`,
        `[SECURITY] Rate limiter verified. All systems nominal.`,
      ];
      setLiveLogs(prev => [logs[Math.floor(Math.random() * logs.length)], ...prev.slice(0, 15)]);
    }, 4000);

    return () => clearInterval(interval);
  }, []);

  const handleVoiceOverride = () => {
    setVoiceOverrideActive(!voiceOverrideActive);
    setLiveLogs(prev => [
      voiceOverrideActive 
        ? "[CMD] Voice override system DEACTIVATED." 
        : "[CMD] Voice override system LISTENING (Bangla / English UI)...",
      ...prev
    ]);
  };

  const triggerConsentMatrix = () => {
    setConsentModalOpen(true);
  };

  useEffect(() => {
    const initialNodes = [
      {
        id: 'central-orb',
        type: 'default',
        data: {
          label: (
            <div className="flex flex-col items-center justify-center p-2 text-center h-full w-full">
              <span className="font-bold text-[12px] tracking-widest text-[#00f3ff] uppercase mb-4">SupremeAI Orchestrator</span>
              <div className="central-orb-outer">
                <div className="central-orb-inner">
                  <div className="central-orb-core flex items-center justify-center bg-[#00f3ff] w-[40px] h-[40px] rounded-full shadow-[0_0_20px_#00f3ff]">
                    <Cpu size={20} className="text-slate-950" />
                  </div>
                </div>
              </div>
              <div className="mt-6 flex flex-col gap-1">
                <span className="text-[10px] text-[#00ff66] font-mono">Model: {activeModel}</span>
                <span className="text-[10px] text-slate-400 font-mono">Global Load: {systemLoad}%</span>
              </div>
            </div>
          )
        },
        position: { x: 260, y: 150 },
        className: 'glass-panel glow-cyan rounded-full border border-[#00f3ff]/40 shadow-[0_0_50px_rgba(0,243,255,0.15)] flex items-center justify-center',
        style: { width: 280, height: 280, background: 'rgba(5, 9, 23, 0.85)', backdropFilter: 'blur(16px)' }
      },
      {
        id: 'node-swarm',
        type: 'aethel',
        data: {
          type: 'swarm',
          status: 'Nominal',
          label: (
            <div className="text-left font-mono pl-2">
              <div className="text-[#00f3ff] font-bold text-[11px]">🤖 Agent Swarm</div>
              <div className="text-[9px] text-slate-400 mt-1">Legal, Medical, Trading</div>
            </div>
          )
        },
        position: { x: 20, y: 60 }
      },
      {
        id: 'node-mesh',
        type: 'aethel',
        data: {
          type: 'mesh',
          status: 'Balanced',
          label: (
            <div className="text-left font-mono pl-2">
              <div className="text-[#00ff66] font-bold text-[11px]">🌐 Cloud Mesh</div>
              <div className="text-[9px] text-slate-400 mt-1">GCP, Render, Railway</div>
            </div>
          )
        },
        position: { x: 20, y: 180 }
      },
      {
        id: 'node-firewall',
        type: 'aethel',
        data: {
          type: 'firewall',
          status: 'Active',
          label: (
            <div className="text-left font-mono pl-2">
              <div className="text-[#ffbd2e] font-bold text-[11px]">🛡️ Security Wall</div>
              <div className="text-[9px] text-slate-400 mt-1">6-Layer Defense & Inject</div>
            </div>
          )
        },
        position: { x: 20, y: 300 }
      },
      {
        id: 'node-evolution',
        type: 'aethel',
        data: {
          type: 'evolution',
          status: 'Standby',
          label: (
            <div className="text-left font-mono pl-2">
              <div className="text-[#00f3ff] font-bold text-[11px]">⚡ Evolution Engine</div>
              <div className="text-[9px] text-slate-400 mt-1">Self-Learning Skills</div>
            </div>
          )
        },
        position: { x: 20, y: 420 }
      },
      {
        id: 'node-api-gw',
        type: 'aethel',
        data: {
          type: 'gateway',
          status: 'Warning',
          label: (
            <div className="text-left font-mono pl-2">
              <div className="text-[#00f3ff] font-bold text-[11px]">🔌 API Gateways</div>
              <div className="text-[8px] text-slate-400 mt-1">
                OpenRouter: {pingStatus.OpenRouter}ms | Groq: {pingStatus.Groq}ms
              </div>
            </div>
          )
        },
        position: { x: 600, y: 100 }
      },
      {
        id: 'node-memory',
        type: 'aethel',
        data: {
          type: 'memory',
          status: 'Nominal',
          label: (
            <div className="text-left font-mono pl-2">
              <div className="text-[#ffbd2e] font-bold text-[11px]">🧠 Memory Core</div>
              <div className="text-[9px] text-slate-400 mt-1">Pinecone / Chroma DB</div>
            </div>
          )
        },
        position: { x: 600, y: 240 }
      },
      {
        id: 'node-cicd',
        type: 'aethel',
        data: {
          type: 'cicd',
          status: 'Nominal',
          label: (
            <div className="text-left font-mono pl-2">
              <div className="text-[#00ff66] font-bold text-[11px]">⚙️ CI/CD Pipeline</div>
              <div className="text-[9px] text-slate-400 mt-1">GitHub Actions Live</div>
            </div>
          )
        },
        position: { x: 600, y: 380 }
      }
    ];

    const initialEdges = [
      { id: 'e-swarm', source: 'node-swarm', target: 'central-orb', animated: true, style: { stroke: '#00f3ff', strokeWidth: 1.5 }, markerEnd: { type: MarkerType.ArrowClosed, color: '#00f3ff' } },
      { id: 'e-mesh', source: 'node-mesh', target: 'central-orb', animated: true, style: { stroke: '#00ff66', strokeWidth: 1.5 }, markerEnd: { type: MarkerType.ArrowClosed, color: '#00ff66' } },
      { id: 'e-firewall', source: 'node-firewall', target: 'central-orb', animated: true, style: { stroke: '#ffbd2e', strokeWidth: 1.5 }, markerEnd: { type: MarkerType.ArrowClosed, color: '#ffbd2e' } },
      { id: 'e-evolution', source: 'node-evolution', target: 'central-orb', animated: true, style: { stroke: '#00f3ff', strokeWidth: 1.5 }, markerEnd: { type: MarkerType.ArrowClosed, color: '#00f3ff' } },
      { id: 'e-api-gw', source: 'central-orb', target: 'node-api-gw', animated: true, style: { stroke: '#00f3ff', strokeWidth: 1.5 }, markerEnd: { type: MarkerType.ArrowClosed, color: '#00f3ff' } },
      { id: 'e-memory', source: 'central-orb', target: 'node-memory', animated: true, style: { stroke: '#ffbd2e', strokeWidth: 1.5 }, markerEnd: { type: MarkerType.ArrowClosed, color: '#ffbd2e' } },
      { id: 'e-cicd', source: 'central-orb', target: 'node-cicd', animated: true, style: { stroke: '#00ff66', strokeWidth: 1.5 }, markerEnd: { type: MarkerType.ArrowClosed, color: '#00ff66' } },
    ];

    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [activeModel, systemLoad, pingStatus]);

  return (
    <div className="flex-grow p-6 flex flex-col lg:flex-row gap-6 overflow-hidden bg-[#03060f] text-white scanline relative min-h-screen">
      <div className="flex-1 flex flex-col gap-6 relative z-10">
        
        {/* Aethel Core Network Nodes Area */}
        <div className="flex-1 bg-[#050917]/70 border border-[#00f3ff]/20 rounded-2xl p-4 min-h-[500px] relative shadow-[0_0_30px_rgba(0,243,255,0.05)] overflow-hidden">
          <div className="absolute top-4 left-4 z-10 font-mono">
            <h2 className="text-sm font-black tracking-widest text-[#00f3ff] uppercase flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#00f3ff] animate-ping" />
              AETHEL ORCHESTRATOR | ADM-01
            </h2>
            <span className="text-[10px] text-slate-500 font-bold">// REAL-TIME MULTI-CLOUD TELEMETRY</span>
          </div>

          <div className="absolute top-4 right-4 z-10 flex gap-2">
            <button 
              onClick={triggerConsentMatrix}
              className="text-[9px] font-mono font-bold bg-[#300c0c] hover:bg-[#4a1212] border border-red-500/50 hover:border-red-500/80 px-3 py-1 rounded text-red-400 transition-all shadow-[0_0_10px_rgba(239,68,68,0.2)] flex items-center gap-1"
            >
              <ShieldAlert size={10} /> TEST HITL
            </button>
            <button 
              onClick={() => setActiveModel(activeModel === "Gemini-2.5-Flash" ? "GPT-4o" : "Gemini-2.5-Flash")}
              className="text-[9px] font-mono font-bold bg-[#0c1830] hover:bg-[#12244a] border border-[#00f3ff]/30 hover:border-[#00f3ff]/80 px-3 py-1 rounded text-[#00f3ff] transition-all"
            >
              🔄 MODEL SELECTOR
            </button>
          </div>

          <div className="w-full h-full">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              onNodesChange={onNodesChange}
              fitView
              zoomOnScroll={false}
              zoomOnDoubleClick={false}
              preventScrolling={true}
              panOnDrag={false}
              nodesDraggable={true}
            >
              <Background color="#00f3ff" gap={20} style={{ opacity: 0.05 }} />
            </ReactFlow>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-center bg-[#070c22]/80 border border-[#00f3ff]/15 p-4 rounded-xl backdrop-blur-md">
          <button className="flex items-center justify-center gap-2 py-2 px-3 rounded bg-slate-900/60 border border-slate-800 hover:border-[#00f3ff]/50 text-slate-300 hover:text-white transition-all font-mono text-xs">
            <Layers size={14} className="text-[#00f3ff]" />
            <span>⚙️ SETTINGS</span>
          </button>
          <button className="flex items-center justify-center gap-2 py-2 px-3 rounded bg-slate-900/60 border border-slate-800 hover:border-[#00ff66]/50 text-slate-300 hover:text-white transition-all font-mono text-xs">
            <DollarSign size={14} className="text-[#00ff66]" />
            <span>📊 METRICS / COST</span>
          </button>
          <div className="md:col-span-2 flex items-center justify-between gap-3 px-4 py-1.5 rounded-lg bg-[#00f3ff]/5 border border-[#00f3ff]/30 shadow-[0_0_15px_rgba(0,243,255,0.05)]">
            <div className="flex items-center gap-2">
              <Volume2 size={16} className={`text-[#00f3ff] ${voiceOverrideActive ? 'animate-bounce' : ''}`} />
              <span className="text-[10px] font-mono font-bold text-slate-300">
                {voiceOverrideActive ? "SPEAK NOW (Listening...)" : "CMD VOICE OVERRIDE"}
              </span>
            </div>
            {voiceOverrideActive && (
              <div className="flex items-center gap-1">
                <span className="w-1 h-3 bg-[#00f3ff] animate-pulse"></span>
                <span className="w-1 h-5 bg-[#00f3ff] animate-pulse delay-75"></span>
                <span className="w-1 h-4 bg-[#00f3ff] animate-pulse delay-150"></span>
              </div>
            )}
            <button 
              onClick={handleVoiceOverride}
              className={`text-[9px] font-bold px-2 py-1 rounded transition-all ${
                voiceOverrideActive ? 'bg-[#ffbd2e] text-black font-black' : 'bg-[#00f3ff] text-black'
              }`}
            >
              {voiceOverrideActive ? "DEACTIVATE" : "ACTIVATE"}
            </button>
          </div>
        </div>
      </div>

      {/* Right Glassmorphic Panels */}
      <div className="w-full lg:w-[350px] flex flex-col gap-6 relative z-10">
        <GlassmorphicPanel 
          title="Live Orchestration Feed" 
          icon={<Activity size={14} className="animate-pulse" />}
          subtitle="Streamed router prompt actions"
          className="max-h-[400px]"
        >
          <div className="flex flex-col gap-3">
            {feed.map(item => (
              <div key={item.id} className="p-2.5 rounded bg-slate-950/70 border border-slate-900 hover:border-[#00f3ff]/30 transition-all font-mono text-[10px]">
                <div className="flex justify-between items-center text-[9px] text-[#00f3ff]">
                  <span>{item.user} ➔ {item.agent}</span>
                  <span className={item.status === 'RESOLVED' ? 'text-[#00ff66]' : 'text-[#ffbd2e] animate-pulse'}>
                    {item.status}
                  </span>
                </div>
                <div className="text-slate-300 mt-1 truncate">{item.request}</div>
                <div className="text-right text-[8px] text-slate-500 mt-1">{item.time}</div>
              </div>
            ))}
          </div>
        </GlassmorphicPanel>

        <GlassmorphicPanel 
          title="Live Logs console" 
          icon={<Terminal size={14} />}
          className="h-[280px]"
        >
          <div className="font-mono text-[9px] text-slate-400 space-y-1.5">
            {liveLogs.map((log, idx) => (
              <div key={idx} className="leading-normal">
                <span className="text-[#00ff66] mr-1">→</span>
                {log}
              </div>
            ))}
          </div>
        </GlassmorphicPanel>
      </div>

      <ConsentMatrixModal 
        isOpen={consentModalOpen}
        request={{
          id: 'REQ-901',
          taskPurpose: 'Deploy new self-learning skill agent to Cloud Mesh node.',
          riskLevel: 'High',
          diffPreview: '+\n+ agent = PlatformLearner()\n+ await agent.deploy_to_render()'
        }}
        onApproveOnce={() => setConsentModalOpen(false)}
        onApproveAlways={() => setConsentModalOpen(false)}
        onRejectWithFeedback={() => setConsentModalOpen(false)}
        onHardReject={() => setConsentModalOpen(false)}
        onClose={() => setConsentModalOpen(false)}
      />
    </div>
  );
}
