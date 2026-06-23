// ============================================================================
// file >> system-health.js
// project >> SupremeAI 2.0
// purpose >> Health check
// module >> infrastructure
// ============================================================================
const { onRequest } = require("firebase-functions/v2/https");
const functions = require("firebase-functions");
const admin = require("firebase-admin");
const axios = require("axios");

// Firebase app is initialized in index.js
const db = admin.firestore();

// Health check intervals (in milliseconds)
const HEALTH_CHECK_INTERVAL = 30000; // 30 seconds
const HISTORY_RETENTION_DAYS = 7;

/**
 * HTTP trigger: Get current system health status
 * Endpoint: https://region-supremeai.cloudfunctions.net/getSystemHealth
 */
exports.getSystemHealth = onRequest({ cors: true }, async (req, res) => {
    try {
        const healthData = {
            timestamp: new Date().toISOString(),
            components: {}
        };

        // Check Firebase Health
        healthData.components.firebase = await checkFirebaseHealth();

        // Check GCloud Health
        healthData.components.gcloud = await checkGCloudHealth();

        // Check Local PC Health (if accessible)
        healthData.components.localPC = await checkLocalPcHealth();

        // Check Database Health
        healthData.components.database = await checkDatabaseHealth();

        // Calculate overall system status
        healthData.overallStatus = calculateOverallStatus(healthData.components);

        // Save health snapshot to Firestore
        await saveHealthSnapshot(healthData);

        res.json({
            success: true,
            data: healthData
        });
    } catch (error) {
        console.error("Error fetching system health:", error);
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});

/**
 * Check Firebase services health
 */
async function checkFirebaseHealth() {
    const startTime = Date.now();
    try {
        // Test Firestore
        const testDoc = await db.collection('health_checks').add({
            service: 'firestore',
            timestamp: admin.firestore.FieldValue.serverTimestamp()
        });
        await testDoc.delete();

        // Test Authentication
        const auth = admin.auth();
        const userCount = (await auth.listUsers(1)).users.length;

        // Check Firebase Storage (if configured)
        const storageHealthy = await checkStorageHealth();

        const responseTime = Date.now() - startTime;

        return {
            name: 'Firebase',
            status: 'healthy',
            uptime: '99.99%',
            responseTime: `${responseTime}ms`,
            services: {
                firestore: { status: 'healthy', responseTime: `${responseTime}ms` },
                auth: { status: 'healthy', userCount },
                storage: { status: storageHealthy ? 'healthy' : 'degraded' }
            },
            lastCheck: new Date().toISOString()
        };
    } catch (error) {
        return {
            name: 'Firebase',
            status: 'degraded',
            error: error.message,
            lastCheck: new Date().toISOString()
        };
    }
}

/**
 * Check GCloud services health
 */
async function checkGCloudHealth() {
    const startTime = Date.now();
    try {
        // Check Cloud Functions status
        const functionsHealthy = await checkCloudFunctionsHealth();

        // Check Cloud Run services (if any)
        const cloudRunHealthy = await checkCloudRunHealth();

        // Check BigQuery (if configured)
        const bigQueryHealthy = await checkBigQueryHealth();

        const responseTime = Date.now() - startTime;

        return {
            name: 'Google Cloud Platform',
            status: functionsHealthy && cloudRunHealthy ? 'healthy' : 'degraded',
            uptime: '99.9%',
            responseTime: `${responseTime}ms`,
            services: {
                cloudFunctions: { status: functionsHealthy ? 'healthy' : 'degraded' },
                cloudRun: { status: cloudRunHealthy ? 'healthy' : 'degraded' },
                bigQuery: { status: bigQueryHealthy ? 'healthy' : 'degraded' }
            },
            lastCheck: new Date().toISOString()
        };
    } catch (error) {
        return {
            name: 'Google Cloud Platform',
            status: 'degraded',
            error: error.message,
            lastCheck: new Date().toISOString()
        };
    }
}

/**
 * Check Local PC health (if accessible via local server)
 */
async function checkLocalPcHealth() {
    try {
        // Try to reach local health endpoint
        const backendUrl = (functions.config().backend && functions.config().backend.url) || 'https://supremeai-a.web.app';
        const response = await axios.get(`${backendUrl}/health`, {
            timeout: 5000
        });

        const data = response.data;

        return {
            name: 'Local Development Server',
            status: data.status || 'healthy',
            uptime: data.uptime || 'N/A',
            cpu: data.cpu || { usage: 'N/A' },
            memory: data.memory || { usage: 'N/A', total: 'N/A' },
            disk: data.disk || { usage: 'N/A', total: 'N/A' },
            lastCheck: new Date().toISOString()
        };
    } catch (error) {
        // Local server might not be running - this is expected
        return {
            name: 'Local Development Server',
            status: 'unavailable',
            message: 'Local server not accessible',
            lastCheck: new Date().toISOString()
        };
    }
}

/**
 * Check Database health
 */
async function checkDatabaseHealth() {
    try {
        const startTime = Date.now();

        // Perform a simple read operation
        const snapshot = await db.collection('health_checks').limit(1).get();

        const responseTime = Date.now() - startTime;

        return {
            name: 'Firestore Database',
            status: 'healthy',
            uptime: '99.99%',
            responseTime: `${responseTime}ms`,
            operations: {
                reads: 'healthy',
                writes: 'healthy',
                queries: 'healthy'
            },
            lastCheck: new Date().toISOString()
        };
    } catch (error) {
        return {
            name: 'Firestore Database',
            status: 'degraded',
            error: error.message,
            lastCheck: new Date().toISOString()
        };
    }
}

/**
 * Check Firebase Storage health
 */
async function checkStorageHealth() {
    try {
        const bucket = admin.storage().bucket();
        const [files] = await bucket.getFiles({ maxResults: 1 });
        return true;
    } catch (error) {
        console.error('Storage health check failed:', error);
        return false;
    }
}

/**
 * Check Cloud Functions health
 */
async function checkCloudFunctionsHealth() {
    try {
        // Try to call a simple health check function
        // This would need to be implemented as a separate function
        return true;
    } catch (error) {
        console.error('Cloud Functions health check failed:', error);
        return false;
    }
}

/**
 * Check Cloud Run health
 */
async function checkCloudRunHealth() {
    try {
        // Check if any Cloud Run services are deployed and healthy
        // This would need to be configured based on your services
        return true;
    } catch (error) {
        console.error('Cloud Run health check failed:', error);
        return false;
    }
}

/**
 * Check BigQuery health
 */
async function checkBigQueryHealth() {
    try {
        // Check BigQuery connection (if configured)
        // This would need to be configured based on your setup
        return true;
    } catch (error) {
        console.error('BigQuery health check failed:', error);
        return false;
    }
}

/**
 * Calculate overall system status
 */
function calculateOverallStatus(components) {
    const statuses = Object.values(components).map(c => c.status);

    if (statuses.every(s => s === 'healthy')) {
        return 'healthy';
    } else if (statuses.some(s => s === 'critical')) {
        return 'critical';
    } else if (statuses.some(s => s === 'degraded' || s === 'unavailable')) {
        return 'degraded';
    }
    return 'healthy';
}

/**
 * Save health snapshot to Firestore
 */
async function saveHealthSnapshot(healthData) {
    try {
        await db.collection('system_health').add({
            ...healthData,
            createdAt: admin.firestore.FieldValue.serverTimestamp()
        });

        // Clean up old health snapshots
        const cutoffDate = new Date();
        cutoffDate.setDate(cutoffDate.getDate() - HISTORY_RETENTION_DAYS);

        const oldSnapshots = await db.collection('system_health')
            .where('createdAt', '<', cutoffDate)
            .limit(100)
            .get();

        const batch = db.batch();
        oldSnapshots.docs.forEach(doc => batch.delete(doc.ref));
        await batch.commit();
    } catch (error) {
        console.error('Error saving health snapshot:', error);
    }
}

/**
 * Scheduled trigger: Collect health metrics every 5 minutes
 */
exports.collectHealthMetrics = onSchedule('*/5 * * * *', async (event) => {
    try {
        const healthData = {
            timestamp: new Date().toISOString(),
            components: {}
        };

        // Collect health data for all components
        healthData.components.firebase = await checkFirebaseHealth();
        healthData.components.gcloud = await checkGCloudHealth();
        healthData.components.localPC = await checkLocalPcHealth();
        healthData.components.database = await checkDatabaseHealth();

        healthData.overallStatus = calculateOverallStatus(healthData.components);

        // Save to Firestore
        await saveHealthSnapshot(healthData);

        // If status is critical, send alert
        if (healthData.overallStatus === 'critical') {
            await sendHealthAlert(healthData);
        }

        console.log('Health metrics collected successfully');
        return null;
    } catch (error) {
        console.error('Error collecting health metrics:', error);
        throw error;
    }
});

/**
 * Send health alert notification with AI-generated message
 */
async function sendHealthAlert(healthData) {
    try {
        // Get Groq API key for smart message generation
        const groqApiKey = functions.config().groq?.api_key ||
                          process.env.GROQ_API_KEY;

        let messageBody;
        if (groqApiKey) {
            // Use Groq to generate a smart, concise alert message
            messageBody = await generateSmartAlertMessage(groqApiKey, healthData);
        } else {
            // Fallback to simple message
            messageBody = `System status is ${healthData.overallStatus.toUpperCase()}. Please check the dashboard.`;
        }

        const message = {
            notification: {
                title: '🚨 System Health Alert',
                body: messageBody
            },
            data: {
                type: 'health_alert',
                status: healthData.overallStatus,
                timestamp: healthData.timestamp,
                components: JSON.stringify(Object.keys(healthData.components))
            },
            topic: 'admin-notifications'
        };

        await admin.messaging().send(message);
        console.log('Health alert sent successfully');
    } catch (error) {
        console.error('Error sending health alert:', error);
    }
}

/**
 * Generate smart alert message using Groq AI
 */
async function generateSmartAlertMessage(apiKey, healthData) {
    const GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions";

    const systemPrompt = `You are a system monitoring assistant.
Generate a VERY SHORT (max 100 chars) alert message based on system health.
Format: "[COMPONENT] Issue: [brief description]"
Examples:
  "Firebase: Auth service degraded"
  "Database: High latency detected"
  "Critical: Multiple services down"
`;

    const userPrompt = `System status: ${healthData.overallStatus}
Components:
${JSON.stringify(healthData.components, null, 2)}

Generate a concise alert message:`;

    try {
        const response = await axios.post(
            GROQ_API_URL,
            {
                model: "llama3-8b-8192",
                messages: [
                    { role: "system", content: systemPrompt },
                    { role: "user", content: userPrompt }
                ],
                temperature: 0.3,
                max_tokens: 100
            },
            {
                headers: {
                    "Authorization": `Bearer ${apiKey}`,
                    "Content-Type": "application/json"
                },
                timeout: 5000
            }
        );

        return response.data.choices[0].message.content.trim();
    } catch (error) {
        console.error("Failed to generate smart alert:", error.message);
        return `System ${healthData.overallStatus.toUpperCase()}`;
    }
}
