// src/components/editor/CollabEditor.tsx
import { useState, useEffect, useRef, useCallback } from 'react';
import Editor from '@monaco-editor/react';

// ব্যাকএন্ডের WebSocket URL (আপনার এনভায়রনমেন্ট অনুযায়ী পরিবর্তন হতে পারে)
const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000';

interface CollabEditorProps {
  sessionId: string;
  clientId: string;
}

export default function CollabEditor({ sessionId, clientId }: CollabEditorProps) {
  const [code, setCode] = useState<string>('// SupremeAI AI-Powered Collaborative Editor\n// Write code or ask AI to generate...\n\n');
  const [isAiProcessing, setIsAiProcessing] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  useEffect(() => {
    // বাংলা মন্তব্য: ব্যাকএন্ডের সাথে WebSocket কানেকশন তৈরি করা হচ্ছে
    const wsUrl = `${WS_BASE_URL}/api/v1/collaborate/ws/${sessionId}/${clientId}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log(`Connected to Collaborative Session: ${sessionId}`);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        // বাংলা মন্তব্য: ব্যাকএন্ড 'sync_state' এর ক্ষেত্রে 'state' অবজেক্টের ভেতর 'document_state' পাঠায়। 
        // আর 'delta' এর ক্ষেত্রে সরাসরি অবজেক্টের লেভেলে 'document_state' থাকে।
        if (data.type === 'sync_state') {
          if (data.state && data.state.document_state !== undefined) {
            setCode(data.state.document_state);
          }
        } else if (data.type === 'delta') {
          if (data.document_state !== undefined) {
            setCode(data.document_state);
          }
        }
        // এআই রেসপন্স প্রসেসিং স্ট্যাটাস হ্যান্ডেল করা
        else if (data.type === 'ai_response') {
          setIsAiProcessing(data.status === 'processing');
        }
      } catch (err) {
        console.error("Error parsing websocket message", err);
      }
    };

    ws.onclose = () => {
      console.log("Disconnected from Collaborative Session");
    };

    return () => {
      ws.close();
    };
  }, [sessionId, clientId]);

  // বাংলা মন্তব্য: ইউজারের কোড চেঞ্জ হলে ব্যাকএন্ডে পাঠানো
  const handleEditorChange = useCallback((value: string | undefined) => {
    const newValue = value || '';
    setCode(newValue);
    
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      // MVP এর জন্য আমরা সিম্পল ডেল্টা পাঠাচ্ছি। (প্রোডাকশনে এখানে Yjs/CRDT ডেল্টা যাবে)
      wsRef.current.send(JSON.stringify({
        type: 'delta',
        delta: { insert: newValue, position: 0 } 
      }));
    }
  }, []);

  // এআই-কে কোড লিখতে বলার ফাংশন
  const handleAskAI = () => {
    const prompt = window.prompt("What should the AI code for you?");
    if (prompt && wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'ai_request',
        prompt: prompt
      }));
      setIsAiProcessing(true);
    }
  };

  return (
    <div className="flex flex-col h-full w-full border border-gray-200 rounded-xl overflow-hidden shadow-sm bg-white">
      {/* Editor Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-b border-gray-200">
        <div className="flex items-center space-x-2">
          <div className="flex space-x-1">
            <div className="w-3 h-3 bg-red-400 rounded-full"></div>
            <div className="w-3 h-3 bg-yellow-400 rounded-full"></div>
            <div className="w-3 h-3 bg-green-400 rounded-full"></div>
          </div>
          <span className="ml-2 text-sm font-semibold text-gray-600 font-mono">supreme_agent.py</span>
        </div>
        
        <div className="flex items-center space-x-3">
          {isAiProcessing && (
            <span className="text-xs font-bold text-indigo-600 animate-pulse flex items-center">
              <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-indigo-600" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              AI is typing...
            </span>
          )}
          <button 
            onClick={handleAskAI}
            className="px-3 py-1.5 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded transition-colors flex items-center"
          >
            ✨ Ask AI
          </button>
        </div>
      </div>

      {/* Monaco Editor Instance */}
      <div className="flex-grow">
        <Editor
          height="100%"
          defaultLanguage="python"
          theme="light"
          value={code}
          onChange={handleEditorChange}
          options={{
            minimap: { enabled: false },
            fontSize: 14,
            wordWrap: "on",
            padding: { top: 16 },
            scrollBeyondLastLine: false,
            smoothScrolling: true,
          }}
        />
      </div>
    </div>
  );
}
