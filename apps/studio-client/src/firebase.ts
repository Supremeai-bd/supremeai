import { initializeApp, getApps, getApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';

// Helper to fetch configuration dynamically or fallback to Vite env vars
const getFirebaseConfig = async () => {
  try {
    const res = await fetch('/__/firebase/init.json');
    if (res.ok) {
      return await res.json();
    }
  } catch (e) {
    // Ignore error and fallback
  }
  return {
    apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "AIzaSyFakeKeyForDevelopmentOnly",
    authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "supremeai-a.firebaseapp.com",
    projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "supremeai-a",
    storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "supremeai-a.appspot.com",
    messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "1234567890",
    appId: import.meta.env.VITE_FIREBASE_APP_ID || "1:1234567890:web:fakeappid"
  };
};

// Initialize Firebase app asynchronously or return existing instance
export const initFirebase = async () => {
  if (getApps().length > 0) {
    return getApp();
  }
  const config = await getFirebaseConfig();
  return initializeApp(config);
};

export const getFirebaseAuth = async () => {
  const app = await initFirebase();
  return getAuth(app);
};
