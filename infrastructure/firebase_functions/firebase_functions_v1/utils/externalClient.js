// ============================================================================
// file >> externalClient.js
// project >> SupremeAI 2.0
// purpose >> General utility
// module >> infrastructure
// ============================================================================
async function callExternal(url, opts = {}) {
  const {
    method = 'get',
    data = null,
    headers = {},
    timeout = process.env.EXTERNAL_TIMEOUT_MS ? parseInt(process.env.EXTERNAL_TIMEOUT_MS, 10) : 4000,
    retries = process.env.EXTERNAL_RETRY ? parseInt(process.env.EXTERNAL_RETRY, 10) : 1,
    enabledFlag = 'ENABLE_EXTERNAL_API'
  } = opts;

  const enabled = (process.env[enabledFlag] || 'false').toLowerCase() === 'true';
  if (!enabled) {
    const err = new Error(`external api disabled via ${enabledFlag}`);
    err.code = 'EXTERNAL_DISABLED';
    throw err;
  }

  let lastErr = null;
  for (let i = 0; i <= retries; i++) {
    try {
      const res = await axios({ url, method, data, headers, timeout });
      return res;
    } catch (e) {
      lastErr = e;
      // small backoff
      await new Promise(r => setTimeout(r, 100 * (i + 1)));
    }
  }

  throw lastErr;
}

module.exports = { callExternal };
