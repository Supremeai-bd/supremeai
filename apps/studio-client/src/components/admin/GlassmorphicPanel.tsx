import React from 'react';
import { motion } from 'framer-motion';
import './AethelCoreStyles.css';

interface GlassmorphicPanelProps {
  children: React.ReactNode;
  title: string;
  icon?: React.ReactNode;
  subtitle?: string;
  className?: string;
}

// বাংলা মন্তব্য: সায়েন্স-ফিকশন গ্লাসমরফিক প্যানেল კომპোনেন্ট ফ্রেমার মোশন সহ
export const GlassmorphicPanel: React.FC<GlassmorphicPanelProps> = ({ children, title, icon, subtitle, className = '' }) => {
  return (
    <motion.div 
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className={`glass-panel rounded-2xl p-4 flex flex-col border border-[#00f3ff]/20 ${className}`}
    >
      <div className="border-b border-[#00f3ff]/15 pb-2 mb-3">
        <h3 className="text-xs font-black font-mono text-[#00f3ff] tracking-widest uppercase flex items-center gap-2">
          {icon}
          {title}
        </h3>
        {subtitle && (
          <span className="text-[9px] text-slate-500 font-mono">// {subtitle}</span>
        )}
      </div>
      <div className="flex-1 overflow-y-auto pr-1">
        {children}
      </div>
    </motion.div>
  );
};
