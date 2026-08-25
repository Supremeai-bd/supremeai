// API routes
 REQUIREMENT PROCESSING ============

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

