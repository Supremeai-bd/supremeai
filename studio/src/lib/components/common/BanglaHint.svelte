<script lang="ts">
	export let text: string = '';
	export let label: string = 'টিপস';
	let show = false;
</script>

<span
	class="relative inline-flex items-center ml-1 text-slate-400 hover:text-cyan-400 cursor-pointer select-none"
	on:mouseenter={() => (show = true)}
	on:mouseleave={() => (show = false)}
	role="tooltip"
>
	<span class="inline-flex items-center justify-center size-3.5 rounded-full bg-slate-800 text-[9px] font-bold border border-slate-700">
		?
	</span>

	{#if show}
		<div class="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 w-56 p-2 rounded-lg bg-gray-950 border border-cyan-500/30 text-gray-200 text-[11px] font-sans shadow-xl z-50 pointer-events-none backdrop-blur-md">
			<div class="text-[10px] font-bold text-cyan-400 mb-0.5 flex items-center gap-1 font-mono">
				<span>💡</span>
				<span>{label}</span>
			</div>
			<div>{text}</div>
		</div>
	{/if}
</span>

