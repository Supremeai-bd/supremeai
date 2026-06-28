import { useState, useEffect, useCallback } from 'react';
import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut as firebaseSignOut,
  onAuthStateChanged,
  type User,
} from 'firebase/auth';
import { getFirebaseAuth } from '../firebase';
import { useCustomerStore } from '../store/customerStore';
import type { UserProfile } from '../types/customer';

interface UseAuthReturn {
  user: UserProfile | null;
  firebaseUser: User | null;
  loading: boolean;
  error: string | null;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, username: string) => Promise<void>;
  signOut: () => Promise<void>;
}

function mapFirebaseUser(firebaseUser: User): UserProfile {
  return {
    id: firebaseUser.uid,
    username: firebaseUser.displayName || firebaseUser.email?.split('@')[0] || 'Anonymous',
    email: firebaseUser.email || '',
    role: 'operator',
    avatar_url: firebaseUser.photoURL || undefined,
    preferences: {
      theme: 'dark',
      sidebar_collapsed: false,
      notification_enabled: true,
      sound_enabled: false,
      compact_mode: false,
      font_size: 'medium',
    },
    created_at: firebaseUser.metadata.creationTime || new Date().toISOString(),
    last_login: firebaseUser.metadata.lastSignInTime || new Date().toISOString(),
  };
}

export function useAuth(): UseAuthReturn {
  const { user, setUser } = useCustomerStore();
  const [firebaseUser, setFirebaseUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [authReady, setAuthReady] = useState(false);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const auth = await getFirebaseAuth();
        onAuthStateChanged(auth, (fbUser) => {
          if (cancelled) return;
          setFirebaseUser(fbUser);
          if (fbUser) {
            setUser(mapFirebaseUser(fbUser));
          } else {
            setUser(null);
          }
          setAuthReady(true);
          setLoading(false);
        });
      } catch (err: any) {
        if (!cancelled) {
          console.warn('Firebase auth initialization failed:', err.message);
          setAuthReady(true);
          setLoading(false);
        }
      }
    })();

    return () => { cancelled = true; };
  }, [setUser]);

  const signIn = useCallback(async (email: string, password: string) => {
    setError(null);
    setLoading(true);
    try {
      const auth = await getFirebaseAuth();
      const credential = await signInWithEmailAndPassword(auth, email, password);
      const profile = mapFirebaseUser(credential.user);
      setUser(profile);
      setFirebaseUser(credential.user);
    } catch (err: any) {
      const message = err.code === 'auth/invalid-credential'
        ? 'Invalid email or password.'
        : err.code === 'auth/too-many-requests'
          ? 'Too many attempts. Please try again later.'
          : err.message || 'Sign in failed.';
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [setUser]);

  const signUp = useCallback(async (email: string, password: string, username: string) => {
    setError(null);
    setLoading(true);
    try {
      const auth = await getFirebaseAuth();
      const credential = await createUserWithEmailAndPassword(auth, email, password);
      const profile: UserProfile = {
        ...mapFirebaseUser(credential.user),
        username,
        role: 'developer',
      };
      setUser(profile);
      setFirebaseUser(credential.user);
    } catch (err: any) {
      const message = err.code === 'auth/email-already-in-use'
        ? 'An account with this email already exists.'
        : err.code === 'auth/weak-password'
          ? 'Password must be at least 6 characters.'
          : err.message || 'Sign up failed.';
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [setUser]);

  const signOut = useCallback(async () => {
    setError(null);
    try {
      const auth = await getFirebaseAuth();
      await firebaseSignOut(auth);
      setUser(null);
      setFirebaseUser(null);
    } catch (err: any) {
      setError(err.message || 'Sign out failed.');
      throw err;
    }
  }, [setUser]);

  return {
    user,
    firebaseUser,
    loading: loading || !authReady,
    error,
    signIn,
    signUp,
    signOut,
  };
}
