// apps/web-chat/script.js

// WebSocket Setup
// Environment Detection for Dynamic WebSocket URL
const isProd = window.location.hostname !== '127.0.0.1' && window.location.hostname !== 'localhost';
const PROTOCOL = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
const HOST = isProd ? window.location.host : '127.0.0.1:8000'; // প্রোডাকশনে অরিজিনাল হোস্ট ব্যবহার করবে
const WS_URL = `${PROTOCOL}${HOST}/ws/chat`;
let ws;
let isGenerating = false;

// DOM Elements
const chatHistory = document.getElementById('chatHistory');
const chatInput = document.getElementById('chatInput');
const btnSend = document.getElementById('btnSend');

// 1. Initialize WebSocket Connection
function connectWebSocket() {
    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
        console.log('🟢 [WS] Connected to Neural Engine');
        addMessage('assistant', 'সিস্টেম কানেক্টেড! আমি SupremeAI এজেন্ট, কীভাবে সাহায্য করতে পারি?');
    };

    ws.onmessage = (event) => {
        const data = event.data;
        
        if (data === '[DONE]') {
            isGenerating = false;
            return;
        }

        // লাইভ টাইপিং ইফেক্ট (শেষ মেসেজটিতে টেক্সট অ্যাপেন্ড করা)
        const lastMessage = chatHistory.lastElementChild;
        if (lastMessage && lastMessage.classList.contains('msg-assistant')) {
            lastMessage.textContent += data;
        } else {
            // যদি নতুন রেসপন্স শুরু হয়
            addMessage('assistant', data);
        }
        
        // অটো-স্ক্রল
        chatHistory.scrollTop = chatHistory.scrollHeight;
    };

    ws.onclose = () => {
        console.log('🔴 [WS] Disconnected. Reconnecting in 3s...');
        setTimeout(connectWebSocket, 3000);
    };
}

// 2. UI Render Helper
function addMessage(role, text) {
    const div = document.createElement('div');
    div.className = `msg msg-${role}`;
    div.textContent = text;
    chatHistory.appendChild(div);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

// 3. Handle Send
function handleSend() {
    const text = chatInput.value.trim();
    if (!text || isGenerating || !ws || ws.readyState !== WebSocket.OPEN) return;

    // Add user message
    addMessage('user', text);
    chatInput.value = '';
    isGenerating = true;

    // Send to WebSocket
    ws.send(text);
    
    // Add empty assistant bubble for the incoming stream
    addMessage('assistant', ''); 
}

// Event Listeners
if(btnSend) {
    btnSend.addEventListener('click', handleSend);
}
if(chatInput) {
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleSend();
    });
}

// Init
connectWebSocket();
