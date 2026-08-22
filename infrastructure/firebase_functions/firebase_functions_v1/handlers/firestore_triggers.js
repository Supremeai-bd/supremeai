// Firestore triggers
 APPROVAL HANDLING ============

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

