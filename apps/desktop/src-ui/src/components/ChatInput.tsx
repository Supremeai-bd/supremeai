import React, { useState } from "react";

interface ChatInputProps {
  onMessageSent: (message: string) => void;
  disabled?: boolean;
}

const ChatInput: React.FC<ChatInputProps> = ({ onMessageSent, disabled = false }) => {
  const [message, setMessage] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim()) return;

    onMessageSent(message.trim());
    setMessage("");
  };

  return (
    <form onSubmit={handleSubmit} className="chat-input">
      <div className="input-group">
        <input
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Type your message here..."
          disabled={disabled}
        />
        <button type="submit" disabled={disabled || !message.trim()}>
          Send
        </button>
      </div>
    </form>
  );
};

export default ChatInput;

