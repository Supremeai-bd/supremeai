import * as functions from 'firebase-functions/v1';
import * as admin from 'firebase-admin';

// Initialize Firebase Admin SDK
admin.initializeApp();

/**
 * Trigger: Executes automatically whenever a new user signs up via Firebase Auth.
 * Action: Assigns a default 'user' custom claim and creates a Firestore profile.
 */
export const onUserSignUp = functions.auth.user().onCreate(async (user: admin.auth.UserRecord) => {
    try {
        // 1. Set Custom User Claims (Embeds the role directly into their JWT token)
        await admin.auth().setCustomUserClaims(user.uid, {
            role: 'user',
            accessLevel: 1
        });

        // 2. Create a synchronized profile document in Firestore
        await admin.firestore().collection('users').doc(user.uid).set({
            email: user.email,
            displayName: user.displayName || 'Operator',
            role: 'user',
            tier: 'FREE',
            createdAt: admin.firestore.FieldValue.serverTimestamp(),
            lastLogin: admin.firestore.FieldValue.serverTimestamp()
        }, { merge: true });

        console.log(`[AUTH] Successfully initialized new user: ${user.uid} with 'user' role.`);
    } catch (error) {
        console.error(`[AUTH ERROR] Failed to initialize user ${user.uid}:`, error);
    }
});