<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import {
		WEBUI_NAME,
		config,
		showSidebar,
		user,
		mobile,
		workspaceActions,
		workspaceCounts
	} from '$lib/stores';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { getModelItems } from '$lib/apis/models';
	import { searchKnowledgeBases } from '$lib/apis/knowledge';
	import { getPromptItems } from '$lib/apis/prompts';
	import { getSkillItems } from '$lib/apis/skills';
	import { getToolList } from '$lib/apis/tools';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Sidebar from '$lib/components/icons/Sidebar.svelte';
	import SplitCreateButton from '$lib/components/common/SplitCreateButton.svelte';
	import { formatNumber } from '$lib/utils';

	const i18n = getContext<Writable<i18nType>>('i18n');

	let loaded = false;
	let lastPath = '';
	let activeWorkspaceSection = '';
	let visibleActions = [];

	$: if ($page.url.pathname !== lastPath) {
		lastPath = $page.url.pathname;
		workspaceActions.set([]);
	}

	$: if (loaded && $page.url.pathname.startsWith('/workspace')) {
		loadWorkspaceCounts();
	}

	$: activeWorkspaceSection = $page.url.pathname.split('/')[2] ?? '';
	$: visibleActions = $workspaceActions.filter((action) => action.visible ?? true);

	const getCount = (res: any) => res?.total ?? (Array.isArray(res) ? res.length : null);
	const formatCount = (count: number | null) => formatNumber(count ?? 0);

	const loadWorkspaceCounts = async () => {
		const canViewModels = $user?.role === 'admin' || $user?.permissions?.workspace?.models;
		const canViewKnowledge = $user?.role === 'admin' || $user?.permissions?.workspace?.knowledge;
		const canViewPrompts = $user?.role === 'admin' || $user?.permissions?.workspace?.prompts;
		const canViewSkills = $user?.role === 'admin' || $user?.permissions?.workspace?.skills;
		const canViewTools =
			$config?.features?.enable_tools &&
			($user?.role === 'admin' || $user?.permissions?.workspace?.tools);

		const [modelRes, knowledgeRes, promptRes, skillRes, toolRes] = await Promise.all([
			canViewModels
				? getModelItems(localStorage.token, null, null, null, null, null, 1).catch(() => null)
				: null,
			canViewKnowledge
				? searchKnowledgeBases(localStorage.token, null, null, 1, null).catch(() => null)
				: null,
			canViewPrompts
				? getPromptItems(localStorage.token, null, null, null, null, null, 1).catch(() => null)
				: null,
			canViewSkills ? getSkillItems(localStorage.token, null, null, 1).catch(() => null) : null,
			canViewTools ? getToolList(localStorage.token).catch(() => null) : null
		]);

		workspaceCounts.set({
			models: getCount(modelRes),
			knowledge: getCount(knowledgeRes),
			prompts: getCount(promptRes),
			skills: getCount(skillRes),
			tools: getCount(toolRes)
		});
	};

	onMount(async () => {
		if ($user?.role !== 'admin') {
			if ($page.url.pathname.includes('/models') && !$user?.permissions?.workspace?.models) {
				goto('/', { replaceState: true });
			} else if (
				$page.url.pathname.includes('/knowledge') &&
				!$user?.permissions?.workspace?.knowledge
			) {
				goto('/', { replaceState: true });
			} else if (
				$page.url.pathname.includes('/prompts') &&
				!$user?.permissions?.workspace?.prompts
			) {
				goto('/', { replaceState: true });
			} else if (
				$page.url.pathname.includes('/tools') &&
				(!$config?.features?.enable_tools || !$user?.permissions?.workspace?.tools)
			) {
				goto('/', { replaceState: true });
			} else if ($page.url.pathname.includes('/skills') && !$user?.permissions?.workspace?.skills) {
				goto('/', { replaceState: true });
			}
		}

		loaded = true;
	});
</script>

<svelte:head>
	<!-- LICENSE covers this Open WebUI browser-title identifier.
	Do not alter, remove, obscure, or replace it except as LICENSE permits:
	https://docs.openwebui.com/license. -->
	<title>
		{$i18n.t('Workspace')} / {$WEBUI_NAME}
	</title>
</svelte:head>

{#if loaded}
	<div
		id="workspace-layout"
		class="flex flex-1 min-w-0 w-full h-screen max-h-[100dvh] transition-width duration-200 ease-in-out {$showSidebar
			? 'md:max-w-[calc(100%-var(--sidebar-width))]'
			: 'md:max-w-[calc(100%-42px)]'} max-w-full"
	>
		<div class="flex h-full min-w-0 flex-1 flex-col">
			<nav class="px-1.5 pt-1.5 backdrop-blur-xl drag-region select-none">
				<div class="flex items-center gap-0.5 md:gap-1">
					{#if $mobile}
						<div class="{$showSidebar ? 'md:hidden' : ''} self-center flex flex-none items-center">
							<Tooltip
								content={$showSidebar ? $i18n.t('Close Sidebar') : $i18n.t('Open Sidebar')}
								interactive={true}
							>
								<button
									id="sidebar-toggle-button"
									class=" cursor-pointer flex rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850 transition cursor-"
									aria-label={$showSidebar ? $i18n.t('Close Sidebar') : $i18n.t('Open Sidebar')}
									on:click={() => {
										showSidebar.set(!$showSidebar);
									}}
								>
									<div class=" self-center p-1.5">
										<Sidebar className="size-4" />
									</div>
								</button>
							</Tooltip>
						</div>
					{/if}

					<div class="flex w-full items-center">
						{#if $user?.role === 'admin'}
							<div class="mr-3 px-2 py-0.5 rounded-md bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 text-xs font-mono font-medium flex items-center gap-1.5 shrink-0">
								<img src="/supremeai-mark.svg" alt="SupremeAI" class="size-3.5" />
								<span>Project: SupremeAI (SSOT)</span>
							</div>
						{/if}

						<div
							class="flex min-w-0 mr-1.5 items-center gap-0.5 md:gap-1 scrollbar-none overflow-x-auto w-fit text-center text-sm font-normal bg-transparent py-1 touch-auto pointer-events-auto"
						>
							{#if $user?.role === 'admin'}
								<!-- Supreme Control Tower & Services Integration -->
								<a
									draggable="false"
									data-sveltekit-keepfocus
									class="min-w-fit px-2.5 py-1 text-xs rounded-lg font-semibold inline-flex items-center gap-1.5 {$page.url.pathname.includes('/tower')
										? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
										: 'text-cyan-400 hover:text-white'} transition select-none"
									href="/tower"
								>
									<img src="/supremeai-mark.svg" alt="Tower" class="size-3.5" />
									<span>Control Tower (17 Services)</span>
								</a>

								<!-- Network & System Diagrams -->
								<a
									draggable="false"
									data-sveltekit-keepfocus
									class="min-w-fit px-2.5 py-1 text-xs rounded-lg font-semibold inline-flex items-center gap-1.5 {$page.url.pathname.includes('/admin/diagrams')
										? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
										: 'text-gray-400 hover:text-white'} transition select-none"
									href="/admin/diagrams"
								>
									<span>🗺️ System Diagrams</span>
								</a>
							{/if}

							<!-- Tab 1: Autonomous Agent Fleet -->
							<a
								draggable="false"
								data-sveltekit-keepfocus
								aria-current={activeWorkspaceSection === 'agents' ? 'page' : null}
								class="min-w-fit px-2.5 py-1 text-xs rounded-lg font-semibold inline-flex items-center gap-1.5 {activeWorkspaceSection ===
								'agents'
									? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
									: 'text-gray-400 hover:text-white'} transition select-none"
								href="/workspace/agents"
							>
								<span>🤖 Autonomous Agents</span>
							</a>

							<!-- Tab 2: Supreme Skills & Tools -->
							<a
								draggable="false"
								data-sveltekit-keepfocus
								aria-current={activeWorkspaceSection === 'supreme-skills' ? 'page' : null}
								class="min-w-fit px-2.5 py-1 text-xs rounded-lg font-semibold inline-flex items-center gap-1.5 {activeWorkspaceSection ===
								'supreme-skills'
									? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
									: 'text-gray-400 hover:text-white'} transition select-none"
								href="/workspace/supreme-skills"
							>
								<span>⚡ Skills & Tools</span>
							</a>

							<!-- Tab: Federation Telemetry & Swarm -->
							<a
								draggable="false"
								data-sveltekit-keepfocus
								aria-current={activeWorkspaceSection === 'telemetry' ? 'page' : null}
								class="min-w-fit px-2.5 py-1 text-xs rounded-lg font-semibold inline-flex items-center gap-1.5 {activeWorkspaceSection ===
								'telemetry'
									? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
									: 'text-gray-400 hover:text-white'} transition select-none"
								href="/workspace/telemetry"
							>
								<span>📡 Telemetry & Swarm</span>
							</a>

							<!-- Tab 3: CI/CD Runners & Pipeline Governance -->
							<a
								draggable="false"
								data-sveltekit-keepfocus
								aria-current={activeWorkspaceSection === 'runners' ? 'page' : null}
								class="min-w-fit px-2.5 py-1 text-xs rounded-lg font-semibold inline-flex items-center gap-1.5 {activeWorkspaceSection ===
								'runners'
									? 'bg-teal-500/20 text-teal-300 border border-teal-500/30'
									: 'text-gray-400 hover:text-white'} transition select-none"
								href="/workspace/runners"
							>
								<span>🏗️ CI/CD Runners (4 Tiers)</span>
							</a>

							<!-- Tab 3: Knowledge Base (RAG) -->
							{#if $user?.role === 'admin' || $user?.permissions?.workspace?.knowledge}
								<a
									draggable="false"
									data-sveltekit-keepfocus
									aria-current={activeWorkspaceSection === 'knowledge' ? 'page' : null}
									class="min-w-fit px-2 py-1 text-xs rounded-lg font-medium inline-flex items-center gap-1.5 {activeWorkspaceSection ===
									'knowledge'
										? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
										: 'text-gray-400 hover:text-white'} transition select-none"
									href="/workspace/knowledge"
								>
									<span>🧠 Knowledge Bases</span>
									<span class="text-[10px] opacity-75 font-mono">
										{formatCount($workspaceCounts.knowledge)}
									</span>
								</a>
							{/if}

							<!-- Tab 4: Prompts & Invariants -->
							{#if $user?.role === 'admin' || $user?.permissions?.workspace?.prompts}
								<a
									draggable="false"
									data-sveltekit-keepfocus
									aria-current={activeWorkspaceSection === 'prompts' ? 'page' : null}
									class="min-w-fit px-2 py-1 text-xs rounded-lg font-medium inline-flex items-center gap-1.5 {activeWorkspaceSection ===
									'prompts'
										? 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
										: 'text-gray-400 hover:text-white'} transition select-none"
									href="/workspace/prompts"
								>
									<span>📜 Prompts & Rules</span>
									<span class="text-[10px] opacity-75 font-mono">
										{formatCount($workspaceCounts.prompts)}
									</span>
								</a>
							{/if}

							<!-- Tab 5: Active Models -->
							{#if $user?.role === 'admin' || $user?.permissions?.workspace?.models}
								<a
									draggable="false"
									data-sveltekit-keepfocus
									aria-current={activeWorkspaceSection === 'models' ? 'page' : null}
									class="min-w-fit px-2 py-1 text-xs rounded-lg font-medium inline-flex items-center gap-1.5 {activeWorkspaceSection ===
									'models'
										? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
										: 'text-gray-400 hover:text-white'} transition select-none"
									href="/workspace/models"
								>
									<span>✨ Models</span>
									<span class="text-[10px] opacity-75 font-mono">
										{formatCount($workspaceCounts.models)}
									</span>
								</a>
							{/if}
						</div>

						<div class="ml-auto flex shrink-0 items-center gap-1">
							<SplitCreateButton actions={visibleActions} />
						</div>
					</div>

					<!-- <div class="flex items-center text-xl font-normal">{$i18n.t('Workspace')}</div> -->
				</div>
			</nav>

			<div
				class="pb-1 flex-1 min-w-0 max-h-full overflow-y-auto overflow-x-hidden"
				class:px-3={!['/workspace/models/create', '/workspace/models/edit'].includes(
					$page.url.pathname
				)}
				id="workspace-container"
			>
				<slot />
			</div>
		</div>
	</div>
{/if}

<style>
	:global(html.high-contrast) a[aria-current='page'] {
		text-decoration-line: underline;
		text-decoration-thickness: 2px;
		text-underline-offset: 3px;
	}
</style>
