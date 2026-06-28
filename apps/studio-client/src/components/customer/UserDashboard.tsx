import { useState } from 'react';
import {
  MessageSquare,
  FolderOpen,
  Zap,
  TrendingUp,
  Settings2,
  Play,
  ChevronRight,
  Activity,
  Clock,
  Sparkles
} from 'lucide-react';
import { HomeFeed } from './HomeFeed';
import { QuickPresets } from './QuickPresets';
import { CodeEditor } from './CodeEditor';
import { ChatPanel } from './ChatPanel';
import './UserDashboard.css';

export interface UserProfile {
  id: string;
  username: string;
  email: string;
  role: 'viewer' | 'operator' | 'developer' | 'admin' | 'god';
  avatar_url?: string;
  preferences: {
    theme: 'dark' | 'light';
    sidebar_collapsed: boolean;
    default_project_id?: string;
    notification_enabled: boolean;
    sound_enabled: boolean;
    compact_mode: boolean;
    font_size: 'small' | 'medium' | 'large';
  };
  created_at: string;
  last_login: string;
}

export interface Project {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  owner_id: string;
  settings: {
    default_model: string;
    system_prompt: string;
    temperature: number;
    max_tokens: number;
    rag_enabled: boolean;
  };
}

export interface ChatMessage {
  id: number;
  sender: 'User' | 'Aethel';
  text: string;
  timestamp?: string;
}

export interface Widget {
  id: string;
  type: 'chat' | 'metrics' | 'history' | 'skills' | 'files' | 'preview';
  title: string;
  position: { x: number; y: number; w: number; h: number };
  settings: Record<string, unknown>;
}

interface UserDashboardProps {
  customerMessages: ChatMessage[];
  customerInput: string;
  setCustomerInput: (val: string) => void;
  loading: boolean;
  handleSendCustomer: () => void;
  theme: 'dark' | 'light';
  toggleTheme: () => void;
  code: string;
  setCode: (code: string) => void;
  isServerOnline?: boolean;
  deployGate?: { status?: string };
  user?: UserProfile | null;
  projects?: Project[];
  chatHistory?: ChatMessage[];
  widgets?: Widget[];
}

export function UserDashboard({
  customerMessages,
  customerInput,
  setCustomerInput,
  loading,
  handleSendCustomer,
  theme,
  toggleTheme,
  code,
  setCode,
  isServerOnline = false,
  deployGate = {},
  user = null,
  projects = [],
  chatHistory = [],
  widgets = []
}: UserDashboardProps) {
  const [activeTab, setActiveTab] = useState<'overview' | 'feed' | 'presets' | 'chat'>('overview');

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const recentChats = chatHistory.length > 0
    ? chatHistory.slice(-4)
    : customerMessages.slice(-4);

  return (
    <div className="min-h-screen bg-[#030611] text-white font-mono relative">
      <div className="scanline pointer-events-none fixed inset-0 z-50" />

      <header className="flex justify-between items-center border-b border-[#00f3ff]/15 pb-3 px-6 pt-3 mb-4">
        <div className="flex items-center gap-3">
          <span className="text-[#00f3ff] animate-pulse text-lg">▲</span>
          <div>
            {/* বাংলা মন্তব্য: টেস্টে সহজে ও নির্ভরযোগ্যভাবে সনাক্ত করার জন্য header-title data-testid যোগ করা হলো */}
            <h1 data-testid="header-title" className="text-sm font-bold tracking-widest text-[#00f3ff] uppercase">
              Welcome back, {user?.username || 'User'}
            </h1>
            <p className="text-[10px] text-slate-500 font-mono">
              Last login: {user?.last_login ? formatDate(user.last_login) : 'Today'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* বাংলা মন্তব্য: সার্ভার স্ট্যাটাস টেস্ট করার জন্য core-status data-testid ব্যবহার করা হলো */}
          <span data-testid="core-status" className={`text-xs font-bold ${isServerOnline ? 'text-[#00f3ff]' : 'text-rose-500'}`}>
            CORE: {isServerOnline ? 'ONLINE' : 'OFFLINE'}
          </span>
          <span className="text-[10px] text-slate-400 font-mono">
            GATE: {deployGate?.status || 'SYNCING...'}
          </span>
          <button
            onClick={toggleTheme}
            className="text-xs font-bold text-[#00f3ff] hover:text-cyan-400 tracking-wider transition-colors px-3 py-1.5 rounded border border-[#00f3ff]/20"
          >
            {theme === 'dark' ? '☀️ Light' : '🌙 Dark'}
          </button>
        </div>
      </header>

      <div className="flex gap-2 px-6 mb-4">
        {/* বাংলা মন্তব্য: টেস্টে নির্দিষ্ট ট্যাবে ক্লিক করার জন্য tab-* ডায়নামিক data-testid দেওয়া হলো */}
        {(['overview', 'feed', 'presets', 'chat'] as const).map((tab) => (
          <button
            key={tab}
            data-testid={`tab-${tab}`}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-xs font-bold tracking-wider rounded-lg transition-all ${
              activeTab === tab
                ? 'bg-[#00f3ff]/20 text-[#00f3ff] border border-[#00f3ff]/30'
                : 'text-slate-400 hover:text-white border border-transparent hover:border-slate-700'
            }`}
          >
            {tab === 'overview' && <><Activity size={10} className="inline mr-1" /> Overview</>}
            {tab === 'feed' && <><Sparkles size={10} className="inline mr-1" /> Home Feed</>}
            {tab === 'presets' && <><Play size={10} className="inline mr-1" /> Quick Presets</>}
            {tab === 'chat' && <><MessageSquare size={10} className="inline mr-1" /> Chat</>}
          </button>
        ))}
      </div>

      {activeTab === 'overview' && (
        <div className="px-6">
          <div className="dashboard-grid mb-6">
            <div className="stat-card">
              <div className="flex items-center justify-between mb-3">
                <FolderOpen size={16} className="text-[#00f3ff]" />
                <span className="badge badge-cyan">Active</span>
              </div>
              <p className="text-2xl font-bold text-white font-['Space_Grotesk']">{projects.length}</p>
              <p className="text-[10px] text-slate-400 font-mono uppercase tracking-widest">Projects</p>
            </div>

            <div className="stat-card">
              <div className="flex items-center justify-between mb-3">
                <MessageSquare size={16} className="text-[#bc13fe]" />
                <span className="badge badge-purple">Live</span>
              </div>
              <p className="text-2xl font-bold text-white font-['Space_Grotesk']">{chatHistory.length + customerMessages.length}</p>
              <p className="text-[10px] text-slate-400 font-mono uppercase tracking-widest">Messages</p>
            </div>

            <div className="stat-card">
              <div className="flex items-center justify-between mb-3">
                <Zap size={16} className="text-yellow-400" />
                <span className="badge badge-green">Ready</span>
              </div>
              <p className="text-2xl font-bold text-white font-['Space_Grotesk']">{widgets.length}</p>
              <p className="text-[10px] text-slate-400 font-mono uppercase tracking-widest">Widgets</p>
            </div>

            <div className="stat-card">
              <div className="flex items-center justify-between mb-3">
                <TrendingUp size={16} className="text-emerald-400" />
                <span className="badge badge-green">Optimal</span>
              </div>
              <p className="text-2xl font-bold text-white font-['Space_Grotesk']">98%</p>
              <p className="text-[10px] text-slate-400 font-mono uppercase tracking-widest">Performance</p>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 dashboard-section">
              <div className="section-header">
                <h2 className="text-xs font-bold tracking-widest text-[#00f3ff] uppercase">Your Projects</h2>
                <button className="text-[10px] text-slate-400 hover:text-[#00f3ff] font-mono transition-colors">
                  View All <ChevronRight size={10} />
                </button>
              </div>

              {projects.length > 0 ? (
                projects.map((project) => (
                  <div key={project.id} className="project-item">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-[#00f3ff]/10 flex items-center justify-center text-[#00f3ff]">
                        <FolderOpen size={14} />
                      </div>
                      <div>
                        <p className="text-xs font-bold text-white">{project.name}</p>
                        <p className="text-[10px] text-slate-500 font-mono">{formatDate(project.updated_at)}</p>
                      </div>
                    </div>
                    <span className="badge badge-cyan">{project.settings.default_model}</span>
                  </div>
                ))
              ) : (
                <div className="text-center py-8 text-slate-500 text-xs font-mono">
                  No projects yet. Create your first project to get started.
                </div>
              )}
            </div>

            <div className="dashboard-section flex flex-col">
              <div className="section-header">
                <h2 className="text-xs font-bold tracking-widest text-[#00f3ff] uppercase">Quick Actions</h2>
              </div>
              <div className="flex flex-col gap-2">
                <button className="quick-action-btn" onClick={() => setActiveTab('chat')}>
                  <MessageSquare size={14} className="text-[#00f3ff]" />
                  <span>New Chat Session</span>
                </button>
                <button className="quick-action-btn" onClick={() => setActiveTab('presets')}>
                  <Play size={14} className="text-[#bc13fe]" />
                  <span>Launch Preset</span>
                </button>
                <button className="quick-action-btn" onClick={() => setActiveTab('feed')}>
                  <Sparkles size={14} className="text-yellow-400" />
                  <span>Home Feed</span>
                </button>
                <button className="quick-action-btn">
                  <Settings2 size={14} className="text-slate-400" />
                  <span>Project Settings</span>
                </button>
              </div>
            </div>
          </div>

          <div className="mt-6 dashboard-section">
            <div className="section-header">
              <h2 className="text-xs font-bold tracking-widest text-[#00f3ff] uppercase">
                <Activity size={12} className="inline mr-2" />
                Recent Activity
              </h2>
              <span className="text-[10px] text-slate-500 font-mono">Last 24 hours</span>
            </div>
            <div className="flex flex-col gap-1">
              {recentChats.length > 0 ? (
                recentChats.map((msg: ChatMessage, idx: number) => (
                  <div key={idx} className="flex items-center gap-3 p-2.5 rounded-lg bg-black/20 border border-white/[0.03] text-[10px] font-mono">
                    <Clock size={10} className="text-slate-500" />
                    <span className="text-slate-400">{msg.sender === 'User' ? 'You' : 'AI'}:</span>
                    <span className="text-slate-300 flex-1 truncate">{msg.text}</span>
                  </div>
                ))
              ) : (
                <p className="text-xs text-slate-500 font-mono text-center py-4">No recent activity</p>
              )}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'feed' && (
        <div className="px-6">
          <HomeFeed />
        </div>
      )}

      {activeTab === 'presets' && (
        <div className="px-6 grid grid-cols-1 lg:grid-cols-2 gap-4">
          <QuickPresets onSelectPreset={setCustomerInput} />
          <CodeEditor code={code} onChange={setCode} />
        </div>
      )}

      {activeTab === 'chat' && (
        <div className="px-6 max-w-3xl mx-auto">
          <div className="dashboard-section" style={{ minHeight: '500px' }}>
            <ChatPanel
              messages={customerMessages}
              input={customerInput}
              onInputChange={setCustomerInput}
              onSend={handleSendCustomer}
              loading={loading}
              onSaveToProject={setCode}
            />
          </div>
        </div>
      )}
    </div>
  );
}
