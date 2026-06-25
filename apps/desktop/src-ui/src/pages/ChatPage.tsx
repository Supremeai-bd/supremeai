import React, { useState } from "react";
import ChatInput from "../components/ChatInput";
import { supremeApi, ApiError } from "../services/api";

const ChatPage: React.FC = () => {
  const [messages, setMessages] = useState<
    Array<{ id: number; text: string; isUser: boolean; error?: boolean }>
  >([]);
  const [isLoading, setIsLoading] = useState(false);

  const addMessage = (
    text: string,
    isUser: boolean,
    error = false
  ) => {
    const newMessage = {
      id: Date.now(),
      text,
      isUser,
      error,
    };
    setMessages((prev) => [...prev, newMessage]);
  };

  const handleSendMessage = async (message: string) => {
    addMessage(message, true);
    setIsLoading(true);

    try {
      const data = await supremeApi.sendMessage(message);
      addMessage(data.response || "Sorry, I couldn't process that.", false);
    } catch (error) {
      console.error("Error sending message:", error);
      const errorMessage =
        error instanceof ApiError
          ? `${error.message}${error.status !== 500 ? ` (${error.status})` : ""}`
          : "Sorry, there was an error processing your request.";
      addMessage(errorMessage, false, true);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="chat-page">
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <h2>Welcome to SupremeAI</h2>
            <p>Start a conversation by typing a message below.</p>
          </div>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`message ${msg.isUser ? "user-message" : "ai-message"} ${msg.error ? "error" : ""}`}
          >
            {msg.text}
          </div>
        ))}
        {isLoading && (
          <div className="message ai-message loading">
            <span className="typing-indicator">
              <span />
              <span />
              <span />
            </span>
          </div>
        )}
      </div>
      <ChatInput onMessageSent={handleSendMessage} disabled={isLoading} />
    </div>
  );
};

export default ChatPage;