import React from 'react';

export interface ChatBubbleProps {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
}

/**
 * ChatBubble — কথোপকথনের একটি বার্তা বুদবুদ আকারে প্রদর্শন করে।
 * role অনুযায়ী CSS ক্লাস বদলায়, ফলে ইউজার ও অ্যাসিস্ট্যান্টের বার্তা
 * দুই পাশে আলাদাভাবে দেখানো যায়।
 */
export const ChatBubble: React.FC<ChatBubbleProps> = ({ role, content, timestamp }) => {
  const isUser = role === 'user';
  // ব্যবহারকারীর লোকেল অনুযায়ী কেবল ঘণ্টা ও মিনিট দেখানো হয় (তারিখ বাদ),
  // কারণ চ্যাট তালিকায় সম্পূর্ণ টাইমস্ট্যাম্প অপ্রয়োজনীয়ভাবে জায়গা নেয়
  const timeStr = timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  return (
    <div className={`message ${role}`}>
      <div className="msg-bubble">{content}</div>
      <div className="msg-info">{isUser ? 'Admin' : 'SupremeAI'} • {timeStr}</div>
    </div>
  );
};
