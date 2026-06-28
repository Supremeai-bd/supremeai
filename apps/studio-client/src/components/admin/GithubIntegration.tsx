import { Card, Badge } from '../ui';
import { GitBranch, Clock, ArrowRight, RefreshCw } from 'lucide-react';
import { useState } from 'react';

const MOCK_REPOS = [
  { id: '1', name: 'supremeai-core', branch: 'main', updated: '2h ago', commits: 124 },
  { id: '2', name: 'supremeai-frontend', branch: 'main', updated: '5h ago', commits: 89 },
  { id: '3', name: 'supremeai-mobile', branch: 'develop', updated: '1d ago', commits: 56 },
];

const MOCK_COMMITS = [
  { hash: 'a1b2c3d', message: 'fix: resolve memory leak in agent loop', author: 'admin', time: '2h ago' },
  { hash: 'e4f5g6h', message: 'feat: add RAG document chunking strategies', author: 'dev1', time: '5h ago' },
  { hash: 'i7j8k9l', message: 'chore: update Docker base image', author: 'ci-bot', time: '8h ago' },
  { hash: 'm0n1o2p', message: 'feat: implement prompt versioning system', author: 'admin', time: '1d ago' },
];

export function GithubIntegration() {
  const [selectedRepo, setSelectedRepo] = useState(MOCK_REPOS[0]);

  return (
    <div className="flex-grow p-6 overflow-y-auto bg-[#030611]">
      <div className="flex items-center justify-between mb-6 pb-2 border-b border-[#00f3ff]/15">
        <h2 className="text-lg font-bold font-['Space_Grotesk'] tracking-widest text-[#00f3ff] uppercase">
          🔗 GitHub Integration
        </h2>
        <button className="flex items-center gap-2 px-3 py-1.5 rounded border border-[#00f3ff]/30 text-[#00f3ff] hover:bg-[#00f3ff]/10 text-[10px] font-bold font-mono uppercase transition-colors">
          <RefreshCw size={10} /> Sync
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card title="Repositories" className="lg:col-span-1">
          <div className="flex flex-col gap-2">
            {MOCK_REPOS.map(repo => (
              <button
                key={repo.id}
                onClick={() => setSelectedRepo(repo)}
                className={`text-left p-3 rounded-lg border transition-all ${
                  selectedRepo.id === repo.id
                    ? 'border-[#00f3ff]/50 bg-[#00f3ff]/10'
                    : 'border-slate-800 bg-slate-900/30 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold text-white font-mono">{repo.name}</span>
                  <Badge variant="info">{repo.branch}</Badge>
                </div>
                <div className="text-[10px] text-slate-500 font-mono flex items-center gap-2">
                  <span className="flex items-center gap-1"><GitBranch size={10} /> {repo.commits} commits</span>
                  <span className="flex items-center gap-1"><Clock size={10} /> {repo.updated}</span>
                </div>
              </button>
            ))}
          </div>
        </Card>

        <Card title={`Commits: ${selectedRepo.name}`} className="lg:col-span-2">
          <div className="flex flex-col gap-2">
            {MOCK_COMMITS.map((commit, i) => (
              <div key={i} className="flex items-center gap-3 p-3 rounded-lg border border-slate-800 bg-slate-900/30">
                <div className="flex-shrink-0">
                  <div className="w-8 h-8 rounded-full bg-[#24292e] flex items-center justify-center">
                    <GitBranch size={12} className="text-white" />
                  </div>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-mono text-white truncate">{commit.message}</div>
                  <div className="text-[10px] text-slate-500 font-mono mt-0.5">
                    {commit.hash} by {commit.author} • {commit.time}
                  </div>
                </div>
                <button className="text-[10px] text-[#00f3ff] hover:text-cyan-300 font-mono px-2 py-1 rounded border border-[#00f3ff]/30">
                  View
                </button>
              </div>
            ))}
          </div>
          <div className="flex justify-between items-center mt-4 pt-3 border-t border-slate-800">
            <span className="text-[10px] text-slate-500 font-mono">Showing 4 of {selectedRepo.commits} commits</span>
            <button className="text-[10px] text-[#00f3ff] hover:text-cyan-300 font-mono flex items-center gap-1">
              View all <ArrowRight size={10} />
            </button>
          </div>
        </Card>
      </div>
    </div>
  );
}
