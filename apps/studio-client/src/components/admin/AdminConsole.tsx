import type { ChatMessage, Skill, Checkpoint, CloudStats, GcpHealth, AdminSubTab } from '../../types';
import { useHydrated } from '../../store/customerStore';
import { LoginView } from './AdminLogin';
import { AuthenticatedView } from './AdminAuthenticated';

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
  adminSubTab: AdminSubTab;
  setAdminSubTab: (tab: AdminSubTab) => void;
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

export function AdminConsole(props: AdminConsoleProps) {
  const hydrated = useHydrated();
  
  if (!hydrated) return null;
  
  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden bg-[#030407]">
      {!props.adminAuthenticated ? (
        <LoginView {...props} />
      ) : (
        <AuthenticatedView {...props} />
      )}
    </div>
  );
}