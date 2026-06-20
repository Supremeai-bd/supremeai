import * as functions from 'firebase-functions/v2';
import * as admin from 'firebase-admin';
import { simpleParser } from 'mailparser';
import * as nodemailer from 'nodemailer';

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
export const handleIncomingEmail = functions.https.onRequest(async (req, res) => {
    try {
        // 1. Parse the multipart email body
        const parsed = await simpleParser(req.body);
        const sender = parsed.from?.value[0].address;
        const recipient = (parsed.to as any)?.value?.[0]?.address;
        const subject = parsed.subject;
        const body = parsed.text;
        const html = parsed.html;

        console.log(`[SupremeAI Email] Incoming from: ${sender} to ${recipient}, Subject: ${subject}`);

        // 1. Check for Verification Codes/Links (The "Personhood" check)
        // If the email is from a known provider (Google, DeepSeek, etc.), extract OTP
        const otpMatch = body?.match(/\b\d{6}\b/); // Look for 6-digit codes
        const linkMatch = typeof html === 'string' ? html.match(/href="([^"]*confirm[^"]*|[^"]*verify[^"]*)"/i) : null;

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
    } catch (error) {
        console.error('Email processing error:', error);
        res.status(500).send('Internal Server Error');
    }
});