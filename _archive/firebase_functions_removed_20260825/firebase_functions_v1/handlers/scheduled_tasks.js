// Scheduled tasks
 SYSTEM HEALTH MONITORING ============

const systemHealth = require('./system-health');
exports.getSystemHealth = systemHealth.getSystemHealth;
exports.collectHealthMetrics = systemHealth.collectHealthMetrics;

// Smart AI Providers (auto-discovery from Cloud Run + env + Firestore)
const smartProviders = require('./providers-smart');
exports.getConfiguredProviders = smartProviders.getConfiguredProviders;
exports.getProviderHealthStats = smartProviders.getProviderHealthStats;

// Central API Router (best long-term solution)
const apiRouter = require('./api-router');
exports.api = require('firebase-functions').https.onRequest(apiRouter);

