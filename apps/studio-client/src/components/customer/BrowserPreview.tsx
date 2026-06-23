// ============================================================================
// component >> BrowserPreview.tsx
// project >> SupremeAI 2.0
// purpose >> Browser automation
// module >> src
// ============================================================================
import { Card } from '../ui';
import { RefreshCw, ExternalLink } from 'lucide-react';

interface BrowserPreviewProps {
  url?: string;
  html?: string;
}

export function BrowserPreview({ url = 'https://supremeai.web.app', html }: BrowserPreviewProps) {
  const [currentUrl, setCurrentUrl] = useState(url);
  const [loading, setLoading] = useState(false);

  const handleRefresh = () => {
    setLoading(true);
    setTimeout(() => setLoading(false), 800);
  };

  return (
    <div className="flex-grow p-6 overflow-y-auto bg-[#030508]">
      <div className="flex items-center justify-between mb-6 pb-2 border-b border-[#00f3ff]/15">
        <h2 className="text-lg font-bold font-['Space_Grotesk'] tracking-widest text-[#00f3ff] uppercase">
          🌐 Browser Preview
        </h2>
      </div>

      <Card>
        <div className="flex items-center gap-2 mb-4">
          <div className="flex-1 flex items-center gap-2 bg-[#06080b] border border-slate-800 rounded-lg px-3 py-1.5">
            <ExternalLink size={12} className="text-slate-500" />
            <input
              type="text"
              value={currentUrl}
              onChange={e => setCurrentUrl(e.target.value)}
              className="flex-1 bg-transparent text-xs text-white outline-none font-mono"
            />
          </div>
          <button
            onClick={handleRefresh}
            className="p-1.5 rounded border border-slate-800 text-slate-400 hover:text-white hover:border-slate-700 transition-colors"
          >
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>

        <div className="border border-slate-800 rounded-lg overflow-hidden bg-white">
          {html ? (
            <iframe
              srcDoc={html}
              title="Preview"
              className="w-full h-[60vh]"
              sandbox="allow-scripts allow-forms"
            />
          ) : (
            <iframe
              src={currentUrl}
              title="Preview"
              className="w-full h-[60vh]"
              sandbox="allow-scripts allow-forms"
            />
          )}
        </div>
      </Card>
    </div>
  );
}
