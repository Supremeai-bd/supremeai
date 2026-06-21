import React from 'react';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  title?: string;
  icon?: React.ReactNode;
}

export function Card({ children, className = '', title, icon }: CardProps) {
  return (
    <div className={`bg-[#080b11]/80 backdrop-blur-md border border-[#00f3ff]/10 rounded-xl p-5 shadow-[0_4px_20px_rgba(0,243,255,0.05)] hover:border-[#00f3ff]/30 transition-all duration-300 ${className}`}>
      {(title || icon) && (
        <div className="flex items-center justify-between mb-4">
          {title && <span className="font-bold tracking-wider text-sm text-slate-200">{title}</span>}
          {icon && <span className="text-[#00f3ff]">{icon}</span>}
        </div>
      )}
      {children}
    </div>
  );
}
