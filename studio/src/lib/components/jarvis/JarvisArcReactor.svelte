<script lang="ts">
	import { onMount } from 'svelte';

	export type OrbState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'executing' | 'alert';

	export let state: OrbState = 'idle';
	export let size: number = 80;
	export let interactive: boolean = true;
	export let language: 'bn' | 'en' = 'bn';
	export let onToggle: (() => void) | undefined = undefined;

	let canvasEl: HTMLCanvasElement;
	let animationFrameId: number;
	let angle = 0;

	const STATE_THEMES: Record<OrbState, { primary: string; glow: string; speed: number; labelBn: string; labelEn: string }> = {
		idle: {
			primary: 'rgba(34, 211, 238, ', // Cyan (#22d3ee)
			glow: 'rgba(6, 182, 212, 0.4)',
			speed: 0.02,
			labelBn: 'স্ট্যান্ডবাই',
			labelEn: 'STANDBY'
		},
		listening: {
			primary: 'rgba(239, 68, 68, ', // Red pulse (#ef4444)
			glow: 'rgba(248, 113, 113, 0.6)',
			speed: 0.05,
			labelBn: 'শুনছি... কথা বলুন',
			labelEn: 'LISTENING'
		},
		thinking: {
			primary: 'rgba(245, 158, 11, ', // Amber gold (#f59e0b)
			glow: 'rgba(251, 191, 36, 0.5)',
			speed: 0.04,
			labelBn: 'চিন্তা করছি...',
			labelEn: 'THINKING'
		},
		speaking: {
			primary: 'rgba(16, 185, 129, ', // Emerald green (#10b981)
			glow: 'rgba(52, 211, 153, 0.6)',
			speed: 0.035,
			labelBn: 'বলছি...',
			labelEn: 'SPEAKING'
		},
		executing: {
			primary: 'rgba(59, 130, 246, ', // Electric blue (#3b82f6)
			glow: 'rgba(96, 165, 250, 0.6)',
			speed: 0.06,
			labelBn: 'টাস্ক রান হচ্ছে...',
			labelEn: 'EXECUTING'
		},
		alert: {
			primary: 'rgba(255, 45, 64, ', // Critical Red (#ff2d40)
			glow: 'rgba(255, 45, 64, 0.8)',
			speed: 0.08,
			labelBn: 'সতর্কতা / DEFCON 1',
			labelEn: 'ALERT'
		}
	};

	function drawOrb() {
		if (!canvasEl) return;
		const ctx = canvasEl.getContext('2d');
		if (!ctx) return;

		const dpr = window.devicePixelRatio || 1;
		const w = size;
		const h = size;

		if (canvasEl.width !== w * dpr || canvasEl.height !== h * dpr) {
			canvasEl.width = w * dpr;
			canvasEl.height = h * dpr;
		}

		ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
		ctx.clearRect(0, 0, w, h);

		const centerX = w / 2;
		const centerY = h / 2;
		const theme = STATE_THEMES[state] || STATE_THEMES.idle;

		// 1. Central Core Radial Glow
		const coreRadius = (w * 0.35);
		const coreGrad = ctx.createRadialGradient(centerX, centerY, 2, centerX, centerY, coreRadius);
		coreGrad.addColorStop(0, theme.primary + '0.95)');
		coreGrad.addColorStop(0.4, theme.primary + '0.45)');
		coreGrad.addColorStop(1, 'rgba(10, 15, 30, 0)');

		ctx.fillStyle = coreGrad;
		ctx.beginPath();
		ctx.arc(centerX, centerY, coreRadius, 0, Math.PI * 2);
		ctx.fill();

		// 2. Arc Reactor Rotating Outer Ring
		const outerR = w * 0.44;
		ctx.strokeStyle = theme.primary + '0.5)';
		ctx.lineWidth = 1.5;
		ctx.beginPath();
		ctx.arc(centerX, centerY, outerR, 0, Math.PI * 2);
		ctx.stroke();

		// Segmented outer ticks
		const ticks = 16;
		for (let i = 0; i < ticks; i++) {
			const tickAngle = angle + (i * (Math.PI * 2)) / ticks;
			const r1 = outerR - (w * 0.04);
			const r2 = outerR + (w * 0.04);
			const x1 = centerX + Math.cos(tickAngle) * r1;
			const y1 = centerY + Math.sin(tickAngle) * r1;
			const x2 = centerX + Math.cos(tickAngle) * r2;
			const y2 = centerY + Math.sin(tickAngle) * r2;

			ctx.strokeStyle = i % 2 === 0 ? theme.primary + '0.85)' : theme.primary + '0.25)';
			ctx.lineWidth = i % 4 === 0 ? 2 : 1;
			ctx.beginPath();
			ctx.moveTo(x1, y1);
			ctx.lineTo(x2, y2);
			ctx.stroke();
		}

		// 3. Counter-rotating Inner Segmented Ring
		const innerR = w * 0.28;
		ctx.strokeStyle = theme.primary + '0.7)';
		ctx.lineWidth = 1.2;
		ctx.beginPath();
		ctx.arc(centerX, centerY, innerR, 0, Math.PI * 2);
		ctx.stroke();

		const innerTicks = 8;
		for (let j = 0; j < innerTicks; j++) {
			const inAngle = -angle * 1.6 + (j * (Math.PI * 2)) / innerTicks;
			const ix1 = centerX + Math.cos(inAngle) * (innerR - 3);
			const iy1 = centerY + Math.sin(inAngle) * (innerR - 3);
			const ix2 = centerX + Math.cos(inAngle) * (innerR + 3);
			const iy2 = centerY + Math.sin(inAngle) * (innerR + 3);

			ctx.strokeStyle = theme.primary + '0.9)';
			ctx.lineWidth = 1.8;
			ctx.beginPath();
			ctx.moveTo(ix1, iy1);
			ctx.lineTo(ix2, iy2);
			ctx.stroke();
		}

		// 4. Center Micro-Pulse Core
		const pulse = (w * 0.1) + Math.sin(angle * 4) * (w * 0.02);
		ctx.fillStyle = theme.primary + '0.95)';
		ctx.beginPath();
		ctx.arc(centerX, centerY, pulse, 0, Math.PI * 2);
		ctx.fill();

		// White center diode
		ctx.fillStyle = '#ffffff';
		ctx.beginPath();
		ctx.arc(centerX, centerY, 2.5, 0, Math.PI * 2);
		ctx.fill();

		angle += theme.speed;
		animationFrameId = requestAnimationFrame(drawOrb);
	}

	onMount(() => {
		drawOrb();
		return () => {
			if (animationFrameId) cancelAnimationFrame(animationFrameId);
		};
	});
</script>

<div
	role="button"
	tabindex="0"
	class="relative inline-flex flex-col items-center justify-center cursor-pointer select-none group"
	on:click={() => interactive && onToggle?.()}
	on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && interactive && onToggle?.()}
	title={`JARVIS Reactor: ${language === 'bn' ? STATE_THEMES[state]?.labelBn : STATE_THEMES[state]?.labelEn}`}
>
	<canvas
		bind:this={canvasEl}
		style="width: {size}px; height: {size}px;"
		class="transition-transform group-hover:scale-105"
	></canvas>

	{#if size >= 60}
		<div class="mt-1 flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-black/60 border border-white/10 backdrop-blur-md">
			<span class="size-1.5 rounded-full animate-ping" style="background-color: {STATE_THEMES[state]?.glow}"></span>
			<span class="text-[9px] font-mono tracking-wider text-cyan-300 uppercase">
				{language === 'bn' ? STATE_THEMES[state]?.labelBn : STATE_THEMES[state]?.labelEn}
			</span>
		</div>
	{/if}
</div>

