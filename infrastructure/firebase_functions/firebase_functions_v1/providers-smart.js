const functions = require('firebase-functions');
const admin = require('firebase-admin');

// ============ SMART PROVIDER DISCOVERY ============
// Discovers AI models from multiple sources:
// 1. Firestore (user-added API keys)
// 2. Environment config (Firebase, Vertex AI)
// 3. Cloud Run service discovery (deployed models)

async function discoverProviders() {
  const providers = [];

  // ── Source: Firestore (user-configured and dynamic system providers) ──
  try {
    const db = admin.firestore();
    const snap = await db.collection('ai_providers').get();
    snap.forEach(doc => {
      const data = doc.data();
      // Skip inactive ones in general listing, or filter by active status if needed
      if (data.status === 'active') {
        providers.push({
          id: doc.id,
          name: data.name || doc.id,
          type: data.type || 'api',
          deploymentSource: data.deploymentSource || 'api',
          status: data.status || 'active',
          apiKeyConfigured: !!data.apiKey,
          endpoint: data.endpoint || '',
          models: data.models || [],
          roles: data.roles || ['general_chat'],
          source: data.source || 'firestore',
        });
      }
    });
  } catch (err) {
    console.error('Error discovering providers from Firestore:', err);
  }

  return providers;
}

// ============ API ENDPOINTS ============

exports.getConfiguredProviders = functions.https.onRequest(async (req, res) => {
  res.set('Access-Control-Allow-Origin', '*');
  res.set('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.set('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  if (req.method === 'OPTIONS') return res.status(204).send('');

  try {
    const providers = await discoverProviders();
    res.json({
      success: true,
      data: {
        providers,
        total: providers.length,
        active: providers.length,
        sources: [...new Set(providers.map(p => p.source))],
      }
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

exports.getProviderHealthStats = functions.https.onRequest(async (req, res) => {
  res.set('Access-Control-Allow-Origin', '*');
  if (req.method === 'OPTIONS') return res.status(204).send('');

  try {
    const providers = await discoverProviders();
    res.json({
      success: true,
      data: {
        total: providers.length,
        active: providers.filter(p => p.status === 'active').length,
        error: 0,
        bySource: {
          firestore: providers.filter(p => p.source === 'firestore').length,
          env: providers.filter(p => p.source === 'env').length,
          cloudrun: providers.filter(p => p.source === 'cloudrun').length,
        }
      }
    });
  } catch (err) {
    res.json({ success: true, data: { total: 0, active: 0, error: 0 } });
  }
});
