<script lang="ts">
	import TelemetryCockpit from '$lib/components/telemetry/TelemetryCockpit.svelte';
	import SwarmDashboard from '$lib/components/swarm/SwarmDashboard.svelte';
	import BanglaHint from '$lib/components/common/BanglaHint.svelte';

	let activeSubTab: 'telemetry' | 'swarm' = 'telemetry';
</script>

<svelte:head>
	<title>SupremeAI Telemetry & Swarm Cockpit</title>
</svelte:head>

<div class="h-full w-full flex flex-col p-4 sm:p-6 space-y-4 overflow-y-auto">
	<!-- Header Bar -->
	<div class="flex items-center justify-between pb-3 border-b border-gray-800">
		<div>
			<div class="flex items-center gap-2">
				<h1 class="text-xl font-bold tracking-tight text-white flex items-center gap-2">
					<span>📡</span>
					<span>Telemetry & Autonomous Swarm Cockpit</span>
				</h1>
				<BanglaHint text="লাইভ এজেন্ট এক্সিকিউশন লগ, সোয়ার্ম নোড কোঅর্ডিনেশন এবং ইমার্জেন্সি কিল সুইচ এখানে অবস্থিত।" />
			</div>
			<p class="text-xs text-gray-400 mt-1">
				Real-time telemetry stream, Honest-Data metrics, and Sovereign multi-agent federation control.
			</p>
		</div>

		<!-- Sub-tab Selector -->
		<div class="flex items-center p-1 rounded-xl bg-black/50 border border-white/10 text-xs font-mono">
			<button
				on:click={() => (activeSubTab = 'telemetry')}
				class="px-3 py-1.5 rounded-lg transition flex items-center gap-1.5 {activeSubTab === 'telemetry'
					? 'bg-cyan-500/20 text-cyan-300 font-bold border border-cyan-500/30'
					: 'text-gray-400 hover:text-white'}"
			>
				<span>📊</span>
				<span>Federation Telemetry</span>
			</button>
			<button
				on:click={() => (activeSubTab = 'swarm')}
				class="px-3 py-1.5 rounded-lg transition flex items-center gap-1.5 {activeSubTab === 'swarm'
					? 'bg-amber-500/20 text-amber-300 font-bold border border-amber-500/30'
					: 'text-gray-400 hover:text-white'}"
			>
				<span>🐝</span>
				<span>Swarm & Kill Switch</span>
			</button>
		</div>
	</div>

	<!-- Main Workspace Panel -->
	<div class="flex-1 min-h-[600px] w-full">
		{#if activeSubTab === 'telemetry'}
			<TelemetryCockpit />
		{:else}
			<SwarmDashboard />
		{/if}
	</div>
</div>

