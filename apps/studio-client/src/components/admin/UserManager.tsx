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
    <div className="flex-grow bg-black/50 p-6 overflow-y-auto font-mono text-xs">
      <h3 className="text-sm font-bold text-slate-200 mb-4 pb-2 border-b border-slate-800">👤 USER & RBAC MANAGEMENT</h3>

      <div className="bg-[#0c0d12] border border-slate-900 rounded-lg p-4 mb-6 flex flex-wrap gap-4 items-end">
        <div className="flex flex-col gap-1.5">
          <label className="text-[10px] text-slate-400 uppercase">Username</label>
          <input
            type="text"
            placeholder="username..."
            value={newUsername}
            onChange={e => setNewUsername(e.target.value)}
            className="bg-[#06080b] border border-slate-800 rounded px-3 py-1.5 text-white outline-none focus:border-[#00f3ff]"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-[10px] text-slate-400 uppercase">Role</label>
          <select
            value={newUserRole}
            onChange={e => setNewUserRole(e.target.value)}
            className="bg-[#06080b] border border-slate-800 rounded px-3 py-1.5 text-white outline-none"
          >
            <option value="Operator">Operator</option>
            <option value="God">God</option>
            <option value="Viewer">Viewer</option>
          </select>
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-[10px] text-slate-400 uppercase">Permissions (comma separated)</label>
          <input
            type="text"
            value={newUserPerms}
            onChange={e => setNewUserPerms(e.target.value)}
            className="bg-[#06080b] border border-slate-800 rounded px-3 py-1.5 text-white outline-none"
          />
        </div>
        <button
          onClick={handleSaveUser}
          className="bg-[#00f3ff] text-black font-bold px-4 py-1.5 rounded transition-colors uppercase font-mono"
        >
          Add/Update User
        </button>
      </div>

      <div className="flex flex-col gap-3">
        {adminUsers.map(user => (
          <div key={user.username} className="bg-[#0c0d12] border border-slate-900 rounded-lg p-4 flex justify-between items-center">
            <div>
              <span className="font-bold text-white text-sm">{user.username}</span>
              <span className="ml-3 px-2 py-0.5 rounded text-[10px] bg-cyan-950 text-[#00f3ff] border border-cyan-900">{user.role}</span>
              <div className="text-slate-500 mt-1 text-[10px]">Perms: {JSON.stringify(user.permissions)}</div>
            </div>
            <button
              onClick={() => handleDeleteUser(user.username)}
              className="bg-red-950/40 hover:bg-red-900/40 text-red-400 border border-red-900/40 px-2 py-1 rounded"
            >
              DELETE
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
