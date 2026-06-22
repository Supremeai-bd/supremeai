import type { AdminSubTab } from '../../types';
import { BanglaHint } from '../BanglaHint';

interface TabBarProps {
  adminSubTab: AdminSubTab;
  setAdminSubTab: (tab: AdminSubTab) => void;
}

export function TabBar({ adminSubTab, setAdminSubTab }: TabBarProps) {
  const tabs: { id: AdminSubTab; label: string; hint: string }[] = [
    { id: 'command-center', label: 'Command Center', hint: 'সিস্টেমের সার্বিক অবস্থা ও অ্যাকশনসমূহ পরিচালনার মূল কেন্দ্র।' },
    { id: 'sandbox', label: 'Orchestrator Sandbox', hint: 'সরাসরি কমান্ড রান ও কনস্টিটিউশনাল রুলস টেস্ট করার স্যান্ডবক্স।' },
    { id: 'logs', label: 'Real-time Logs', hint: 'রিয়েল-টাইম সিস্টেমের অ্যাক্টিভিটি এবং সার্ভার লগ ভিউয়ার।' },
    { id: 'costs', label: 'Cost Auditor', hint: 'সিস্টেম ও প্রোভাইডার ভিত্তিক খরচ বা কস্ট অডিটর।' },
    { id: 'health', label: 'Provider Map', hint: 'ক্লাউড এবং থার্ড-পার্টি এপিআই প্রোভাইডার ম্যাপ।' },
    { id: 'users', label: 'User Manager', hint: 'অ্যাডমিন এবং অপারেটর ইউজার অ্যাকাউন্ট ও পারমিশন কন্ট্রোল।' },
    { id: 'config', label: 'Config Editor', hint: 'এনভায়রনমেন্ট কনফিগারেশন এবং সিস্টেম ভেরিয়েবল এডিটর।' },
    { id: 'model-router', label: 'Model Router', hint: 'এআই মডেল এবং রাউটিং রুলস ম্যানেজমেন্ট।' },
    { id: 'skills', label: 'Skills', hint: 'পদ্ধতিগত কাজের জন্য প্রাক-নির্মিত এআই স্কিল কালেকশন।' },
    { id: 'memory', label: 'Memory', hint: 'এজেন্টদের ইন্টারনাল মেমোরি ও প্রসঙ্গ ডাটা ব্রাউজার।' },
    { id: 'cloud', label: 'Cloud', hint: 'গুগল ক্লাউড প্ল্যাটফর্ম অরকেস্ট্রেশন ও রিসোর্স ম্যানেজমেন্ট।' },
    { id: 'observability', label: 'Observability', hint: 'রিয়েল-টাইম পারফরম্যান্স এবং লেটেন্সি মনিটরিং ড্যাশবোর্ড।' },
    { id: 'threats', label: 'Threats', hint: 'সিকিউরিটি এবং সম্ভাব্য আক্রমণ শনাক্তকরণ থ্রেট ডিটেকশন।' },
    { id: 'rules', label: 'Rules', hint: 'ভিজুয়াল কনস্টিটিউশনাল পলিসি এবং ফিল্টারিং রুলস বিল্ডার।' },
    { id: 'cicd', label: 'CI/CD', hint: 'সিআই/সিডি পাইপলাইন স্ট্যাটাস এবং ডিপ্লয়মেন্ট ভিজুয়ালাইজার।' },
    { id: 'github', label: 'GitHub', hint: 'গিটহাব রেপো ইন্টিগ্রেশন এবং পিআর স্ট্যাটাস ট্র্যাকার।' },
    { id: 'backups', label: 'Backups', hint: 'ডাটাবেস ব্যাকআপ এবং মেমোরি পয়েন্ট রিস্টোরেশন ম্যানেজার।' },
    { id: 'rate-limits', label: '🛡️ Rate Limits', hint: 'প্রতিটি টেন্যান্টের API রেট লিমিট ও বিলিং টায়ার ম্যানেজমেন্ট।' },
  ];
  
  return (
    <div className="h-10 bg-[var(--tabbar-bg)] border-b border-[var(--border-color)] flex items-center justify-between px-4 overflow-x-auto">
      <div className="flex gap-2 items-center">
        {tabs.map(tab => (
          <div key={tab.id} className="flex items-center gap-1">
            <TabButton
              active={adminSubTab === tab.id}
              onClick={() => setAdminSubTab(tab.id)}
            >
              {tab.label}
            </TabButton>
            <BanglaHint text={tab.hint} />
          </div>
        ))}
      </div>
    </div>
  );
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1 text-xs font-semibold rounded font-mono transition-colors whitespace-nowrap ${
        active ? 'bg-[#00f3ff]/20 text-[#00f3ff]' : 'text-slate-400 hover:text-[var(--foreground)]'
      }`}
    >
      {children}
    </button>
  );
}