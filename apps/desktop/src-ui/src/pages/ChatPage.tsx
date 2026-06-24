import React, { useState, useEffect } from "react";
import ChatInput from "../components/ChatInput";
import { supremeApi } from "../services/api";

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
    
    try {
      // Call the API
      const response = await supremeApi.sendMessage(message);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      // Assuming the API returns { response: "AI message" }
      const aiMessage = data.response || "Sorry, I couldn't process that.";
      // Add AI response
      addMessage(aiMessage, false);
    } catch (error) {
      console.error('Error sending message:', error);
      addMessage("Sorry, there was an error processing your request.", false);
    }
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