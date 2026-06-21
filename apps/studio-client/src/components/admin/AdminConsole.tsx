import type { ChatMessage, Skill, Checkpoint, CloudStats, GcpHealth } from '../types';
import { useHydrated } from '../store/customerStore';

interface AdminConsoleProps {
  adminAuthenticated: boolean;
  adminPassword: string;
  setAdminPassword: (val: string) => void;
  adminEmail: string;
  setAdminEmail: (val: string) => void;
  totpSetupRequired: boolean;
  totpSecret: string;
  provisioningUri: string;
  adminError: string;
  handleAdminLogin: () => void;
  handleAdminOtpVerify: () => void;
  handleAdminLogout: () => void;
  actionStatus: string;
  gcpHealth: GcpHealth | null;
  cloudStats: CloudStats | null;
  skillQuery: string;
  setSkillQuery: (val: string) => void;
  skills: Skill[];
  handleInstallSkill: (name: string) => void;
  checkpoints: Checkpoint[];
  handleDeleteCheckpoint: (taskId: string) => void;
  adminSubTab: 'sandbox' | 'logs' | 'costs' | 'health' | 'users' | 'config' | 'command-center' | 'model-router' | 'skills' | 'memory' | 'cloud' | 'observability' | 'threats' | 'rules' | 'cicd' | 'github' | 'backups';
  setAdminSubTab: (tab: 'sandbox' | 'logs' | 'costs' | 'health' | 'users' | 'config' | 'command-center' | 'model-router' | 'skills' | 'memory' | 'cloud' | 'observability' | 'threats' | 'rules' | 'cicd' | 'github' | 'backups') => void;
  handleTriggerDeploy: () => void;
  adminMessages: ChatMessage[];
  loading: boolean;
  adminInput: string;
  setAdminInput: (val: string) => void;
  handleSendAdmin: () => void;
  rulesJson: string;
  setRulesJson: (val: string) => void;
  saveStatus: string;
  handleSaveRules: () => void;
  liveLogs: string[];
  setLiveLogs: (logs: string[]) => void;
  costReport: string;
  healthMap: any;
  newUsername: string;
  setNewUsername: (val: string) => void;
  newUserRole: string;
  setNewUserRole: (val: string) => void;
  newUserPerms: string;
  setNewUserPerms: (val: string) => void;
  handleSaveUser: () => void;
  adminUsers: any[];
  handleDeleteUser: (username: string) => void;
  envConfig: Record<string, string>;
  setEnvConfig: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  handleSaveConfig: () => void;
  otpRequired: boolean;
  adminOtp: string;
  setAdminOtp: (val: string) => void;
  theme: 'dark' | 'light';
  toggleTheme: () => void;
}

const TabButton = ({ 
  active, 
  onClick, 
  children 
}: { 
  active: boolean; 
  onClick: () => void; 
  children: React.ReactNode;
}) => (
  <button
    onClick={onClick}
    className={`px-3 py-1 text-xs font-semibold rounded font-mono transition-colors ${
      active ? 'bg-[#00f3ff]/20 text-[#00f3ff]' : 'text-slate-400 hover:text-white'
    }`}
  >
    {children}
  </button>
);

export function AdminConsole(props: AdminConsoleProps) {
  const hydrated = useHydrated();
  const { adminAuthenticated, adminSubTab, setAdminSubTab, handleAdminLogout, toggleTheme, theme, handleTriggerDeploy, adminError, actionStatus } = props;
  
  if (!hydrated) return null;
  
  return (
    <div className="flex-grow flex flex-col overflow-hidden bg-[#030407]">
      {!adminAuthenticated ? (
        <LoginView {...props} />
      ) : (
        <AuthenticatedView {...props} />
      )}
    </div>
  );
}