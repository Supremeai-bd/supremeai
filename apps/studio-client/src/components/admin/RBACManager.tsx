import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Card, Badge } from '../ui';
import { Shield, UserPlus, Trash2, Settings2, CheckCircle2, XCircle } from 'lucide-react';

export function RBACManager() {
  const { data: users } = useQuery({
    queryKey: ['users'],
    queryFn: () => fetch('/admin-api/users').then(r => r.json()),
  });
  const qc = useQueryClient();
  const [newUser, setNewUser] = useState({ username: '', role: 'Operator', permissions: 'read,write' });

  const addUser = useMutation({
    mutationFn: (user: any) =>
      fetch('/admin-api/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(user),
      }).then(r => r.json()),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  });

  const deleteUser = useMutation({
    mutationFn: (username: string) =>
      fetch(`/admin-api/users/${username}`, { method: 'DELETE' }).then(r => r.json()),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  });

  const roleColors: Record<string, 'purple' | 'info' | 'warning' | 'default'> = {
    God: 'purple',
    Admin: 'info',
    Developer: 'info',
    Operator: 'warning',
    Viewer: 'default',
  };

  return (
    <div className="flex-grow p-6 overflow-y-auto bg-[#030611]">
      <div className="flex items-center justify-between mb-6 pb-2 border-b border-[#00f3ff]/15">
        <h2 className="text-lg font-bold font-['Space_Grotesk'] tracking-widest text-[#00f3ff] uppercase">
          🔐 User Governance & RBAC
        </h2>
        <Badge variant="info">{users?.length || 0} Users</Badge>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 mb-6">
        <Card title="Create User" icon={<UserPlus size={14} />} className="xl:col-span-1">
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] text-slate-400 uppercase">Username</label>
              <input
                type="text"
                value={newUser.username}
                onChange={e => setNewUser(prev => ({ ...prev, username: e.target.value }))}
                className="bg-[#06080b] border border-slate-800 rounded px-3 py-1.5 text-white outline-none focus:border-[#00f3ff] text-xs font-mono"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] text-slate-400 uppercase">Role</label>
              <select
                value={newUser.role}
                onChange={e => setNewUser(prev => ({ ...prev, role: e.target.value }))}
                className="bg-[#06080b] border border-slate-800 rounded px-3 py-1.5 text-white outline-none text-xs font-mono"
              >
                <option value="Viewer">Viewer</option>
                <option value="Operator">Operator</option>
                <option value="Developer">Developer</option>
                <option value="Admin">Admin</option>
                <option value="God">God</option>
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] text-slate-400 uppercase">Permissions (comma-separated)</label>
              <input
                type="text"
                value={newUser.permissions}
                onChange={e => setNewUser(prev => ({ ...prev, permissions: e.target.value }))}
                className="bg-[#06080b] border border-slate-800 rounded px-3 py-1.5 text-white outline-none focus:border-[#00f3ff] text-xs font-mono"
              />
            </div>
            <button
              onClick={() => addUser.mutate(newUser)}
              className="bg-[#00f3ff] hover:bg-cyan-400 text-black font-bold px-4 py-1.5 rounded text-xs uppercase font-mono"
            >
              Add User
            </button>
          </div>
        </Card>

        <Card title="User Directory" icon={<Shield size={14} />} className="xl:col-span-2">
          <div className="flex flex-col gap-2 max-h-[50vh] overflow-y-auto">
            {users?.map((user: any) => (
              <div key={user.username} className="flex items-center justify-between p-3 rounded-lg border border-slate-800 bg-slate-900/30">
                <div className="flex items-center gap-3">
                  <div>
                    <div className="text-xs font-bold text-white font-mono">{user.username}</div>
                    <div className="text-[10px] text-slate-500 font-mono mt-0.5">
                      {user.permissions?.join(', ')}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={roleColors[user.role] || 'default'}>{user.role}</Badge>
                  <button
                    onClick={() => deleteUser.mutate(user.username)}
                    className="text-red-400 hover:text-red-300 p-1 rounded"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              </div>
            ))}
            {(!users || users.length === 0) && (
              <div className="text-xs text-slate-500 font-mono text-center py-4">No users configured.</div>
            )}
          </div>
        </Card>
      </div>

      <Card title="Permission Matrix" icon={<Settings2 size={14} />}>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[10px] font-mono">
            <thead>
              <tr className="border-b border-slate-800">
                <th className="pb-2 text-slate-400 font-semibold">Permission</th>
                <th className="pb-2 text-center text-slate-400 font-semibold">Viewer</th>
                <th className="pb-2 text-center text-slate-400 font-semibold">Operator</th>
                <th className="pb-2 text-center text-slate-400 font-semibold">Developer</th>
                <th className="pb-2 text-center text-slate-400 font-semibold">Admin</th>
                <th className="pb-2 text-center text-slate-400 font-semibold">God</th>
              </tr>
            </thead>
            <tbody>
              {[
                ['system:read', true, true, true, true, true],
                ['model:override', false, true, true, true, true],
                ['skill:install', false, true, true, true, true],
                ['rules:edit', false, false, true, true, true],
                ['deploy:prod', false, false, true, true, true],
                ['user:admin', false, false, false, true, true],
                ['audit:read', false, false, false, false, true],
              ].map(([perm, ...access]) => (
                <tr key={perm as string} className="border-b border-slate-800/50">
                  <td className="py-2 text-slate-300">{perm as string}</td>
                  {access.map((a: any, i) => (
                    <td key={i} className="py-2 text-center">
                      {a ? <CheckCircle2 size={12} className="text-emerald-400 inline" /> : <XCircle size={12} className="text-slate-600 inline" />}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
