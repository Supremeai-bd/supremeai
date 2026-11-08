<script lang="ts">
	import { onMount } from 'svelte';
	import { user } from '$lib/stores';

	interface SupremeSkill {
		id: string;
		name: string;
		category: string;
		description: string;
		enabled: boolean;
		scope: 'repo' | 'mcp' | 'custom';
		path: string;
	}

	let skillsList: SupremeSkill[] = [
		{
			id: 'sk-1',
			name: 'browser-automation',
			category: 'Browser & Testing',
			description: 'Stealth headless web testing, scraping, and anti-detection interaction patterns.',
			enabled: true,
			scope: 'repo',
			path: '.agents/skills/browser-automation'
		},
		{
			id: 'sk-2',
			name: 'build-dashboard',
			category: 'Visual & Analytics',
			description: 'Build interactive self-contained HTML dashboards with charts, KPI cards and filters.',
			enabled: true,
			scope: 'repo',
			path: '.agents/skills/build-dashboard'
		},
		{
			id: 'sk-3',
			name: 'codebase-mapper',
			category: 'Core Engineering',
			description: 'Analyzes existing codebases to understand structure, architectural patterns, and technical debt.',
			enabled: true,
			scope: 'repo',
			path: '.agents/skills/codebase-mapper'
		},
		{
			id: 'sk-4',
			name: 'context-health-monitor',
			category: 'Agent Memory',
			description: 'Monitors context complexity and triggers state dumps before LLM token quality degrades.',
			enabled: true,
			scope: 'repo',
			path: '.agents/skills/context-health-monitor'
		},
		{
			id: 'sk-5',
			name: 'deployment-release-verification',
			category: 'CI/CD & SSOT',
			description: 'Verifies production deployment provenance, commit alignment, Redis and Supabase schema parity.',
			enabled: true,
			scope: 'repo',
			path: '.agents/skills/deployment-release-verification'
		},
		{
			id: 'sk-6',
			name: 'fastapi-pro',
			category: 'Backend Moat',
			description: 'High-performance async APIs with FastAPI, SQLAlchemy 2.0, Pydantic V2 and microservices.',
			enabled: true,
			scope: 'repo',
			path: '.agents/skills/fastapi-pro'
		},
		{
			id: 'sk-7',
			name: 'impeccable-taste-ui',
			category: 'Frontend Aesthetic',
			description: 'Impeccable taste guidelines, typographic hierarchy, dark aesthetic harmony and mathematical spacing.',
			enabled: true,
			scope: 'repo',
			path: '.agents/skills/impeccable-taste-ui'
		},
		{
			id: 'sk-8',
			name: 'mcp-tool-developer',
			category: 'MCP Protocol',
			description: 'Model Context Protocol (MCP) server & tool developer from scratch with full-stack TypeScript/Python.',
			enabled: true,
			scope: 'mcp',
			path: '.agents/skills/mcp-tool-developer'
		},
		{
			id: 'sk-9',
			name: 'platform-guardian',
			category: 'Security & Health',
			description: 'Audits SupremeAI verified 3rd party integrations for health, latency, quota and configuration drift.',
			enabled: true,
			scope: 'repo',
			path: '.agents/skills/platform-guardian'
		},
		{
			id: 'sk-10',
			name: 'supremeai-skill-author',
			category: 'Metaprogramming',
			description: 'Designs and packages reusable skills, entry-points, and runtime blueprints following AGENTS.md.',
			enabled: true,
			scope: 'repo',
			path: '.agents/skills/supremeai-skill-author'
		}
	];

	let searchQuery = '';
	let filterCategory = 'all';

	let showAddModal = false;
	let editingSkill: SupremeSkill | null = null;

	let newSkillName = '';
	let newSkillCategory = 'General';
	let newSkillDesc = '';

	$: filteredSkills = skillsList.filter(s => {
		const matchesQuery = s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
		                     s.description.toLowerCase().includes(searchQuery.toLowerCase());
		const matchesCat = filterCategory === 'all' || s.category === filterCategory;
		return matchesQuery && matchesCat;
	});

	function toggleSkill(id: string) {
		skillsList = skillsList.map(s => s.id === id ? { ...s, enabled: !s.enabled } : s);
	}

	function removeSkill(id: string) {
		if (confirm('Are you sure you want to remove this skill from the active repository pool?')) {
			skillsList = skillsList.filter(s => s.id !== id);
		}
	}

	function addNewSkill() {
		if (!newSkillName.trim()) return;
		skillsList = [
			{
				id: `sk-${Date.now()}`,
				name: newSkillName.trim().toLowerCase().replace(/\s+/g, '-'),
				category: newSkillCategory,
				description: newSkillDesc.trim() || 'Custom registered agent skill package.',
				enabled: true,
				scope: 'custom',
				path: `.agents/skills/${newSkillName.trim().toLowerCase()}`
			},
			...skillsList
		];
		newSkillName = '';
		newSkillDesc = '';
		showAddModal = false;
	}

	function saveEditSkill() {
		if (!editingSkill) return;
		skillsList = skillsList.map(s => s.id === editingSkill!.id ? editingSkill! : s);
		editingSkill = null;
	}
</script>

<svelte:head>
	<title>SupremeAI Skills & Tools SSOT</title>
</svelte:head>

<div class="h-full w-full overflow-y-auto px-4 py-6 md:px-8 bg-transparent text-gray-900 dark:text-gray-100">
	<div class="max-w-6xl mx-auto space-y-6">
		<!-- Header -->
		<div class="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-gray-200 dark:border-gray-800">
			<div class="flex items-center gap-3">
				<div class="size-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 font-bold text-lg">
					⚡
				</div>
				<div>
					<h1 class="text-2xl font-bold tracking-tight bg-gradient-to-r from-cyan-400 via-teal-300 to-blue-500 bg-clip-text text-transparent flex items-center gap-2">
						SupremeAI Agent Skills & Tools
						<span class="text-xs px-2.5 py-0.5 rounded-full font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
							{skillsList.length} Registered
						</span>
					</h1>
					<p class="text-xs text-gray-500 dark:text-gray-400">
						Authoritative SSOT repository skills from <code>.agents/skills/</code> with full Admin CRUD lifecycle
					</p>
				</div>
			</div>

			{#if $user?.role === 'admin'}
				<button
					on:click={() => showAddModal = true}
					class="px-4 py-2 text-xs font-semibold rounded-xl bg-cyan-500 hover:bg-cyan-400 text-black transition shadow-[0_0_15px_rgba(0,231,245,0.3)] flex items-center gap-2"
				>
					<span>+ Register New Skill</span>
				</button>
			{/if}
		</div>

		<!-- Filters & Search -->
		<div class="flex flex-col sm:flex-row items-center gap-3 justify-between">
			<div class="w-full sm:w-72">
				<input
					type="text"
					bind:value={searchQuery}
					placeholder="Search skills by name or description..."
					class="w-full px-3 py-2 rounded-xl bg-white/40 dark:bg-gray-900/40 border border-gray-200 dark:border-gray-800 text-xs text-gray-900 dark:text-white placeholder:text-gray-400 focus:outline-none focus:border-cyan-500"
				/>
			</div>

			<div class="text-xs text-gray-400 font-mono">
				Active Skills: <span class="text-emerald-400 font-bold">{skillsList.filter(s => s.enabled).length}</span> / {skillsList.length}
			</div>
		</div>

		<!-- Skills Grid -->
		<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
			{#each filteredSkills as skill}
				<div
					class="p-5 rounded-xl border transition backdrop-blur-md flex flex-col justify-between space-y-3 {
						skill.enabled
							? 'bg-white/40 dark:bg-gray-900/40 border-gray-200 dark:border-gray-800 hover:border-cyan-500/30'
							: 'bg-black/10 dark:bg-black/40 border-gray-200/50 dark:border-gray-800/40 opacity-60'
					}"
				>
					<div class="space-y-2">
						<div class="flex items-start justify-between gap-2">
							<div>
								<div class="flex items-center gap-2">
									<span class="size-2 rounded-full {skill.enabled ? 'bg-emerald-400' : 'bg-gray-500'}"></span>
									<h3 class="font-bold text-sm text-gray-900 dark:text-white font-mono">{skill.name}</h3>
								</div>
								<span class="text-[10px] font-mono uppercase tracking-wider text-cyan-400">{skill.category}</span>
							</div>

							<div class="flex items-center gap-1.5">
								<!-- Toggle Switch -->
								<button
									on:click={() => toggleSkill(skill.id)}
									class="px-2.5 py-1 rounded text-[11px] font-semibold transition {skill.enabled ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : 'bg-gray-700/30 text-gray-400 border border-gray-700'}"
								>
									{skill.enabled ? 'ACTIVE' : 'MUTED'}
								</button>
							</div>
						</div>

						<p class="text-xs text-gray-600 dark:text-gray-400 leading-relaxed">
							{skill.description}
						</p>

						<div class="text-[11px] font-mono text-gray-500 truncate bg-black/20 p-1.5 rounded">
							📁 {skill.path}
						</div>
					</div>

					<!-- Admin Action Controls -->
					{#if $user?.role === 'admin'}
						<div class="flex items-center justify-end gap-2 pt-2 border-t border-gray-200 dark:border-gray-800/60 text-xs">
							<button
								on:click={() => editingSkill = { ...skill }}
								class="px-3 py-1 rounded-lg border border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/10 transition"
							>
								Edit Details
							</button>
							<button
								on:click={() => removeSkill(skill.id)}
								class="px-3 py-1 rounded-lg border border-rose-500/30 text-rose-400 hover:bg-rose-500/10 transition"
							>
								Remove
							</button>
						</div>
					{/if}
				</div>
			{/each}
		</div>

		<!-- Add Skill Modal -->
		{#if showAddModal}
			<div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
				<div class="bg-gray-900 border border-gray-800 rounded-2xl p-6 max-w-md w-full shadow-2xl space-y-4">
					<h3 class="text-base font-bold text-white">Register New Skill / Tool</h3>
					<div class="space-y-3">
						<div>
							<label for="sk-name" class="block text-xs text-gray-400 mb-1">Skill Identifier / Slug</label>
							<input
								id="sk-name"
								type="text"
								bind:value={newSkillName}
								placeholder="e.g. redis-sentinel-guard"
								class="w-full px-3 py-2 rounded-lg bg-black/50 border border-gray-700 text-xs text-cyan-400 font-mono"
							/>
						</div>

						<div>
							<label for="sk-cat" class="block text-xs text-gray-400 mb-1">Category</label>
							<input
								id="sk-cat"
								type="text"
								bind:value={newSkillCategory}
								placeholder="e.g. Infrastructure & Cache"
								class="w-full px-3 py-2 rounded-lg bg-black/50 border border-gray-700 text-xs text-white"
							/>
						</div>

						<div>
							<label for="sk-desc" class="block text-xs text-gray-400 mb-1">Description & Prompt Mandate</label>
							<textarea
								id="sk-desc"
								rows="3"
								bind:value={newSkillDesc}
								placeholder="Explain what the skill does and when an agent should invoke it..."
								class="w-full px-3 py-2 rounded-lg bg-black/50 border border-gray-700 text-xs text-white resize-none"
							></textarea>
						</div>

						<div class="flex justify-end gap-2 pt-2">
							<button on:click={() => showAddModal = false} class="px-3 py-1.5 text-xs text-gray-400">Cancel</button>
							<button on:click={addNewSkill} class="px-4 py-1.5 text-xs font-semibold rounded-lg bg-cyan-500 text-black">Register Skill</button>
						</div>
					</div>
				</div>
			</div>
		{/if}

		<!-- Edit Skill Modal -->
		{#if editingSkill}
			<div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
				<div class="bg-gray-900 border border-gray-800 rounded-2xl p-6 max-w-md w-full shadow-2xl space-y-4">
					<h3 class="text-base font-bold text-white">Edit Skill Specification</h3>
					<div class="space-y-3">
						<div>
							<label for="edit-name" class="block text-xs text-gray-400 mb-1">Skill Identifier</label>
							<input
								id="edit-name"
								type="text"
								bind:value={editingSkill.name}
								class="w-full px-3 py-2 rounded-lg bg-black/50 border border-gray-700 text-xs text-cyan-400 font-mono"
							/>
						</div>

						<div>
							<label for="edit-cat" class="block text-xs text-gray-400 mb-1">Category</label>
							<input
								id="edit-cat"
								type="text"
								bind:value={editingSkill.category}
								class="w-full px-3 py-2 rounded-lg bg-black/50 border border-gray-700 text-xs text-white"
							/>
						</div>

						<div>
							<label for="edit-desc" class="block text-xs text-gray-400 mb-1">Description</label>
							<textarea
								id="edit-desc"
								rows="3"
								bind:value={editingSkill.description}
								class="w-full px-3 py-2 rounded-lg bg-black/50 border border-gray-700 text-xs text-white resize-none"
							></textarea>
						</div>

						<div class="flex justify-end gap-2 pt-2">
							<button on:click={() => editingSkill = null} class="px-3 py-1.5 text-xs text-gray-400">Cancel</button>
							<button on:click={saveEditSkill} class="px-4 py-1.5 text-xs font-semibold rounded-lg bg-cyan-500 text-black">Save Changes</button>
						</div>
					</div>
				</div>
			</div>
		{/if}
	</div>
</div>

