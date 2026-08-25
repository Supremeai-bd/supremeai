// Auth
 AUTHENTICATION MIDDLEWARE ============
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

