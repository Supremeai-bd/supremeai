// apps/web-chat/script.js

// WebSocket Setup
// Environment Detection for Dynamic WebSocket URL
const isProd = window.location.hostname !== '127.0.0.1' && window.location.hostname !== 'localhost';
const PROTOCOL = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
const HOST = isProd ? window.location.host : '127.0.0.1:8000'; // প্রোডাকশনে অরিজিনাল হোস্ট ব্যবহার করবে
const WS_URL = `${PROTOCOL}${HOST}/ws/chat`;

let ws;
let isGenerating = false;
let currentImageBase64 = null; // নতুন স্টেট

// DOM Elements
const chatHistory = document.getElementById('chatHistory');
const chatInput = document.getElementById('chatInput');
const btnSend = document.getElementById('btnSend');

// Multi-modal UI Elements
const imageUpload = document.getElementById('imageUpload');
const btnAttach = document.getElementById('btnAttach');
const imagePreviewContainer = document.getElementById('imagePreviewContainer');
const imagePreview = document.getElementById('imagePreview');
const btnRemoveImage = document.getElementById('btnRemoveImage');

// ---------------------------------------------
// 📎 Attachment Logic
// ---------------------------------------------
btnAttach.addEventListener('click', () => imageUpload.click());

imageUpload.addEventListener('change', function(e) {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = function(event) {
        currentImageBase64 = event.target.result;
        imagePreview.src = currentImageBase64;
        imagePreviewContainer.style.display = 'block';
    };
    reader.readAsDataURL(file);
});

btnRemoveImage.addEventListener('click', clearImageAttachment);

function clearImageAttachment() {
    currentImageBase64 = null;
    imageUpload.value = '';
    imagePreviewContainer.style.display = 'none';
    imagePreview.src = '';
}

// ---------------------------------------------
// 🔌 WebSocket Logic
// ---------------------------------------------
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

        const lastMessage = chatHistory.lastElementChild;
        if (lastMessage && lastMessage.classList.contains('msg-assistant')) {
            lastMessage.textContent += data;
        } else {
            addMessage('assistant', data);
        }
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
    // Simple styling for bubbles (Assuming CSS classes exist, fallback applied)
    div.style.padding = '10px 14px';
    div.style.borderRadius = '12px';
    div.style.marginBottom = '8px';
    div.style.maxWidth = '80%';
    div.style.color = 'white';
    div.style.alignSelf = role === 'user' ? 'flex-end' : 'flex-start';
    div.style.background = role === 'user' ? '#3B82F6' : '#1F2937';
    
    chatHistory.appendChild(div);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

// 3. Handle Send
function handleSend() {
    const text = chatInput.value.trim();
    
    // Validate: Needs either text or an image
    if ((!text && !currentImageBase64) || isGenerating || !ws || ws.readyState !== WebSocket.OPEN) return;

    // UI Update
    const displayMessage = text ? text : '[📸 Image Attached]';
    addMessage('user', displayMessage);
    chatInput.value = '';
    isGenerating = true;

    // 🚀 Multi-Modal Payload Construction
    const payload = { text: text };
    if (currentImageBase64) {
        payload.image_base64 = currentImageBase64;
    }

    // Send JSON string over WS
    ws.send(JSON.stringify(payload));
    
    // Add empty bubble for incoming stream
    addMessage('assistant', ''); 
    
    // Cleanup Attachment
    clearImageAttachment();
}

// Event Listeners
btnSend.addEventListener('click', handleSend);
chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') handleSend();
});

// Make chat history a flex column for message alignment
chatHistory.style.display = 'flex';
chatHistory.style.flexDirection = 'column';

// Init
connectWebSocket();
