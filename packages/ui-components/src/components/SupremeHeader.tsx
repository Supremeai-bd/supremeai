import React from 'react';

export interface SupremeHeaderProps extends React.HTMLAttributes<HTMLHeadingElement> {
  children: React.ReactNode;
  subtitle?: React.ReactNode;
  gradient?: boolean;
}

/**
 * SupremeHeader — পেজের শিরোনাম ও ঐচ্ছিক উপশিরোনাম দেখানোর কম্পোনেন্ট।
 * gradient সক্রিয় করলে শিরোনামে ব্র্যান্ড গ্রেডিয়েন্ট রঙ প্রয়োগ হয়।
 */
export const SupremeHeader: React.FC<SupremeHeaderProps> = ({
  children,
  subtitle,
  gradient = false,
  className = '',
  ...props
}) => {
  // গ্রেডিয়েন্ট টেক্সট তৈরির কৌশল: ব্যাকগ্রাউন্ডে গ্রেডিয়েন্ট বসিয়ে সেটিকে
  // টেক্সটের আকারে ক্লিপ করা হয় এবং লেখার নিজস্ব রঙ স্বচ্ছ রাখা হয়।
  const titleColor = gradient
    ? "bg-gradient-to-r from-accent-primary to-neon-purple bg-clip-text text-transparent"
    : "text-foreground";

  return (
    <div className={`mb-6 ${className}`}>
      <h1 className={`text-2xl md:text-3xl font-bold tracking-tight ${titleColor}`} {...props}>
        {children}
      </h1>
      {subtitle && (
        <p className="mt-2 text-sm text-text-secondary font-mono tracking-wide">
          {subtitle}
        </p>
      )}
    </div>
  );
};
