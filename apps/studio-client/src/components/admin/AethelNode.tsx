import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';
import { motion, AnimatePresence } from 'framer-motion';
import './AethelCoreStyles.css';

interface AethelNodeProps {
  data: {
    label: string | React.ReactNode;
    status?: 'Nominal' | 'Warning' | 'Critical';
    type?: 'orb' | 'swarm' | 'mesh' | 'firewall' | 'evolution' | 'gateway' | 'memory' | 'cicd';
  };
  isConnectable: boolean;
}

// বাংলা মন্তব্য: কাস্টম এথেল নোড কম্পোনেন্ট ফ্রেমার মোশন দিয়ে আরও স্মুথ করা হলো।
const AethelNode = ({ data, isConnectable }: AethelNodeProps) => {
  const [isHovered, setIsHovered] = React.useState(false);

  const getGlowClass = (type?: string) => {
    switch (type) {
      case 'swarm': return 'glow-cyan';
      case 'mesh': return 'glow-green';
      case 'firewall': return 'glow-gold';
      case 'evolution': return 'glow-cyan';
      case 'gateway': return 'glow-cyan';
      case 'memory': return 'glow-gold';
      case 'cicd': return 'glow-green';
      default: return 'glow-cyan';
    }
  };

  return (
    <motion.div 
      initial={{ scale: 0.8, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      whileHover={{ scale: 1.05 }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className={`aethel-node ${getGlowClass(data.type)} group relative`}
    >
      <Handle type="target" position={Position.Left} isConnectable={isConnectable} className="!bg-[#00f3ff] !w-2 !h-2 !border-none" />
      
      {/* Holographic Tooltip using Framer Motion */}
      <AnimatePresence>
        {isHovered && (
          <motion.div 
            initial={{ opacity: 0, y: 10, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.9 }}
            transition={{ duration: 0.2 }}
            className="absolute -top-12 left-1/2 -translate-x-1/2 z-50 pointer-events-none"
          >
            <div className="bg-[#050917]/90 border border-[#00f3ff]/40 text-[#00f3ff] text-[9px] px-3 py-1.5 rounded backdrop-blur-md whitespace-nowrap shadow-[0_0_10px_rgba(0,243,255,0.2)] font-mono">
               Holographic Hint: {data.status || 'Active Node'}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      
      <div className="flex flex-col items-start justify-center">
        {data.label}
      </div>
      
      <Handle type="source" position={Position.Right} isConnectable={isConnectable} className="!bg-[#00f3ff] !w-2 !h-2 !border-none" />
    </motion.div>
  );
};

export default memo(AethelNode);
