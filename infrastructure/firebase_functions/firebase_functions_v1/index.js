// functions/index.js - Firebase Cloud Functions for AI System
// Deploy with: firebase deploy --only functions

const { onSchedule } = require("firebase-functions/v2/scheduler");
const { onRequest } = require("firebase-functions/v2/https");
const { onDocumentCreated } = require("firebase-functions/v2/firestore");
const functions = require("firebase-functions");
const admin = require("firebase-admin");
const axios = require("axios");

admin.initializeApp();
const db = admin.firestore();

// ============ GLOBAL CORS (for 127.0.0.1 emulator + future) ============
const allowedOrigins = [
    'http://127.0.0.1:3000',
    'http://127.0.0.1:5173',
    'http://127.0.0.1:5000',
    'http://127.0.0.1:3000',
    'http://127.0.0.1:5173',
    'http://127.0.0.1:5000'
];

const allowCors = (handler) => async (req, res) => {
    const origin = req.headers.origin;
    const allowedOrigin = (origin && (allowedOrigins.includes(origin) || origin.includes('supremeai'))) ? origin : 'https://supremeai-dashboard.web.app';

    res.set('Access-Control-Allow-Origin', allowedOrigin);
    res.set('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
    res.set('Access-Control-Allow-Headers', 'Content-Type, Authorization, x-api-key');
    res.set('Vary', 'Origin');

    if (req.method === 'OPTIONS') {
        return res.status(204).send('');
    }
    return handler(req, res);
};

// ============ AUTHENTICATION MIDDLEWARE ============
const authenticate = async (req, res, next) => {
    // 1. Allow Java backend to bypass if correct system secret is provided
    const apiKey = req.get('x-api-key') || (req.body && req.body.apiKey) || (req.query && req.query.apiKey);
    const systemSecret = functions.config().system && functions.config().system.secret;

    // SECURITY FIX: Only allow bypass if system secret is configured AND matches
    // Do NOT allow bypass if systemSecret is undefined/null/empty
    if (systemSecret && systemSecret.trim() !== '' && apiKey && apiKey === systemSecret) {
        console.log('Java backend authenticated via system secret');
        return next();
    }

    // 2. Require Firebase Auth Admin Token for frontend/admin UI calls
    const authHeader = req.get('Authorization');
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
        return res.status(401).json({ error: "Unauthorized: Missing or invalid token" });
    }

    try {
        const idToken = authHeader.split('Bearer ')[1];
        const decodedToken = await admin.auth().verifyIdToken(idToken);
        // Enforce 'admin' claim as a strict boolean true
        if (decodedToken.admin !== true) {
            return res.status(403).json({ error: "Forbidden: Admin access required" });
        }
        req.user = decodedToken;
        return next();
    } catch (error) {
        console.error('Error verifying token:', error);
        return res.status(401).json({ error: "Unauthorized: Invalid token" });
    }
};

const withAuth = (handler) => {
    return async (req, res) => {
        return authenticate(req, res, () => handler(req, res));
    };
};

// ============ SYSTEM HEALTH MONITORING ============

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

// ============ REQUIREMENT PROCESSING ============

/**
 * HTTP trigger: Process new requirement from admin
 * Endpoint: https://region-supremeai.cloudfunctions.net/processRequirement
 */
exports.processRequirement = onRequest(withAuth(async (req, res) => {
    try {
        const { projectId, description } = req.body;

        if (!projectId || !description) {
            return res.status(400).json({ error: "Missing projectId or description" });
        }

        // Call Java backend to classify
        const backendUrl = (functions.config().backend && functions.config().backend.url) || process.env.JAVA_BACKEND_URL || 'http://127.0.0.1:8080';
        const classificationUrl = `${backendUrl}/classify`;
        const classifyResponse = await axios.post(classificationUrl, { description });
        const size = classifyResponse.data.size; // SMALL, MEDIUM, or BIG

        // Save requirement to Firestore
        const reqRef = await db.collection("requirements").add({
            projectId,
            description,
            size,
            status: "pending",
            createdAt: admin.firestore.FieldValue.serverTimestamp(),
        });

        // Auto-approve or notify
        if (size === "SMALL") {
            await reqRef.update({ status: "approved" });
            console.log(`✅ Auto-approved SMALL requirement: ${reqRef.id}`);
        } else if (size === "MEDIUM") {
            // Schedule auto-approve after 10 minutes
            db.collection("scheduled_approvals").add({
                requirementId: reqRef.id,
                approvalTime: admin.firestore.Timestamp.fromDate(new Date(Date.now() + 10 * 60000)),
            });

            // Send notification
            await admin.messaging().send({
                notification: {
                    title: "⏳ Approval Needed",
                    body: description,
                },
                data: { requirementId: reqRef.id },
                topic: "admin-notifications",
            });
            console.log(`⏳ MEDIUM requirement pending approval: ${reqRef.id}`);
        } else {
            // Send urgent notification for BIG tasks
            await admin.messaging().send({
                notification: {
                    title: "🛑 URGENT: Manual Approval Required",
                    body: description,
                },
                data: { requirementId: reqRef.id, type: "big_approval" },
                topic: "admin-notifications",
            });
            console.log(`🛑 BIG requirement awaiting manual approval: ${reqRef.id}`);
        }

        res.json({
            success: true,
            requirementId: reqRef.id,
            size,
            message: `Requirement processed as ${size}`,
        });
    } catch (error) {
        console.error("Error processing requirement:", error);
        res.status(500).json({ error: error.message });
    }
}));

// ============ APPROVAL HANDLING ============

/**
 * HTTP trigger: Admin approves/rejects requirement
 * Endpoint: https://region-supremeai.cloudfunctions.net/approveRequirement
 */
exports.approveRequirement = onRequest(withAuth(async (req, res) => {
    try {
        const { requirementId, approved, notes } = req.body;

        if (!requirementId) {
            return res.status(400).json({ error: "Missing requirementId" });
        }

        // Update requirement status
        await db.collection("requirements").doc(requirementId).update({
            status: approved ? "approved" : "rejected",
            notes,
            approvedAt: admin.firestore.FieldValue.serverTimestamp(),
        });

        // If approved, trigger agent orchestrator
        if (approved) {
            const req_doc = await db.collection("requirements").doc(requirementId).get();
            const { projectId, description } = req_doc.data();

            // Call Java backend orchestrator
            const backendUrl = (functions.config().backend && functions.config().backend.url) || process.env.JAVA_BACKEND_URL || 'http://127.0.0.1:8080';
            const orchestrateUrl = `${backendUrl}/orchestrate`;
            await axios.post(orchestrateUrl, {
                projectId,
                requirementDescription: description,
            });

            // Update project status
            await db.collection("projects").doc(projectId).update({
                status: "building",
                updatedAt: admin.firestore.FieldValue.serverTimestamp(),
            });
        }

        res.json({
            success: true,
            status: approved ? "approved" : "rejected",
        });
    } catch (error) {
        console.error("Error approving requirement:", error);
        res.status(500).json({ error: error.message });
    }
}));

// ============ AUTO-APPROVAL SCHEDULER ============

/**
 * Scheduled trigger: Auto-approve MEDIUM tasks after 10 minutes
 */
exports.autoApproveScheduled = onSchedule("*/5 * * * *", async (event) => {
    const now = admin.firestore.Timestamp.now();

    const scheduledApprovals = await db.collection("scheduled_approvals")
        .where("approvalTime", "<=", now)
        .get();

    for (const doc of scheduledApprovals.docs) {
        const { requirementId } = doc.data();

        // Check if still pending
        const req = await db.collection("requirements").doc(requirementId).get();
        if (req.data().status === "pending") {
            await req.ref.update({
                status: "approved",
                autoApprovedAt: admin.firestore.FieldValue.serverTimestamp(),
            });
            console.log(`✅ Auto-approved MEDIUM requirement: ${requirementId}`);
        }

        // Delete scheduled entry
        await doc.ref.delete();
    }

    return null;
});

// ============ AI AGENT ROTATION ============

/**
 * HTTP trigger: Handle quota exceeded / API errors
 * Called by Java backend on 429/403 errors
 */
exports.rotateAgent = onRequest(withAuth(async (req, res) => {
    try {
        const { agentId, reason } = req.body;

        // Update agent status
        await db.collection("ai_pool").doc(agentId).update({
            status: "rotated",
            reason,
            rotatedAt: admin.firestore.FieldValue.serverTimestamp(),
        });

        // Trigger VPN switch (if enabled in config)
        const config = await db.collection("config").doc("system").get();
        if (config.data().vpn_enabled) {
            const vpnResult = await switchVPN(agentId);
            console.log(`🔄 VPN switched for ${agentId}: ${vpnResult}`);
        }

        // Notify admin
        await admin.messaging().send({
            notification: {
                title: "⚠️  Agent Rotated",
                body: `${agentId} rotated due to: ${reason}`,
            },
            topic: "admin-notifications",
        });

        res.json({ success: true, message: "Agent rotated" });
    } catch (error) {
        console.error("Error rotating agent:", error);
        res.status(500).json({ error: error.message });
    }
}));

// ============ CHAT MESSAGE HANDLER ============

/**
 * Firestore trigger: Save AI messages to chat history
 */
exports.onChatMessage = onDocumentCreated("projects/{projectId}/chat/{messageId}", async (event) => {
    const { projectId } = event.params;
    const message = event.data.data();

    // Update project's lastMessage timestamp
    await admin.firestore().collection("projects").doc(projectId).update({
        lastMessageAt: admin.firestore.FieldValue.serverTimestamp(),
        updatedAt: admin.firestore.FieldValue.serverTimestamp(),
    });

    // Send real-time notification if from AI
    if (message.sender !== "admin") {
        const project = await admin.firestore().collection("projects").doc(projectId).get();
        const adminUserId = project.data().adminUserId;

        if (adminUserId) {
            await admin.messaging().send({
                notification: {
                    title: `${message.sender} Updated`,
                    body: message.message.substring(0, 50) + "...",
                },
                data: {
                    projectId,
                    type: "chat_update",
                },
                topic: `user-${adminUserId}`,
            });
        }
    }
});

// ============ PROGRESS TRACKER ============

/**
 * HTTP trigger: Update project progress
 */
exports.updateProgress = onRequest(withAuth(async (req, res) => {
    try {
        const { projectId, progress, status } = req.body;

        const updateData = {
            progress,
            updatedAt: admin.firestore.FieldValue.serverTimestamp(),
        };
        if (status) {
            updateData.status = status;
        }
        await db.collection("projects").doc(projectId).update(updateData);

        res.json({ success: true });
    } catch (error) {
        console.error("Error updating project progress:", error);
        res.status(500).json({ error: error.message });
    }
}));

// ============ SERVER CONNECTION MONITORING ============

const serverConnectionMonitor = require('./server-connection-monitor');
exports.checkServerConnections = serverConnectionMonitor.checkServerConnections;
exports.monitorConnections = serverConnectionMonitor.monitorConnections;

// ============ AI DEPLOYMENT MONITORING ============

const deploymentMonitor = require('./deployment-monitor');
exports.analyzeDeployment = deploymentMonitor.analyzeDeployment;
exports.monitorSystemHealth = deploymentMonitor.monitorSystemHealth;

// ============ BENGALI OCR PROCESSING ============

/**
 * HTTP trigger: Process Multi-language OCR on uploaded images
 * Endpoint: https://region-supremeai.cloudfunctions.net/processOCR
 */
const locales = {
  en: {
    ocr_complete_title: "✅ OCR Processing Complete",
    ocr_complete_body: "Processed {success_count}/{total_count} images",
    error_missing_urls: "Missing or invalid imageUrls array",
    error_forbidden_url: "Forbidden URL target",
    error_vision_api: "Vision API error: {message}"
  },
  bn: {
    ocr_complete_title: "✅ ওসিআর প্রসেসিং সম্পন্ন",
    ocr_complete_body: "সফলভাবে {success_count}/{total_count} টি ইমেজ প্রসেস করা হয়েছে",
    error_missing_urls: "অনুপস্থিত বা অবৈধ imageUrls অ্যারে",
    error_forbidden_url: "নিষিদ্ধ ইউআরএল টার্গেট",
    error_vision_api: "ভিশন এপিআই ত্রুটি: {message}"
  }
};

function getLocaleString(locale, key, params = {}) {
  const dict = locales[locale] || locales['en'];
  let str = dict[key] || locales['en'][key] || key;
  for (const [k, v] of Object.entries(params)) {
    str = str.replace(`{${k}}`, v);
  }
  return str;
}

const axiosGetWithRetry = async (url, options, retries = 3, delay = 1000) => {
    for (let i = 0; i < retries; i++) {
        try {
            return await axios.get(url, options);
        } catch (error) {
            if (i === retries - 1) throw error;
            console.warn(`Axios fetch failed, retrying in ${delay}ms... (Attempt ${i + 1}/${retries})`);
            await new Promise(res => setTimeout(res, delay));
            delay *= 2; // Exponential Backoff
        }
    }
};

exports.processOCR = onRequest(withAuth(async (req, res) => {
    try {
        const { imageUrls, projectId, userId, languages = ['en', 'bn'], locale = 'en' } = req.body;

        if (!imageUrls || !Array.isArray(imageUrls) || imageUrls.length === 0) {
            return res.status(400).json({ error: getLocaleString(locale, 'error_missing_urls') });
        }

        const results = [];
        const vision = require('@google-cloud/vision');
        const client = new vision.ImageAnnotatorClient();

        // Use Promise.all for parallel processing to improve performance
        const processingPromises = imageUrls.map(async (imageUrl) => {
            try {
                console.log(`🔍 Processing OCR for: ${imageUrl}`);

                // SSRF Protection: Validate URL
                const urlObj = new URL(imageUrl);
                const forbiddenHostPatterns = [/169\.254/, /127\.0\.0\.1/, /127.0.0.1/];
                if (forbiddenHostPatterns.some(pattern => pattern.test(urlObj.hostname))) {
                    throw new Error(getLocaleString(locale, 'error_forbidden_url'));
                }

                // For Firebase Storage URLs, we need to download the image
                let image;
                if (imageUrl.startsWith('gs://') || imageUrl.startsWith('https://firebasestorage.googleapis.com')) {
                    // Download from Firebase Storage
                    const bucket = admin.storage().bucket();
                    // Note: Improved parsing logic needed for complex URLs
                    const fileName = imageUrl.split('/').pop();
                    const file = bucket.file(fileName);
                    const [buffer] = await file.download();
                    image = { content: buffer };
                } else if (imageUrl.startsWith('data:image/')) {
                    // Base64 encoded image
                    const base64Data = imageUrl.split(',')[1];
                    image = { content: Buffer.from(base64Data, 'base64') };
                } else {
                    // External URL with timeout and retry logic
                    const response = await axiosGetWithRetry(imageUrl, {
                        responseType: 'arraybuffer',
                        timeout: 10000,
                        headers: { 'Accept': 'image/*' }
                    });
                    image = { content: Buffer.from(response.data) };
                }

                // Configure for multi-language text recognition
                const imageContext = {
                    languageHints: languages,
                };

                // Perform OCR
                const [result] = await client.textDetection({
                    image,
                    imageContext,
                });

                if (result.error) {
                    throw new Error(getLocaleString(locale, 'error_vision_api', { message: result.error.message }));
                }

                const detections = result.textAnnotations;
                const extractedText = detections.length > 0 ? detections[0].description : '';

                // Parse table structure if possible
                const lines = extractedText.split('\n').filter(line => line.trim());
                const tableData = parseTableFromText(lines);

                // Save to Firestore
                const ocrResult = {
                    imageUrl,
                    extractedText,
                    tableData,
                    languages_requested: languages,
                    processedAt: admin.firestore.FieldValue.serverTimestamp(),
                    confidence: detections.length > 0 ? detections[0].boundingPoly : null,
                };

                if (projectId) {
                    await db.collection('projects').doc(projectId).collection('ocr_results').add(ocrResult);
                }

                return {
                    imageUrl,
                    success: true,
                    textLength: extractedText.length,
                    linesCount: lines.length,
                    tableDetected: tableData.length > 0,
                };

            } catch (imageError) {
                console.error(`Error processing ${imageUrl}:`, imageError);
                return {
                    imageUrl,
                    success: false,
                    error: imageError.message,
                };
            }
        });

        const results = await Promise.all(processingPromises);

        if (userId && results.some(r => r.success)) {
            const successCount = results.filter(r => r.success).length;
            await admin.messaging().send({
                notification: {
                    title: getLocaleString(locale, 'ocr_complete_title'),
                    body: getLocaleString(locale, 'ocr_complete_body', { success_count: successCount, total_count: results.length }),
                },
                data: {
                    type: "ocr_complete",
                    projectId: projectId || "",
                },
                topic: `user-${userId}`,
            });
        }

        res.json({
            success: true,
            results,
            summary: {
                total: results.length,
                successful: results.filter(r => r.success).length,
                failed: results.filter(r => !r.success).length,
            },
            // Pattern from seed_data: Consistent meta response
            _meta: {
                timestamp: new Date().toISOString(),
                version: "2.1.0-international"
            }
        });

    } catch (error) {
        console.error("Error in Bengali OCR processing:", error);
        res.status(500).json({ error: error.message });
    }
}));

/**
 * HTTP trigger: Get OCR results for a project
 * Endpoint: https://region-supremeai.cloudfunctions.net/getOCRResults
 */
exports.getOCRResults = onRequest(withAuth(async (req, res) => {
    try {
        const { projectId } = req.query;

        if (!projectId) {
            return res.status(400).json({ error: "Missing projectId" });
        }

        const ocrResults = await db.collection('projects').doc(projectId)
            .collection('ocr_results')
            .orderBy('processedAt', 'desc')
            .get();

        const results = [];
        ocrResults.forEach(doc => {
            results.push({
                id: doc.id,
                ...doc.data(),
            });
        });

        res.json({
            success: true,
            results,
        });

    } catch (error) {
        console.error("Error fetching OCR results:", error);
        res.status(500).json({ error: error.message });
    }
}));

/**
 * HTTP trigger: Convert OCR results to Excel and upload
 * Endpoint: https://region-supremeai.cloudfunctions.net/exportOCRToExcel
 */
exports.exportOCRToExcel = onRequest(withAuth(async (req, res) => {
    try {
        const { projectId, resultIds } = req.body;

        if (!projectId || !resultIds || !Array.isArray(resultIds)) {
            return res.status(400).json({ error: "Missing projectId or resultIds array" });
        }

        const ExcelJS = require('exceljs');
        const workbook = new ExcelJS.Workbook();

        for (const resultId of resultIds) {
            const resultDoc = await db.collection('projects').doc(projectId)
                .collection('ocr_results').doc(resultId).get();

            if (!resultDoc.exists) {
                continue;
            }

            const result = resultDoc.data();
            const worksheet = workbook.addWorksheet(`OCR_${resultId.slice(-8)}`);

            // Add metadata
            worksheet.addRow(['Image URL', result.imageUrl]);
            worksheet.addRow(['Processed At', result.processedAt.toDate()]);
            worksheet.addRow(['Language', result.language]);
            worksheet.addRow(['']); // Empty row

            // Add extracted text
            worksheet.addRow(['Extracted Text']);
            worksheet.addRow([result.extractedText]);
            worksheet.addRow(['']); // Empty row

            // Add table data if available
            if (result.tableData && result.tableData.length > 0) {
                worksheet.addRow(['Structured Table Data']);
                result.tableData.forEach(row => {
                    worksheet.addRow(row);
                });
            }
        }

        // Generate Excel buffer
        const buffer = await workbook.xlsx.writeBuffer();

        // Upload to Firebase Storage
        const bucket = admin.storage().bucket();
        const fileName = `ocr_exports/${projectId}/bengali_ocr_${Date.now()}.xlsx`;
        const file = bucket.file(fileName);

        await file.save(buffer, {
            metadata: {
                contentType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            },
        });

        // Get download URL
        const [url] = await file.getSignedUrl({
            action: 'read',
            expires: Date.now() + 7 * 24 * 60 * 60 * 1000, // Expires in 7 days
        });

        // Save export record
        await db.collection('projects').doc(projectId).collection('exports').add({
            type: 'bengali_ocr_excel',
            fileName,
            downloadUrl: url,
            exportedAt: admin.firestore.FieldValue.serverTimestamp(),
            resultCount: resultIds.length,
        });

        res.json({
            success: true,
            downloadUrl: url,
            fileName,
            message: `Excel file created with ${resultIds.length} OCR results`,
        });

    } catch (error) {
        console.error("Error exporting to Excel:", error);
        res.status(500).json({ error: error.message });
    }
}));

// ============ HELPER FUNCTIONS ============

/**
 * Parse table structure from OCR text lines
 */
function parseTableFromText(lines) {
    if (!lines || lines.length === 0) return [];

    const tableData = [];

    // Simple table detection: look for consistent column patterns
    // This is a basic implementation - can be enhanced with ML

    for (const line of lines) {
        // Split on multiple spaces or tabs (common in tabular data)
        const cells = line.split(/\s{2,}|\t/).map(cell => cell.trim()).filter(cell => cell);
        if (cells.length > 1) { // Likely a table row
            tableData.push(cells);
        }
    }

    return tableData;
}

// ============ HELPER: VPN SWITCHING ============

async function switchVPN(agentId) {
    // Call Proton/Windscribe API to rotate IP
    // For demo: just log
    console.log(`🔄 Switching VPN for ${agentId}`);
    return "VPN_SWITCHED";
}

// ============ FIRESTORE SECURITY RULES ============
// The active Firestore rules are configured in config/firestore.rules.
// Modifying this comment will not change the active rules. Please refer to config/firestore.rules.
