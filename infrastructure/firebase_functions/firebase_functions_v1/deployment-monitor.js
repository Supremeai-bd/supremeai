// functions/deployment-monitor.js - AI-Powered Deployment Monitor
// Uses Groq AI to analyze GitHub changes and wake system if needed

const { onSchedule } = require("firebase-functions/v2/scheduler");
const { onRequest } = require("firebase-functions/v2/https");
const functions = require("firebase-functions");
const admin = require("firebase-admin");
const axios = require("axios");

// Initialize Firebase Admin only once (index.js already calls initializeApp)
if (!admin.apps.length) {
    admin.initializeApp();
}
const db = admin.firestore();

// Groq API configuration
const GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions";

/**
 * HTTP trigger: Analyze deployment changes with AI
 * Endpoint: https://region-supremeai.cloudfunctions.net/analyzeDeployment
 * 
 * LOCAL-FIRST MODE: If no AI API key is configured, uses heuristic analysis.
 */
exports.analyzeDeployment = onRequest(async (req, res) => {
    try {
        const { commitMessage, changedFiles, author, branch, runId } = req.body;

        if (!commitMessage || !changedFiles) {
            return res.status(400).json({
                error: "Missing required fields: commitMessage, changedFiles"
            });
        }

        // LOCAL-FIRST: No external AI API key required
        console.log("[LOCAL-FIRST] Analyzing deployment without external AI API key...");

        // Always use local heuristic analysis - no external API required
        const analysis = fallbackAnalysis({
            commitMessage,
            changedFiles,
            author,
            branch,
            projectInfo: getProjectContext()
        });

        // Determine if system needs to be woken up
        const needsWakeUp = shouldWakeSystem(analysis);

        // BUG FIX: Actually call the wakeSystem function if needed
        if (needsWakeUp) {
            console.log(`[MONITOR] High-impact deployment detected for Run ID: ${runId}. Pinging backend...`);
            const success = await wakeSystem(runId, analysis);
            if (!success) {
                console.warn(`[MONITOR] Warning: System wake-up failed for Run ID: ${runId}`);
            }
        }

        // Save analysis to Firestore for tracking
        await saveDeploymentAnalysis({
            timestamp: new Date().toISOString(),
            commitMessage,
            author,
            branch,
            changedFiles,
            analysis,
            needsWakeUp,
            runId,
            actionTaken: needsWakeUp ? "system_woken" : "none"
        });

        // Send notification to admin
        await sendDeploymentNotification(analysis, needsWakeUp);

        res.json({
            success: true,
            analysis,
            needsWakeUp,
            action: needsWakeUp ? "System woken up" : "No action needed",
            localMode: true
        });

    } catch (error) {
        console.error("Error analyzing deployment:", error);
        res.status(500).json({
            error: error.message,
            stack: process.env.NODE_ENV === 'development' ? error.stack : undefined
        });
    }
});

/**
 * Use Groq AI to analyze deployment changes
 */
async function analyzeWithGroq(apiKey, deploymentInfo) {
    const systemPrompt = `
You are an AI DevOps engineer monitoring the SupremeAI deployment system.
Analyze GitHub commits/changes and determine:

1. IMPACT LEVEL: (critical, high, medium, low, none)
   - critical: Core system files changed (backend, database, security, API)
   - high: Major feature changes affecting multiple components
   - medium: Feature additions or significant modifications
   - low: Documentation, minor UI tweaks, non-essential changes
   - none: Test files, CI/CD config updates only

2. WAKE_NEEDED: (true/false)
   - TRUE if impact is critical OR high AND files are in: src/, build.gradle*, Dockerfile, application.yml, functions/
   - FALSE for low-impact changes

3. ACTION: Recommended action (deploy, notify, ignore, wake_system)

4. REASON: Brief explanation in 1-2 sentences

Respond in JSON format:
{
  "impact": "critical|high|medium|low|none",
  "wakeNeeded": true|false,
  "action": "string",
  "reason": "string",
  "affectedComponents": ["list", "of", "components"]
}
`;

    const userMessage = `
Analyze this deployment:

Commit: ${deploymentInfo.commitMessage}
Author: ${deploymentInfo.author || 'Unknown'}
Branch: ${deploymentInfo.branch}
Changed Files:
${deploymentInfo.changedFiles.map(f => `- ${f}`).join('\n')}

Project Context:
${deploymentInfo.projectInfo}

Analyze and respond with JSON only.
`;

    try {
        const response = await axios.post(
            GROQ_API_URL,
            {
                model: "llama3-70b-8192",
                messages: [
                    { role: "system", content: systemPrompt },
                    { role: "user", content: userMessage }
                ],
                temperature: 0.1,
                max_tokens: 512
            },
            {
                headers: {
                    "Authorization": `Bearer ${apiKey}`,
                    "Content-Type": "application/json"
                },
                timeout: 10000
            }
        );

        const content = response.data.choices[0].message.content;
        // Extract JSON from response (Groq may include markdown)
        const jsonMatch = content.match(/\{[\s\S]*\}/);
        if (jsonMatch) {
            return JSON.parse(jsonMatch[0]);
        }

        throw new Error("Could not parse AI response");
    } catch (error) {
        console.error("Groq API error:", error.message);
        // Fallback: simple heuristic analysis
        return fallbackAnalysis(deploymentInfo);
    }
}

/**
 * Fallback analysis if Groq fails
 */
function fallbackAnalysis(deploymentInfo) {
    const criticalPatterns = [
        /src\/main/,
        /build\.gradle/,
        /application\.yml/,
        /Dockerfile/,
        /functions\//,
        /firebase\.json/,
        /security/,
        /auth/,
        /database/
    ];

    const allFiles = deploymentInfo.changedFiles.join(' ').toLowerCase();

    const isCritical = criticalPatterns.some(pattern => pattern.test(allFiles));

    return {
        impact: isCritical ? "critical" : "medium",
        wakeNeeded: isCritical,
        action: isCritical ? "wake_system" : "notify",
        reason: isCritical
            ? "Critical system files changed - immediate attention required"
            : "Non-critical changes detected",
        affectedComponents: isCritical ? ["core_system"] : ["ui_or_docs"],
        fallback: true
    };
}

/**
 * Determine if system needs to be woken up
 */
function shouldWakeSystem(analysis) {
    return analysis.wakeNeeded === true ||
        analysis.impact === "critical" ||
        analysis.action === "wake_system";
}

/**
 * Wake up the Cloud Run service by sending a health check request
 */
async function wakeSystem(runId, analysis) {
    const backendUrl = process.env.JAVA_BACKEND_URL || "https://ide-api.supremeai.google.com";

    try {
        console.log(`Waking system for run ${runId}...`);

        // Send wake-up ping to health endpoint
        const response = await axios.get(`${backendUrl}/api/health`, {
            timeout: 30000,
            headers: {
                "X-Wake-Call": "true",
                "X-Run-ID": runId || "unknown"
            }
        });

        console.log(`System wake response:`, response.data);

        // Log wake event
        await db.collection('system_wake_events').add({
            timestamp: admin.firestore.FieldValue.serverTimestamp(),
            runId,
            analysis,
            status: "woken",
            response: response.data
        });

        return true;
    } catch (error) {
        console.error("Failed to wake system:", error.message);
        await db.collection('system_wake_events').add({
            timestamp: admin.firestore.FieldValue.serverTimestamp(),
            runId,
            analysis,
            status: "failed",
            error: error.message
        });
        return false;
    }
}

/**
 * Get project context for AI analysis
 */
function getProjectContext() {
    return `
SupremeAI Multi-Agent System:
- Backend: Spring Boot 3 (Java 21) on Cloud Run
- Frontend: Flutter web on Firebase Hosting
- Functions: Firebase Cloud Functions
- AI: 10+ providers (Groq, OpenAI, Gemini, Claude, etc.)
- Database: Firestore + Redis caching
- Key directories:
  * src/main/java/com/supremeai/ - Backend Java code
  * supremeai/ - Flutter frontend
  * functions/ - Firebase Cloud Functions
  * dashboard/ - 3D React dashboard
  * build.gradle.kts, settings.gradle.kts - Gradle config
  * application.yml - Spring configuration
`;
}

/**
 * Save deployment analysis to Firestore
 */
async function saveDeploymentAnalysis(data) {
    try {
        await db.collection('deployment_analysis').add({
            ...data,
            createdAt: admin.firestore.FieldValue.serverTimestamp()
        });
    } catch (error) {
        console.error("Error saving analysis:", error.message);
    }
}

/**
 * Send smart deployment notification via FCM
 */
async function sendDeploymentNotification(analysis, needsWakeUp) {
    const title = needsWakeUp
        ? "🚨 CRITICAL: System Woken Up"
        : analysis.impact === "high"
            ? "⚠️ High Impact Deployment"
            : "📦 Deployment Detected";

    const body = needsWakeUp
        ? `Critical changes detected. System has been activated. ${analysis.reason || ''}`
        : analysis.reason || "Deployment completed with medium/low impact changes";

    const notification = {
        notification: {
            title,
            body,
            clickAction: "FLUTTER_NOTIFICATION_CLICK"
        },
        data: {
            type: "deployment_analysis",
            impact: analysis.impact || "unknown",
            wakeNeeded: needsWakeUp.toString(),
            timestamp: new Date().toISOString()
        },
        topic: "admin-notifications"
    };

    try {
        await admin.messaging().send(notification);
        console.log("Deployment notification sent");
    } catch (error) {
        console.error("Error sending notification:", error.message);
    }
}

/**
 * Scheduled trigger: Periodic system health check with AI analysis
 * Runs every 5 minutes
 */
exports.monitorSystemHealth = onSchedule('*/5 * * * *', async (event) => {
    try {
        const backendUrl = process.env.JAVA_BACKEND_URL || "https://ide-api.supremeai.google.com";
        const healthResponse = await axios.get(`${backendUrl}/api/health`, {
            timeout: 10000
        }).catch(() => null);

        if (!healthResponse) {
            console.log("System appears to be down. Attempting to diagnose...");
            await diagnoseAndAlert();
        } else {
            console.log("System health check passed:", healthResponse.data);
        }

        return null;
    } catch (error) {
        console.error("Health monitor error:", error);
        return null;
    }
});

/**
 * Diagnose system issues and alert admin
 */
async function diagnoseAndAlert() {
    const groqApiKey = functions.config().groq?.api_key ||
        process.env.GROQ_API_KEY_DEPLOYMENT_MONITOR;

    if (!groqApiKey) {
        console.warn("Groq API key not available for diagnosis");
        return;
    }

    // Collect recent logs and errors
    const recentErrors = await db.collection('system_health')
        .orderBy('createdAt', 'desc')
        .limit(10)
        .get();

    const errorSummaries = recentErrors.docs.map(doc => doc.data());

    // Ask Groq to diagnose
    const diagnosis = await askGroqForDiagnosis(groqApiKey, errorSummaries);

    await admin.messaging().send({
        notification: {
            title: "🚨 System Down - AI Diagnosis",
            body: diagnosis.summary || "System appears offline. Check Cloud Run logs.",
            clickAction: "FLUTTER_NOTIFICATION_CLICK"
        },
        data: {
            type: "system_diagnosis",
            diagnosis: JSON.stringify(diagnosis),
            timestamp: new Date().toISOString()
        },
        topic: "admin-notifications"
    });
}

/**
 * Ask Groq to diagnose system issues
 */
async function askGroqForDiagnosis(apiKey, errorData) {
    try {
        const prompt = `
Based on these recent system health records, diagnose the likely cause and suggest fixes:

${JSON.stringify(errorData, null, 2)}

Respond in JSON:
{
  "likelyCause": "brief description",
  "suggestedFix": "actionable fix",
  "severity": "critical|high|medium|low",
  "summary": "One-line summary for notification"
}
`;

        const response = await axios.post(
            GROQ_API_URL,
            {
                model: "llama3-70b-8192",
                messages: [{ role: "user", content: prompt }],
                temperature: 0.2,
                max_tokens: 256
            },
            {
                headers: {
                    "Authorization": `Bearer ${apiKey}`,
                    "Content-Type": "application/json"
                },
                timeout: 10000
            }
        );

        const content = response.data.choices[0].message.content;
        const jsonMatch = content.match(/\{[\s\S]*\}/);
        return jsonMatch ? JSON.parse(jsonMatch[0]) : { summary: "AI analysis unavailable" };
    } catch (error) {
        return {
            likelyCause: "Unknown",
            suggestedFix: "Check Cloud Run logs manually",
            severity: "high",
            summary: "System down - manual investigation required"
        };
    }
}
