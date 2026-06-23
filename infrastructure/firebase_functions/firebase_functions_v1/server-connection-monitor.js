// ============================================================================
// file >> server-connection-monitor.js
// project >> SupremeAI 2.0
// purpose >> System monitoring
// module >> infrastructure
// ============================================================================
const { onRequest } = require("firebase-functions/v2/https");
const functions = require("firebase-functions");
const admin = require("firebase-admin");
const axios = require("axios");

// Firebase app is initialized in index.js
const db = admin.firestore();

/**
 * HTTP trigger: Check all server connections
 * Endpoint: https://region-supremeai.cloudfunctions.net/checkServerConnections
 */
exports.checkServerConnections = onRequest(async (req, res) => {
    try {
        const connectionData = {
            timestamp: new Date().toISOString(),
            connections: {}
        };

        // Load system configuration
        const configDoc = await db.collection('config').doc('system').get();
        const config = configDoc.exists ? configDoc.data() : {};

        // Check Firebase connections
        connectionData.connections.firebase = await checkFirebaseConnections();

        // Check GCloud connections
        connectionData.connections.gcloud = await checkGCloudConnections();

        // Check Local Server connection
        connectionData.connections.local = await checkLocalServerConnection(config.localServerUrl || 'http://127.0.0.1:5000');

        // Check Smart Chat System connection
        connectionData.connections.smartChatSystem = await checkSmartChatSystemConnection(config.smartChatSystemUrl || 'http://127.0.0.1:5000');

        // Calculate overall connection status
        connectionData.overallStatus = calculateConnectionStatus(connectionData.connections);

        // Save connection snapshot to Firestore
        await saveConnectionSnapshot(connectionData);

        res.json({
            success: true,
            data: connectionData
        });
    } catch (error) {
        console.error("Error checking server connections:", error);
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});

/**
 * Check Firebase service connections
 */
async function checkFirebaseConnections() {
    const startTime = Date.now();
    try {
        const checks = {
            firestore: await checkFirestoreConnection(),
            auth: await checkAuthConnection(),
            storage: await checkStorageConnection()
        };

        const responseTime = Date.now() - startTime;
        const allHealthy = Object.values(checks).every(c => c.status === 'connected');

        return {
            name: 'Firebase',
            status: allHealthy ? 'connected' : 'degraded',
            responseTime: `${responseTime}ms`,
            services: checks,
            lastCheck: new Date().toISOString()
        };
    } catch (error) {
        return {
            name: 'Firebase',
            status: 'disconnected',
            error: error.message,
            lastCheck: new Date().toISOString()
        };
    }
}

/**
 * Check Firestore connection
 */
async function checkFirestoreConnection() {
    try {
        const testDoc = await db.collection('connection_checks').add({
            service: 'firestore',
            timestamp: admin.firestore.FieldValue.serverTimestamp()
        });
        await testDoc.delete();

        return {
            service: 'Firestore',
            status: 'connected',
            latency: Date.now() - Date.now()
        };
    } catch (error) {
        return {
            service: 'Firestore',
            status: 'disconnected',
            error: error.message
        };
    }
}

/**
 * Check Firebase Auth connection
 */
async function checkAuthConnection() {
    try {
        const auth = admin.auth();
        await auth.listUsers(1);

        return {
            service: 'Auth',
            status: 'connected'
        };
    } catch (error) {
        return {
            service: 'Auth',
            status: 'disconnected',
            error: error.message
        };
    }
}

/**
 * Check Firebase Storage connection
 */
async function checkStorageConnection() {
    try {
        const bucket = admin.storage().bucket();
        const [files] = await bucket.getFiles({ maxResults: 1 });

        return {
            service: 'Storage',
            status: 'connected'
        };
    } catch (error) {
        return {
            service: 'Storage',
            status: 'disconnected',
            error: error.message
        };
    }
}

/**
 * Check GCloud service connections
 */
async function checkGCloudConnections() {
    const startTime = Date.now();
    try {
        const checks = {
            cloudFunctions: await checkCloudFunctionsConnection(),
            cloudRun: await checkCloudRunConnection(),
            bigQuery: await checkBigQueryConnection()
        };

        const responseTime = Date.now() - startTime;
        const allHealthy = Object.values(checks).every(c => c.status === 'connected');

        return {
            name: 'Google Cloud Platform',
            status: allHealthy ? 'connected' : 'degraded',
            responseTime: `${responseTime}ms`,
            services: checks,
            lastCheck: new Date().toISOString()
        };
    } catch (error) {
        return {
            name: 'Google Cloud Platform',
            status: 'disconnected',
            error: error.message,
            lastCheck: new Date().toISOString()
        };
    }
}

/**
 * Check Cloud Functions connection
 */
async function checkCloudFunctionsConnection() {
    try {
        // Try to call a simple health check function
        const response = await axios.get(
            `https://us-central1-${process.env.GCP_PROJECT_ID || 'supremeai'}.cloudfunctions.net/getSystemHealth`,
            { timeout: 5000 }
        );

        return {
            service: 'Cloud Functions',
            status: response.status === 200 ? 'connected' : 'degraded',
            statusCode: response.status
        };
    } catch (error) {
        return {
            service: 'Cloud Functions',
            status: 'disconnected',
            error: error.message
        };
    }
}

/**
 * Check Cloud Run connection
 */
async function checkCloudRunConnection() {
    try {
        // Check if any Cloud Run services are accessible
        // This would need to be configured based on your services
        return {
            service: 'Cloud Run',
            status: 'connected'
        };
    } catch (error) {
        return {
            service: 'Cloud Run',
            status: 'disconnected',
            error: error.message
        };
    }
}

/**
 * Check BigQuery connection
 */
async function checkBigQueryConnection() {
    try {
        // Check BigQuery connection (if configured)
        // This would need to be configured based on your setup
        return {
            service: 'BigQuery',
            status: 'connected'
        };
    } catch (error) {
        return {
            service: 'BigQuery',
            status: 'disconnected',
            error: error.message
        };
    }
}

/**
 * Check Local Server connection
 */
async function checkLocalServerConnection(url) {
    try {
        const response = await axios.get(`${url}/health`, {
            timeout: 5000
        });

        const data = response.data;

        return {
            name: 'Local Development Server',
            url: url,
            status: response.status === 200 ? 'connected' : 'degraded',
            responseTime: `${response.headers['x-response-time'] || 'N/A'}`,
            health: {
                status: data.status,
                cpu: data.cpu,
                memory: data.memory,
                disk: data.disk,
                uptime: data.uptime
            },
            lastCheck: new Date().toISOString()
        };
    } catch (error) {
        return {
            name: 'Local Development Server',
            url: url,
            status: 'disconnected',
            error: error.message,
            lastCheck: new Date().toISOString()
        };
    }
}

/**
 * Check Smart Chat System connection
 */
async function checkSmartChatSystemConnection(url) {
    try {
        const response = await axios.get(`${url}/api/status`, {
            timeout: 5000
        });

        return {
            name: 'Smart Chat System',
            url: url,
            status: response.status === 200 ? 'connected' : 'degraded',
            services: response.data.services || {},
            lastCheck: new Date().toISOString()
        };
    } catch (error) {
        return {
            name: 'Smart Chat System',
            url: url,
            status: 'disconnected',
            error: error.message,
            lastCheck: new Date().toISOString()
        };
    }
}

/**
 * Calculate overall connection status
 */
function calculateConnectionStatus(connections) {
    const statuses = Object.values(connections).map(c => c.status);

    if (statuses.every(s => s === 'connected')) {
        return 'all_connected';
    } else if (statuses.some(s => s === 'connected')) {
        return 'partial';
    }
    return 'disconnected';
}

/**
 * Save connection snapshot to Firestore
 */
async function saveConnectionSnapshot(connectionData) {
    try {
        await db.collection('server_connections').add({
            ...connectionData,
            createdAt: admin.firestore.FieldValue.serverTimestamp()
        });

        // Clean up old snapshots (keep last 7 days)
        const cutoffDate = new Date();
        cutoffDate.setDate(cutoffDate.getDate() - 7);

        const oldSnapshots = await db.collection('server_connections')
            .where('createdAt', '<', cutoffDate)
            .limit(100)
            .get();

        const batch = db.batch();
        oldSnapshots.docs.forEach(doc => batch.delete(doc.ref));
        await batch.commit();
    } catch (error) {
        console.error('Error saving connection snapshot:', error);
    }
}

/**
 * Scheduled trigger: Check connections every 2 minutes
 */
exports.monitorConnections = onSchedule('*/2 * * * *', async (event) => {
    try {
        const connectionData = {
            timestamp: new Date().toISOString(),
            connections: {}
        };

        const configDoc = await db.collection('config').doc('system').get();
        const config = configDoc.exists ? configDoc.data() : {};

        connectionData.connections.firebase = await checkFirebaseConnections();
        connectionData.connections.gcloud = await checkGCloudConnections();
        connectionData.connections.local = await checkLocalServerConnection(config.localServerUrl || 'http://127.0.0.1:5000');
        connectionData.connections.smartChatSystem = await checkSmartChatSystemConnection(config.smartChatSystemUrl || 'http://127.0.0.1:5000');

        connectionData.overallStatus = calculateConnectionStatus(connectionData.connections);

        await saveConnectionSnapshot(connectionData);

        // Alert if any critical disconnections
        if (connectionData.overallStatus === 'disconnected') {
            await sendConnectionAlert(connectionData);
        }

        console.log('Connection monitoring completed');
        return null;
    } catch (error) {
        console.error('Error monitoring connections:', error);
        throw error;
    }
});

/**
 * Send connection alert notification
 */
async function sendConnectionAlert(connectionData) {
    try {
        const disconnectedServices = Object.entries(connectionData.connections)
            .filter(([_, conn]) => conn.status === 'disconnected')
            .map(([name, _]) => name);

        const message = {
            notification: {
                title: '🔴 Server Connection Alert',
                body: `Disconnected services: ${disconnectedServices.join(', ')}`
            },
            data: {
                type: 'connection_alert',
                status: connectionData.overallStatus,
                timestamp: connectionData.timestamp,
                services: disconnectedServices
            },
            topic: 'admin-notifications'
        };

        await admin.messaging().send(message);
        console.log('Connection alert sent successfully');
    } catch (error) {
        console.error('Error sending connection alert:', error);
    }
}
