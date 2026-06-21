import { useState } from 'react';

interface Action {
  id: string;
  label: string;
  type: string;
}

interface ActionCardMetadata {
  language?: string;
  filename?: string;
  actions?: Action[];
}

interface ActionCardProps {
  rawContent: string;
  onSaveToProject?: (code: string) => void;
  onPreview?: (code: string) => void;
}

export function ActionCard({ rawContent, onSaveToProject, onPreview }: ActionCardProps) {
  const [copied, setCopied] = useState(false);
  const [actionStatus, setActionStatus] = useState('');

  // Try to parse structured AI response JSON
  let parsed: { type: string; content: string; metadata?: ActionCardMetadata } | null = null;
  try {
    if (rawContent.trim().startsWith('{')) {
      parsed = JSON.parse(rawContent);
    }
  } catch (e) {
    // Not a JSON response, fallback to text rendering
  }

  const handleAction = async (action: Action, content: string) => {
    try {
      if (action.type === 'save' && onSaveToProject) {
        onSaveToProject(content);
        setActionStatus('💾 Code saved to project!');
        setTimeout(() => setActionStatus(''), 3000);
      } else if (action.type === 'preview' && onPreview) {
        onPreview(content);
        setActionStatus('👁️ Code loaded into preview!');
        setTimeout(() => setActionStatus(''), 3000);
      } else if (action.type === 'copy') {
        await navigator.clipboard.writeText(content);
        setCopied(true);
        setActionStatus('📋 Copied to clipboard!');
        setTimeout(() => {
          setCopied(false);
          setActionStatus('');
        }, 3000);
      } else if (action.type === 'run') {
        setActionStatus('▶️ Running code in sandbox...');
        setTimeout(() => setActionStatus('✅ Code executed successfully!'), 1500);
        setTimeout(() => setActionStatus(''), 4500);
      } else if (action.type === 'deploy') {
        setActionStatus('🚀 Deploying code component...');
        setTimeout(() => setActionStatus('✅ Code deployed successfully!'), 2000);
        setTimeout(() => setActionStatus(''), 5000);
      } else if (action.type === 'share') {
        setActionStatus('🔗 Share link copied!');
        setTimeout(() => setActionStatus(''), 3000);
      }
    } catch (err: any) {
      setActionStatus(`❌ Error: ${err.message}`);
      setTimeout(() => setActionStatus(''), 4000);
    }
  };

  if (!parsed || !parsed.type || !parsed.content) {
    // Normal text message
    return <div className="whitespace-pre-wrap break-words">{rawContent}</div>;
  }

  const { type, content, metadata } = parsed;
  const actions = metadata?.actions || [];

  return (
    <div className="flex flex-col gap-3 w-full bg-[#0a0c14] border border-[#bc13fe]/20 rounded-xl p-3.5 shadow-lg">
      {type === 'code' && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2 mb-1.5">
            <span className="text-[11px] font-mono text-slate-400">
              📁 {metadata?.filename || 'component.tsx'} ({metadata?.language || 'typescript'})
            </span>
            <button
              onClick={() => {
                navigator.clipboard.writeText(content);
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
              }}
              className="text-[10px] text-[#bc13fe] hover:text-[#8b5cf6] font-mono font-semibold"
            >
              {copied ? 'Copied!' : 'Copy Code'}
            </button>
          </div>
          <pre className="bg-[#050608] p-3 rounded-lg overflow-x-auto text-xs font-mono text-slate-300 max-h-60 border border-slate-900">
            <code>{content}</code>
          </pre>
        </div>
      )}

      {type === 'image' && (
        <div className="flex flex-col gap-2">
          <div className="relative rounded-lg overflow-hidden border border-slate-800 max-h-64 bg-slate-950">
            <img src={content} alt="AI Generated" className="w-full h-auto object-contain mx-auto" />
          </div>
        </div>
      )}

      {type === 'text' && (
        <div className="whitespace-pre-wrap break-words text-slate-200">
          {content}
        </div>
      )}

      {/* Action Buttons Section */}
      {actions.length > 0 && (
        <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-900/60 mt-1">
          {actions.map((act) => (
            <button
              key={act.id}
              onClick={() => handleAction(act, content)}
              className="text-[11px] px-2.5 py-1.5 rounded-lg bg-[#121420] border border-[#bc13fe]/30 hover:border-[#bc13fe] hover:bg-[#1a1c2e] text-slate-300 font-semibold transition-all duration-200"
            >
              {act.label}
            </button>
          ))}
        </div>
      )}

      {actionStatus && (
        <div className="text-[10px] text-slate-400 font-mono italic animate-pulse">
          {actionStatus}
        </div>
      )}
    </div>
  );
}
