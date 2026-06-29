// apps/web-chat/script.js
import { api } from './api.js';

// State Management
const state = {
    messages: [
        { role: 'assistant', content: 'স্বাগতম! আমি আপনার পার্সোনাল এআই অ্যাসিস্ট্যান্ট। আমাকে যেকোনো টাস্ক বা নির্দেশ দিন।' }
    ],
    language: 'bn',
    theme: 'dark',
    activeSkill: null,
    loading: false
};

// DOM Elements
const chatHistory = document.getElementById('chatHistory');
const chatInput = document.getElementById('chatInput');
const btnSend = document.getElementById('btnSend');
const btnTheme = document.getElementById('btnTheme');
const btnLang = document.getElementById('btnLang');
const nodes = document.querySelectorAll('.floating-node, .central-core');

// 1. Initial Render
function renderMessages() {
    chatHistory.innerHTML = '';
    state.messages.forEach(msg => {
        const div = document.createElement('div');
        div.className = `msg msg-${msg.role}`;
        div.textContent = msg.content;
        chatHistory.appendChild(div);
    });
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

// 2. Handle Sending Message
async function handleSend(text = null) {
    const userText = text || chatInput.value.trim();
    if (!userText || state.loading) return;

    // Add user message
    chatInput.value = '';
    state.messages.push({ role: 'user', content: userText });
    renderMessages();

    // Add Loading UI
    state.loading = true;
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'msg msg-assistant';
    loadingDiv.textContent = state.language === 'bn' ? 'প্রসেস করা হচ্ছে...' : 'Thinking...';
    chatHistory.appendChild(loadingDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;

    // Call API (Sending Context/History!)
    const response = await api.executeTask(userText, state.messages);
    
    // Remove Loading & Add Response
    chatHistory.removeChild(loadingDiv);
    state.messages.push({ 
        role: 'assistant', 
        content: response.result || (state.language === 'bn' ? 'সার্ভার এরর।' : 'Server Error.')
    });
    
    state.loading = false;
    renderMessages();
}

// 3. Event Listeners
btnSend.addEventListener('click', () => handleSend());
chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') handleSend();
});

// Theme Toggle
btnTheme.addEventListener('click', () => {
    state.theme = state.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', state.theme);
    btnTheme.innerHTML = `⚙️ ${state.theme.toUpperCase()} THEME`;
});

// Language Toggle
btnLang.addEventListener('click', () => {
    state.language = state.language === 'bn' ? 'en' : 'bn';
    btnLang.innerHTML = `🛍️ LANG: ${state.language === 'bn' ? 'বাংলা' : 'ENGLISH'}`;
});

// Node Selection
nodes.forEach(node => {
    node.addEventListener('click', (e) => {
        const skill = e.currentTarget.getAttribute('data-skill') || 'Assistant Core';
        state.activeSkill = skill;
        chatInput.value = `Activate ${skill} task: `;
        chatInput.focus();
    });
});

// Init
renderMessages();
