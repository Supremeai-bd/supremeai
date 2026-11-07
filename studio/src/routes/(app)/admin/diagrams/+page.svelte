<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { fade } from 'svelte/transition';
	import { toast } from 'svelte-sonner';

	// Mapping diagram categories & definitions (SSOT derived from SupremeAI Architecture Specs)
	interface DiagramItem {
		id: string;
		title: string;
		category: 'network' | 'cicd' | 'stealth' | 'agents' | 'keepwarm';
		description: string;
		code: string;
		badge: string;
	}

	const diagrams: DiagramItem[] = [
		{
			id: 'network-topology',
			title: 'SupremeAI Global Mesh & Network Mapping (SSOT)',
			category: 'network',
			badge: 'Zero-Egress Mesh',
			description: 'Real-time multi-tier topology connecting Cloudflare Edge, Ghost Scraper Fleet, Supabase, Redis, and Render Services with 0% Local-PC dependency.',
			code: `flowchart TD
    Client["Client Devices / IDEs / Open-WebUI"] -->|HTTPS / Port 443| CF["Cloudflare Edge Proxy & WAF (keepwarm mesh)"]
    
    subgraph CLOUDFLARE_ZONE ["Edge Acceleration Layer"]
        CF --> CF_Worker["Keep-Warm Mesh Worker\\n(every 5m ping)"]
        CF --> CF_DNS["Zero-Trust DNS & SSL Tunnel"]
    end
    
    CF -->|SSL Routed| Gateway["SupremeAI API Gateway\\n(supremeai-api.onrender.com)"]
    
    subgraph CORE_MESH ["SupremeAI Core Cloud Federation"]
        Gateway --> Auth["HMAC Key Guard & SHA-256 Validator"]
        Auth --> Router{"Model / Intent Router\\n(/v1/models)"}
        
        Router -->|Tier 1: $0 Cost| ScraperNode["Stealth Scraper Fleet\\n(browser/server.py)"]
        Router -->|Tier 2: Pool Fallback| KeyPool["Multi-Key Squad Pool\\n(service/pool.py)"]
        
        Gateway <--> Redis[(Upstash Redis Cache & Sessions)]
        Gateway <--> Supabase[(Supabase PG + Vector / RLS)]
        Gateway <--> Qdrant[(Qdrant Vector DB / Embeddings)]
    end
    
    subgraph TOWER_PLANE ["Control & Governance Plane"]
        Tower["MCP Control Tower\\n(supremeai-mcp-tower)"]
        Tower <--> Gateway
        Tower <--> Infisical["Infisical Cloud Vault\\n(200+ Encrypted Secrets)"]
    end
    
    subgraph STEALTH_EGRESS ["Stealth Execution Nodes"]
        ScraperNode --> Blaze["Blaze AI Stream (<1.0s, 0% RAM)"]
        ScraperNode --> Ghost["Ghost Tower Sovereign Fleet"]
        ScraperNode --> Residential["Cloudflare Tunnel Accelerator"]
    end

    classDef mesh fill:#0e1e28,stroke:#06b6d4,stroke-width:1.5px,color:#fff;
    classDef edge fill:#1f132b,stroke:#a855f7,stroke-width:1.5px,color:#fff;
    classDef storage fill:#0a2318,stroke:#10b981,stroke-width:1.5px,color:#fff;
    class Gateway,ScraperNode,Tower,KeyPool mesh;
    class CF,CF_Worker,CF_DNS edge;
    class Redis,Supabase,Qdrant,Infisical storage;`
		},
		{
			id: 'runner-execution-tier',
			title: 'Universal 4-Tier CI/CD & Lowest-Runtime Runner',
			category: 'cicd',
			badge: '≤ 20s Cloud Cap',
			description: 'Lowest runtime pipeline allocating 95% of heavy tests to Local-PC Native runner with Render & GitHub Cloud fallback.',
			code: `flowchart TD
    PR["PR Created / Pushed\\n(100,000+ Workflows)"] --> TierCheck{"resolve_execution_tier.py\\nCheck Runner Online"}
    
    TierCheck -- "🟢 Online (95% Work)" --> LocalPC["Priority 1: Local Host (local-pc)\\n• Windows Native Runner\\n• 11,000+ Full Test Battery\\n• 0 GitHub Cloud Mins Spent"]
    
    LocalPC --> LocalPassed{"Local Battery Green?"}
    
    TierCheck -- "🔴 Offline / Quota Fallback" --> CheckRender{"Render CI Quota >= 50m?"}
    
    CheckRender -- "Yes" --> RenderCI["Priority 2: Render CI Pool\\n• srv-dbl8tbmtlv9c73bbkvqg\\n• 500m Free Monthly Pool"]
    CheckRender -- "No" --> GitHubCloud["Priority 3: GitHub Cloud Fallback\\n• Ubuntu 24.04 Last Defense"]
    
    RenderCI --> LocalPassed
    GitHubCloud --> LocalPassed
    
    LocalPassed -- "❌ Test Failed" --> BlockMerge["🚫 Merge BLOCKED (Zero Bad Code Lands)"]
    LocalPassed -- "✅ Tests 100% Green" --> AutoMerge["Autonomous Auto-Landing (≤ 20s)\\n• gh pr merge --squash --delete-branch"]
    
    AutoMerge --> CD_Engine["Harness CD Deploy Engine"]
    CD_Engine --> DeployLive["Production Mesh Live Rollout"]
    
    DeployLive --> HealthCheck{"Live 2xx Probe"}
    HealthCheck -- "Fail / 5xx" --> AutoRollback["Instant Auto-Rollback 🚨"]
    HealthCheck -- "Pass (2xx)" --> AllGreen["System Fully Live & Verified 🟢"]

    classDef pass fill:#064e3b,stroke:#10b981,stroke-width:1.5px,color:#fff;
    classDef gate fill:#3b0764,stroke:#c084fc,stroke-width:1.5px,color:#fff;
    classDef fail fill:#4c0519,stroke:#f43f5e,stroke-width:1.5px,color:#fff;
    class LocalPassed,HealthCheck,TierCheck,CheckRender gate;
    class LocalPC,RenderCI,AutoMerge,AllGreen pass;
    class BlockMerge,AutoRollback fail;`
		},
		{
			id: 'stealth-pipeline',
			title: 'Ghost Scraper Stealth Egress & Anti-Detection Shield',
			category: 'stealth',
			badge: 'Zero-Fingerprint',
			description: 'Chrome 124+ client hints, human micro-jitter, deduplication windowing, and zero-cost web relay routing.',
			code: `flowchart LR
    Req["Incoming Prompt Stream"] --> Dedup["Conversational Deduplication\\n(32KB Rolling Window)"]
    Dedup --> Jitter["Human Micro-Jitter Generator\\n(50ms - 150ms Gaussian Delay)"]
    Jitter --> Fingerprint["Chrome 124+ Client Hints\\n• sec-ch-ua & platform emulation\\n• Random Canvas & Audio Noise"]
    Fingerprint --> CB["Circuit Breaker Sentinel\\n• 15m Cooldown Protection\\n• Error Spike Throttling"]
    
    CB --> RouteTarget{"Target Selection"}
    RouteTarget -->|Primary| Blaze["Blaze AI Stream (<1.0s, 0% Memory)"]
    RouteTarget -->|Secondary| GhostVault["Ghost Tower Fleet (Infisical Synced Cookies)"]
    RouteTarget -->|Fallback| ResidentialTunnel["Local Residential Accelerator Tunnel"]

    classDef shield fill:#172554,stroke:#38bdf8,stroke-width:1.5px,color:#fff;
    class Dedup,Jitter,Fingerprint,CB,RouteTarget shield;`
		},
		{
			id: 'agents-loop',
			title: 'Autonomous Multi-Agent Continuous Loop & Board Invariants',
			category: 'agents',
			badge: 'Single Door SSOT',
			description: 'Self-dispatching continuous loop matching issues with solver, inspector, platform-guardian, rules-breaker, and human-eye.',
			code: `flowchart TD
    Board["GitHub Issues & Public Work Board\\n(Supremeai-bd/supremeai)"] --> Loop["Continuous Agent Loop\\n(continuous_agent_loop.py)"]
    
    subgraph LOOP_ENGINE ["Loop Decision & Dispatch Engine"]
        Loop --> Inspect{"Unclaimed Issues Available?"}
        Inspect -- "Yes" --> Solver["Dispatch: Solver Role\\n(Claim Lease: 30m)"]
        Inspect -- "No" --> Cadence{"Cadence Timers Elapsed?"}
        
        Cadence -->|Every 30m| Guardian["Platform Guardian\\n(17 Service Probes)"]
        Cadence -->|Every 45m| RulesBreaker["Rules Breaker\\n(Red-Team & Security Audit)"]
        Cadence -->|Every 60m| Scout["Ecosystem Scout\\n(Tool & Tech Innovations)"]
        Cadence -->|Every 15m| HumanEye["Human Eye\\n(UX, Visual & Flow Review)"]
    end
    
    Solver --> PatchSubmit["Bridge Submit Patch / CAS baseSha"]
    PatchSubmit --> Verify["3-Tier Verification\\n1. Reflection -> 2. Smoke -> 3. Tests"]
    Verify --> AutoLanding["Autonomous Auto-Landing Gate"]

    classDef agent fill:#311042,stroke:#d946ef,stroke-width:1.5px,color:#fff;
    class Solver,Guardian,RulesBreaker,Scout,HumanEye agent;`
		},
		{
			id: 'keepwarm-mesh',
			title: 'Zero-Cost Cloudflare Keep-Warm Mesh Architecture',
			category: 'keepwarm',
			badge: 'Zero Cold-Start',
			description: 'Persistent 5-minute scheduled keep-warm ping keeping 17 Render and cloud endpoints awake with zero sleep penalty.',
			code: `flowchart LR
    Cron["Cloudflare Cron Trigger\\n(Every 5 Minutes)"] --> Worker["Keepwarm Edge Worker\\n(infrastructure/cloudflare-render-keepwarm)"]
    
    subgraph SERVICES ["Render Free-Tier Services (15m Dormancy Cap)"]
        Worker -->|GET /healthz| Core["Core API (dau7c9ek)"]
        Worker -->|GET /healthz| Gateway["API Gateway (dbappass)"]
        Worker -->|GET /healthz| Tower["MCP Tower (dblb0253)"]
        Worker -->|GET /healthz| Scraper["Scraper Node (dabm7gfq)"]
        Worker -->|GET /healthz| Brain["Tiny Brain (dbirv58a)"]
        Worker -->|GET /healthz| WorkerSvc["Async Worker (dabm7evq)"]
    end
    
    Core & Gateway & Tower & Scraper & Brain & WorkerSvc --> Response{"HTTP Status"}
    Response -- "200 OK (< 250ms)" --> LogSuccess["Telemetry Log: Kept Alive ⚡"]
    Response -- "Non-200 / Timeout" --> Incident["Treat as ACTIVE DEFECT 🚨\\n(Auto File Work Order)"]

    classDef ok fill:#022c22,stroke:#14b8a6,stroke-width:1.5px,color:#fff;
    classDef alert fill:#450a0a,stroke:#f87171,stroke-width:1.5px,color:#fff;
    class LogSuccess ok;
    class Incident alert;`
		}
	];

	let activeDiagramId = diagrams[0].id;
	let activeCategory: 'all' | 'network' | 'cicd' | 'stealth' | 'agents' | 'keepwarm' = 'all';
	let diagramContainer: HTMLDivElement;
	let mermaidInstance: any = null;
	let rendering = false;
	let renderError = '';
	let zoomScale = 1;

	$: activeDiagram = diagrams.find((d) => d.id === activeDiagramId) || diagrams[0];
	$: filteredDiagrams = activeCategory === 'all' 
		? diagrams 
		: diagrams.filter((d) => d.category === activeCategory);

	const initMermaid = async () => {
		try {
			const mermaidModule = await import('mermaid');
			mermaidInstance = mermaidModule.default;
			mermaidInstance.initialize({
				startOnLoad: false,
				theme: 'dark',
				themeVariables: {
					darkMode: true,
					background: '#090d16',
					primaryColor: '#0891b2',
					primaryTextColor: '#f8fafc',
					primaryBorderColor: '#06b6d4',
					lineColor: '#38bdf8',
					secondaryColor: '#1e1b4b',
					tertiaryColor: '#111827',
					fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace'
				},
				securityLevel: 'loose',
				flowchart: {
					htmlLabels: true,
					curve: 'basis'
				}
			});
		} catch (err: any) {
			console.error('Failed to initialize mermaid:', err);
			renderError = err?.message || 'Mermaid engine initialization failed';
		}
	};

	const renderActiveDiagram = async () => {
		if (!mermaidInstance || !activeDiagram) return;
		rendering = true;
		renderError = '';

		await tick();
		try {
			const uniqueId = `mermaid-svg-${activeDiagram.id}-${Date.now()}`;
			const { svg } = await mermaidInstance.render(uniqueId, activeDiagram.code);
			if (diagramContainer) {
				diagramContainer.innerHTML = svg;
				// enhance svg responsiveness
				const svgEl = diagramContainer.querySelector('svg');
				if (svgEl) {
					svgEl.style.width = '100%';
					svgEl.style.height = 'auto';
					svgEl.style.maxHeight = '720px';
				}
			}
		} catch (err: any) {
			console.error('Mermaid render error:', err);
			renderError = err?.message || 'Error parsing diagram syntax';
			if (diagramContainer) {
				diagramContainer.innerHTML = '';
			}
		} finally {
			rendering = false;
		}
	};

	const selectDiagram = (id: string) => {
		activeDiagramId = id;
		zoomScale = 1;
		renderActiveDiagram();
	};

	const copyDiagramCode = async () => {
		try {
			await navigator.clipboard.writeText(activeDiagram.code);
			toast.success('Mermaid diagram definition copied to clipboard');
		} catch {
			toast.error('Failed to copy to clipboard');
		}
	};

	const adjustZoom = (delta: number) => {
		zoomScale = Math.max(0.5, Math.min(2.5, zoomScale + delta));
	};

	const resetZoom = () => {
		zoomScale = 1;
	};

	onMount(async () => {
		await initMermaid();
		await renderActiveDiagram();
	});
</script>

<svelte:head>
	<title>System & Network Diagrams | SupremeAI Admin</title>
</svelte:head>

<div class="min-h-screen bg-transparent p-4 md:p-6 lg:p-8 space-y-6 text-gray-800 dark:text-gray-100 max-w-[1700px] mx-auto">
	<!-- Header Banner -->
	<div class="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-gray-200 dark:border-gray-800/80">
		<div class="space-y-1">
			<div class="flex items-center gap-2.5">
				<div class="p-2 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
					<span class="text-xl">🗺️</span>
				</div>
				<div>
					<h1 class="text-2xl font-bold font-mono tracking-tight text-gray-900 dark:text-white flex items-center gap-2">
						System & Network Diagrams
						<span class="text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 uppercase tracking-widest">
							SSOT Visualizer
						</span>
					</h1>
					<p class="text-xs text-gray-500 dark:text-gray-400">
						Interactive architectural mappings, network mesh topologies, CI/CD runners, and autonomous agent contracts.
					</p>
				</div>
			</div>
		</div>

		<!-- Action Controls -->
		<div class="flex items-center gap-2">
			<button
				on:click={copyDiagramCode}
				class="px-3 py-1.5 rounded-xl border border-gray-200 dark:border-gray-800 bg-white/50 dark:bg-gray-900/60 hover:bg-gray-100 dark:hover:bg-gray-800 text-xs font-mono font-medium transition flex items-center gap-1.5 shadow-xs"
			>
				<span>📋</span>
				<span>Copy Raw Mermaid</span>
			</button>
			<button
				on:click={renderActiveDiagram}
				class="px-3.5 py-1.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-black font-mono font-bold text-xs transition flex items-center gap-1.5 shadow-sm shadow-cyan-500/20"
			>
				<span>🔄</span>
				<span>Re-render</span>
			</button>
		</div>
	</div>

	<!-- Category Filter Bar -->
	<div class="flex items-center gap-2 overflow-x-auto scrollbar-none pb-1 text-xs font-mono">
		<span class="text-gray-500 text-[11px] uppercase tracking-wider mr-1">Filter:</span>
		{#each [
			{ id: 'all', label: 'All Mappings (5)' },
			{ id: 'network', label: '🌐 Network & Mesh' },
			{ id: 'cicd', label: '🏗️ CI/CD Runner Flow' },
			{ id: 'stealth', label: '🥷 Stealth Scraper' },
			{ id: 'agents', label: '🤖 Multi-Agent Loop' },
			{ id: 'keepwarm', label: '⚡ Keep-Warm Mesh' }
		] as tab}
			<button
				on:click={() => (activeCategory = tab.id as any)}
				class="px-3 py-1.5 rounded-xl transition whitespace-nowrap {activeCategory === tab.id
					? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold'
					: 'bg-white/40 dark:bg-gray-900/40 border border-gray-200 dark:border-gray-800 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'}"
			>
				{tab.label}
			</button>
		{/each}
	</div>

	<!-- Main Workspace Grid: Left Selector List & Right Interactive Viewer -->
	<div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
		<!-- Left Diagram Catalog (4 cols) -->
		<div class="lg:col-span-4 space-y-3">
			<div class="text-[11px] font-mono text-gray-500 uppercase tracking-wider px-1">
				Available Diagrams ({filteredDiagrams.length})
			</div>

			<div class="space-y-2 max-h-[750px] overflow-y-auto pr-1">
				{#each filteredDiagrams as diag}
					<button
						on:click={() => selectDiagram(diag.id)}
						class="w-full text-left p-3.5 rounded-2xl border transition group relative {activeDiagramId === diag.id
							? 'bg-cyan-500/10 border-cyan-500/50 dark:bg-cyan-950/20 dark:border-cyan-500/40 shadow-sm'
							: 'bg-white/40 dark:bg-gray-900/40 border-gray-200 dark:border-gray-800/80 hover:border-gray-300 dark:hover:border-gray-700'}"
					>
						<div class="flex items-center justify-between gap-2 mb-1">
							<span class="text-xs font-mono font-bold {activeDiagramId === diag.id ? 'text-cyan-400' : 'text-gray-900 dark:text-white'}">
								{diag.title}
							</span>
							<span class="text-[9px] font-mono px-1.5 py-0.5 rounded bg-black/20 dark:bg-white/5 border border-white/5 text-gray-400 shrink-0">
								{diag.badge}
							</span>
						</div>
						<p class="text-[11px] text-gray-500 dark:text-gray-400 line-clamp-2 leading-relaxed">
							{diag.description}
						</p>

						{#if activeDiagramId === diag.id}
							<div class="absolute left-0 top-3 bottom-3 w-1 bg-cyan-400 rounded-r-full"></div>
						{/if}
					</button>
				{/each}
			</div>

			<!-- Technical Invariant Note -->
			<div class="p-4 rounded-2xl bg-cyan-950/10 border border-cyan-500/20 text-xs space-y-2">
				<div class="flex items-center gap-1.5 text-cyan-400 font-mono font-bold text-[11px]">
					<span>🔒</span>
					<span>Single Monorepo Topology SSOT</span>
				</div>
				<p class="text-[11px] text-gray-400 leading-normal">
					All architecture layouts strictly adhere to the Pure Monorepo model. Zero external satellite repositories remain writable.
				</p>
			</div>
		</div>

		<!-- Right Canvas / Interactive Diagram View (8 cols) -->
		<div class="lg:col-span-8 flex flex-col space-y-3">
			<div class="p-4 rounded-2xl border border-gray-200 dark:border-gray-800 bg-white/40 dark:bg-gray-900/40 backdrop-blur-md flex flex-col min-h-[750px]">
				<!-- Canvas Action Toolbar -->
				<div class="flex items-center justify-between pb-3 border-b border-gray-200 dark:border-gray-800/80 mb-4">
					<div>
						<h3 class="text-sm font-mono font-bold text-gray-900 dark:text-white flex items-center gap-2">
							{activeDiagram.title}
						</h3>
						<p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
							{activeDiagram.description}
						</p>
					</div>

					<!-- Zoom & View Tools -->
					<div class="flex items-center gap-1.5 bg-black/30 p-1 rounded-xl border border-white/10 shrink-0">
						<button
							on:click={() => adjustZoom(-0.15)}
							class="size-7 rounded-lg hover:bg-white/10 flex items-center justify-center text-xs font-mono text-gray-300 transition"
							title="Zoom Out"
						>
							-
						</button>
						<span class="text-[10px] font-mono px-1.5 text-cyan-300 font-semibold min-w-[42px] text-center">
							{Math.round(zoomScale * 100)}%
						</span>
						<button
							on:click={() => adjustZoom(0.15)}
							class="size-7 rounded-lg hover:bg-white/10 flex items-center justify-center text-xs font-mono text-gray-300 transition"
							title="Zoom In"
						>
							+
						</button>
						<button
							on:click={resetZoom}
							class="px-2 py-0.5 rounded-lg hover:bg-white/10 text-[10px] font-mono text-gray-400 hover:text-white transition"
							title="Reset Scale"
						>
							Reset
						</button>
					</div>
				</div>

				<!-- Diagram Render Target Area -->
				<div class="relative flex-1 rounded-xl bg-gray-950/70 border border-gray-800/60 p-6 flex items-center justify-center overflow-auto min-h-[580px]">
					{#if rendering}
						<div class="flex flex-col items-center gap-2 text-cyan-400 font-mono text-xs" in:fade>
							<div class="size-6 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin"></div>
							<span>Compiling & Rendering Architectural Mesh...</span>
						</div>
					{:else if renderError}
						<div class="p-4 rounded-xl bg-rose-950/30 border border-rose-500/40 text-rose-300 max-w-lg text-xs font-mono space-y-2">
							<div class="font-bold flex items-center gap-1.5">
								<span>⚠️</span>
								<span>Diagram Compilation Error</span>
							</div>
							<pre class="overflow-x-auto whitespace-pre-wrap text-[10px] text-rose-200/80 bg-black/40 p-2.5 rounded-lg">{renderError}</pre>
						</div>
					{/if}

					<!-- Scaled Container -->
					<div
						bind:this={diagramContainer}
						class="w-full flex justify-center items-center transition-transform duration-150 origin-center select-none"
						style="transform: scale({zoomScale});"
					></div>
				</div>

				<!-- Bottom Spec Info Footer -->
				<div class="mt-4 pt-3 border-t border-gray-200 dark:border-gray-800/80 flex flex-wrap items-center justify-between text-[11px] font-mono text-gray-500">
					<div class="flex items-center gap-2">
						<span class="size-2 rounded-full bg-emerald-400"></span>
						<span>Engine: Mermaid.js v11 Client-Side Render</span>
					</div>
					<div class="text-cyan-400">
						Single Door SSOT &bull; Live Topological Mapping
					</div>
				</div>
			</div>
		</div>
	</div>
</div>

