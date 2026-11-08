<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { fade } from 'svelte/transition';
	import { toast } from 'svelte-sonner';

	export let authToken: string = '';

	interface AgentLogEntry {
		timestamp: string;
		level?: 'info' | 'warn' | 'error' | 'success';
		message?: string;
		msg?: string;
		agent?: string;
	}

	let activeTab: 'agentLog' | 'executionShell' | 'topology' = 'agentLog';
	let agentLogs: AgentLogEntry[] = [];
	let isConnected = false;
	let executionState: 'idle' | 'running' | 'paused' | 'error' | 'completed' = 'idle';
	let agentState: 'thinking' | 'planning' | 'executing' | 'reviewing' | 'analyzing' = 'thinking';
	let ws: WebSocket | null = null;
	let currentCommand = '';
	let shellHistory: string[] = [
		'[SupremeAI Sovereign Cockpit Initialized]',
		'[Doctrine]: Zero-Mock Invariant strictly active. Only authentic WebSocket telemetry is rendered.'
	];

	// Connect to live Sovereign Gateway WebSocket
	function connectWebSocket() {
		try {
			const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
			const wsHost = window.location.hostname === 'localhost' ? 'localhost:8000' : 'supremeai-gateway.onrender.com';
			const wsUrl = `${wsProtocol}//${wsHost}/ws/dashboard`;

			ws = new WebSocket(wsUrl);

			ws.onopen = () => {
				isConnected = true;
				const token = authToken || localStorage.getItem('token') || '';
				if (token && ws) {
					ws.send(JSON.stringify({ type: 'auth', payload: { token } }));
				}
				shellHistory = [...shellHistory, `Connected to live telemetry mesh: ${wsUrl}`];
			};

			ws.onclose = () => {
				isConnected = false;
				shellHistory = [...shellHistory, 'Telemetry link offline. Reconnecting in 5s...'];
			};

			ws.onerror = (err) => {
				console.warn('Telemetry WS connection notice:', err);
				isConnected = false;
			};

			ws.onmessage = (event) => {
				try {
					const data = JSON.parse(event.data);
					if (data.type === 'log_entry') {
						agentLogs = [
							...agentLogs.slice(-99),
							{ ...data.payload, timestamp: new Date().toLocaleTimeString() }
						];
					} else if (data.type === 'execution_state') {
						executionState = data.payload?.state || 'idle';
					} else if (data.type === 'agent_state') {
						agentState = data.payload?.state || 'thinking';
					}
				} catch (e) {
					console.error('Telemetry JSON parse error:', e);
				}
			};
		} catch (e) {
			console.warn('WS Init failed:', e);
		}
	}

	function handleExecuteCommand() {
		const cmd = currentCommand.trim();
		if (!cmd) return;

		shellHistory = [...shellHistory, `$ ${cmd}`];
		if (ws && isConnected) {
			ws.send(JSON.stringify({ type: 'shell_exec', command: cmd }));
		} else {
			shellHistory = [
				...shellHistory,
				'[Honest-Data Doctrine Notice]: Live backend execution pipeline is currently unreachable. No fabricated responses simulated.'
			];
		}
		currentCommand = '';
	}

	onMount(() => {
		connectWebSocket();
	});

	onDestroy(() => {
		if (ws) ws.close();
	});
</script>

<div class="w-full h-full flex flex-col bg-gray-950 text-gray-200 border border-gray-800/80 rounded-2xl overflow-hidden shadow-2xl font-mono">
	<!-- Cockpit Header -->
	<div class="h-12 px-4 bg-gray-900/90 border-b border-gray-800 flex items-center justify-between shrink-0">
		<div class="flex items-center gap-3">
			<span class="text-cyan-400 font-bold flex items-center gap-2 text-xs">
				<span class="size-2 rounded-full {isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'}"></span>
				<span>FEDERATION TELEMETRY COCKPIT</span>
			</span>
			<span class="text-[11px] px-2 py-0.5 rounded bg-black/40 border border-white/5 text-gray-400">
				Status: <span class="text-cyan-300 font-semibold">{isConnected ? 'LIVE SYNC' : 'DISCONNECTED'}</span>
			</span>
		</div>

		<!-- View Switcher -->
		<div class="flex items-center gap-1 bg-black/40 p-0.5 rounded-lg border border-white/5 text-xs">
			<button
				on:click={() => (activeTab = 'agentLog')}
				class="px-2.5 py-1 rounded-md transition {activeTab === 'agentLog'
					? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
					: 'text-gray-400 hover:text-white'}"
			>
				Agent Logs ({agentLogs.length})
			</button>
			<button
				on:click={() => (activeTab = 'executionShell')}
				class="px-2.5 py-1 rounded-md transition {activeTab === 'executionShell'
					? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
					: 'text-gray-400 hover:text-white'}"
			>
				Sovereign Shell
			</button>
		</div>
	</div>

	<!-- Cockpit Body -->
	<div class="flex-1 min-h-0 p-4 overflow-hidden flex flex-col">
		{#if activeTab === 'agentLog'}
			<div class="flex-1 w-full bg-black/60 rounded-xl border border-gray-800/70 p-3 overflow-y-auto space-y-1.5 text-xs">
				{#if agentLogs.length === 0}
					<div class="h-full flex flex-col items-center justify-center text-center text-gray-500 space-y-2">
						<div class="text-2xl">📡</div>
						<div>Awaiting agent log stream from Gateway WebSocket...</div>
						<div class="text-[10px] text-gray-600">
							[Honest Data Policy]: Zero fabricated logs. Real stream displays upon agent dispatch.
						</div>
					</div>
				{:else}
					{#each agentLogs as log}
						<div class="flex items-start gap-2 hover:bg-white/5 p-1 rounded">
							<span class="text-gray-500 shrink-0 text-[10px]">[{log.timestamp}]</span>
							<span class="px-1.5 py-0.2 rounded text-[10px] font-bold shrink-0 {
								log.level === 'error' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
								log.level === 'warn' ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' :
								'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
							}">
								{log.level?.toUpperCase() || 'INFO'}
							</span>
							{#if log.agent}
								<span class="text-purple-300 font-bold shrink-0">@{log.agent}:</span>
							{/if}
							<span class="text-gray-300 break-all">{log.message || log.msg}</span>
						</div>
					{/each}
				{/if}
			</div>
		{:else}
			<!-- Sovereign Shell Console -->
			<div class="flex-1 w-full bg-black rounded-xl border border-gray-800/80 p-3 flex flex-col justify-between overflow-hidden">
				<div class="flex-1 overflow-y-auto space-y-1 text-xs">
					{#each shellHistory as line}
						<div class="text-gray-400 {line.startsWith('$') ? 'text-cyan-300 font-bold' : ''}">
							{line}
						</div>
					{/each}
				</div>

				<form on:submit|preventDefault={handleExecuteCommand} class="mt-2 flex items-center gap-2 pt-2 border-t border-gray-800">
					<span class="text-cyan-400 font-bold">$</span>
					<input
						type="text"
						bind:value={currentCommand}
						placeholder="Send instruction or query to telemetry agent..."
						class="flex-1 bg-transparent border-none outline-none text-xs text-gray-200 placeholder-gray-600"
					/>
					<button
						type="submit"
						class="px-3 py-1 rounded bg-cyan-600 hover:bg-cyan-500 text-black font-bold text-xs transition"
					>
						Execute
					</button>
				</form>
			</div>
		{/if}
	</div>
</div>

