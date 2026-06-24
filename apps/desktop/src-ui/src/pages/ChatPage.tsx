import React, { useState, useEffect } from "react";
import ChatInput from "../components/ChatInput";

const ChatPage: React.FC = () => {
  const [messages, setMessages] = useState<Array<{id: number; text: string; isUser: boolean}>>([]);
  const [inputValue, setInputValue] = useState("");

  const addMessage = (text: string, isUser: boolean) => {
    const newMessage = {
      id: Date.now(),
      text,
      isUser
    };
    setMessages(prev => [...prev, newMessage]);
  };

  const handleSendMessage = async (message: string) => {
    // Add user message
    addMessage(message, true);
    
    // Simulate AI response (in real app, this would come from API)
    setTimeout(() => {
      addMessage("This is a simulated AI response. In the full implementation, this would connect to the SupremeAI backend.", false);
    }, 1000);
  };

  return (
    <div className="chat-page">
      <div className="chat-messages">
        {messages.map(msg => (
          <div key={msg.id} className={`message ${msg.isUser ? "user-message" : "ai-message"}`}>
            {msg.text}
          </div>
        ))}
      </div>
      <ChatInput onMessageSent={handleSendMessage} />
    </div>
  );
};

export default ChatPage;

