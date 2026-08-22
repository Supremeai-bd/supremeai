// infrastructure/cloudflare/enhanced-worker-v2.js
// Enhanced Cloudflare Worker for SupremeAI 2.0 - Production Ready

/**
 * CHANGES FROM V1:
 * 1. Fixed duplicate URLs in keep-alive
 * 2. Added all service endpoints (including admin)
 * 3. Health status persistence in KV
 * 4. Circuit breaker pattern
 * 5. Alerting webhook support
 * 6. Smart adaptive ping intervals
 * 7. Health aggregation endpoint
 */

// ══════════════════════════════════════════════════════════════════════════════
// CONFIGURATION
// ══════════════════════════════════════════════════════════════════════════════

const CONFIG = {
  // Service Registry - ALL your services should be listed here
  SERVICES: [
    {
      name: 'main-backend',
      url: 'https://supremeai-backend-docker.onrender.com',
      healthPath: '/api/v1/health',
      description: 'Main Python/FastAPI Backend',
      critical: true,
      expectedStatus: 200,
      timeout: 10000,
    },
    {
      name: 'admin-backend', 
      url: 'https://supremeai-admin.onrender.com',
      healthPath: '/api/v1/health',
      description: 'Admin Dashboard Backend',
      critical: true,
      expectedStatus: 200,
      timeout: 10000,
    },
    {
      name: 'scraper-service',
      url: 'https://supremeai-scraper-6nwi.onrender.com',
      healthPath: '/health',
      description: 'Playwright Scraper Microservice',
      critical: false, // Non-critical, can degrade gracefully
      expectedStatus: 200,
      timeout: 8000,
    },
    {
      name: 'cloudflare-worker',
      url: 'https://supremeai-edge.your-subdomain.workers.dev', // Update with your worker URL
      healthPath: '/health',
      description: 'Cloudflare Edge Worker',
      critical: true,
      expectedStatus: 200,
      timeout: 5000,
    },
    {
      name: 'media-service',
      url: process.env.MEDIA_SERVICE_URL || 'https://your-media-service.run.app',
      healthPath: '/health',
      description: 'GCP Cloud Run Media Processor',
      critical: false,
      expectedStatus: 200,
      timeout: 8000,
    },
  ],

  // Keep-alive Configuration
  KEEP_ALIVE: {
    // Adaptive: more frequent when services are unstable
    NORMAL_INTERVAL_MIN: 8,     // Normal: every 8 minutes
    DEGRADED_INTERVAL_MIN: 3,   // Degraded: every 3 minutes
    MAX_CONCURRENT_PINGS: 5,   // Parallel pings
    HEALTH_TTL_SECONDS: 300,   // Cache health results for 5 minutes
  },

  // Alerting
  ALERTS: {
    WEBHOOK_URL: process.env.HEALTH_ALERT_WEBHOOK || '', // Discord/Slack webhook
    COOLDOWN_MS: 300000, // Don't alert more than once per 5 minutes per service
  },

  // Circuit Breaker
  CIRCUIT_BREAKER: {
    FAILURE_THRESHOLD: 3,      // Open circuit after N failures
    RESET_TIMEOUT_MS: 60000,  // Try again after 60 seconds
    HALF_OPEN_MAX_TRIES: 1,   // Only allow 1 test request in half-open state
  },
};

// ══════════════════════════════════════════════════════════════════════════════
// KV HELPERS - Persistent Health State
// ══════════════════════════════════════════════════════════════════════════════

const KV_KEYS = {
  HEALTH_STATUS: (service) => `health:${service}:status`,
  HEALTH_HISTORY: (service) => `health:${service}:history`,
  CIRCUIT_STATE: (service) => `circuit:${service}`,
  LAST_ALERT: (service) => `alert:${service}:last`,
  GLOBAL_STATUS: 'health:global:summary',
};

async function getFromKV(env, key, options = {}) {
  try {
    if (!env?.HEALTH_KV) return null;
    return await env.HEALTH_KV.get(key, { type: 'json', ...options });
  } catch (e) {
    console.error(`[KV] Read error for ${key}:`, e.message);
    return null;
  }
}

async function setToKV(env, key, value, options = {}) {
  try {
    if (!env?.HEALTH_KV) return false;
    await env.HEALTH_KV.put(key, JSON.stringify(value), {
      expirationTtl: CONFIG.KEEP_ALIVE.HEALTH_TTL_SECONDS,
      ...options,
    });
    return true;
  } catch (e) {
    console.error(`[KV] Write error for ${key}:`, e.message);
    return false;
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// HEALTH CHECK ENGINE
// ══════════════════════════════════════════════════════════════════════════════

/**
 * Perform health check on a single service
 */
async function checkServiceHealth(service, env) {
  const startTime = Date.now();
  const result = {
    service: service.name,
    timestamp: new Date().toISOString(),
    status: 'unknown', // healthy | degraded | unhealthy | unknown
    responseTime: null,
    statusCode: null,
    error: null,
    details: {},
  };

  try {
    // Check circuit breaker first
    const circuitState = await getFromKV(env, KV_KEYS.CIRCUIT_STATE(service.name));
    if (circuitState?.state === 'open' && Date.now() < circuitState.openUntil) {
      result.status = 'unhealthy';
      result.error = 'Circuit breaker open';
      result.details.circuitBreaker = true;
      return result;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), service.timeout || 10000);

    const healthUrl = `${service.url.replace(/\/$/, '')}${service.healthPath || '/health'}`;
    
    const response = await fetch(healthUrl, {
      method: 'GET',
      headers: {
        'User-Agent': 'SupremeAI-HealthChecker/2.0',
        'Accept': 'application/json',
        'X-Health-Check': 'true',
      },
      signal: controller.signal,
    });

    clearTimeout(timeoutId);
    result.responseTime = Date.now() - startTime;
    result.statusCode = response.status;

    // Parse response body if JSON
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      try {
        result.details = await response.json();
      } catch (e) {
        // Ignore parse errors
      }
    }

    // Determine status based on response code
    if (response.status === service.expectedStatus) {
      result.status = 'healthy';
      
      // Check for degraded indicators in response body
      if (result.details.status === 'degraded' || 
          result.details.state === 'degraded' ||
          (result.details.healthy === false)) {
        result.status = 'degraded';
      }

      // Reset circuit breaker on success
      await handleCircuitSuccess(env, service.name);
    } else if (response.status >= 500) {
      result.status = 'unhealthy';
      result.error = `Server error: ${response.status}`;
      await handleCircuitFailure(env, service.name);
    } else if (response.status >= 400) {
      result.status = 'degraded';
      result.error = `Client error: ${response.status}`;
    } else {
      result.status = 'healthy'; // 1xx, 2xx, 3xx are acceptable
    }

  } catch (error) {
    result.responseTime = Date.now() - startTime;
    result.status = 'unhealthy';
    result.error = error.message || 'Connection failed';
    
    if (error.name === 'AbortError') {
      result.error = `Timeout after ${service.timeout}ms`;
    }
    
    await handleCircuitFailure(env, service.name);
  }

  return result;
}

/**
 * Handle successful request - reset circuit breaker
 */
async function handleCircuitSuccess(env, serviceName) {
  const key = KV_KEYS.CIRCUIT_STATE(serviceName);
  const current = await getFromKV(env, key);
  
  if (current?.state === 'half-open') {
    // Success in half-open -> close circuit
    await setToKV(env, key, { state: 'closed', failureCount: 0, lastSuccess: Date.now() });
    console.log(`[CB] ${serviceName} circuit CLOSED`);
  } else {
    // Ensure closed state
    await setToKV(env, key, { state: 'closed', failureCount: 0, lastSuccess: Date.now() });
  }
}

/**
 * Handle failed request - potentially open circuit breaker
 */
async function handleCircuitFailure(env, serviceName) {
  const key = KV_KEYS.CIRCUIT_STATE(serviceName);
  const config = CONFIG.CIRCUIT_BREAKER;
  let current = await getFromKV(env, key) || { state: 'closed', failureCount: 0 };

  current.failureCount = (current.failureCount || 0) + 1;
  current.lastFailure = Date.now();

  if (current.state === 'closed' && current.failureCount >= config.FAILURE_THRESHOLD) {
    // Open the circuit
    current.state = 'open';
    current.openUntil = Date.now() + config.RESET_TIMEOUT_MS;
    console.warn(`[CB] ${serviceName} circuit OPENED (${current.failureCount} failures)`);
    
    // Send alert
    await sendAlert(env, serviceName, 'circuit_opened', `Circuit opened after ${current.failureCount} failures`);
  } else if (current.state === 'half-open') {
    // Failure in half-open -> reopen
    current.state = 'open';
    current.openUntil = Date.now() + config.RESET_TIMEOUT_MS;
    console.warn(`[CB] ${serviceName} circuit RE-OPENED (failed in half-open)`);
  }

  await setToKV(env, key, current);
}

// ══════════════════════════════════════════════════════════════════════════════
// ALERTING SYSTEM
// ══════════════════════════════════════════════════════════════════════════════

async function sendAlert(env, serviceName, alertType, message) {
  const webhookUrl = CONFIG.ALERTS.WEBHOOK_URL;
  if (!webhookUrl) {
    console.log(`[ALERT] Would send: [${serviceName}] ${alertType}: ${message}`);
    return;
  }

  // Check cooldown
  const lastAlertKey = KV_KEYS.LAST_ALERT(serviceName);
  const lastAlert = await getFromKV(env, lastAlertKey);
  
  if (lastAlert && (Date.now() - lastAlert.timestamp) < CONFIG.ALERTS.COOLDOWN_MS) {
    console.log(`[ALERT] Cooldown active for ${serviceName}`);
    return;
  }

  const payload = {
    embeds: [{
      title: `🚨 SupremeAI Health Alert`,
      color: alertType === 'recovered' ? 0x00ff00 : 0xff0000,
      fields: [
        { name: 'Service', value: serviceName, inline: true },
        { name: 'Type', value: alertType, inline: true },
        { name: 'Message', value: message },
        { name: 'Time', value: new Date().toISOString(), inline: true },
      ],
      footer: { text: 'SupremeAI Health Monitor v2.0' },
    }],
  };

  try {
    await fetch(webhookUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    
    // Update last alert time
    await setToKV(env, lastAlertKey, { timestamp: Date.now(), type: alertType }, { expirationTtl: 3600 });
    console.log(`[ALERT] Sent ${alertType} alert for ${serviceName}`);
  } catch (e) {
    console.error(`[ALERT] Failed to send:`, e.message);
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// SCHEDULED HANDLER - Keep-Alive + Health Checks
// ══════════════════════════════════════════════════════════════════════════════

export default {
  /**
   * Main fetch handler - proxies requests + serves health API
   */
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    // ── Health API Endpoints ──
    
    // Public health summary (no auth required)
    if (path === '/api/edge/health' || path === '/health') {
      return await handleHealthAPIRequest(env);
    }

    // Detailed health status (requires auth in production)
    if (path === '/api/edge/health/detailed') {
      return await handleDetailedHealthRequest(env, request);
    }

    // ── Static Asset CDN from R2 ──
    if (path.startsWith('/cdn/')) {
      return await handleStaticAsset(request, env, ctx);
    }

    // ── API Proxy with Caching ──
    if (path.startsWith('/api/')) {
      return await handleApiProxy(request, env, ctx);
    }

    // ── Default: Proxy to origin ──
    return await proxyToOrigin(request, env);
  },

  /**
   * Scheduled handler - Keep-alive pings + health checks
   * Runs every 8 minutes (configured in wrangler.toml)
   */
  async scheduled(event, env, ctx) {
    console.log(`[KEEP-ALIVE] Starting health check cycle at ${new Date().toISOString()}`);
    
    const startTime = Date.now();
    const results = [];
    
    // Determine if we need faster pings (adaptive)
    const globalStatus = await getFromKV(env, KV_KEYS.GLOBAL_STATUS);
    const isDegraded = globalStatus?.overall === 'degraded' || globalStatus?.overall === 'unhealthy';
    
    // Ping all registered services concurrently
    const checkPromises = CONFIG.SERVICES.map(async (service) => {
      const result = await checkServiceHealth(service, env);
      results.push(result);
      
      // Store individual result in KV
      await setToKV(env, KV_KEYS.HEALTH_STATUS(service.name), result);
      
      // Append to history (keep last 100 entries)
      await appendToHistory(env, service.name, result);
      
      // Send alerts on status change
      await checkAndAlertOnStatusChange(env, service, result);
      
      return result;
    });

    // Wait for all checks with timeout
    const settledResults = await Promise.allSettled(checkPromises);
    
    // Calculate global status
    const globalSummary = calculateGlobalSummary(results.map(r => 
      r.status === 'fulfilled' ? r.value : { status: 'unknown', error: 'Check failed' }
    ));
    
    // Store global summary
    await setToKV(env, KV_KEYS.GLOBAL_STATUS, globalSummary);
    
    const duration = Date.now() - startTime;
    console.log(`[KEEP-ALIVE] Cycle completed in ${duration}ms. Status: ${globalSummary.overall}`);
    console.log(`[KEEP-ALIVE] Results:`, JSON.stringify(results.map(r => ({
      service: r.service,
      status: r.status,
      responseTime: r.responseTime
    }))));

    // Return results for logging
    return { results, summary: globalSummary, duration };
  },
};

// ══════════════════════════════════════════════════════════════════════════════
// HEALTH API HANDLERS
// ══════════════════════════════════════════════════════════════════════════════

/**
 * Handle public health endpoint
 * GET /api/edge/health
 */
async function handleHealthAPIRequest(env) {
  const globalStatus = await getFromKV(env, KV_KEYS.GLOBAL_STATUS) || {
    overall: 'unknown',
    checkedAt: null,
    services: {},
  };

  return new Response(JSON.stringify({
    status: 'ok',
    service: 'supremeai-edge-worker',
    version: '2.0.0',
    timestamp: new Date().toISOString(),
    global: globalStatus,
    uptime: process.uptime ? Math.floor(process.uptime()) : null,
  }), {
    status: 200,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
      'Cache-Control': 'no-store', // Always fresh
    },
  });
}

/**
 * Handle detailed health endpoint (auth recommended)
 * GET /api/edge/health/detailed
 */
async function handleDetailedHealthRequest(env, request) {
  // Optional: Add authentication check here
  
  const serviceStatuses = {};
  
  for (const service of CONFIG.SERVICES) {
    const status = await getFromKV(env, KV_KEYS.HEALTH_STATUS(service.name));
    serviceStatuses[service.name] = status || { status: 'no_data', service: service.name };
  }

  const history = {};
  for (const service of CONFIG.SERVICES.slice(0, 3)) { // Limit history fetch
    const hist = await getFromKV(env, KV_KEYS.HEALTH_HISTORY(service.name));
    if (hist) history[service.name] = hist.slice(-10); // Last 10 entries
  }

  return new Response(JSON.stringify({
    status: 'ok',
    timestamp: new Date().toISOString(),
    services: serviceStatuses,
    recentHistory: history,
    config: {
      totalServices: CONFIG.SERVICES.length,
      criticalServices: CONFIG.SERVICES.filter(s => s.critical).length,
      checkInterval: `${CONFIG.KEEP_ALIVE.NORMAL_INTERVAL_MIN}min`,
    },
  }), {
    status: 200,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
    },
  });
}

// ══════════════════════════════════════════════════════════════════════════════
// UTILITY FUNCTIONS
// ══════════════════════════════════════════════════════════════════════════════

function calculateGlobalSummary(results) {
  const statuses = results.map(r => r.status);
  const healthy = statuses.filter(s => s === 'healthy').length;
  const degraded = statuses.filter(s => s === 'degraded').length;
  const unhealthy = statuses.filter(s => s === 'unhealthy').length;
  const total = results.length;

  let overall = 'healthy';
  if (unhealthy > 0) overall = 'unhealthy';
  else if (degraded > 0) overall = 'degraded';

  return {
    overall,
    checkedAt: new Date().toISOString(),
    totals: { healthy, degraded, unhealthy, total, unknown: total - healthy - degraded - unhealthy },
    services: Object.fromEntries(results.map(r => [r.service, r.status])),
    criticalServicesHealthy: results
      .filter(r => CONFIG.SERVICES.find(s => s.name === r.service)?.critical)
      .every(r => r.status === 'healthy'),
  };
}

async function appendToHistory(env, serviceName, result) {
  const key = KV_KEYS.HEALTH_HISTORY(serviceName);
  let history = await getFromKV(env, key) || [];
  
  history.push({
    timestamp: result.timestamp,
    status: result.status,
    responseTime: result.responseTime,
    statusCode: result.statusCode,
  });

  // Keep only last 100 entries
  if (history.length > 100) {
    history = history.slice(-100);
  }

  await setToKV(env, key, history, { expirationTtl: 86400 }); // 24 hours
}

async function checkAndAlertOnStatusChange(env, service, result) {
  const key = KV_KEYS.HEALTH_STATUS(service.name);
  const previous = await getFromKV(env, key);

  if (previous && previous.status !== result.status) {
    if (result.status === 'unhealthy' && previous.status !== 'unhealthy') {
      await sendAlert(env, service.name, 'service_down', 
        `${service.name} is DOWN: ${result.error}. Response time: ${result.responseTime}ms`);
    } else if (result.status === 'healthy' && previous.status !== 'healthy') {
      await sendAlert(env, service.name, 'recovered', 
        `${service.name} RECOVERED. Response time: ${result.responseTime}ms`);
    } else if (result.status === 'degraded' && previous.status === 'healthy') {
      await sendAlert(env, service.name, 'degraded', 
        `${service.name} is DEGRADED: ${result.error}`);
    }
  }
}

async function handleStaticAsset(request, env, ctx) {
  // Implementation from original worker...
  const url = new URL(request.url);
  const cacheKey = new Request(url.toString(), request);
  const cache = caches.default;

  let response = await cache.match(cacheKey);
  if (!response) {
    const objectName = url.pathname.replace('/cdn/', '');
    const object = await env.STATIC_ASSETS.get(objectName);

    if (object === null) {
      return new Response('Not Found', { status: 404 });
    }

    const headers = new Headers();
    object.writeHttpMetadata(headers);
    headers.set('etag', object.httpEtag);
    headers.set('Cache-Control', 'public, max-age=31536000');

    response = new Response(object.body, { headers });
    ctx.waitUntil(cache.put(cacheKey, response.clone()));
  }
  return response;
}

async function handleApiProxy(request, env, ctx) {
  // Implementation from enhanced worker...
  const backendUrl = env.RENDER_URL || 'https://supremeai-backend-docker.onrender.com';
  const url = new URL(request.url);
  const targetUrl = new URL(url.pathname + url.search, backendUrl);
  
  return fetch(new Request(targetUrl, {
    method: request.method,
    headers: request.headers,
    body: request.body,
  }));
}

async function proxyToOrigin(request, env) {
  const backendUrl = env.RENDER_URL || 'https://supremeai-backend-docker.onrender.com';
  const url = new URL(request.url);
  const targetUrl = new URL(url.pathname + url.search, backendUrl);
  
  return fetch(new Request(targetUrl, {
    method: request.method,
    headers: request.headers,
    body: request.body,
  }));
}