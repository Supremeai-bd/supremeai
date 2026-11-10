<script lang="ts">
	import { onMount } from 'svelte';
	import { artifactContents } from '$lib/stores';
	import { toast } from 'svelte-sonner';

	export let url: string = 'http://localhost:3000';

	interface DeviceModel {
		id: string;
		name: string;
		width: number;
		height: number;
		os: 'ios' | 'android';
	}

	const devices: DeviceModel[] = [
		{ id: 'iphone-15-pro', name: 'iPhone 15 Pro', width: 393, height: 852, os: 'ios' },
		{ id: 'pixel-8', name: 'Google Pixel 8', width: 412, height: 915, os: 'android' },
		{ id: 's24-ultra', name: 'Samsung Galaxy S24', width: 412, height: 884, os: 'android' }
	];

	let selectedDevice: DeviceModel = devices[0];
	let orientation: 'portrait' | 'landscape' = 'portrait';
	let currentUrl = url;
	let inputUrl = url;
	let isLoading = false;
	let batteryLevel = 94;
	let currentTime = '09:41';
	let volume = 80;
	let isLocked = false;
	let activeApp: 'browser' | 'home' | 'settings' | 'artifacts' = 'home';
	let artifactsList: any[] = [];
	let selectedArtifactIdx = 0;

	$: frameWidth = orientation === 'portrait' ? `${selectedDevice.width}px` : `${selectedDevice.height}px`;
	$: frameHeight = orientation === 'portrait' ? `${selectedDevice.height}px` : `${selectedDevice.width}px`;

	// Clock simulation
	function updateClock() {
		const now = new Date();
		currentTime = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
	}

	let mobileProxyHtml = '';
	let useMobileProxy = false;
	let isMobileLoading = false;

	const isLocalUrl = (u: string) => {
		return (
			u.includes('localhost') ||
			u.includes('127.0.0.1') ||
			u.startsWith('/') ||
			u.includes('openwebui')
		);
	};

	async function loadMobileUrl(target: string) {
		if (isLocalUrl(target)) {
			useMobileProxy = false;
			currentUrl = target;
		} else {
			isMobileLoading = true;
			useMobileProxy = true;
			try {
				const proxyEndpoint = `/api/proxy?url=${encodeURIComponent(target)}`;
				const res = await fetch(proxyEndpoint);
				if (res.ok) {
					mobileProxyHtml = await res.text();
				} else {
					useMobileProxy = false;
					currentUrl = target;
				}
			} catch {
				useMobileProxy = false;
				currentUrl = target;
			} finally {
				isMobileLoading = false;
			}
		}
	}

	function handleNavigate() {
		let target = inputUrl.trim();
		if (!target.startsWith('http://') && !target.startsWith('https://')) {
			target = `https://${target}`;
			inputUrl = target;
		}
		loadMobileUrl(target);
		activeApp = 'browser';
	}

	function toggleRotate() {
		orientation = orientation === 'portrait' ? 'landscape' : 'portrait';
	}

	function goHome() {
		activeApp = 'home';
	}

	function lockUnlock() {
		isLocked = !isLocked;
	}

	onMount(() => {
		updateClock();
		const timer = setInterval(updateClock, 30000);
		const unsub = artifactContents.subscribe((items) => {
			artifactsList = items || [];
			// Fix (wiring audit 2026-11-11): clamp the selected index when the
			// artifact list shrinks — parity with SideBrowserPreview; without
			// this a stale index renders an undefined artifact in srcdoc.
			if (artifactsList.length > 0 && selectedArtifactIdx >= artifactsList.length) {
				selectedArtifactIdx = artifactsList.length - 1;
			}
		});
		return () => {
			clearInterval(timer);
			unsub();
		};
	});
</script>

<div class="h-full w-full flex flex-col bg-gray-950 text-gray-200 font-sans select-none overflow-hidden">
	<!-- Virtual Mobile Control Toolbar -->
	<div class="h-11 px-3 bg-gray-900/90 border-b border-gray-800 flex items-center justify-between gap-2 shrink-0">
		<!-- Left: Device Select & Rotate -->
		<div class="flex items-center gap-1.5">
			<span class="text-xs font-mono font-bold text-cyan-400 flex items-center gap-1">
				<span>📱</span>
				<span class="hidden sm:inline">Virtual Mobile:</span>
			</span>

			<select
				bind:value={selectedDevice}
				class="bg-black/50 border border-gray-700 rounded-lg px-2 py-1 text-xs font-mono text-gray-300 focus:outline-none focus:border-cyan-500"
			>
				{#each devices as dev}
					<option value={dev}>{dev.name} ({dev.width}×{dev.height})</option>
				{/each}
			</select>

			<button
				on:click={toggleRotate}
				class="px-2 py-1 rounded-lg border border-gray-700 bg-black/30 hover:bg-white/10 text-xs font-mono text-gray-300 transition flex items-center gap-1"
				title="Rotate Phone Orientation"
			>
				<span>🔄</span>
				<span class="hidden md:inline uppercase text-[10px]">{orientation}</span>
			</button>
		</div>

		<!-- Center: Mobile Status & URL when in mobile browser -->
		{#if activeApp === 'browser'}
			<form on:submit|preventDefault={handleNavigate} class="flex-1 max-w-xs mx-2">
				<div class="flex items-center gap-1 bg-black/60 border border-cyan-500/30 rounded-lg px-2 py-0.5 text-xs font-mono">
					<span class="text-[10px] text-gray-500">🌐</span>
					<input
						type="text"
						bind:value={inputUrl}
						class="w-full bg-transparent border-none outline-none text-cyan-300 text-[11px] font-mono"
						placeholder="Mobile URL..."
					/>
				</div>
			</form>
		{/if}

		<!-- Right: Quick Hardware Controls -->
		<div class="flex items-center gap-1 text-xs font-mono">
			<button
				on:click={goHome}
				class="px-2 py-1 rounded-lg border border-gray-700 bg-black/30 hover:bg-white/10 text-gray-300 hover:text-white transition"
				title="Home Screen"
			>
				🏠 Home
			</button>
			<button
				on:click={lockUnlock}
				class="px-2 py-1 rounded-lg border border-gray-700 bg-black/30 hover:bg-white/10 text-gray-300 hover:text-white transition"
				title="Power / Lock Phone"
			>
				{isLocked ? '🔓 Unlock' : '🔒 Power'}
			</button>
		</div>
	</div>

	<!-- Canvas Center: Simulated Smartphone Shell -->
	<div class="flex-1 w-full min-h-0 bg-gradient-to-b from-gray-950 via-gray-900 to-black p-4 flex items-center justify-center overflow-auto relative">
		<!-- Phone Chassis / Bezel -->
		<div
			class="relative bg-black border-[10px] border-gray-800 rounded-[3rem] shadow-[0_25px_60px_-15px_rgba(0,0,0,0.9)] ring-1 ring-white/10 flex flex-col overflow-hidden transition-all duration-300"
			style="width: {frameWidth}; height: {frameHeight}; max-height: 96%; max-width: 98%;"
		>
			{#if isLocked}
				<!-- Lock Screen -->
				<div class="w-full h-full bg-gradient-to-t from-gray-950 via-purple-950/40 to-black flex flex-col items-center justify-between p-8 text-white">
					<div class="text-center space-y-1 mt-10">
						<div class="text-5xl font-light font-mono tracking-tight">{currentTime}</div>
						<div class="text-xs text-purple-300 font-medium">SupremeAI Mobile OS</div>
					</div>

					<button
						on:click={lockUnlock}
						class="px-6 py-2.5 rounded-full bg-white/10 hover:bg-white/20 backdrop-blur-md border border-white/20 text-xs font-medium tracking-wide transition animate-bounce"
					>
						Swipe up to unlock 🔓
					</button>
				</div>
			{:else}
				<!-- Dynamic Island / Top Notch -->
				<div class="h-6 w-full bg-black flex items-center justify-between px-6 text-[10px] font-mono text-gray-400 shrink-0 z-30 select-none">
					<span>{currentTime}</span>

					<!-- Notch Pill -->
					<div class="w-20 h-3.5 bg-gray-900 rounded-full flex items-center justify-center gap-1 border border-white/5">
						<span class="size-1.5 rounded-full bg-blue-500/80"></span>
					</div>

					<!-- Battery & Signal -->
					<div class="flex items-center gap-1.5">
						<span>5G</span>
						<span>{batteryLevel}% 🔋</span>
					</div>
				</div>

				<!-- Phone Main Screen Body -->
				<div class="flex-1 w-full min-h-0 relative bg-gray-900 flex flex-col overflow-hidden">
					{#if activeApp === 'home'}
						<!-- Home Screen with Simulated App Grid -->
						<div class="flex-1 p-6 flex flex-col justify-between bg-gradient-to-br from-gray-950 via-slate-900 to-purple-950/60">
							<div class="grid grid-cols-4 gap-4 pt-4 text-center">
								<!-- App 1: Safari / Web Browser -->
								<button
									on:click={() => (activeApp = 'browser')}
									class="flex flex-col items-center gap-1.5 group"
								>
									<div class="size-14 rounded-2xl bg-gradient-to-tr from-blue-600 to-cyan-400 flex items-center justify-center text-2xl shadow-lg group-hover:scale-105 transition">
										🧭
									</div>
									<span class="text-[10px] text-gray-300 font-medium truncate w-full">Browser</span>
								</button>

								<!-- App 2: Code Artifacts -->
								<button
									on:click={() => (activeApp = 'artifacts')}
									class="flex flex-col items-center gap-1.5 group"
								>
									<div class="size-14 rounded-2xl bg-gradient-to-tr from-purple-600 to-pink-500 flex items-center justify-center text-2xl shadow-lg group-hover:scale-105 transition">
										⚡
									</div>
									<span class="text-[10px] text-gray-300 font-medium truncate w-full">Artifacts</span>
								</button>

								<!-- App 3: Camera -->
								<button
									on:click={() => toast.info('Mobile Camera simulated')}
									class="flex flex-col items-center gap-1.5 group"
								>
									<div class="size-14 rounded-2xl bg-gradient-to-tr from-gray-700 to-gray-500 flex items-center justify-center text-2xl shadow-lg group-hover:scale-105 transition">
										📷
									</div>
									<span class="text-[10px] text-gray-300 font-medium truncate w-full">Camera</span>
								</button>

								<!-- App 4: Settings -->
								<button
									on:click={() => (activeApp = 'settings')}
									class="flex flex-col items-center gap-1.5 group"
								>
									<div class="size-14 rounded-2xl bg-gradient-to-tr from-slate-700 to-slate-600 flex items-center justify-center text-2xl shadow-lg group-hover:scale-105 transition">
										⚙️
									</div>
									<span class="text-[10px] text-gray-300 font-medium truncate w-full">Settings</span>
								</button>
							</div>

							<!-- Bottom Dock -->
							<div class="p-3 bg-white/10 backdrop-blur-xl rounded-3xl border border-white/10 flex items-center justify-around mb-2">
								<button on:click={() => (activeApp = 'browser')} class="size-11 rounded-2xl bg-blue-500 flex items-center justify-center text-xl">
									🌐
								</button>
								<button on:click={() => (activeApp = 'artifacts')} class="size-11 rounded-2xl bg-purple-500 flex items-center justify-center text-xl">
									⚡
								</button>
								<button on:click={() => (activeApp = 'settings')} class="size-11 rounded-2xl bg-gray-600 flex items-center justify-center text-xl">
									⚙️
								</button>
							</div>
						</div>
					{:else if activeApp === 'browser'}
						<!-- Running Mobile Browser App -->
						<div class="w-full h-full flex flex-col bg-white relative">
							{#if isMobileLoading}
								<div class="absolute inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center text-cyan-400 text-xs font-mono z-20">
									Loading page via proxy...
								</div>
							{/if}
							{#if useMobileProxy && mobileProxyHtml}
								<iframe
									title="Virtual Mobile Browser Frame Proxied"
									srcdoc={mobileProxyHtml}
									class="w-full flex-1 border-0"
									sandbox="allow-scripts allow-forms allow-popups"
								></iframe>
							{:else}
								<iframe
									src={currentUrl}
									title="Virtual Mobile Browser Frame"
									class="w-full flex-1 border-0"
									sandbox="allow-scripts allow-forms allow-popups"
								></iframe>
							{/if}
						</div>
					{:else if activeApp === 'artifacts'}
						<!-- Running Artifacts App -->
						<div class="w-full h-full flex flex-col bg-gray-900 text-white">
							<div class="p-3 bg-gray-950 border-b border-gray-800 text-xs font-mono flex justify-between items-center">
								<span>⚡ Generated Mobile Artifacts</span>
								<span class="text-purple-400">{artifactsList.length} items</span>
							</div>
							<div class="flex-1 overflow-auto p-4">
								{#if artifactsList.length > 0}
									<iframe
										srcdoc={artifactsList[selectedArtifactIdx]?.content || ''}
										title="Mobile Artifact View"
										class="w-full h-full border-0 bg-white rounded-xl"
										sandbox="allow-scripts"
									></iframe>
								{:else}
									<div class="text-center text-gray-500 text-xs mt-20">
										No code artifacts generated in current chat.
									</div>
								{/if}
							</div>
						</div>
					{:else if activeApp === 'settings'}
						<!-- Mobile Settings App -->
						<div class="w-full h-full bg-black p-6 text-white space-y-4">
							<h3 class="text-base font-bold">Settings</h3>
							<div class="p-4 rounded-xl bg-gray-900 border border-gray-800 space-y-3 text-xs font-mono">
								<div class="flex justify-between">
									<span class="text-gray-400">Model:</span>
									<span class="text-cyan-400 font-bold">{selectedDevice.name}</span>
								</div>
								<div class="flex justify-between">
									<span class="text-gray-400">Virtual OS:</span>
									<span class="text-purple-400">{selectedDevice.os === 'ios' ? 'iOS 18.2' : 'Android 15'}</span>
								</div>
								<div class="flex justify-between">
									<span class="text-gray-400">Resolution:</span>
									<span>{selectedDevice.width} × {selectedDevice.height}</span>
								</div>
							</div>
						</div>
					{/if}
				</div>

				<!-- Bottom Home Bar / Gesture Pill -->
				<div
					on:click={goHome}
					class="h-5 w-full bg-black flex items-center justify-center shrink-0 cursor-pointer hover:bg-gray-900 transition"
					title="Click to go Home"
				>
					<div class="w-32 h-1 bg-white/60 rounded-full hover:bg-white transition"></div>
				</div>
			{/if}
		</div>
	</div>
</div>

