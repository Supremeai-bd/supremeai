// SupremeAI — WorkspaceLayout (single-frontend migration, roadmap Phase 3)
// বাংলা মন্তব্য: User context এখন UnifiedAppShell-এর ভেতরে রেন্ডার হয়। শুধুমাত্র
// user-specific business অংশ (DnD dock, HITL modal) এখানে থাকে — shell/header/nav
// infra unified shell থেকে আসে। পুরোনো NAV_GROUPS + UserSidebar navigationRegistry.ts-
// তে সরানো হয়েছে (একক nav registry; এখানে দ্বিতীয় definition নেই)।

import { useEffect } from 'react';
import { Smartphone } from 'lucide-react';
import { UnifiedAppShell } from '../shell/UnifiedAppShell';
import { CommandBar } from './CommandBar';
import { MobilePreviewPanel } from '../common/MobilePreviewPanel';
import { useMobilePreview, setupMobilePreviewKeyboard } from '../../hooks/useMobilePreview';
import { LiveBackground } from '../visual/LiveBackground';

/**
 * Keep the default viewer shell boring and predictable. Feature-specific docks,
 * drag/drop, and approval UI belong inside the feature that explicitly needs it;
 * they must not be mounted for every read-only page.
 *
 * #4148: Mobile preview panel (floating overlay) + Ctrl+M keyboard shortcut.
 */
export function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  const { isOpen, toggle } = useMobilePreview();

  // Setup keyboard shortcut (Ctrl+M)
  useEffect(() => {
    setupMobilePreviewKeyboard();
  }, []);

  return (
    <UnifiedAppShell context="user">
      {/* (#4138 Phase 1): কর্মক্ষেত্রের পেছনে ফিকে জীবন্ত স্তর — workspace-ভ্যারিয়েন্ট
          (শুধু দুটি ধীর অরব, কণা নেই) যাতে ঘন ড্যাশবোর্ডের পাঠযোগ্যতা অটুট থাকে। */}
      <LiveBackground variant="workspace" />
      <main className="relative flex min-h-0 flex-1 flex-col overflow-y-auto">
        {children}
      </main>
      {/* RESTORE-AND-WIRE (2026-09-14): universal Ctrl+K command palette restored.
          Hidden until the hotkey is pressed, so the default shell stays boring
          and predictable per the FRONTEND_SIMPLICITY contract. */}
      <CommandBar />

      {/* #4148: Mobile Preview floating toggle button */}
      <button
        onClick={toggle}
        title="Toggle Mobile Preview (Ctrl+M)"
        className={`fixed bottom-4 right-4 z-40 rounded-full p-3 shadow-lg transition-all duration-300 ${
          isOpen
            ? 'bg-cyan-600 hover:bg-cyan-700'
            : 'bg-slate-800 hover:bg-slate-700'
        }`}
      >
        <Smartphone className="h-5 w-5 text-white" />
      </button>

      {/* #4148: Mobile Preview floating panel overlay */}
      <MobilePreviewPanel url={typeof window !== 'undefined' ? window.location.href : ''} />
    </UnifiedAppShell>
  );
}
