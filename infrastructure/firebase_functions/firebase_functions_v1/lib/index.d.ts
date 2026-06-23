import * as functions from 'firebase-functions/v1';
/**
 * Trigger: Executes automatically whenever a new user signs up via Firebase Auth.
 * Action: Assigns a default 'user' custom claim and creates a Firestore profile.
 */
export declare const onUserSignUp: functions.CloudFunction<import("firebase-admin/auth").UserRecord>;
//# sourceMappingURL=index.d.ts.map