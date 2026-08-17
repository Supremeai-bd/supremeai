import React from 'react';

export interface SupremeCardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  glow?: boolean;
  blur?: boolean;
}

/**
 * SupremeCard — অ্যাপজুড়ে ব্যবহৃত গ্লাসমরফিজম স্টাইলের কার্ড কম্পোনেন্ট।
 *
 * glow: সক্রিয় করলে ব্র্যান্ড রঙের আভা (glow) যুক্ত হয় এবং হোভারে তা বৃদ্ধি পায়।
 * blur: পেছনের কনটেন্টে ঝাপসা (backdrop blur) প্রভাব দেয়, ডিফল্টে চালু।
 */
export const SupremeCard: React.FC<SupremeCardProps> = ({
  children,
  glow = false,
  blur = true,
  className = '',
  ...props
}) => {
  // স্টাইলগুলো আলাদা ভাগে রাখা হয়েছে যাতে প্রতিটি প্রপের প্রভাব স্পষ্ট বোঝা যায়।
  // রঙ ও অ্যানিমেশনের মান CSS ভেরিয়েবল থেকে নেওয়া হয়, ফলে থিম পরিবর্তন করলে
  // এই কম্পোনেন্ট নিজে থেকেই সেই অনুযায়ী পরিবর্তিত হয়।
  const baseStyle = "rounded-3xl border border-border-accent bg-card-bg transition-all";
  const motionStyle = "duration-[var(--supremeai-motion-duration-normal)] ease-[var(--supremeai-motion-easing-bounce)]";
  const glowStyle = glow ? "shadow-[0_0_15px_var(--supremeai-color-brand-primary-dark)] hover:shadow-[0_0_25px_var(--supremeai-color-brand-primary-dark)]" : "shadow-xl";
  const blurStyle = blur ? "backdrop-blur-xl" : "";

  return (
    <div
      // className সবার শেষে যুক্ত করা হয়েছে, যাতে বাইরে থেকে পাঠানো ক্লাস
      // প্রয়োজনে ডিফল্ট স্টাইল ওভাররাইড করতে পারে
      className={`${baseStyle} ${motionStyle} ${glowStyle} ${blurStyle} p-6 ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};
