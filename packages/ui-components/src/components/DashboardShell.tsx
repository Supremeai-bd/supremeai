import React from 'react';
import './styles.css';
import { LiveSujonBackground } from './LiveSujonBackground';

/**
 * DashboardShell — ড্যাশবোর্ড পেজগুলোর সাধারণ কাঠামো (সাইডবার + মূল অংশ)।
 *
 * অ্যানিমেটেড ব্যাকগ্রাউন্ডটি পেছনে থাকে, তাই সাইডবার ও মূল কনটেন্টে
 * `relative z-10` দেওয়া হয়েছে যেন সেগুলো ব্যাকগ্রাউন্ডের ওপরে দৃশ্যমান থাকে।
 */
export function DashboardShell({ children, isServerOnline = false }: any) {
  return (
    <div className="relative min-h-screen flex bg-[#0b0f19] text-white">
      <LiveSujonBackground />
      <aside className="relative z-10 w-56 shrink-0 border-r border-white/[0.06] bg-[#080b13] flex flex-col">
        <div className="flex items-center gap-2 px-4 py-4 border-b border-white/[0.06]">
          <span className="text-blue-400 text-lg">▲</span>
          <h1 className="text-sm font-semibold tracking-wide m-0">SupremeAI</h1>
        </div>
      </aside>
      {/* min-w-0 জরুরি: এটি ছাড়া ফ্লেক্স আইটেমের ভেতরের বড় কনটেন্ট
          সংকুচিত হতে না পেরে পুরো লেআউট ভেঙে দিতে পারে */}
      <main data-testid="dashboard-main" className="relative z-10 flex-1 min-w-0 overflow-y-auto flex flex-col">
        {children}
      </main>
    </div>
  );
}
