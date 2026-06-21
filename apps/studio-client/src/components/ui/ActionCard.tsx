import React from 'react';

interface ActionCardProps {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  variant?: 'default' | 'primary' | 'danger' | 'success' | 'warning';
  disabled?: boolean;
  onClick?: () => void;
  children?: React.ReactNode;
  className?: string;
}

export function ActionCard({
  title,
  description,
  icon,
  variant = 'default',
  disabled = false,
  onClick,
  children,
  className = ''
}: ActionCardProps) {
  const baseStyles = 'p-4 rounded-xl border transition-all duration-200 cursor-pointer';
  const variants: Record<string, string> = {
    default: 'border-slate-800 bg-slate-900/30 hover:border-[#00f3ff]/30 hover:bg-[#00f3ff]/5',
    primary: 'border-[#00f3ff]/30 bg-[#00f3ff]/10 hover:border-[#00f3ff]/50 hover:bg-[#00f3ff]/15',
    danger: 'border-red-900/30 bg-red-950/20 hover:border-red-900/50 hover:bg-red-950/30',
    success: 'border-emerald-900/30 bg-emerald-950/20 hover:border-emerald-900/50 hover:bg-emerald-950/30',
    warning: 'border-yellow-900/30 bg-yellow-950/20 hover:border-yellow-900/50 hover:bg-yellow-950/30',
  };

  return (
    <div
      onClick={onClick}
      className={`${baseStyles} ${variants[variant]} ${disabled ? 'opacity-50 cursor-not-allowed' : ''} ${className}`}
    >
      <div className="flex items-start gap-3">
        {icon && <span className="text-[#00f3ff] mt-0.5">{icon}</span>}
        <div className="flex-1 min-w-0">
          <h3 className="text-xs font-bold text-white font-mono truncate">{title}</h3>
          {description && <p className="text-[10px] text-slate-400 mt-1 line-clamp-2">{description}</p>}
          {children}
        </div>
      </div>
    </div>
  );
}
