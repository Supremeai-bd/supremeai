// ============================================================================
// component >> Card.tsx
// project >> SupremeAI 2.0
// purpose >> General utility
// module >> src
// ============================================================================
import { BanglaHint } from '../BanglaHint';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  title?: string;
  icon?: React.ReactNode;
  banglaHint?: string;
}

export function Card({ children, className = '', title, icon, banglaHint }: CardProps) {
  return (
    <div className={`bg-[var(--card-bg)] backdrop-blur-md border border-[var(--card-border)] rounded-xl p-5 shadow-[0_4px_20px_rgba(0,243,255,0.05)] hover:border-[#00f3ff]/30 dark:hover:border-[#00f3ff]/30 transition-all duration-300 text-[var(--foreground)] ${className}`}>
      {(title || icon || banglaHint) && (
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            {title && <span className="font-bold tracking-wider text-sm text-[var(--card-title-text)]">{title}</span>}
            {banglaHint && <BanglaHint text={banglaHint} />}
          </div>
          {icon && <span className="text-[#00f3ff]">{icon}</span>}
        </div>
      )}
      {children}
    </div>
  );
}

