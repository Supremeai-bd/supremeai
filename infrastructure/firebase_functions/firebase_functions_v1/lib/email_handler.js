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
Object.defineProperty(exports, "__esModule", { value: true });
exports.handleIncomingEmail = void 0;
const functions = __importStar(require("firebase-functions/v2"));
const admin = __importStar(require("firebase-admin"));
const mailparser_1 = require("mailparser");
const nodemailer = __importStar(require("nodemailer"));
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
        const authorizedAdmins = ['admin@yourdomain.com'];
        if (!sender || !authorizedAdmins.includes(sender)) {
            console.warn(`Unauthorized access attempt by ${sender}`);
            res.status(403).send('Forbidden');
            return;
        }
        // 3. Process Logic (Pseudo-code)
        // Here you would pass 'body' to your Gemini-powered agent
        // result = await supremeAiCore.processCommand(body);
        // 4. Send Confirmation/Result back to Admin
        await transporter.sendMail({
            from: '"SupremeAI Assistant" <supremeai@yourdomain.com>',
            to: sender,
            subject: `Re: ${subject} [PROCESSED]`,
            text: `Hello Admin, I have received your request and executed the tasks. \n\nCommand: ${subject}\nStatus: Successfully completed via SupremeAI Core Engine.`
        });
        res.status(200).send('Email Processed');
    }
    catch (error) {
        console.error('Email processing error:', error);
        res.status(500).send('Internal Server Error');
    }
});
//# sourceMappingURL=email_handler.js.map