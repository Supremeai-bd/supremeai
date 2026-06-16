import React, { useState } from 'react';
import Editor from '@monaco-editor/react';

interface ChatMessage {
  id: string;
  sender: 'ai' | 'user';
  text: string;
}

function App() {
  const [code, setCode] = useState('// Welcome to SupremeAI Studio\n\nfunction helloWorld() {\n  console.log("Hello SupremeAI!");\n}\n');
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: '1', sender: 'ai', text: "Hello! I'm SupremeAI, your AI pair programmer. How can I help you build today?" }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSend = async () => {
    if (!input.trim() || loading) return;
    
    const userMsg = input.trim();
    setInput('');
    setMessages(prev => [...prev, { id: Date.now().toString(), sender: 'user', text: userMsg }]);
    setLoading(true);

    try {
      const res = await fetch('http://localhost:8080/api/ide/assistant/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: userMsg, context: code })
      });
      const data = await res.json();
      
      setMessages(prev => [...prev, { 
        id: Date.now().toString(), 
        sender: 'ai', 
        text: data.response || data.error || 'No response.' 
      }]);
      
      if (data.code) {
         setCode(data.code);
      }
    } catch (err: any) {
      setMessages(prev => [...prev, { id: Date.now().toString(), sender: 'ai', text: 'Error connecting to SupremeAI API.' }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-screen w-screen flex flex-col bg-slate-900 text-white overflow-hidden font-sans">
      {/* Titlebar for Electron */}
      <div className="h-8 flex-shrink-0 drag-region bg-slate-950 flex items-center px-4 border-b border-slate-800">
        <div className="flex gap-2">
          <div className="w-3 h-3 rounded-full bg-red-500"></div>
          <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
          <div className="w-3 h-3 rounded-full bg-green-500"></div>
        </div>
        <div className="mx-auto text-xs text-slate-400 font-medium">SupremeAI Studio</div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-row">
        {/* Sidebar */}
        <div className="w-16 flex-shrink-0 bg-slate-900 flex flex-col items-center py-4 gap-4 border-r border-slate-800">
          <button className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors" title="Explorer">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" /></svg>
          </button>
          <button className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors" title="Search">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
          </button>
          <button className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors bg-purple-900/50" title="SupremeAI AI">
            <svg className="w-6 h-6 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
          </button>
        </div>

        {/* Editor Area */}
        <div className="flex-1 flex flex-col">
          <div className="h-10 bg-slate-900 flex items-center px-4 border-b border-slate-800">
            <div className="px-4 py-1 text-sm bg-slate-800 text-white rounded-t-md border-t border-x border-slate-700">main.js</div>
          </div>
          <div className="flex-1 relative">
            <Editor
              height="100%"
              defaultLanguage="javascript"
              theme="vs-dark"
              value={code}
              onChange={(value) => setCode(value || '')}
              options={{
                minimap: { enabled: false },
                fontSize: 14,
                fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                lineHeight: 24,
                padding: { top: 16 },
                scrollBeyondLastLine: false,
                smoothScrolling: true,
                cursorBlinking: 'smooth',
                cursorSmoothCaretAnimation: 'on'
              }}
            />
          </div>
        </div>

        {/* AI Assistant Sidebar */}
        <div className="w-80 flex-shrink-0 bg-slate-950 border-l border-slate-800 flex flex-col">
          <div className="h-10 flex items-center px-4 border-b border-slate-800 font-medium text-sm text-slate-200">
            SupremeAI Assistant
          </div>
          <div className="flex-1 p-4 overflow-y-auto flex flex-col gap-4">
            {messages.map(msg => (
              <div key={msg.id} className={`p-3 rounded-lg text-sm ${msg.sender === 'user' ? 'bg-purple-900/40 text-slate-200 self-end border border-purple-800/50' : 'bg-slate-800 text-slate-300'}`}>
                {msg.text}
              </div>
            ))}
            {loading && (
              <div className="text-xs text-slate-500 animate-pulse">SupremeAI is typing...</div>
            )}
          </div>
          <div className="p-4 border-t border-slate-800">
            <input 
              type="text" 
              placeholder="Ask SupremeAI..." 
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSend()}
              className="w-full bg-slate-900 border border-slate-700 rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500 transition-colors"
            />
          </div>
        </div>
      </div>

      {/* Status Bar */}
      <div className="h-6 flex-shrink-0 bg-blue-600 flex items-center px-4 text-xs font-medium text-white justify-between">
        <div className="flex items-center gap-4">
          <span>SupremeAI Cloud Run: Connected</span>
          <span>SupremeAI Engine Active</span>
        </div>
        <div className="flex items-center gap-4">
          <span>UTF-8</span>
          <span>JavaScript</span>
        </div>
      </div>
    </div>
  );
}

export default App;
