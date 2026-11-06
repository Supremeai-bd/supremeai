export interface PreviewTemplate {
  id: string;
  nameEn: string;
  nameBn?: string;
  description?: string;
  html: string;
}

const baseShell = (title: string, accent: string, body: string) => `<!doctype html>
<html lang="en">
  <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><script src="https://cdn.tailwindcss.com"></script></head>
  <body class="min-h-screen bg-slate-950 text-white"><main class="mx-auto max-w-5xl p-8"><div class="rounded-3xl border border-white/10 bg-white/5 p-8 shadow-2xl"><p class="mb-3 text-sm uppercase tracking-[0.3em] text-${accent}-300">SupremeAI preview</p><h1 class="text-4xl font-bold">${title}</h1>${body}</div></main></body>
</html>`;

export const PREVIEW_TEMPLATES: PreviewTemplate[] = [
  {
    id: 'food-delivery',
    nameEn: 'Hot Bowl Delivery',
    description: 'Restaurant and food-delivery landing page.',
    html: baseShell('Order your next favorite meal', 'emerald', '<p class="mt-4 text-slate-300">Fast delivery, fresh ingredients, and a seamless checkout experience.</p><button class="mt-8 rounded-xl bg-emerald-500 px-5 py-3 font-semibold">Order Hot Bowl Now</button>'),
  },
  {
    id: 'saas-glassmorphism',
    nameEn: 'SaaS Glassmorphism',
    description: 'Modern SaaS product landing page.',
    html: baseShell('Operate every workflow from one command center', 'cyan', '<p class="mt-4 text-slate-300">Live metrics, model routing, and secure team collaboration in one place.</p><button class="mt-8 rounded-xl bg-cyan-400 px-5 py-3 font-semibold text-slate-950">Start building</button>'),
  },
  {
    id: 'fintech-analytics',
    nameEn: 'Fintech Analytics',
    description: 'Financial analytics dashboard preview.',
    html: baseShell('Realtime portfolio intelligence', 'violet', '<p class="mt-4 text-slate-300">Track liquidity, risk, and performance with a calm operational surface.</p><div class="mt-8 grid grid-cols-3 gap-3"><div class="rounded-xl bg-violet-500/20 p-4">+18.4%</div><div class="rounded-xl bg-white/10 p-4">$84.2k</div><div class="rounded-xl bg-white/10 p-4">Low risk</div></div>'),
  },
  {
    id: 'kanban-workflow',
    nameEn: 'Kanban Workflow',
    description: 'Agile workflow board preview.',
    html: baseShell('Ship work with less coordination overhead', 'amber', '<div class="mt-8 grid grid-cols-3 gap-3"><div class="rounded-xl bg-white/10 p-4">Backlog</div><div class="rounded-xl bg-white/10 p-4">In progress</div><div class="rounded-xl bg-white/10 p-4">Done</div></div>'),
  },
];
