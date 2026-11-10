import type { RequestHandler } from './$types';

// Security hardening (audit 2026-11-11): this endpoint previously fetched ANY
// URL server-side with no private-network protection — an unauthenticated SSRF
// open relay (cloud metadata 169.254.169.254, localhost, RFC1918). Targets are
// now validated by hostname literal AND by resolved IP (anti DNS-rebinding).
const BLOCKED_HOSTNAMES = new Set([
	'localhost',
	'127.0.0.1',
	'0.0.0.0',
	'::1',
	'[::1]',
	'169.254.169.254',
	'metadata.google.internal',
	'metadata.goog'
]);

const isPrivateIp = (host: string): boolean => {
	const ipv4 = host.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
	if (ipv4) {
		const a = Number(ipv4[1]);
		const b = Number(ipv4[2]);
		if (a === 0 || a === 10 || a === 127) return true;
		if (a === 169 && b === 254) return true; // link-local incl. cloud metadata
		if (a === 172 && b >= 16 && b <= 31) return true;
		if (a === 192 && b === 168) return true;
		if (a === 100 && b >= 64 && b <= 127) return true; // CGNAT
		if (a >= 224) return true; // multicast + reserved
		return false;
	}
	// IPv6: loopback, unique-local (fc00::/7), link-local (fe80::/10)
	return /^(::1|f[cd][0-9a-f]{2}:|fe80:)/i.test(host);
};

export const GET: RequestHandler = async ({ url, fetch }) => {
	const targetUrl = url.searchParams.get('url');

	if (!targetUrl) {
		return new Response(JSON.stringify({ error: 'Missing url parameter' }), {
			status: 400,
			headers: { 'Content-Type': 'application/json' }
		});
	}

	try {
		const parsed = new URL(targetUrl);
		if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
			return new Response(JSON.stringify({ error: 'Invalid protocol' }), { status: 400 });
		}

		const hostname = parsed.hostname.toLowerCase();
		if (
			BLOCKED_HOSTNAMES.has(hostname) ||
			hostname.endsWith('.internal') ||
			hostname.endsWith('.local') ||
			hostname.endsWith('.localhost') ||
			isPrivateIp(hostname)
		) {
			return new Response(JSON.stringify({ error: 'Forbidden target' }), { status: 403 });
		}

		// Resolve DNS and reject targets whose addresses are private/loopback.
		// Fail-closed: if resolution fails, the fetch is refused.
		const { lookup } = await import('node:dns/promises');
		try {
			const resolved = await lookup(hostname, { all: true });
			if (resolved.length === 0 || resolved.some((entry) => isPrivateIp(entry.address))) {
				return new Response(JSON.stringify({ error: 'Forbidden target' }), { status: 403 });
			}
		} catch {
			return new Response(JSON.stringify({ error: 'DNS resolution failed' }), { status: 400 });
		}

		const response = await fetch(targetUrl, {
			headers: {
				'User-Agent':
					'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 SupremeAI/2.0'
			}
		});

		const contentType = response.headers.get('content-type') || 'text/html';
		let body = await response.text();

		// Inject <base> tag so relative CSS, JS, and image assets resolve to the target domain
		if (contentType.includes('text/html')) {
			const baseTag = `<base href="${targetUrl}">`;
			if (body.includes('<head>')) {
				body = body.replace('<head>', `<head>${baseTag}`);
			} else if (body.includes('<html>')) {
				body = body.replace('<html>', `<html><head>${baseTag}</head>`);
			} else {
				body = `${baseTag}${body}`;
			}
		}

		// Return content stripped of restrictive X-Frame-Options & Content-Security-Policy.
		// No Access-Control-Allow-Origin: consumers are same-origin; a public ACAO
		// turned this endpoint into a cross-origin reading relay.
		return new Response(body, {
			status: response.status,
			headers: {
				'Content-Type': contentType,
				'X-SupremeAI-Proxy': 'true'
			}
		});
	} catch (err: any) {
		return new Response(
			JSON.stringify({ error: 'Proxy fetch failed', message: err?.message || String(err) }),
			{
				status: 502,
				headers: { 'Content-Type': 'application/json' }
			}
		);
	}
};
