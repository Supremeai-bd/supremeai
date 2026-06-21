import type { AdminSubTab } from '../../types';

interface TabBarProps {
  adminSubTab: AdminSubTab;
  setAdminSubTab: (tab: AdminSubTab) => void;
}

export function TabBar({ adminSubTab, setAdminSubTab }: TabBarProps) {
  const tabs: { id: AdminSubTab; label: string }[] = [
    { id: 'command-center', label: 'Command Center' },
    { id: 'sandbox', label: 'Orchestrator Sandbox' },
    { id: 'logs', label: 'Real-time Logs' },
    { id: 'costs', label: 'Cost Auditor' },
    { id: 'health', label: 'Provider Map' },
    { id: 'users', label: 'User Manager' },
    { id: 'config', label: 'Config Editor' },
    { id: 'model-router', label: 'Model Router' },
    { id: 'skills', label: 'Skills' },
    { id: 'memory', label: 'Memory' },
    { id: 'cloud', label: 'Cloud' },
    { id: 'observability', label: 'Observability' },
    { id: 'threats', label: 'Threats' },
    { id: 'rules', label: 'Rules' },
    { id: 'cicd', label: 'CI/CD' },
    { id: 'github', label: 'GitHub' },
    { id: 'backups', label: 'Backups' },
  ];
  
  return (
    <div className="h-10 bg-[#090b11] border-b border-slate-800 flex items-center justify-between px-4">
      <div className="flex gap-2 overflow-x-auto">
        {tabs.map(tab => (
          <TabButton
            key={tab.id}
            active={adminSubTab === tab.id}
            onClick={() => setAdminSubTab(tab.id)}
          >
            {tab.label}
          </TabButton>
        ))}
      </div>
    </div>
  );
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1 text-xs font-semibold rounded font-mono transition-colors whitespace-nowrap ${
        active ? 'bg-[#00f3ff]/20 text-[#00f3ff]' : 'text-slate-400 hover:text-white'
      }`}
    >
      {children}
    </button>
  );
}