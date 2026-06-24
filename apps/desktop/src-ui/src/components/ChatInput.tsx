import React, { useState } from "react";
import { supremeApi } from "../services/api";

interface ChatInputProps {
  onMessageSent: (message: string) => void;
}

const ChatInput: React.FC<ChatInputProps> = ({ onMessageSent }) => {
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim()) return;

    setIsLoading(true);
    try {
      await supremeApi.sendMessage(message);
      onMessageSent(message);
      setMessage("");
    } catch (error) {
      console.error("Failed to send message:", error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="chat-input">
      <div className="input-group">
        <input
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Type your message here..."
          disabled={isLoading}
        />
        <button type="submit" disabled={isLoading}>
          {isLoading ? "Sending..." : "Send"}
        </button>
      </div>
    </form>
  );
};

export default ChatInput;

