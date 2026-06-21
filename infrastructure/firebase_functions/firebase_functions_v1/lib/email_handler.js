"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.handleIncomingEmail = void 0;
const functions = __importStar(require("firebase-functions/v2"));
const admin = __importStar(require("firebase-admin"));
// @ts-ignore
const mailparser_1 = require("mailparser");
// @ts-ignore
const nodemailer = __importStar(require("nodemailer"));
const axios_1 = __importDefault(require("axios"));
// Configuration for outgoing status updates
const transporter = nodemailer.createTransport({
    service: 'gmail',
    auth: {
        user: process.env.SUPREMEAI_EMAIL,
        pass: process.env.SUPREMEAI_EMAIL_PASSWORD
    }
});
/**
 * Inbound Email Webhook
 * Triggered by an email provider (e.g., SendGrid Inbound Parse)
 */
exports.handleIncomingEmail = functions.https.onRequest(async (req, res) => {
    try {
        // 1. Parse the multipart email body
        const parsed = await (0, mailparser_1.simpleParser)(req.body);
        const sender = parsed.from?.value[0].address;
        const recipient = parsed.to?.value?.[0]?.address;
        const subject = parsed.subject;
        const body = parsed.text;
        const html = parsed.html;
        console.log(`[SupremeAI Email] Incoming from: ${sender} to ${recipient}, Subject: ${subject}`);
        // 1. Check for Verification Codes/Links (The "Personhood" check)
        // If the email is from a known provider (Google, DeepSeek, etc.), extract OTP
        const otpMatch = body?.match(/\b\d{6}\b/); // Look for 6-digit codes
        const linkMatch = html?.match(/href="([^"]*confirm[^"]*|[^"]*verify[^"]*)"/i);
        if (otpMatch || linkMatch) {
            await admin.firestore().collection('verification_queue').add({
                sender,
                email_target: recipient,
                subject,
                code: otpMatch ? otpMatch[0] : null,
                link: linkMatch ? linkMatch[1] : null,
                receivedAt: admin.firestore.FieldValue.serverTimestamp(),
                processed: false
            });
            console.log(`[SupremeAI] Extracted verification data from ${sender}`);
        }
        // 2. Security: Only process if it's from the verified Admin
        const authorizedAdmins = process.env.AUTHORIZED_ADMINS
            ? process.env.AUTHORIZED_ADMINS.split(',').map(email => email.trim().toLowerCase())
            : ['admin@yourdomain.com'];
        if (!sender || !authorizedAdmins.includes(sender.toLowerCase())) {
            console.warn(`Unauthorized access attempt by ${sender}`);
            res.status(403).send('Forbidden');
            return;
        }
        // 3. Process Logic with Gemini API via Axios
        let resultText = '';
        const geminiApiKey = process.env.GEMINI_API_KEY;
        if (geminiApiKey && body) {
            console.log(`[SupremeAI] Processing command using Gemini API...`);
            try {
                const response = await axios_1.default.post(`https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${geminiApiKey}`, {
                    contents: [{
                            parts: [{ text: `You are the SupremeAI Core Engine. Execute or respond to this command from the Admin:\n\n${body}` }]
                        }]
                }, {
                    headers: { 'Content-Type': 'application/json' }
                });
                resultText = response.data?.candidates?.[0]?.content?.parts?.[0]?.text || 'No response from AI engine.';
            }
            catch (err) {
                console.error('Error calling Gemini API:', err?.response?.data || err.message);
                resultText = `Failed to process command with AI: ${err.message}`;
            }
        }
        else {
            console.log(`[SupremeAI] Empty body or GEMINI_API_KEY not configured. Returning dummy execution.`);
            resultText = `Hello Admin, I received your command "${subject}" but could not process it using AI because the GEMINI_API_KEY is not set.`;
        }
        // 4. Send Confirmation/Result back to Admin
        await transporter.sendMail({
            from: `"SupremeAI Assistant" <${process.env.SUPREMEAI_EMAIL || 'supremeai@yourdomain.com'}>`,
            to: sender,
            subject: `Re: ${subject} [PROCESSED]`,
            text: `Hello Admin, I have received your request and executed the tasks. \n\nCommand: ${subject}\n\nExecution Result:\n${resultText}`
        });
        res.status(200).send('Email Processed');
    }
    catch (error) {
        console.error('Email processing error:', error);
        res.status(500).send('Internal Server Error');
    }
});
//# sourceMappingURL=email_handler.js.map