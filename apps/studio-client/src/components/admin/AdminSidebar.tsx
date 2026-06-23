// ============================================================================
// component >> AdminSidebar.tsx
// project >> SupremeAI 2.0
// purpose >> Admin panel and controls
// module >> src
// ============================================================================
import type { GcpHealth, CloudStats, Skill, Checkpoint } from '../../types';

interface SidebarNavProps {
  handleAdminLogout: () => void;
  actionStatus: string;
  gcpHealth: GcpHealth | null;
  cloudStats: CloudStats | null;
  theme: 'dark' | 'light';
  toggleTheme: () => void;
  skillQuery: string;
  setSkillQuery: (val: string) => void;
  skills: Skill[];
  checkpoints: Checkpoint[];
  handleDeleteCheckpoint: (taskId: string) => void;
}

export function SidebarNav({
  handleAdminLogout, actionStatus,
  gcpHealth, cloudStats, theme, toggleTheme, skillQuery, setSkillQuery, skills,
  checkpoints, handleDeleteCheckpoint,
}: SidebarNavProps) {
  return (
    <div className="lg:w-64 lg:flex-shrink-0 w-full bg-[var(--sidebar-bg)] border-b border-[var(--border-color)] flex flex-col p-4 overflow-hidden lg:overflow-y-auto lg:border-r lg:border-b-0 text-[var(--foreground)]">
      <SidebarHeader handleAdminLogout={handleAdminLogout} />
      
      {actionStatus && (
        <div className="mb-4 p-2.5 bg-cyan-950/30 border border-cyan-800/40 rounded text-[11px] font-mono text-[#00f3ff]">
          {actionStatus}
        </div>
      )}
      
      <ThemeToggle theme={theme} toggleTheme={toggleTheme} />
      <GcpHealthMatrix gcpHealth={gcpHealth} />
      <CloudStatsPanel cloudStats={cloudStats} />
      <SkillMarketplace skillQuery={skillQuery} setSkillQuery={setSkillQuery} skills={skills} />
      <MemoryCheckpoints checkpoints={checkpoints} handleDeleteCheckpoint={handleDeleteCheckpoint} />
    </div>
  );
}

function SidebarHeader({ handleAdminLogout }: { handleAdminLogout: () => void }) {
  return (
    <div className="flex justify-between items-center mb-6">
      <span className="text-[11px] uppercase tracking-[2px] text-[#00f3ff] font-semibold">
        God Configuration
      </span>
      <button
        onClick={handleAdminLogout}
        className="text-xs font-bold text-red-400 hover:text-red-300 tracking-wider transition-colors"
      >
        LOGOUT
      </button>
    </div>
  );
}

function ThemeToggle({ theme, toggleTheme }: { theme: 'dark' | 'light'; toggleTheme: () => void }) {
  return (
    <div className="flex items-center gap-2 mb-6">
      <button
        onClick={toggleTheme}
        className="text-xs font-bold text-[#00f3ff] hover:text-cyan-400 tracking-wider transition-colors"
      >
        {theme === 'dark' ? '🌙 Light Mode' : '☀️ Dark Mode'}
      </button>
    </div>
  );
}

function GcpHealthMatrix({ gcpHealth }: { gcpHealth: GcpHealth | null }) {
  return (
    <div className="mb-6">
      <div className="text-[10px] text-slate-500 uppercase tracking-widest mb-2 font-semibold font-mono flex items-center gap-1">
        <span>GCP Health Matrix</span>
        <BanglaHint text="জিসিপি ক্লাউড সার্ভিসসমূহের বর্তমান অ্যাক্টিভ স্টেট ও কানেকশন স্ট্যাটাস।" />
      </div>
      <div className="bg-[var(--alert-bg)] border border-[var(--border-color)] rounded-lg p-3 flex flex-col gap-2 text-xs font-mono">
        <div className="flex justify-between">
          <span className="text-slate-400">Cloud Run Mode:</span>
          <span className={gcpHealth?.status === 'ok' ? 'text-emerald-400' : 'text-yellow-400'}>
            {gcpHealth?.cloud_run?.status || 'Active'}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">Firestore Mode:</span>
          <span className="text-indigo-400">{gcpHealth?.firestore_mode || 'Local'}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">PubSub Queue:</span>
          <span className="text-purple-400">{gcpHealth?.pubsub_mode || 'Local'}</span>
        </div>
      </div>
    </div>
  );
}

function CloudStatsPanel({ cloudStats }: { cloudStats: CloudStats | null }) {
  if (!cloudStats) return null;
  
  return (
    <div className="mb-6">
      <div className="text-[10px] text-slate-500 uppercase tracking-widest mb-2 font-semibold font-mono flex items-center gap-1">
        <span>Cloud Distribution Stats</span>
        <BanglaHint text="ক্লাউড প্রোভাইডার ডিস্ট্রিবিউশন এবং রিকোয়েস্টের রিয়েল-টাইম পরিসংখ্যান।" />
      </div>
      <div className="bg-[var(--alert-bg)] border border-[var(--border-color)] rounded-lg p-3 flex flex-col gap-2.5 text-xs font-mono">
        <div className="flex justify-between">
          <span className="text-slate-400">Total Requests:</span>
          <span className="text-[var(--foreground)]">{cloudStats.total_requests}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">Active Providers:</span>
          <span className="text-emerald-400">{cloudStats.active_providers}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">Strategy:</span>
          <span className="text-indigo-400">{cloudStats.strategy}</span>
        </div>
      </div>
    </div>
  );
}

function SkillMarketplace({ skillQuery, setSkillQuery, skills }: { skillQuery: string; setSkillQuery: (val: string) => void; skills: Skill[] }) {
  return (
    <div className="mb-6">
      <div className="text-[10px] text-slate-500 uppercase tracking-widest mb-2 font-semibold flex items-center gap-1">
        <span>Skill Marketplace</span>
        <BanglaHint text="এখানে নতুন স্কিল বা প্লাগইন সার্চ করে ইনস্টল করতে পারবেন।" />
      </div>
      <div className="flex gap-1 mb-2">
        <input
          type="text"
          placeholder="Search marketplace..."
          value={skillQuery}
          onChange={e => { setSkillQuery(e.target.value); }}
          className="bg-[var(--input-bg)] border border-[var(--input-border)] rounded px-2 py-1 text-[11px] text-[var(--foreground)] focus:outline-none focus:border-[#00f3ff] w-full font-mono"
        />
      </div>
      <div className="flex flex-col gap-2 max-h-48 overflow-y-auto">
        {skills.length === 0 ? (
          <div className="text-[10px] text-slate-500 font-mono">No skills found.</div>
        ) : (
          skills.map(skill => (
            <div key={skill.id} className="bg-[var(--cyber-gray)] border border-[var(--border-color)] rounded p-2.5 text-xs">
              <div className="font-semibold text-slate-200 flex justify-between font-mono">
                <span>{skill.name}</span>
                <span className="text-[#00f3ff] text-[10px]">v{skill.version}</span>
              </div>
              <div className="text-slate-400 text-[10px] mt-1 font-sans">{skill.description}</div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function MemoryCheckpoints({ checkpoints, handleDeleteCheckpoint }: { checkpoints: Checkpoint[]; handleDeleteCheckpoint: (taskId: string) => void }) {
  return (
    <div className="mb-6">
      <div className="text-[10px] text-slate-500 uppercase tracking-widest mb-2 font-semibold font-mono flex items-center gap-1">
        <span>Memory Checkpoints</span>
        <BanglaHint text="পূর্বে সংরক্ষিত এজেন্ট মেমরি রিস্টোর পয়েন্ট বা চেকপয়েন্টসমূহ।" />
      </div>
      <div className="flex flex-col gap-2 max-h-40 overflow-y-auto font-mono">
        {checkpoints.length === 0 ? (
          <div className="text-[10px] text-slate-500 font-mono">No checkpoints stored.</div>
        ) : (
          checkpoints.map(cp => (
            <div key={cp.task_id} className="bg-[var(--cyber-gray)] border border-[var(--border-color)] rounded p-2 flex justify-between items-center text-[11px]">
              <div className="min-w-0">
                <div className="text-slate-200 truncate" title={cp.task_id}>{cp.task_id}</div>
                <div className="text-slate-500 text-[10px]">Step: {cp.step_index}</div>
              </div>
              <button
                onClick={() => handleDeleteCheckpoint(cp.task_id)}
                className="text-red-400 hover:text-red-300 font-bold px-2 py-1 text-[10px] rounded transition-all"
                title="Delete checkpoint"
              >
                🗑️
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}