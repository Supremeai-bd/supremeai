// SupremeAI — Canonical Sovereign Model Registry & Branding Utility
// SSOT: docs/SUPREMEAI_UNIFIED_CHAT_PIPELINE_SSOT.md
// Invariant 1: Zero External Provider Branding (no OpenAI, Gemini, Claude, Groq names in public UI)
// Invariant 2: Standardized Sovereign Badges (Blaze stream, Ghost relay, Deep Research, Enterprise)

export interface SupremeModel {
	id: string;
	name: string;
	tier: 'Autonomous' | 'Ultra-Fast' | 'Zero-Cost Web' | 'Reasoning' | 'Enterprise Pool';
	latency: string;
	description: string;
	routingTarget: string;
	badge: string;
	isDefault?: boolean;
}

export const SOVEREIGN_MODELS: SupremeModel[] = [
	{
		id: 'auto',
		name: 'SupremeAI Auto (Autonomous Tier)',
		tier: 'Autonomous',
		latency: '~0.8 – 1.8s',
		description: 'Dynamic smart router autonomously selecting the optimal tier based on prompt complexity.',
		routingTarget: 'Dynamic Smart Router',
		badge: 'SupremeAI Auto Router',
		isDefault: true
	},
	{
		id: 'supremeai-turbo',
		name: 'SupremeAI Turbo (Blaze Stream)',
		tier: 'Ultra-Fast',
		latency: '~0.8 – 1.2s',
		description: 'Ultra-fast stream for rapid coding, autocomplete, quick Q&A, and terminal commands.',
		routingTarget: 'Blaze AI Stream (<1.0s, 0% RAM bloat)',
		badge: 'SupremeAI w.bz Turbo'
	},
	{
		id: 'supremeai-webhook',
		name: 'SupremeAI Webhook (Zero-Cost Web)',
		tier: 'Zero-Cost Web',
		latency: '~1.0 – 2.0s',
		description: 'Ghost Tower stealth relay worker with Infisical synced cookies for zero-cost conversational assistance.',
		routingTarget: 'Ghost Tower Sovereign Fleet',
		badge: 'SupremeAI w.dk Turbo'
	},
	{
		id: 'supremeai-deep-research',
		name: 'SupremeAI Deep Research (Reasoning)',
		tier: 'Reasoning',
		latency: '~3.0 – 6.0s',
		description: 'Deep synthesis session for architectural refactoring, multi-file codebase analysis, and debugging.',
		routingTarget: 'Deep Synthesis Session Relay',
		badge: 'SupremeAI w.ge Deep-Research'
	},
	{
		id: 'supremeai-api',
		name: 'SupremeAI API (Enterprise Dynamic Squad)',
		tier: 'Enterprise Pool',
		latency: '~1.0 – 2.5s',
		description: 'Sovereign multi-key enterprise pool with dedicated throughput and high concurrency fallback.',
		routingTarget: 'Sovereign Multi-Key Squad Pool',
		badge: 'SupremeAI api.sq Enterprise'
	}
];

export const SOVEREIGN_MODEL_IDS = SOVEREIGN_MODELS.map((m) => m.id);

/**
 * Strips raw upstream provider names to prevent leaks.
 */
export function sanitizeModelName(rawName: string): string {
	if (!rawName) return 'SupremeAI Auto';
	const lower = rawName.toLowerCase();

	if (lower.includes('deep-research') || lower.includes('reason') || lower.includes('opus')) {
		return 'SupremeAI Deep Research';
	}
	if (lower.includes('turbo') || lower.includes('flash') || lower.includes('blaze')) {
		return 'SupremeAI Turbo';
	}
	if (lower.includes('webhook') || lower.includes('relay') || lower.includes('ghost')) {
		return 'SupremeAI Webhook';
	}
	if (lower.includes('api') || lower.includes('enterprise') || lower.includes('pool')) {
		return 'SupremeAI API Enterprise';
	}
	return 'SupremeAI Auto';
}

