// ============================================================================
// component >> App.tsx
// project >> SupremeAI 2.0
// purpose >> General utility
// module >> src
// ============================================================================
import { ChatBubble } from '@supremeai/ui-components';
import type { Skill } from '@supremeai/shared-types';

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
}

const RULES = [
  { id: '1', title: 'Rule #1: Admin God', body: 'Admin = सत्यिकারের ঈশ্বর | SupremeAI = অপরাজেয় AI সাম্রাজ্য' },
  { id: '2', title: 'Rule #2: Budget Cap', body: 'Maximum cost per task execution cannot exceed $0.01.' },
  { id: '3', title: 'Rule #3: Sandboxed Skills', body: 'All downloaded skills are sandboxed and secure.' },
];

function App() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: 'স্বাগতম! আমি SupremeAI 2.0 মাস্টার অর্কেস্ট্রেটর। আমি যেকোনো কাজ স্বয়ংক্রিয়ভাবে করতে পারি। আপনাকে কীভাবে সাহায্য করতে পারি?',
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(false);
  const chatAreaRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = chatAreaRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  useEffect(() => {
    const fetchSkills = async () => {
      try {
        const res = await fetch('/skills');
        const data = await res.json();
        const skillsArray = Object.entries(data).map(([name, info]: [string, any]) => ({
          id: name,
          name: info.name ?? name,
          description: info.description ?? '',
          version: info.version ?? '1.0.0',
          enabled: true,
        }));
        setSkills(skillsArray);
      } catch (e) {
        console.error('Failed to load skills', e);
      }
    };
    fetchSkills();
  }, []);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text) return;
    setInput('');

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);

    const typingMsg: Message = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: 'Thinking...',
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, typingMsg]);
    setLoading(true);

    try {
      const response = await fetch('/task/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task: text,
          task_type: text.toLowerCase().includes('code') ? 'coding' : 'general',
        }),
      });
      const data = await response.json() as { result?: string };
      setMessages((prev) =>
        prev.map((m) =>
          m.id === typingMsg.id ? { ...m, content: data.result || 'No response generated.' } : m
        )
      );
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error';
      setMessages((prev) =>
        prev.map((m) =>
          m.id === typingMsg.id ? { ...m, content: `Error connecting to SupremeAI backend: ${errorMsg}` } : m
        )
      );
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="logo-container">
          <div className="logo-icon">🔱</div>
          <div className="logo-text">SUPREME<span>AI</span></div>
        </div>
        <div className="section-title">Constitutional Laws</div>
        <div className="rules-panel">
          {RULES.map((rule) => (
            <div key={rule.id} className="rule-card">
              <strong>{rule.title}</strong>
              <br />
              {rule.body}
            </div>
          ))}
        </div>
        <div className="section-title">Dynamic Skills</div>
        <div className="rules-panel" style={{ maxHeight: 200, marginBottom: 24 }}>
          {skills.length === 0 ? (
            <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Loading skills...</div>
          ) : (
            skills.map((skill) => (
              <div key={skill.id} className="rule-card">
                <strong>{skill.name} v{skill.version}</strong>
                <br />
                {skill.description}
              </div>
            ))
          )}
        </div>
        <div className="system-status">
          <div className="status-dot" />
          <div>Orchestrator: Online (FastAPI)</div>
        </div>
      </aside>

      {/* Main Container */}
      <div className="main-container">
        <div className="header">
          <div className="header-title">Command Center UI</div>
          <div style={{ fontSize: 13, color: 'var(--accent-color)' }}>Admin verified</div>
        </div>
        <div className="chat-area" ref={chatAreaRef}>
          {messages.map((msg) => (
            <ChatBubble key={msg.id} role={msg.role} content={msg.content} timestamp={msg.timestamp} />
          ))}
        </div>
        <div className="input-panel">
          <div className="input-container">
            <input
              type="text"
              className="chat-input"
              placeholder="Ask anything (e.g., 'write a python binary search')..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={loading}
            />
            <button className="send-btn" onClick={sendMessage} disabled={loading}>
              {loading ? 'Sending...' : 'Send'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
