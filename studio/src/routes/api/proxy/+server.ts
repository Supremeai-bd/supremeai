import type { RequestHandler } from './$types';

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
		// Basic security check: disallow private IP ranges if needed
		if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
			return new Response(JSON.stringify({ error: 'Invalid protocol' }), { status: 400 });
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

		// Return content stripped of restrictive X-Frame-Options & Content-Security-Policy
		return new Response(body, {
			status: response.status,
			headers: {
				'Content-Type': contentType,
				'Access-Control-Allow-Origin': '*',
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

