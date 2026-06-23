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
exports.onUserSignUp = void 0;
const functions = __importStar(require("firebase-functions/v1"));
const admin = __importStar(require("firebase-admin"));
// Initialize Firebase Admin SDK
admin.initializeApp();
/**
 * Trigger: Executes automatically whenever a new user signs up via Firebase Auth.
 * Action: Assigns a default 'user' custom claim and creates a Firestore profile.
 */
exports.onUserSignUp = functions.auth.user().onCreate(async (user) => {
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
    }
    catch (error) {
        console.error(`[AUTH ERROR] Failed to initialize user ${user.uid}:`, error);
    }
});
//# sourceMappingURL=index.js.map