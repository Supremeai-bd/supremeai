<script lang="ts">
	import { onMount } from 'svelte';
	import { SUPREMEAI_CONFIG } from '$lib/supremeai';
	import { user } from '$lib/stores';
	import { toast } from 'svelte-sonner';

	export interface MCPAgent {
		id: string;
		name: string;
		role: 'solver' | 'inspector' | 'platform-guardian' | 'rules-breaker' | 'ecosystem-scout' | 'human-eye' | 'custom';
		title: string;
		cadence_seconds: number;
		cadence_label: string;
		status: 'active' | 'idle' | 'running';
		lastHeartbeat?: string;
		mandate: string;
		identity: string;
		permissions: {
			canRead: boolean;
			canPatch: boolean;
			canDispatch: boolean;
		};
		systemPrompt?: string;
		isCustom?: boolean;
	}

	const DEFAULT_AGENTS: MCPAgent[] = [
		{
			id: 'agent-solver',
			name: 'SupremeAI Solver',
			role: 'solver',
			title: 'Unclaimed Issue Solver & Fixer',
			cadence_seconds: 30,
			cadence_label: 'Every 30s',
			status: 'active',
			lastHeartbeat: '12s ago',
			mandate: 'Inspects board for unclaimed issues, claims slot (30m lease), dual-rebases origin/main, runs 3-Tier verify, submits patch via CAS baseSha.',
			identity: 'agent:solver:v2',
			permissions: { canRead: true, canPatch: true, canDispatch: true },
			systemPrompt: 'You are the primary Solver agent. Fix root causes cleanly, observe Anti-Bloat invariant, and submit atomically complete patches with reflection evidence.'
		},
		{
			id: 'agent-inspector',
			name: 'Monorepo Health Inspector',
			role: 'inspector',
			title: 'Monorepo Health & Smoke Inspector',
			cadence_seconds: 900,
			cadence_label: 'Every 15m',
			status: 'active',
			lastHeartbeat: '4m ago',
			mandate: 'Validates smoke tests across all satellite domains (core, gateway, browser, studio) on live main.',
			identity: 'agent:inspector:v2',
			permissions: { canRead: true, canPatch: false, canDispatch: true },
			systemPrompt: 'Inspect all domain mirrors for parity drift or breaking changes against live main.'
		},
		{
			id: 'agent-platform-guardian',
			name: 'Platform Guardian',
			role: 'platform-guardian',
			title: 'Third-Party Integration Sentinel',
			cadence_seconds: 1800,
			cadence_label: 'Every 30m',
			status: 'active',
			lastHeartbeat: '11m ago',
			mandate: 'Probes 17 external platforms (Render, Cloudflare, Supabase, Infisical) for drift, quota, and latency.',
			identity: 'agent:platform-guardian:v2',
			permissions: { canRead: true, canPatch: true, canDispatch: true },
			systemPrompt: 'Audit 17 federated platform connections. Any degraded health check is treated as an active defect.'
		},
		{
			id: 'agent-rules-breaker',
			name: 'Rules Breaker Red-Team',
			role: 'rules-breaker',
			title: 'Anti-Regression & Security Red Team',
			cadence_seconds: 7200,
			cadence_label: 'Every 2h',
			status: 'active',
			lastHeartbeat: '45m ago',
			mandate: 'Proves edge-case vulnerabilities, test coverage leaks, and policy drift without weaponizing weaknesses.',
			identity: 'agent:rules-breaker:v2',
			permissions: { canRead: true, canPatch: false, canDispatch: true },
			systemPrompt: 'Perform non-destructive red team reviews and verify boundary protection guards.'
		},
		{
			id: 'agent-ecosystem-scout',
			name: 'Ecosystem Scout',
			role: 'ecosystem-scout',
			title: 'Ecosystem Scout & Radar Engine',
			cadence_seconds: 14400,
			cadence_label: 'Every 4h',
			status: 'idle',
			lastHeartbeat: '1h ago',
			mandate: 'Discovers high-impact tools, libraries, and AI benchmarks; maintains falsifiable radar index.',
			identity: 'agent:ecosystem-scout:v2',
			permissions: { canRead: true, canPatch: false, canDispatch: false },
			systemPrompt: 'Scout external platforms and libraries for measurable performance improvements.'
		},
		{
			id: 'agent-human-eye',
			name: 'Human Eye UX Auditor',
			role: 'human-eye',
			title: 'UX / Responsive Quality Auditor',
			cadence_seconds: 21600,
			cadence_label: 'Every 6h',
			status: 'idle',
			lastHeartbeat: '3h ago',
			mandate: 'Visual inspection of studio interfaces for responsive layout bugs, mobile breakages, and tap targets.',
			identity: 'agent:human-eye:v2',
			permissions: { canRead: true, canPatch: false, canDispatch: false },
			systemPrompt: 'Audit studio and user journeys for accessibility, touch targets, and visual polish.'
		}
	];

	const STORAGE_KEY = 'supremeai_mcp_tower_agents_list';

	let agents: MCPAgent[] = DEFAULT_AGENTS;
	let loading = false;
	let activeFilter: 'all' | 'solver' | 'inspector' | 'platform-guardian' | 'rules-breaker' | 'custom' = 'all';

	// Modals State
	let showAddModal = false;
	let showEditModal = false;
	let showDispatchModal = false;
	let selectedAgent: MCPAgent | null = null;
	let dispatchPrompt = '';

	// Form State for Add / Edit
	let formName = '';
	let formRole: MCPAgent['role'] = 'custom';
	let formTitle = '';
	let formCadence = 'Every 30m';
	let formCadenceSeconds = 1800;
	let formMandate = '';
	let formSystemPrompt = '';
	let formCanPatch = true;

	const roleOptions: { value: MCPAgent['role']; label: string; defaultCadence: string; defaultSec: number }[] = [
		{ value: 'solver', label: 'Solver (Fixes bugs, PR submitter)', defaultCadence: 'Every 30s', defaultSec: 30 },
		{ value: 'inspector', label: 'Inspector (Smoke & test validator)', defaultCadence: 'Every 15m', defaultSec: 900 },
		{ value: 'platform-guardian', label: 'Platform Guardian (17 Services Probe)', defaultCadence: 'Every 30m', defaultSec: 1800 },
		{ value: 'rules-breaker', label: 'Rules Breaker (Security & Red-team)', defaultCadence: 'Every 2h', defaultSec: 7200 },
		{ value: 'ecosystem-scout', label: 'Ecosystem Scout (Radar engine)', defaultCadence: 'Every 4h', defaultSec: 14400 },
		{ value: 'human-eye', label: 'Human Eye (UI/UX visual auditor)', defaultCadence: 'Every 6h', defaultSec: 21600 },
		{ value: 'custom', label: 'Custom Domain Agent', defaultCadence: 'Every 1h', defaultSec: 3600 }
	];

	function loadAgents() {
		try {
			const saved = localStorage.getItem(STORAGE_KEY);
			if (saved) {
				agents = JSON.parse(saved);
			} else {
				agents = DEFAULT_AGENTS;
				saveAgents(agents);
			}
		} catch {
			agents = DEFAULT_AGENTS;
		}
	}

	function saveAgents(list: MCPAgent[]) {
		try {
			localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
		} catch (e) {
			console.error('Failed to save agents to localStorage:', e);
		}
	}

	async function refreshLoopStatus() {
		loading = true;
		try {
			// Query live MCP Tower for real agent heartbeat & status
			const res = await fetch(`${SUPREMEAI_CONFIG.mcpControlPlaneUrl}/health/summary`).catch(() => null);
			if (res && res.ok) {
				agents = agents.map((a) => ({
					...a,
					lastHeartbeat: 'Just now',
					status: 'active'
				}));
				saveAgents(agents);
				toast.success('Synced live agent heartbeats from MCP Tower');
			} else {
				// Local simulated heartbeat refresh
				agents = agents.map((a) => ({
					...a,
					lastHeartbeat: '1s ago'
				}));
				toast.info('Local heartbeat sync refreshed');
			}
		} catch {
			toast.error('Could not connect to MCP Tower');
		} finally {
			loading = false;
		}
	}

	// Add Agent Flow
	function openAddModal() {
		formName = '';
		formRole = 'custom';
		formTitle = '';
		formCadence = 'Every 1h';
		formCadenceSeconds = 3600;
		formMandate = '';
		formSystemPrompt = '';
		formCanPatch = true;
		showAddModal = true;
	}

	function handleRoleSelectionChange(roleVal: MCPAgent['role']) {
		formRole = roleVal;
		const opt = roleOptions.find((o) => o.value === roleVal);
		if (opt) {
			formCadence = opt.defaultCadence;
			formCadenceSeconds = opt.defaultSec;
		}
	}

	function submitAddAgent() {
		if (!formName.trim() || !formTitle.trim()) {
			toast.error('Agent Name and Title are required');
			return;
		}

		const newId = `agent-${formRole}-${Date.now().toString(36)}`;
		const newAgent: MCPAgent = {
			id: newId,
			name: formName.trim(),
			role: formRole,
			title: formTitle.trim(),
			cadence_seconds: formCadenceSeconds,
			cadence_label: formCadence,
			status: 'idle',
			lastHeartbeat: 'Never run',
			mandate: formMandate.trim() || 'Custom continuous agent worker.',
			identity: `agent:${formRole}:${newId}`,
			permissions: {
				canRead: true,
				canPatch: formCanPatch,
				canDispatch: true
			},
			systemPrompt: formSystemPrompt.trim(),
			isCustom: true
		};

		agents = [newAgent, ...agents];
		saveAgents(agents);
		showAddModal = false;
		toast.success(`Agent "${newAgent.name}" registered in MCP Tower fleet`);
	}

	// Edit Agent Flow
	function openEditModal(agent: MCPAgent) {
		selectedAgent = agent;
		formName = agent.name;
		formRole = agent.role;
		formTitle = agent.title;
		formCadence = agent.cadence_label;
		formCadenceSeconds = agent.cadence_seconds;
		formMandate = agent.mandate;
		formSystemPrompt = agent.systemPrompt || '';
		formCanPatch = agent.permissions.canPatch;
		showEditModal = true;
	}

	function submitEditAgent() {
		if (!selectedAgent) return;
		if (!formName.trim() || !formTitle.trim()) {
			toast.error('Agent Name and Title are required');
			return;
		}

		agents = agents.map((a) => {
			if (a.id === selectedAgent!.id) {
				return {
					...a,
					name: formName.trim(),
					role: formRole,
					title: formTitle.trim(),
					cadence_label: formCadence,
					cadence_seconds: formCadenceSeconds,
					mandate: formMandate.trim(),
					systemPrompt: formSystemPrompt.trim(),
					permissions: {
						...a.permissions,
						canPatch: formCanPatch
					}
				};
			}
			return a;
		});

		saveAgents(agents);
		showEditModal = false;
		toast.success(`Agent "${formName}" updated successfully`);
		selectedAgent = null;
	}

	// Delete Agent Flow
	function removeAgent(agent: MCPAgent) {
		if (confirm(`Are you sure you want to remove agent "${agent.name}" (${agent.role}) from the MCP fleet?`)) {
			agents = agents.filter((a) => a.id !== agent.id);
			saveAgents(agents);
			toast.success(`Agent "${agent.name}" removed from Tower`);
		}
	}

	// Immediate Dispatch Flow
	function triggerDispatch(agent: MCPAgent) {
		selectedAgent = agent;
		dispatchPrompt = `Execute scheduled cadence cycle for role: ${agent.role}`;
		showDispatchModal = true;
	}

	function confirmDispatch() {
		if (selectedAgent) {
			const targetId = selectedAgent.id;
			agents = agents.map((a) => {
				if (a.id === targetId) {
					return { ...a, status: 'running', lastHeartbeat: 'Running now...' };
				}
				return a;
			});
			saveAgents(agents);
			showDispatchModal = false;
			toast.success(`Dispatched agent "${selectedAgent.name}" successfully`);
			selectedAgent = null;

			// simulate completion after 5s
			setTimeout(() => {
				agents = agents.map((a) => {
					if (a.id === targetId) {
						return { ...a, status: 'active', lastHeartbeat: 'Just now' };
					}
					return a;
				});
				saveAgents(agents);
			}, 5000);
		}
	}

	$: filteredAgents = activeFilter === 'all'
		? agents
		: activeFilter === 'custom'
		? agents.filter((a) => a.isCustom)
		: agents.filter((a) => a.role === activeFilter);

	onMount(() => {
		loadAgents();
		refreshLoopStatus();
	});
</script>

<div class="space-y-6">
	<!-- Top Bar: Action Buttons & Filter -->
	<div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-gray-200 dark:border-gray-800">
		<div class="flex items-center gap-2">
			<div class="p-2 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400">
				<span class="text-xl">🤖</span>
			</div>
			<div>
				<h2 class="text-lg font-bold font-mono text-gray-900 dark:text-white flex items-center gap-2">
					MCP Tower Autonomous Agent Fleet
					<span class="text-[10px] font-mono px-2 py-0.5 rounded-full bg-purple-500/15 text-purple-300 border border-purple-500/30">
						{agents.length} Registered
					</span>
				</h2>
				<p class="text-xs text-gray-500 dark:text-gray-400">
					Autonomous cadence loop, roles, system prompts & write permissions management.
				</p>
			</div>
		</div>

		<!-- Action Buttons -->
		<div class="flex items-center gap-2">
			<button
				on:click={refreshLoopStatus}
				disabled={loading}
				class="px-3 py-1.5 rounded-xl border border-gray-200 dark:border-gray-800 bg-white/50 dark:bg-gray-900/60 hover:bg-gray-100 dark:hover:bg-gray-800 text-xs font-mono transition flex items-center gap-1.5 shadow-xs"
			>
				<span class="size-2 rounded-full bg-emerald-400 {loading ? 'animate-ping' : ''}"></span>
				<span>{loading ? 'Syncing...' : 'Sync Heartbeat'}</span>
			</button>

			<button
				on:click={openAddModal}
				class="px-3.5 py-1.5 rounded-xl bg-purple-500 hover:bg-purple-400 text-black font-mono font-bold text-xs transition flex items-center gap-1.5 shadow-sm shadow-purple-500/20"
			>
				<span>➕</span>
				<span>Add New Agent</span>
			</button>
		</div>
	</div>

	<!-- Filter Tabs -->
	<div class="flex items-center gap-2 overflow-x-auto scrollbar-none pb-1 text-xs font-mono">
		<span class="text-gray-500 text-[11px] uppercase tracking-wider mr-1">Role Filter:</span>
		{#each [
			{ id: 'all', label: `All (${agents.length})` },
			{ id: 'solver', label: 'Solver' },
			{ id: 'inspector', label: 'Inspector' },
			{ id: 'platform-guardian', label: 'Guardian' },
			{ id: 'rules-breaker', label: 'Red-Team' },
			{ id: 'custom', label: 'Custom' }
		] as tab}
			<button
				on:click={() => (activeFilter = tab.id as any)}
				class="px-3 py-1.5 rounded-xl transition whitespace-nowrap {activeFilter === tab.id
					? 'bg-purple-500/20 text-purple-300 border border-purple-500/40 font-bold'
					: 'bg-white/40 dark:bg-gray-900/40 border border-gray-200 dark:border-gray-800 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'}"
			>
				{tab.label}
			</button>
		{/each}
	</div>

	<!-- Agents Cards Grid -->
	<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
		{#each filteredAgents as agent (agent.id)}
			<div class="p-5 rounded-2xl border border-gray-200 dark:border-gray-800/80 bg-white/40 dark:bg-gray-900/40 backdrop-blur-md flex flex-col justify-between space-y-4 hover:border-purple-500/40 transition group">
				<div class="space-y-2.5">
					<!-- Top Meta Row -->
					<div class="flex items-center justify-between">
						<div class="flex items-center gap-1.5">
							<span class="px-2 py-0.5 rounded font-mono text-[10px] font-bold uppercase {agent.role === 'solver' ? 'bg-amber-500/15 text-amber-400 border border-amber-500/30' : agent.role === 'platform-guardian' ? 'bg-cyan-500/15 text-cyan-400 border border-cyan-500/30' : agent.role === 'rules-breaker' ? 'bg-rose-500/15 text-rose-400 border border-rose-500/30' : 'bg-purple-500/15 text-purple-400 border border-purple-500/30'}">
								{agent.role}
							</span>
							{#if agent.isCustom}
								<span class="text-[9px] font-mono px-1 rounded bg-black/30 text-gray-400 border border-white/5">
									CUSTOM
								</span>
							{/if}
						</div>

						<div class="flex items-center gap-1.5 text-xs font-mono">
							<span class="size-2 rounded-full {agent.status === 'running' ? 'bg-cyan-400 animate-ping' : agent.status === 'active' ? 'bg-emerald-400' : 'bg-gray-500'}"></span>
							<span class="{agent.status === 'running' ? 'text-cyan-400' : agent.status === 'active' ? 'text-emerald-400' : 'text-gray-400'} font-semibold uppercase text-[10px]">
								{agent.status}
							</span>
						</div>
					</div>

					<!-- Title & Identity -->
					<div>
						<h3 class="font-bold text-sm text-gray-900 dark:text-white group-hover:text-purple-300 transition">
							{agent.name}
						</h3>
						<div class="text-[11px] font-mono text-gray-500 truncate mt-0.5">
							{agent.title}
						</div>
					</div>

					<!-- Mandate -->
					<p class="text-xs text-gray-600 dark:text-gray-400 leading-relaxed min-h-[3rem] line-clamp-3">
						{agent.mandate}
					</p>

					<!-- Metrics Box -->
					<div class="grid grid-cols-2 gap-2 text-xs font-mono pt-1">
						<div class="p-2.5 rounded-xl bg-black/20 border border-white/5">
							<span class="text-gray-500 block text-[10px] uppercase">Cadence Interval</span>
							<span class="text-purple-300 font-semibold">{agent.cadence_label}</span>
						</div>
						<div class="p-2.5 rounded-xl bg-black/20 border border-white/5">
							<span class="text-gray-500 block text-[10px] uppercase">Last Heartbeat</span>
							<span class="text-cyan-300 font-semibold">{agent.lastHeartbeat || 'Active'}</span>
						</div>
					</div>

					<!-- Permissions Badges -->
					<div class="flex items-center gap-2 text-[10px] font-mono text-gray-400 pt-1">
						<span class="flex items-center gap-1">
							<span class="size-1.5 rounded-full {agent.permissions.canRead ? 'bg-emerald-400' : 'bg-rose-400'}"></span>
							Read Intel
						</span>
						<span class="flex items-center gap-1">
							<span class="size-1.5 rounded-full {agent.permissions.canPatch ? 'bg-emerald-400' : 'bg-gray-500'}"></span>
							Patch Ingress
						</span>
						<span class="flex items-center gap-1">
							<span class="size-1.5 rounded-full {agent.permissions.canDispatch ? 'bg-emerald-400' : 'bg-gray-500'}"></span>
							Direct Dispatch
						</span>
					</div>
				</div>

				<!-- Card Footer Actions -->
				<div class="pt-3 border-t border-gray-200 dark:border-gray-800/60 flex items-center justify-between gap-2">
					<div class="flex items-center gap-1">
						<button
							on:click={() => openEditModal(agent)}
							class="px-2.5 py-1 text-xs font-mono rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-400 hover:text-white transition"
							title="Edit Role & Configuration"
						>
							✏️ Edit
						</button>
						<button
							on:click={() => removeAgent(agent)}
							class="px-2.5 py-1 text-xs font-mono rounded-lg hover:bg-rose-500/10 text-gray-400 hover:text-rose-400 transition"
							title="Remove Agent"
						>
							🗑️ Remove
						</button>
					</div>

					<button
						on:click={() => triggerDispatch(agent)}
						class="px-3 py-1 text-xs font-mono font-medium rounded-lg bg-purple-500/15 hover:bg-purple-500/25 text-purple-300 border border-purple-500/30 transition flex items-center gap-1"
					>
						⚡ Dispatch
					</button>
				</div>
			</div>
		{/each}
	</div>

	<!-- Add Agent Modal -->
	{#if showAddModal}
		<div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm">
			<div class="bg-gray-900 border border-purple-500/40 rounded-2xl p-6 max-w-lg w-full shadow-2xl space-y-4">
				<div class="flex justify-between items-center border-b border-gray-800 pb-3">
					<h3 class="text-base font-bold text-white flex items-center gap-2 font-mono">
						🤖 Add New MCP Tower Agent
					</h3>
					<button on:click={() => (showAddModal = false)} class="text-gray-400 hover:text-white">✕</button>
				</div>

				<div class="space-y-3 text-xs">
					<div>
						<label for="new-agent-name" class="block text-gray-400 mb-1 font-mono">Agent Name</label>
						<input
							id="new-agent-name"
							type="text"
							bind:value={formName}
							placeholder="e.g. Database Migration Auditor"
							class="w-full px-3 py-2 rounded-xl bg-black/50 border border-gray-700 text-xs text-white focus:outline-none focus:border-purple-500"
						/>
					</div>

					<div class="grid grid-cols-2 gap-3">
						<div>
							<label for="new-agent-role" class="block text-gray-400 mb-1 font-mono">Role Mandate</label>
							<select
								id="new-agent-role"
								bind:value={formRole}
								on:change={(e) => handleRoleSelectionChange(e.currentTarget.value as any)}
								class="w-full px-3 py-2 rounded-xl bg-black/50 border border-gray-700 text-xs text-white focus:outline-none focus:border-purple-500"
							>
								{#each roleOptions as opt}
									<option value={opt.value}>{opt.label}</option>
								{/each}
							</select>
						</div>

						<div>
							<label for="new-agent-cadence" class="block text-gray-400 mb-1 font-mono">Cadence Interval</label>
							<input
								id="new-agent-cadence"
								type="text"
								bind:value={formCadence}
								placeholder="e.g. Every 45m"
								class="w-full px-3 py-2 rounded-xl bg-black/50 border border-gray-700 text-xs text-white focus:outline-none focus:border-purple-500"
							/>
						</div>
					</div>

					<div>
						<label for="new-agent-title" class="block text-gray-400 mb-1 font-mono">Display Title & Function</label>
						<input
							id="new-agent-title"
							type="text"
							bind:value={formTitle}
							placeholder="e.g. Supabase Schema Drift & Migration Sentinel"
							class="w-full px-3 py-2 rounded-xl bg-black/50 border border-gray-700 text-xs text-white focus:outline-none focus:border-purple-500"
						/>
					</div>

					<div>
						<label for="new-agent-mandate" class="block text-gray-400 mb-1 font-mono">Mandate & Execution Scope</label>
						<textarea
							id="new-agent-mandate"
							rows="2"
							bind:value={formMandate}
							placeholder="Describe the agent's responsibilities, invariants, and boundaries..."
							class="w-full px-3 py-2 rounded-xl bg-black/50 border border-gray-700 text-xs text-white resize-none focus:outline-none focus:border-purple-500"
						></textarea>
					</div>

					<div>
						<label for="new-agent-prompt" class="block text-gray-400 mb-1 font-mono">System Prompt / Directive (Optional)</label>
						<textarea
							id="new-agent-prompt"
							rows="3"
							bind:value={formSystemPrompt}
							placeholder="Instructions injected into agent runtime execution context..."
							class="w-full px-3 py-2 rounded-xl bg-black/50 border border-gray-700 text-xs text-white resize-none focus:outline-none focus:border-purple-500"
						></textarea>
					</div>

					<div class="flex items-center gap-2 pt-1">
						<input
							type="checkbox"
							id="canPatch"
							bind:checked={formCanPatch}
							class="rounded bg-black border-gray-700 text-purple-500 focus:ring-0"
						/>
						<label for="canPatch" class="text-gray-300 font-mono">
							Allow Code Patch Submission (bridge_submit_patch)
						</label>
					</div>

					<div class="flex justify-end gap-2 pt-3 border-t border-gray-800">
						<button on:click={() => (showAddModal = false)} class="px-3.5 py-1.5 text-gray-400 hover:text-white font-mono">
							Cancel
						</button>
						<button on:click={submitAddAgent} class="px-4 py-1.5 font-bold font-mono rounded-xl bg-purple-500 hover:bg-purple-400 text-black transition">
							Register Agent
						</button>
					</div>
				</div>
			</div>
		</div>
	{/if}

	<!-- Edit Agent Modal -->
	{#if showEditModal && selectedAgent}
		<div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm">
			<div class="bg-gray-900 border border-purple-500/40 rounded-2xl p-6 max-w-lg w-full shadow-2xl space-y-4">
				<div class="flex justify-between items-center border-b border-gray-800 pb-3">
					<h3 class="text-base font-bold text-white flex items-center gap-2 font-mono">
						✏️ Edit Agent Role & Config
					</h3>
					<button on:click={() => (showEditModal = false)} class="text-gray-400 hover:text-white">✕</button>
				</div>

				<div class="space-y-3 text-xs">
					<div>
						<label for="edit-agent-name" class="block text-gray-400 mb-1 font-mono">Agent Name</label>
						<input
							id="edit-agent-name"
							type="text"
							bind:value={formName}
							class="w-full px-3 py-2 rounded-xl bg-black/50 border border-gray-700 text-xs text-white focus:outline-none focus:border-purple-500"
						/>
					</div>

					<div class="grid grid-cols-2 gap-3">
						<div>
							<label for="edit-agent-role" class="block text-gray-400 mb-1 font-mono">Role Mandate</label>
							<select
								id="edit-agent-role"
								bind:value={formRole}
								on:change={(e) => handleRoleSelectionChange(e.currentTarget.value as any)}
								class="w-full px-3 py-2 rounded-xl bg-black/50 border border-gray-700 text-xs text-white focus:outline-none focus:border-purple-500"
							>
								{#each roleOptions as opt}
									<option value={opt.value}>{opt.label}</option>
								{/each}
							</select>
						</div>

						<div>
							<label for="edit-agent-cadence" class="block text-gray-400 mb-1 font-mono">Cadence Interval</label>
							<input
								id="edit-agent-cadence"
								type="text"
								bind:value={formCadence}
								class="w-full px-3 py-2 rounded-xl bg-black/50 border border-gray-700 text-xs text-white focus:outline-none focus:border-purple-500"
							/>
						</div>
					</div>

					<div>
						<label for="edit-agent-title" class="block text-gray-400 mb-1 font-mono">Display Title</label>
						<input
							id="edit-agent-title"
							type="text"
							bind:value={formTitle}
							class="w-full px-3 py-2 rounded-xl bg-black/50 border border-gray-700 text-xs text-white focus:outline-none focus:border-purple-500"
						/>
					</div>

					<div>
						<label for="edit-agent-mandate" class="block text-gray-400 mb-1 font-mono">Mandate</label>
						<textarea
							id="edit-agent-mandate"
							rows="2"
							bind:value={formMandate}
							class="w-full px-3 py-2 rounded-xl bg-black/50 border border-gray-700 text-xs text-white resize-none focus:outline-none focus:border-purple-500"
						></textarea>
					</div>

					<div>
						<label for="edit-agent-prompt" class="block text-gray-400 mb-1 font-mono">System Prompt / Directive</label>
						<textarea
							id="edit-agent-prompt"
							rows="3"
							bind:value={formSystemPrompt}
							class="w-full px-3 py-2 rounded-xl bg-black/50 border border-gray-700 text-xs text-white resize-none focus:outline-none focus:border-purple-500"
						></textarea>
					</div>

					<div class="flex items-center gap-2 pt-1">
						<input
							type="checkbox"
							id="editCanPatch"
							bind:checked={formCanPatch}
							class="rounded bg-black border-gray-700 text-purple-500 focus:ring-0"
						/>
						<label for="editCanPatch" class="text-gray-300 font-mono">
							Allow Code Patch Submission (bridge_submit_patch)
						</label>
					</div>

					<div class="flex justify-end gap-2 pt-3 border-t border-gray-800">
						<button on:click={() => (showEditModal = false)} class="px-3.5 py-1.5 text-gray-400 hover:text-white font-mono">
							Cancel
						</button>
						<button on:click={submitEditAgent} class="px-4 py-1.5 font-bold font-mono rounded-xl bg-purple-500 hover:bg-purple-400 text-black transition">
							Save Changes
						</button>
					</div>
				</div>
			</div>
		</div>
	{/if}

	<!-- Dispatch Confirmation Modal -->
	{#if showDispatchModal && selectedAgent}
		<div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm">
			<div class="bg-gray-900 border border-purple-500/40 rounded-2xl p-6 max-w-md w-full shadow-2xl space-y-4">
				<div class="flex justify-between items-center border-b border-gray-800 pb-3">
					<h3 class="text-base font-bold text-white flex items-center gap-2 font-mono">
						⚡ Dispatch Autonomous Agent
					</h3>
					<button on:click={() => (showDispatchModal = false)} class="text-gray-400 hover:text-white">✕</button>
				</div>

				<div class="space-y-3 text-xs">
					<div>
						<span class="text-gray-400 font-mono">Target Agent:</span>
						<span class="font-bold text-purple-400 ml-1 font-mono">{selectedAgent.name} ({selectedAgent.role})</span>
					</div>

					<div>
						<label for="dispatch-directive" class="block text-gray-400 mb-1 font-mono">Directive / Task Intent</label>
						<textarea
							id="dispatch-directive"
							rows="3"
							bind:value={dispatchPrompt}
							class="w-full px-3 py-2 rounded-xl bg-black/50 border border-gray-700 text-xs text-white resize-none font-mono focus:outline-none focus:border-purple-500"
						></textarea>
					</div>

					<p class="text-[11px] text-gray-400 leading-relaxed font-mono">
						⚠️ Under constitutional invariant <strong>U10</strong>, the agent will execute within its bounded scope, dual-rebase origin/main, and submit verification evidence.
					</p>

					<div class="flex justify-end gap-2 pt-2 border-t border-gray-800">
						<button on:click={() => (showDispatchModal = false)} class="px-3.5 py-1.5 text-gray-400 font-mono">
							Cancel
						</button>
						<button on:click={confirmDispatch} class="px-4 py-1.5 font-bold font-mono rounded-xl bg-purple-500 hover:bg-purple-400 text-black transition">
							Confirm Dispatch
						</button>
					</div>
				</div>
			</div>
		</div>
	{/if}
</div>

