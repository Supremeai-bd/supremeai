interface UserManagerProps {
  newUsername: string;
  setNewUsername: (val: string) => void;
  newUserRole: string;
  setNewUserRole: (val: string) => void;
  newUserPerms: string;
  setNewUserPerms: (val: string) => void;
  handleSaveUser: () => void;
  adminUsers: any[];
  handleDeleteUser: (username: string) => void;
}

export function UserManager({
  newUsername, setNewUsername,
  newUserRole, setNewUserRole,
  newUserPerms, setNewUserPerms,
  handleSaveUser,
  adminUsers, handleDeleteUser
}: UserManagerProps) {
  return (
    <div className="flex-grow bg-[#030611] p-6 overflow-y-auto font-sans">
      <div className="flex items-center justify-between mb-6 pb-2 border-b border-slate-800">
        <h3 className="text-sm font-bold text-slate-200 tracking-wider font-mono">👤 USER & RBAC MANAGEMENT</h3>
        <span className="text-[10px] text-slate-400 font-mono bg-slate-900 border border-slate-800 px-2 py-0.5 rounded">Active Admins: {adminUsers.length}</span>
      </div>

      {/* Add New User Panel */}
      <div className="bg-[#0c0d12]/90 border border-slate-900 rounded-xl p-5 mb-6">
        <h4 className="text-xs font-bold text-slate-300 mb-4 uppercase tracking-wider font-mono">Add / Update Administrative Role</h4>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
          <div className="flex flex-col gap-1.5">
            <label className="text-[9px] text-slate-400 uppercase font-mono tracking-wider">Username</label>
            <input
              type="text"
              placeholder="e.g. alice"
              value={newUsername}
              onChange={e => setNewUsername(e.target.value)}
              className="bg-[#05060a] border border-slate-850 rounded-lg px-3.5 py-2 text-xs text-white outline-none focus:border-[#00f3ff] transition-all font-mono"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-[9px] text-slate-400 uppercase font-mono tracking-wider">System Role</label>
            <select
              value={newUserRole}
              onChange={e => setNewUserRole(e.target.value)}
              className="bg-[#05060a] border border-slate-850 rounded-lg px-3.5 py-2 text-xs text-white outline-none focus:border-[#00f3ff] transition-all font-mono"
            >
              <option value="Operator">Operator</option>
              <option value="God">God Mode</option>
              <option value="Viewer">Viewer (Read-Only)</option>
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-[9px] text-slate-400 uppercase font-mono tracking-wider">Permissions (comma separated)</label>
            <input
              type="text"
              placeholder="e.g. read:logs,write:config"
              value={newUserPerms}
              onChange={e => setNewUserPerms(e.target.value)}
              className="bg-[#05060a] border border-slate-850 rounded-lg px-3.5 py-2 text-xs text-white outline-none focus:border-[#00f3ff] transition-all font-mono"
            />
          </div>
        </div>
        <div className="flex justify-end mt-4">
          <button
            onClick={handleSaveUser}
            className="bg-[#00f3ff] hover:bg-cyan-400 text-black font-extrabold px-6 py-2 rounded-lg text-xs transition-colors uppercase font-mono tracking-wider shadow-[0_4px_12px_rgba(0,243,255,0.15)]"
          >
            Provision / Save User
          </button>
        </div>
      </div>

      {/* Users List */}
      <h4 className="text-xs font-bold text-slate-400 mb-4 tracking-wider uppercase font-mono">Administrative User Registry</h4>
      <div className="flex flex-col gap-3">
        {adminUsers.map(user => {
          const perms = Array.isArray(user.permissions) 
            ? user.permissions 
            : typeof user.permissions === 'string'
              ? user.permissions.split(',').map((p: string) => p.trim())
              : [];

          return (
            <div key={user.username} className="bg-[#0c0d12]/60 border border-slate-900 rounded-xl p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="flex flex-col gap-2">
                <div className="flex items-center gap-3">
                  <span className="font-bold text-sm text-white font-mono">{user.username}</span>
                  <span className={`px-2 py-0.5 rounded text-[9px] font-bold border font-mono ${
                    user.role === 'God'
                      ? 'bg-red-950/80 text-red-400 border-red-900/60'
                      : user.role === 'Operator'
                        ? 'bg-cyan-950/80 text-[#00f3ff] border-cyan-900/60'
                        : 'bg-slate-900 text-slate-400 border-slate-800'
                  }`}>
                    {user.role}
                  </span>
                </div>
                
                {/* Permission Badges */}
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {perms.map((perm: string, idx: number) => (
                    <span key={idx} className="bg-slate-950 text-slate-400 border border-slate-900 px-2 py-0.5 rounded text-[9px] font-mono">
                      {perm}
                    </span>
                  ))}
                  {perms.length === 0 && <span className="text-[10px] text-slate-500 italic font-mono">No special permissions assigned</span>}
                </div>
              </div>
              
              <button
                onClick={() => handleDeleteUser(user.username)}
                className="self-end md:self-auto bg-red-950/30 hover:bg-red-900/40 text-red-400 border border-red-900/30 hover:border-red-900/60 px-3 py-1.5 rounded-lg text-xs font-bold transition-all uppercase font-mono tracking-wider"
              >
                Revoke Role
              </button>
            </div>
          );
        })}
        {adminUsers.length === 0 && (
          <div className="text-center py-8 bg-[#0c0d12]/30 border border-slate-900 rounded-xl text-slate-500 italic font-mono">
            No administrative users provisioned in registry.
          </div>
        )}
      </div>
    </div>
  );
}
