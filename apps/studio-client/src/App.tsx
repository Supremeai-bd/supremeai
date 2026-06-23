import React, { useEffect, useState } from "react";

// Pro Tip: গ্লোবাল ব্যাকএন্ড URL ম্যাপ
const API_BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

export const App: React.FC = () => {
  const [isServerOnline, setIsServerOnline] = useState<boolean>(false);
  const [streamLogs, setStreamLogs] = useState<string[]>([]);

  useEffect(() => {
    // ⚡ ১. আলাদা /health পোলিং সম্পূর্ণ ডিলিট করে সরাসরি মেইন SSE স্ট্রিমে কানেক্ট করা হচ্ছে
    // আপনার প্রজেক্টের একচুয়াল স্ট্রিমিং এন্ডপয়েন্ট (যেমন: /api/task/stream) এখানে বসাবেন
    const sseEndpoint = `${API_BASE_URL}/api/task/stream`;
    
    console.log("🔌 Initializing SupremeAI Unified Lifespan SSE Stream...");
    const eventSource = new EventSource(sseEndpoint);

    // 🟢 ২. SSE কানেকশন সাকসেসফুলি ওপেন হলে স্টেট চেঞ্জ (Zero Network Cost Health Check)
    eventSource.onopen = () => {
      console.log("🟢 [SYSTEM ON] SupremeAI Backend Core is ONLINE. SSE Stream active.");
      setIsServerOnline(true);
    };

    // ৩. রিয়েল-টাইম লাইভ মেসেজ বা টাস্ক লগ রিসিভ করার লজিক
    eventSource.onmessage = (event) => {
      try {
        const parsedData = JSON.parse(event.data);
        if (parsedData.log) {
          setStreamLogs((prev) => [...prev, parsedData.log]);
        }
      } catch (err) {
        // প্লেইন টেক্সট ডাটা আসলে সরাসরি হ্যান্ডেল করবে
        setStreamLogs((prev) => [...prev, event.data]);
      }
    };

    // 🔴 ৪. সার্ভার ডাউন হলে বা কন্টেইনার স্লিপে গেলে স্বয়ংক্রিয়ভাবে অফলাইন স্টেট টগল
    // EventSource নিজে থেকেই ব্যাকগ্রাউন্ডে রি-কানেক্ট ট্রাই করতে থাকবে, কোনো setInterval লাগবে না
    eventSource.onerror = (error) => {
      console.error("🔴 [SYSTEM CRITICAL] SSE Stream severed. SupremeAI Server is OFFLINE.");
      setIsServerOnline(false);
    };

    // 🧹 ৫. কম্পোনেন্ট আনমাউন্ট বা রিলিজ হ্যান্ডলার (Zombie Tab & Memory Leak Prevention)
    return () => {
      console.warn("🔌 Disconnecting active SSE stream context wrapper.");
      eventSource.close();
    };
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans p-6 relative">
      {/* 🛡️ গড-টিয়ার রিয়েল-টাইম লাইভ হেলথ ইন্ডিকেটর ব্যাজ */}
      <div className="absolute top-4 right-4 flex items-center gap-2 bg-slate-900/80 border border-slate-800 px-3 py-1.5 rounded-full shadow-lg backdrop-blur-md">
        <span className={`h-2.5 w-2.5 rounded-full ${isServerOnline ? "bg-emerald-500 animate-pulse" : "bg-rose-500"}`} />
        <span className="text-xs font-mono tracking-wider font-bold text-slate-300">
          {isServerOnline ? "SUPREME_CORE: ACTIVE" : "SUPREME_CORE: OFFLINE"}
        </span>
      </div>

      {/* ড্যাশবোর্ডের বাকি UI সেকশন এখানে বসবে */}
      <main className="mt-12">
        <h1 className="text-2xl font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
          SupremeAI Dashboard Console
        </h1>
        
        {/* লাইভ লগ মনিটর স্ক্রিন */}
        <div className="mt-6 p-4 bg-slate-900 border border-slate-800 rounded-xl font-mono text-xs max-h-60 overflow-y-auto">
          <p className="text-slate-500">// Live Infrastructure Logs:</p>
          {streamLogs.map((log, index) => (
            <p key={index} className="text-cyan-400 mt-1">{log}</p>
          ))}
        </div>
      </main>
    </div>
  );
};
