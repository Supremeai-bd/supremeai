<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { fade } from 'svelte/transition';
	import { toast } from 'svelte-sonner';
	import { artifactContents, showArtifacts } from '$lib/stores';

	export let url: string = 'http://localhost:3000';

	let currentUrl = url;
	let inputUrl = url;
	let isLoading = false;
	let iframeEl: HTMLIFrameElement;
	let activeTab: 'live' | 'artifacts' = 'live';
	let artifactsList: any[] = [];
	let selectedArtifactIdx = 0;
	let proxyHtml = '';
	let useProxy = false;
	let loadError = false;

	// Check if URL is local or external
	const isLocalUrl = (u: string) => {
		return (
			u.includes('localhost') ||
			u.includes('127.0.0.1') ||
			u.startsWith('/') ||
			u.includes('openwebui')
		);
	};

	async function loadExternalViaProxy(targetUrl: string) {
		isLoading = true;
		loadError = false;
		useProxy = true;
		proxyHtml = '';

		try {
			const proxyEndpoint = `/api/proxy?url=${encodeURIComponent(targetUrl)}`;
			const res = await fetch(proxyEndpoint);
			if (!res.ok) throw new Error(`HTTP error ${res.status}`);
			const html = await res.text();
			if (html) {
				proxyHtml = html;
				isLoading = false;
				return;
			}
			throw new Error('No content returned from proxy');
		} catch (err: any) {
			console.warn('Proxy fetch failed, rendering fallback iframe:', err);
			useProxy = false;
			loadError = true;
			isLoading = false;
		}
	}

	function navigateToUrl() {
		let target = inputUrl.trim();
		if (!target.startsWith('http://') && !target.startsWith('https://')) {
			target = `https://${target}`;
			inputUrl = target;
		}

		currentUrl = target;

		if (isLocalUrl(target)) {
			useProxy = false;
			isLoading = true;
			loadError = false;
			if (iframeEl) iframeEl.src = target;
		} else {
			loadExternalViaProxy(target);
		}
	}

	function handleRefresh() {
		if (useProxy) {
			loadExternalViaProxy(currentUrl);
		} else {
			isLoading = true;
			loadError = false;
			if (iframeEl) {
				iframeEl.src = currentUrl;
			}
		}
	}

	function handleIframeLoad() {
		isLoading = false;
	}

	function openInNewTab() {
		window.open(currentUrl, '_blank', 'noopener,noreferrer');
	}

	onMount(() => {
		const unsub = artifactContents.subscribe((items) => {
			artifactsList = items || [];
			if (artifactsList.length > 0 && selectedArtifactIdx >= artifactsList.length) {
				selectedArtifactIdx = artifactsList.length - 1;
			}
		});
		return () => unsub();
	});
</script>

<div class="h-full w-full flex flex-col bg-gray-950 text-gray-200 border-l border-gray-800/80 font-sans select-none overflow-hidden">
	<!-- Dedicated Desktop Browser Toolbar -->
	<div class="h-11 px-3 bg-gray-900/90 border-b border-gray-800 flex items-center justify-between gap-2 shrink-0">
		<!-- Left: Tab Switcher (Live Browser vs Code Artifacts) -->
		<div class="flex items-center gap-1.5">
			<div class="flex items-center p-0.5 bg-black/40 rounded-lg border border-white/5 text-[11px] font-mono">
				<button
					on:click={() => (activeTab = 'live')}
					class="px-2.5 py-1 rounded-md transition flex items-center gap-1.5 {activeTab === 'live'
						? 'bg-cyan-500/20 text-cyan-300 font-bold border border-cyan-500/30'
						: 'text-gray-400 hover:text-white'}"
				>
					<span>🌐</span>
					<span>Desktop Browser</span>
				</button>
				<button
					on:click={() => (activeTab = 'artifacts')}
					class="px-2.5 py-1 rounded-md transition flex items-center gap-1.5 {activeTab === 'artifacts'
						? 'bg-purple-500/20 text-purple-300 font-bold border border-purple-500/30'
						: 'text-gray-400 hover:text-white'}"
				>
					<span>⚡</span>
					<span>Code Artifacts ({artifactsList.length})</span>
				</button>
			</div>
		</div>

		<!-- Center: Desktop Browser Address Bar -->
		{#if activeTab === 'live'}
			<form on:submit|preventDefault={navigateToUrl} class="flex-1 max-w-lg mx-2 flex items-center">
				<div class="w-full flex items-center gap-1.5 bg-black/50 border border-gray-700/60 rounded-lg px-2.5 py-1 text-xs font-mono">
					<span class="text-gray-500 text-[10px]">🔒</span>
					<input
						type="text"
						bind:value={inputUrl}
						class="w-full bg-transparent border-none outline-none text-gray-300 placeholder-gray-600 text-xs font-mono"
						placeholder="http://localhost:3000 or website URL..."
					/>
					{#if isLoading}
						<div class="size-3 border border-cyan-400 border-t-transparent rounded-full animate-spin"></div>
					{:else}
						<button type="submit" class="text-gray-400 hover:text-cyan-400 transition" title="Go">
							↵
						</button>
					{/if}
				</div>
			</form>
		{/if}

		<!-- Right: Quick Window Action Buttons -->
		<div class="flex items-center gap-1.5">
			<button
				on:click={handleRefresh}
				class="size-7 rounded-lg hover:bg-gray-800 flex items-center justify-center text-gray-400 hover:text-white text-xs transition"
				title="Reload page"
			>
				🔄
			</button>

			<button
				on:click={openInNewTab}
				class="size-7 rounded-lg hover:bg-gray-800 flex items-center justify-center text-gray-400 hover:text-white text-xs transition"
				title="Open URL in native browser window"
			>
				↗
			</button>
		</div>
	</div>

	<!-- Main Canvas Body -->
	<div class="flex-1 w-full min-h-0 bg-gray-950 flex items-center justify-center p-2 relative overflow-hidden">
		{#if activeTab === 'live'}
			<div class="w-full h-full flex flex-col bg-white dark:bg-black rounded-xl overflow-hidden shadow-2xl relative border border-gray-800">
				{#if isLoading}
					<div class="absolute inset-0 bg-gray-950/80 backdrop-blur-xs z-20 flex flex-col items-center justify-center gap-2 text-xs font-mono text-cyan-400">
						<div class="size-6 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin"></div>
						<span>Connecting & Bypassing Frame Restriction...</span>
					</div>
				{/if}

				{#if useProxy && proxyHtml}
					<iframe
						title="Proxied Live Web Content"
						srcdoc={proxyHtml}
						class="w-full flex-1 border-0 bg-white"
						sandbox="allow-scripts allow-forms allow-same-origin allow-popups"
					></iframe>
				{:else}
					<iframe
						bind:this={iframeEl}
						src={currentUrl}
						title="Live SupremeAI Desktop Browser"
						class="w-full flex-1 border-0 bg-white"
						sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals"
						on:load={handleIframeLoad}
					></iframe>
				{/if}

				{#if loadError}
					<div class="absolute bottom-3 inset-x-3 p-3 rounded-xl bg-amber-950/90 border border-amber-500/40 text-amber-200 text-xs font-mono flex items-center justify-between shadow-xl backdrop-blur-md">
						<div class="flex items-center gap-2">
							<span>⚠️</span>
							<span>Site strictly blocked by X-Frame-Options (CORS)</span>
						</div>
						<button
							on:click={openInNewTab}
							class="px-2.5 py-1 rounded bg-amber-500 hover:bg-amber-400 text-black font-bold transition flex items-center gap-1"
						>
							<span>Open Tab</span>
							<span>↗</span>
						</button>
					</div>
				{/if}
			</div>
		{:else}
			<!-- Code Artifacts Preview Mode -->
			<div class="w-full h-full flex flex-col">
				{#if artifactsList.length > 0}
					<div class="h-9 px-3 bg-gray-900 border-b border-gray-800 flex items-center justify-between text-xs font-mono shrink-0">
						<div class="flex items-center gap-2">
							<span class="text-gray-400">Artifact:</span>
							<select
								bind:value={selectedArtifactIdx}
								class="bg-black/40 border border-gray-700 rounded px-2 py-0.5 text-xs text-purple-300"
							>
								{#each artifactsList as item, idx}
									<option value={idx}>#{idx + 1} - {item.type || 'HTML / Code'}</option>
								{/each}
							</select>
						</div>
						<span class="text-[10px] text-gray-500">
							{selectedArtifactIdx + 1} of {artifactsList.length}
						</span>
					</div>

					<div class="flex-1 w-full bg-white dark:bg-gray-900 overflow-auto flex items-center justify-center p-2">
						{#if artifactsList[selectedArtifactIdx]?.type === 'svg'}
							<div class="max-w-full max-h-full">
								{@html artifactsList[selectedArtifactIdx].content}
							</div>
						{:else}
							<iframe
								srcdoc={artifactsList[selectedArtifactIdx]?.content || ''}
								title="Artifact Document"
								class="w-full h-full border-0 bg-white"
								sandbox="allow-scripts"
							></iframe>
						{/if}
					</div>
				{:else}
					<div class="m-auto text-center space-y-2 text-gray-500 font-mono text-xs">
						<div class="text-3xl">📦</div>
						<div>No HTML/UI artifacts generated in this conversation yet.</div>
						<div class="text-[11px] text-gray-600">Ask SupremeAI to generate code, HTML, or mockups to preview them live.</div>
					</div>
				{/if}
			</div>
		{/if}
	</div>
</div>
