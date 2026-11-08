<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	interface SwarmNode {
		id: string;
		name: string;
		role: string;
		status: 'active' | 'idle' | 'executing' | 'offline';
		load: number; // 0 - 100
	}

	let nodes: SwarmNode[] = [
		{ id: 'solver', name: 'Task Solver', role: 'Autonomous Code & Bug Fix', status: 'idle', load: 12 },
		{ id: 'platform-guardian', name: 'Platform Guardian', role: 'Health & Quota Monitor', status: 'active', load: 34 },
		{ id: 'rules-breaker', name: 'Rules Breaker', role: 'Security & Parity Auditor', status: 'idle', load: 0 },
		{ id: 'ecosystem-scout', name: 'Ecosystem Scout', role: 'Tool & Model Scouting', status: 'idle', load: 0 },
		{ id: 'human-eye', name: 'Human Eye UX', role: 'Visual & A11y Inspector', status: 'idle', load: 0 }
	];

	let isHolding = false;
	let holdTimer: any = null;
	let holdProgress = 0; // 0 to 100
	let swarmHalted = false;

	function startHold() {
		if (swarmHalted) return;
		isHolding = true;
		holdProgress = 0;
		const interval = 20; // 20ms steps
		const duration = 2000; // 2 seconds
		const step = (interval / duration) * 100;

		holdTimer = setInterval(() => {
			holdProgress += step;
			if (holdProgress >= 100) {
				clearInterval(holdTimer);
				triggerKillSwitch();
			}
		}, interval);
	}

	function endHold() {
		if (holdProgress < 100) {
			clearInterval(holdTimer);
			isHolding = false;
			holdProgress = 0;
		}
	}

	function triggerKillSwitch() {
		isHolding = false;
		swarmHalted = true;
		toast.error('EMERGENCY KILL SWITCH ACTIVATED: All autonomous swarm agents halted immediately.');
		nodes = nodes.map(n => ({ ...n, status: 'offline', load: 0 }));
	}

	function resumeSwarm() {
		swarmHalted = false;
		holdProgress = 0;
		nodes = nodes.map(n => ({ ...n, status: n.id === 'platform-guardian' ? 'active' : 'idle', load: 15 }));
		toast.success('Autonomous Swarm Operations Resumed.');
	}
</script>

<div class="w-full h-full flex flex-col bg-gray-950 text-gray-200 border border-gray-800 rounded-2xl overflow-hidden font-mono p-4 space-y-4 shadow-2xl">
	<!-- Top Bar -->
	<div class="flex items-center justify-between pb-3 border-b border-gray-800">
		<div>
			<h2 class="text-base font-bold text-cyan-400 flex items-center gap-2">
				<span>🐝</span>
				<span>SOVEREIGN SWARM CONTROLLER</span>
			</h2>
			<p class="text-xs text-gray-500">Autonomous Multi-Agent Federation Coordination & Circuit Breaker</p>
		</div>

		<!-- Hold-to-Kill Switch Button -->
		{#if !swarmHalted}
			<button
				type="button"
				class="relative overflow-hidden px-4 py-2 rounded-xl border border-red-500/40 bg-red-950/40 text-red-300 font-bold text-xs select-none hover:border-red-400 transition"
				on:mousedown={startHold}
				on:mouseup={endHold}
				on:mouseleave={endHold}
				on:touchstart|preventDefault={startHold}
				on:touchend|preventDefault={endHold}
			>
				<div
					class="absolute inset-0 bg-red-600/60 transition-all pointer-events-none"
					style="width: {holdProgress}%"
				></div>
				<span class="relative z-10 flex items-center gap-2">
					<span>🛑</span>
					<span>{isHolding ? `HOLDING TO KILL (${Math.round(holdProgress)}%)...` : 'HOLD TO HALT SWARM (2s)'}</span>
				</span>
			</button>
		{:else}
			<button
				on:click={resumeSwarm}
				class="px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-black font-bold text-xs flex items-center gap-2 transition"
			>
				<span>▶</span>
				<span>RESUME SWARM FEDERATION</span>
			</button>
		{/if}
	</div>

	<!-- Swarm Nodes Grid -->
	<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
		{#each nodes as node}
			<div class="p-3 rounded-xl bg-black/40 border border-gray-800 hover:border-gray-700 transition flex flex-col justify-between space-y-2">
				<div class="flex items-start justify-between">
					<div>
						<div class="text-xs font-bold text-white flex items-center gap-1.5">
							<span class="size-2 rounded-full {
								node.status === 'active' ? 'bg-emerald-400 animate-pulse' :
								node.status === 'executing' ? 'bg-cyan-400 animate-spin' :
								node.status === 'offline' ? 'bg-red-500' : 'bg-gray-500'
							}"></span>
							<span>{node.name}</span>
						</div>
						<div class="text-[10px] text-gray-500">@{node.id}</div>
					</div>
					<span class="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded {
						node.status === 'active' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' :
						node.status === 'offline' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
						'bg-gray-800 text-gray-400'
					}">
						{node.status}
					</span>
				</div>

				<div class="text-[11px] text-gray-400">{node.role}</div>

				<!-- Load meter -->
				<div class="space-y-1">
					<div class="flex justify-between text-[10px] text-gray-500">
						<span>Load Capacity</span>
						<span>{node.load}%</span>
					</div>
					<div class="w-full h-1.5 bg-gray-900 rounded-full overflow-hidden">
						<div class="h-full bg-cyan-500 rounded-full" style="width: {node.load}%"></div>
					</div>
				</div>
			</div>
		{/each}
	</div>
</div>

