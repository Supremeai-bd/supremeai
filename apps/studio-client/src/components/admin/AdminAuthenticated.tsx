import type { GcpHealth, CloudStats } from '../../types';
import { SidebarNav } from './AdminSidebar';
import { TabBar } from './AdminTabBar';
import { SubTabContent } from './AdminSubTabContent';

interface AuthenticatedViewProps {
  gcpHealth: GcpHealth | null;
  cloudStats: CloudStats | null;
  skillQuery: string;
  setSkillQuery: (val: string) => void;
  skills: any[];
  handleInstallSkill: (name: string) => void;
  checkpoints: any[];
  handleDeleteCheckpoint: (taskId: string) => void;
  adminSubTab: 'sandbox' | 'logs' | 'costs' | 'health' | 'users' | 'config' | 'command-center' | 'model-router' | 'skills' | 'memory' | 'cloud' | 'observability' | 'threats' | 'rules' | 'cicd' | 'github' | 'backups';
  setAdminSubTab: (tab: 'sandbox' | 'logs' | 'costs' | 'health' | 'users' | 'config' | 'command-center' | 'model-router' | 'skills' | 'memory' | 'cloud' | 'observability' | 'threats' | 'rules' | 'cicd' | 'github' | 'backups') => void;
  handleTriggerDeploy: () => void;
  adminMessages: any[];
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
  actionStatus: string;
  handleAdminLogout: () => void;
  theme: 'dark' | 'light';
  toggleTheme: () => void;
}

export function AuthenticatedView(props: AuthenticatedViewProps) {
  const { 
    adminSubTab, setAdminSubTab, handleAdminLogout, 
    actionStatus, gcpHealth, cloudStats, theme, toggleTheme,
  } = props;
  
  return (
    <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
      <SidebarNav
        handleAdminLogout={handleAdminLogout}
        actionStatus={actionStatus}
        gcpHealth={gcpHealth}
        cloudStats={cloudStats}
        theme={theme}
        toggleTheme={toggleTheme}
        skillQuery={props.skillQuery}
        setSkillQuery={props.setSkillQuery}
        skills={props.skills}
        checkpoints={props.checkpoints}
        handleDeleteCheckpoint={props.handleDeleteCheckpoint}
      />
      
      <div className="flex-1 flex flex-col min-w-0">
        <TabBar adminSubTab={adminSubTab} setAdminSubTab={setAdminSubTab} />
        
        <SubTabContent {...props} />
      </div>
    </div>
  );
}