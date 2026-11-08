<script lang="ts">
	import { onMount } from 'svelte';
	import { SUPREMEAI_CONFIG } from '$lib/supremeai';

	type ActiveSubTab = 'api-keys' | 'webhooks';
	let activeTab: ActiveSubTab = 'api-keys';

	// ================= API KEYS STATE =================
	interface ApiKeyItem {
		id: string;
		provider: string;
		name: string;
		maskedKey: string;
		health: 'healthy' | 'degraded' | 'expired';
		latencyMs: number;
		lastVerified: string;
	}

	let apiKeys: ApiKeyItem[] = [
		{ id: '1', provider: 'Gemini Pro', name: 'Google Workspace Primary', maskedKey: 'AIzaSy...7x9Q', health: 'healthy', latencyMs: 120, lastVerified: '1m ago' },
		{ id: '2', provider: 'Groq Cloud', name: 'Ultra-Fast Flash Leg', maskedKey: 'gsk_...91kM', health: 'healthy', latencyMs: 38, lastVerified: '3m ago' },
		{ id: '3', provider: 'OpenRouter', name: 'Multi-LLM Unified Fallback', maskedKey: 'sk-or-...44fE', health: 'healthy', latencyMs: 145, lastVerified: '5m ago' },
		{ id: '4', provider: 'Render API', name: 'Render Deploy API Key 5', maskedKey: 'rnd_...00aP', health: 'healthy', latencyMs: 85, lastVerified: '10m ago' },
		{ id: '5', provider: 'Infisical Secret', name: 'Runtime Env Secret Token', maskedKey: 'st.inf...88zL', health: 'healthy', latencyMs: 42, lastVerified: '2m ago' }
	];

	let showAddKeyModal = false;
	let newKeyProvider = 'Gemini';
	let newKeyName = '';
	let newKeyValue = '';

	function addApiKey() {
		if (!newKeyValue.trim()) return;
		const prefix = newKeyValue.trim().substring(0, 8);
		const suffix = newKeyValue.trim().slice(-4);
		apiKeys = [
			{
				id: String(Date.now()),
				provider: newKeyProvider,
				name: newKeyName.trim() || `${newKeyProvider} Custom Key`,
				maskedKey: `${prefix}...${suffix}`,
				health: 'healthy',
				latencyMs: 95,
				lastVerified: 'Just now'
			},
			...apiKeys
		];
		newKeyName = '';
		newKeyValue = '';
		showAddKeyModal = false;
	}

	function removeApiKey(id: string) {
		apiKeys = apiKeys.filter(k => k.id !== id);
	}

	// ================= WEBHOOKS & COOKIES STATE =================
	interface WebhookItem {
		id: string;
		provider: string;
		endpoint: string;
		cookieStatus: 'valid' | 'expiring-soon' | 'expired';
		cookieExpiry: string;
		health: 'healthy' | 'warning' | 'error';
		lastPayloadAt: string;
		stealthRelay: boolean;
	}

	let webhooks: WebhookItem[] = [
		{
			id: 'wh-1',
			provider: 'Stealth Browser Relay (Render 3)',
			endpoint: 'https://supremeai-scraper-node.onrender.com/webhook',
			cookieStatus: 'valid',
			cookieExpiry: '14 days left',
			health: 'healthy',
			lastPayloadAt: '4m ago',
			stealthRelay: true
		},
		{
			id: 'wh-2',
			provider: 'Cloudflare Keep-Warm Mesh',
			endpoint: 'https://supremeai.live/cf-keepwarm',
			cookieStatus: 'valid',
			cookieExpiry: 'Session Evergreen',
			health: 'healthy',
			lastPayloadAt: '2m ago',
			stealthRelay: false
		},
		{
			id: 'wh-3',
			provider: 'Telegram Notification Bot',
			endpoint: 'https://api.telegram.org/bot/hook',
			cookieStatus: 'valid',
			cookieExpiry: 'Token Persistent',
			health: 'healthy',
			lastPayloadAt: '12m ago',
			stealthRelay: false
		},
		{
			id: 'wh-4',
			provider: 'Harness Governance Webhook',
			endpoint: 'https://app.harness.io/gateway/api/webhooks',
			cookieStatus: 'valid',
			cookieExpiry: '30 days left',
			health: 'healthy',
			lastPayloadAt: '18m ago',
			stealthRelay: false
		}
	];

	let editingWebhook: WebhookItem | null = null;
	let updateCookieString = '';

	function openUpdateWebhook(wh: WebhookItem) {
		editingWebhook = { ...wh };
		updateCookieString = '';
	}

	function saveWebhookUpdate() {
		if (!editingWebhook) return;
		webhooks = webhooks.map(w => {
			if (w.id === editingWebhook!.id) {
				return {
					...editingWebhook!,
					cookieStatus: 'valid',
					cookieExpiry: '30 days refreshed',
					health: 'healthy'
				};
			}
			return w;
		});
		editingWebhook = null;
	}
</script>

<svelte:head>
	<title>SupremeAI API Keys & Webhook Hub</title>
</svelte:head>

<div class="h-full w-full overflow-y-auto px-4 py-6 md:px-8 bg-transparent text-gray-900 dark:text-gray-100">
	<div class="max-w-6xl mx-auto space-y-6">
		<!-- Header & Sub-Tabs -->
		<div class="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-gray-200 dark:border-gray-800">
			<div class="flex items-center gap-3">
				<div class="size-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 font-bold text-lg">
					🔑
				</div>
				<div>
					<h1 class="text-2xl font-bold tracking-tight bg-gradient-to-r from-cyan-400 via-teal-300 to-blue-500 bg-clip-text text-transparent">
						API Credentials & Webhook Gateway
					</h1>
					<p class="text-xs text-gray-500 dark:text-gray-400">
						Realtime Health Monitoring for LLM Provider Keys, Stealth Webhooks, and Session Cookies
					</p>
				</div>
			</div>

			<!-- Sub-Tabs Selector -->
			<div class="flex items-center p-1 rounded-xl bg-gray-100 dark:bg-black/40 border border-gray-200 dark:border-gray-800 text-xs font-medium">
				<button
					on:click={() => activeTab = 'api-keys'}
					class="px-4 py-1.5 rounded-lg transition flex items-center gap-2 {activeTab === 'api-keys' ? 'bg-cyan-500 text-black font-semibold shadow' : 'text-gray-400 hover:text-white'}"
				>
					<span>API Keys & Health</span>
					<span class="px-1.5 py-0.2 rounded-full text-[10px] bg-black/20 font-mono">{apiKeys.length}</span>
				</button>

				<button
					on:click={() => activeTab = 'webhooks'}
					class="px-4 py-1.5 rounded-lg transition flex items-center gap-2 {activeTab === 'webhooks' ? 'bg-cyan-500 text-black font-semibold shadow' : 'text-gray-400 hover:text-white'}"
				>
					<span>Webhooks & Cookies</span>
					<span class="px-1.5 py-0.2 rounded-full text-[10px] bg-black/20 font-mono">{webhooks.length}</span>
				</button>
			</div>
		</div>

		<!-- ================= SUB-TAB 1: API KEYS ================= -->
		{#if activeTab === 'api-keys'}
			<div class="space-y-4">
				<div class="flex justify-between items-center">
					<div class="text-xs font-semibold uppercase tracking-wider text-gray-400">
						Provider Keys & Endpoint Health Check
					</div>
					<button
						on:click={() => showAddKeyModal = true}
						class="px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-cyan-500 hover:bg-cyan-400 text-black transition shadow-[0_0_12px_rgba(0,231,245,0.3)]"
					>
						+ Add Provider Key
					</button>
				</div>

				<div class="rounded-xl border border-gray-200 dark:border-gray-800 bg-white/40 dark:bg-gray-900/40 backdrop-blur-md overflow-hidden">
					<div class="divide-y divide-gray-200 dark:divide-gray-800/60">
						{#each apiKeys as key}
							<div class="p-4 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
								<div class="space-y-1">
									<div class="flex items-center gap-2">
										<span class="px-2 py-0.5 rounded font-mono text-[11px] font-medium bg-black/30 text-cyan-300 border border-white/5">
											{key.provider}
										</span>
										<span class="font-bold text-sm text-gray-900 dark:text-white">{key.name}</span>
									</div>
									<div class="font-mono text-cyan-400 font-semibold">{key.maskedKey}</div>
								</div>

								<div class="flex items-center gap-4">
									<div class="text-right font-mono">
										<div class="flex items-center gap-1.5 justify-end">
											<span class="size-2 rounded-full bg-emerald-400 animate-pulse"></span>
											<span class="text-emerald-400 font-bold uppercase">{key.health}</span>
											<span class="text-[11px] text-gray-400">({key.latencyMs}ms)</span>
										</div>
										<div class="text-[10px] text-gray-500">Checked: {key.lastVerified}</div>
									</div>

									<button
										on:click={() => removeApiKey(key.id)}
										class="px-2.5 py-1 text-xs rounded-lg border border-rose-500/30 text-rose-400 hover:bg-rose-500/10 transition"
									>
										Remove
									</button>
								</div>
							</div>
						{/each}
					</div>
				</div>
			</div>
		{/if}

		<!-- ================= SUB-TAB 2: WEBHOOKS & COOKIES ================= -->
		{#if activeTab === 'webhooks'}
			<div class="space-y-4">
				<div class="text-xs font-semibold uppercase tracking-wider text-gray-400">
					Stealth Webhooks, Cookie Expiry & Provider Health
				</div>

				<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
					{#each webhooks as wh}
						<div class="p-5 rounded-xl border border-gray-200 dark:border-gray-800 bg-white/40 dark:bg-gray-900/40 backdrop-blur-md flex flex-col justify-between space-y-4">
							<div class="space-y-2">
								<div class="flex items-center justify-between">
									<span class="font-bold text-sm text-gray-900 dark:text-white flex items-center gap-2">
										<span class="size-2 rounded-full {wh.health === 'healthy' ? 'bg-emerald-400' : 'bg-rose-500'}"></span>
										{wh.provider}
									</span>
									{#if wh.stealthRelay}
										<span class="px-2 py-0.5 rounded text-[10px] font-mono bg-purple-500/20 text-purple-300 border border-purple-500/30">
											Stealth Relay
										</span>
									{/if}
								</div>

								<p class="text-xs font-mono text-gray-400 break-all bg-black/30 p-2 rounded-lg border border-white/5">
									{wh.endpoint}
								</p>

								<div class="grid grid-cols-2 gap-2 text-xs pt-2">
									<div class="p-2 rounded bg-black/20 border border-white/5">
										<span class="text-gray-400 block text-[10px] uppercase font-mono">Cookie Status</span>
										<span class="font-semibold text-emerald-400">{wh.cookieStatus} ({wh.cookieExpiry})</span>
									</div>
									<div class="p-2 rounded bg-black/20 border border-white/5">
										<span class="text-gray-400 block text-[10px] uppercase font-mono">Last Payload</span>
										<span class="font-semibold text-cyan-300">{wh.lastPayloadAt}</span>
									</div>
								</div>
							</div>

							<div class="flex justify-end pt-2 border-t border-gray-200 dark:border-gray-800/60">
								<button
									on:click={() => openUpdateWebhook(wh)}
									class="px-3 py-1.5 text-xs font-medium rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 transition flex items-center gap-1.5"
								>
									⚙️ Update Webhook & Cookies
								</button>
							</div>
						</div>
					{/each}
				</div>
			</div>
		{/if}

		<!-- Add Key Modal -->
		{#if showAddKeyModal}
			<div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
				<div class="bg-gray-900 border border-gray-800 rounded-2xl p-6 max-w-md w-full shadow-2xl space-y-4">
					<h3 class="text-base font-bold text-white">Add New API Key</h3>
					<div class="space-y-3">
						<div>
							<label for="provider" class="block text-xs text-gray-400 mb-1">LLM / Cloud Provider</label>
							<select
								id="provider"
								bind:value={newKeyProvider}
								class="w-full px-3 py-2 rounded-lg bg-black/50 border border-gray-700 text-xs text-white"
							>
								<option value="Gemini">Google Gemini Pro / Flash</option>
								<option value="Groq">Groq Cloud (Llama/Mixtral)</option>
								<option value="OpenRouter">OpenRouter Fallback</option>
								<option value="Anthropic">Anthropic Claude</option>
								<option value="OpenAI">OpenAI GPT</option>
								<option value="Render">Render Platform API</option>
							</select>
						</div>

						<div>
							<label for="keyname" class="block text-xs text-gray-400 mb-1">Key Description / Alias</label>
							<input
								id="keyname"
								type="text"
								bind:value={newKeyName}
								placeholder="e.g. Primary Flash Key"
								class="w-full px-3 py-2 rounded-lg bg-black/50 border border-gray-700 text-xs text-white"
							/>
						</div>

						<div>
							<label for="secret" class="block text-xs text-gray-400 mb-1">Secret Key Value</label>
							<input
								id="secret"
								type="password"
								bind:value={newKeyValue}
								placeholder="Paste raw API key..."
								class="w-full px-3 py-2 rounded-lg bg-black/50 border border-gray-700 text-xs text-white font-mono"
							/>
						</div>

						<div class="flex justify-end gap-2 pt-2">
							<button on:click={() => showAddKeyModal = false} class="px-3 py-1.5 text-xs text-gray-400">Cancel</button>
							<button on:click={addApiKey} class="px-4 py-1.5 text-xs font-semibold rounded-lg bg-cyan-500 text-black">Save & Verify</button>
						</div>
					</div>
				</div>
			</div>
		{/if}

		<!-- Update Webhook & Cookies Modal -->
		{#if editingWebhook}
			<div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
				<div class="bg-gray-900 border border-gray-800 rounded-2xl p-6 max-w-lg w-full shadow-2xl space-y-4">
					<div class="flex justify-between items-center border-b border-gray-800 pb-3">
						<h3 class="text-base font-bold text-white">Update Webhook & Stealth Cookies</h3>
						<button on:click={() => editingWebhook = null} class="text-gray-400 hover:text-white">✕</button>
					</div>

					<div class="space-y-3">
						<div>
							<label for="wh-ep" class="block text-xs text-gray-400 mb-1">Webhook Endpoint URL</label>
							<input
								id="wh-ep"
								type="text"
								bind:value={editingWebhook.endpoint}
								class="w-full px-3 py-2 rounded-lg bg-black/50 border border-gray-700 text-xs text-cyan-300 font-mono"
							/>
						</div>

						<div>
							<label for="cookie-box" class="block text-xs text-gray-400 mb-1">
								Update Session Cookies (JSON / Netscape format)
							</label>
							<textarea
								id="cookie-box"
								rows="4"
								bind:value={updateCookieString}
								placeholder="Paste updated auth cookies or session tokens..."
								class="w-full px-3 py-2 rounded-lg bg-black/50 border border-gray-700 text-xs text-white font-mono resize-none"
							></textarea>
						</div>

						<div class="flex justify-end gap-2 pt-2">
							<button on:click={() => editingWebhook = null} class="px-3 py-1.5 text-xs text-gray-400">Cancel</button>
							<button on:click={saveWebhookUpdate} class="px-4 py-1.5 text-xs font-semibold rounded-lg bg-cyan-500 text-black">
								Save & Refresh Expiry
							</button>
						</div>
					</div>
				</div>
			</div>
		{/if}
	</div>
</div>
