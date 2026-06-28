import { useEffect, useState, useMemo } from 'react';
import ReactFlow, {
  Background,
  useNodesState,
  useEdgesState,
} from 'reactflow';
import 'reactflow/dist/style.css';
import './AethelCoreStyles.css';
import { 
  Cpu, 
  Send,
  Mic,
  Maximize2,
  Settings,
  Activity,
  Shield,
  LifeBuoy,
  FileText
} from 'lucide-react';
import AethelNode from './AethelNode';

// বাংলা মন্তব্য: চ্যাট এবং ভয়েস ওভাররাইডের জন্য ডামি কথোপকথন ডাটা ডিক্লেয়ার করা হচ্ছে
const initialChat = [
  { id: 1, sender: 'Admin', text: 'Execute deployment check on Node 47.' },
  { id: 2, sender: 'Aethel', text: 'Analyzing Node 47 (Analytics). Status: Nominal. Load: 38%. Connected.' },
  { id: 3, sender: 'System', text: 'Optimizing cluster nodes...' },
];

export function CommandCenter() {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges] = useEdgesState([]);
  const [chatMessages, setChatMessages] = useState(initialChat);
  const [chatInput, setChatInput] = useState('');
  const [voiceActive] = useState(true);

  // Custom node types for ReactFlow
  const nodeTypes = useMemo(() => ({ aethel: AethelNode }), []);

  const handleSendChat = () => {
    if (!chatInput.trim()) return;
    setChatMessages(prev => [
      ...prev,
      { id: Date.now(), sender: 'Admin', text: chatInput },
      { id: Date.now() + 1, sender: 'Aethel', text: `Processing command "${chatInput}"... Authorization confirmed.` }
    ]);
    setChatInput('');
  };

  useEffect(() => {
    const initialNodes = [
      {
        id: 'central-orb',
        type: 'default',
        data: {
          label: (
            <div className="flex flex-col items-center justify-center p-2 text-center h-full w-full">
              <span className="font-bold text-[9px] tracking-widest text-[#00f3ff] uppercase mb-3">AETHEL CENTRAL ORC</span>
              <div className="central-orb-outer">
                <div className="central-orb-inner">
                  <div className="central-orb-core flex items-center justify-center bg-[#00f3ff] w-[45px] h-[45px] rounded-full shadow-[0_0_25px_#00f3ff]">
                    <Cpu size={22} className="text-slate-950" />
                  </div>
                </div>
              </div>
              <div className="mt-3 flex flex-col gap-0.5">
                <span className="text-[9px] text-[#00ff66] font-mono">v.9.2</span>
                <span className="text-[8px] text-slate-500 font-mono">ACTIVE TELEMETRY</span>
              </div>
            </div>
          )
        },
        position: { x: 320, y: 90 },
        className: 'border-none flex items-center justify-center bg-transparent',
        style: { width: 220, height: 280 }
      },
      // Left Nodes
      {
        id: 'node-deploy',
        type: 'aethel',
        data: { type: 'deploy', status: 'Nominal', label: 'DEPLOY' },
        position: { x: 20, y: 30 }
      },
      {
        id: 'node-analytics',
        type: 'aethel',
        data: { type: 'analytics', status: 'Nominal', label: 'ANALYTICS' },
        position: { x: 180, y: 70 }
      },
      {
        id: 'node-mesh',
        type: 'aethel',
        data: { type: 'mesh', status: 'Nominal', label: 'MESH_A1' },
        position: { x: 180, y: 170 }
      },
      {
        id: 'node-network',
        type: 'aethel',
        data: { type: 'network', status: 'Nominal', label: 'NETWORK' },
        position: { x: 20, y: 220 }
      },
      {
        id: 'node-kubernetes',
        type: 'aethel',
        data: { type: 'kubernetes', status: 'Nominal', label: 'KUBERNETES' },
        position: { x: 20, y: 320 }
      },
      {
        id: 'node-security',
        type: 'aethel',
        data: { type: 'security', status: 'Nominal', label: 'SECURITY' },
        position: { x: 180, y: 270 }
      },
      // Right Nodes
      {
        id: 'node-api-gw',
        type: 'aethel',
        data: { type: 'aplgw', status: 'Nominal', label: 'API_GW' },
        position: { x: 740, y: 30 }
      },
      {
        id: 'node-rubernetes',
        type: 'aethel',
        data: { type: 'kubernetes', status: 'Nominal', label: 'RUBERNETES' },
        position: { x: 570, y: 70 }
      },
      {
        id: 'node-instances',
        type: 'aethel',
        data: { type: 'instances', status: 'Nominal', label: 'INSTANCES' },
        position: { x: 570, y: 170 }
      },
      {
        id: 'node-storage',
        type: 'aethel',
        data: { type: 'storage', status: 'Nominal', label: 'STORAGE' },
        position: { x: 740, y: 270 }
      },
      {
        id: 'node-aplsw',
        type: 'aethel',
        data: { type: 'aplsw', status: 'Nominal', label: 'APLSW' },
        position: { x: 570, y: 270 }
      }
    ];

    const initialEdges = [
      // Left side connections
      { id: 'e-deploy-analytics', source: 'node-deploy', target: 'node-analytics', animated: true, style: { stroke: '#00f3ff', strokeWidth: 1.5 } },
      { id: 'e-analytics-mesh', source: 'node-analytics', target: 'node-mesh', animated: true, style: { stroke: '#00f3ff', strokeWidth: 1.5 } },
      { id: 'e-network-mesh', source: 'node-network', target: 'node-mesh', animated: true, style: { stroke: '#00ff66', strokeWidth: 1.5 } },
      { id: 'e-kubernetes-security', source: 'node-kubernetes', target: 'node-security', animated: true, style: { stroke: '#ffbd2e', strokeWidth: 1.5 } },
      { id: 'e-mesh-security', source: 'node-mesh', target: 'node-security', animated: true, style: { stroke: '#00ff66', strokeWidth: 1.5 } },
      { id: 'e-security-central', source: 'node-security', target: 'central-orb', animated: true, style: { stroke: '#ffbd2e', strokeWidth: 2 } },
      { id: 'e-analytics-central', source: 'node-analytics', target: 'central-orb', animated: true, style: { stroke: '#00f3ff', strokeWidth: 2 } },

      // Right side connections
      { id: 'e-apigw-rubernetes', source: 'node-api-gw', target: 'node-rubernetes', animated: true, style: { stroke: '#00f3ff', strokeWidth: 1.5 } },
      { id: 'e-rubernetes-central', source: 'node-rubernetes', target: 'central-orb', animated: true, style: { stroke: '#00ff66', strokeWidth: 2 } },
      { id: 'e-instances-central', source: 'node-instances', target: 'central-orb', animated: true, style: { stroke: '#00ff66', strokeWidth: 2 } },
      { id: 'e-storage-aplsw', source: 'node-storage', target: 'node-aplsw', animated: true, style: { stroke: '#ffbd2e', strokeWidth: 1.5 } },
      { id: 'e-aplsw-central', source: 'node-aplsw', target: 'central-orb', animated: true, style: { stroke: '#ffbd2e', strokeWidth: 2 } }
    ];

    setNodes(initialNodes);
    setEdges(initialEdges);
  }, []);

  return (
    <div className="flex-grow flex flex-col overflow-hidden bg-[#030611] text-white scanline relative h-screen font-mono p-4">
      {/* ── TOP HUD HEADER BAR ────────────────────────────────────── */}
      <header className="flex justify-between items-center border-b border-[#00f3ff]/15 pb-2 mb-4">
        <div className="flex items-center gap-2">
          <span className="text-[#00f3ff] animate-pulse">▲</span>
          <span className="text-xs font-bold tracking-widest text-[#00f3ff] uppercase">AETHEL ORCHESTRATOR | ADM-01</span>
        </div>
        <div className="text-sm font-bold tracking-widest text-[#00f3ff] uppercase">
          AETHEL CORE
        </div>
        <div className="flex items-center gap-4 text-[10px] text-[#00f3ff] font-bold">
          <span>14:32 | OCT 26</span>
          <span className="text-[#00ff66]">📶 SYSTEM ONLINE</span>
        </div>
      </header>

      {/* ── MAIN WORKSPACE CONTENT ────────────────────────────────── */}
      <div className="flex-1 flex flex-row gap-4 overflow-hidden mb-4">
        
        {/* Core React Flow Telemetry Canvas */}
        <div className="flex-1 bg-[#050917]/50 border border-[#00f3ff]/15 rounded-xl relative overflow-hidden flex flex-col">
          <div className="flex-1 w-full h-full relative">
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
              <Background color="#00f3ff" gap={24} style={{ opacity: 0.03 }} />
            </ReactFlow>
          </div>

          {/* Floating Telemetry Waveform Panel at Bottom of Canvas */}
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 w-[380px] bg-[#060b1b]/90 border border-[#00f3ff]/25 rounded-lg p-3 shadow-[0_0_20px_rgba(0,243,255,0.15)] backdrop-blur-md z-20 flex flex-col items-center">
            <div className="flex justify-between w-full text-[9px] text-slate-400 font-bold mb-1">
              <span>CMD | v3.0</span>
              <div className="flex items-center gap-1.5">
                <Mic size={10} className={voiceActive ? 'text-[#00f3ff] animate-pulse' : 'text-slate-500'} />
                <span>VOICE CONTROLS</span>
              </div>
            </div>

            {/* Glowing Waveform representation */}
            <div className="flex items-center justify-center h-8 my-1 w-full">
              <span className="waveform-bar" style={{ height: '8px' }} />
              <span className="waveform-bar pulse-delay-1" style={{ height: '14px' }} />
              <span className="waveform-bar pulse-delay-2" style={{ height: '22px' }} />
              <span className="waveform-bar pulse-delay-3" style={{ height: '12px' }} />
              <span className="waveform-bar pulse-delay-4" style={{ height: '26px' }} />
              <span className="waveform-bar pulse-delay-5" style={{ height: '10px' }} />
              <span className="waveform-bar pulse-delay-1" style={{ height: '18px' }} />
              <span className="waveform-bar pulse-delay-2" style={{ height: '6px' }} />
            </div>

            <div className="flex justify-between w-full text-[8px] text-slate-500 font-bold mt-1">
              <span className="text-[#00ff66]">Voice Recognition: Listening...</span>
              <span>CPU: 74% MEM: 68%</span>
            </div>
          </div>
        </div>

        {/* Right Sidebar: AI Assistant Glassmorphic Chat Panel */}
        <div className="w-[300px] flex flex-col bg-[#050917]/60 border border-[#00f3ff]/15 rounded-xl backdrop-blur-md overflow-hidden">
          <div className="border-b border-[#00f3ff]/15 p-3 flex justify-between items-center bg-[#070d22]">
            <span className="text-xs font-black tracking-widest text-[#00f3ff] uppercase">AETHEL | AI ASSISTANT</span>
            <Maximize2 size={12} className="text-[#00f3ff] cursor-pointer" />
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-3">
            {chatMessages.map(msg => (
              <div key={msg.id} className="text-[10px] leading-relaxed border-b border-cyan-900/10 pb-2">
                <span className={`font-bold tracking-wider mr-1 ${
                  msg.sender === 'Admin' ? 'text-slate-300' : msg.sender === 'Aethel' ? 'text-[#00f3ff]' : 'text-emerald-500'
                }`}>
                  {msg.sender}:
                </span>
                <span className="text-slate-300">{msg.text}</span>
              </div>
            ))}
          </div>

          <div className="p-3 border-t border-[#00f3ff]/15 bg-[#060b1c]/80 flex gap-2">
            <input
              type="text"
              value={chatInput}
              onChange={e => setChatInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSendChat()}
              placeholder="[Type command...]"
              className="flex-grow bg-[#030611] border border-cyan-500/20 focus:border-[#00f3ff]/60 rounded px-2.5 py-1.5 text-[10px] text-slate-100 outline-none placeholder:text-slate-600"
            />
            <button onClick={handleSendChat} className="bg-[#00f3ff]/20 hover:bg-[#00f3ff]/40 text-[#00f3ff] p-1.5 rounded transition-all">
              <Send size={12} />
            </button>
          </div>
        </div>

      </div>

      {/* ── BOTTOM DECK CONTROLLER / ICON PANELS ──────────────────── */}
      <footer className="flex justify-between items-center border-t border-[#00f3ff]/15 pt-2 text-[10px] text-slate-400 font-bold">
        {/* Left Deck Actions */}
        <div className="flex gap-4">
          <button className="flex items-center gap-1.5 hover:text-white transition-colors">
            <Settings size={12} className="text-[#00f3ff]" />
            <span>Settings</span>
          </button>
          <button className="flex items-center gap-1.5 hover:text-white transition-colors">
            <Activity size={12} className="text-[#00ff66]" />
            <span>Metrics</span>
          </button>
          <button className="flex items-center gap-1.5 hover:text-white transition-colors">
            <FileText size={12} className="text-yellow-500" />
            <span>Logs</span>
          </button>
        </div>

        {/* Right Deck Status Indicator */}
        <div className="flex gap-4">
          <button className="flex items-center gap-1.5 hover:text-white transition-colors">
            <FileText size={12} className="text-[#00f3ff]" />
            <span>Logs</span>
          </button>
          <button className="flex items-center gap-1.5 hover:text-white transition-colors">
            <Shield size={12} className="text-[#00ff66]" />
            <span>Security</span>
          </button>
          <button className="flex items-center gap-1.5 hover:text-white transition-colors">
            <LifeBuoy size={12} className="text-yellow-500" />
            <span>Health</span>
          </button>
        </div>
      </footer>
    </div>
  );
}
