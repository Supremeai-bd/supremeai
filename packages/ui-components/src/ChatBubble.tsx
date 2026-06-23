// ============================================================================
// component >> ChatBubble.tsx
// project >> SupremeAI 2.0
// purpose >> Chat interface
// module >> packages
// ============================================================================
export interface ChatBubbleProps {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
}

export const ChatBubble: React.FC<ChatBubbleProps> = ({ role, content, timestamp }) => {
  const isUser = role === 'user';
  const timeStr = timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  return (
    <div className={`message ${role}`}>
      <div className="msg-bubble">{content}</div>
      <div className="msg-info">{isUser ? 'Admin' : 'SupremeAI'} • {timeStr}</div>
    </div>
  );
};
