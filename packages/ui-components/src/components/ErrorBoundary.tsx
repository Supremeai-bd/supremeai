// @supremeai/ui-components/src/components/ErrorBoundary.tsx
// বাংলা মন্তব্য: ফ্রন্টএন্ড এরর বাউন্ডারি — কোনো রিঅ্যাক্ট কম্পোনেন্ট ক্র্যাশ করলে অ্যাপ সম্পূর্ণ ব্রেক হওয়া রোধ করে ও সেলফ-হিলিং রিট্রাই এক্সিকিউট করে।

import React, { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';

export interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: (error: Error, recoveryAttempts: number) => ReactNode;
  componentName?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
  recoveryAttempts: number;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, State> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      recoveryAttempts: 0,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error(`[ErrorBoundary:${this.props.componentName || 'Unknown'}] Uncaught error:`, error, errorInfo);
    this.attemptAutonomousRecovery(error);
  }

  attemptAutonomousRecovery = (error: Error): void => {
    const { recoveryAttempts } = this.state;

    if (recoveryAttempts >= 3) {
      console.warn('[Self-Healing] Max recovery attempts reached on frontend.');
      return;
    }

    if (error.message.includes('NetworkError') || error.message.includes('Failed to fetch')) {
      console.warn('[Self-Healing] Network issue detected. Retrying render with backoff...');
      setTimeout(() => {
        this.setState((prevState) => ({
          hasError: false,
          recoveryAttempts: prevState.recoveryAttempts + 1,
        }));
      }, 1500 * (recoveryAttempts + 1));
    }
  };

  render(): ReactNode {
    const { hasError, error, recoveryAttempts } = this.state;
    const { fallback, children } = this.props;

    if (hasError) {
      if (fallback && error) {
        return fallback(error, recoveryAttempts);
      }

      return (
        <div
          style={{
            padding: '24px',
            margin: '20px',
            borderRadius: '12px',
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            color: '#f87171',
            fontFamily: 'system-ui, -apple-system, sans-serif',
          }}
        >
          <h3 style={{ marginTop: 0, marginBottom: '8px' }}>⚠️ Something went wrong</h3>
          <p style={{ fontSize: '14px', opacity: 0.9 }}>
            Our self-healing system is attempting to restore this component context.
          </p>
          {recoveryAttempts > 0 && (
            <p style={{ fontSize: '12px', opacity: 0.75 }}>
              Recovery attempt {recoveryAttempts} of 3...
            </p>
          )}
          <div style={{ marginTop: '16px', display: 'flex', gap: '10px' }}>
            <button
              onClick={() => this.setState({ hasError: false })}
              style={{
                padding: '8px 16px',
                borderRadius: '6px',
                background: '#ef4444',
                color: '#fff',
                border: 'none',
                cursor: 'pointer',
                fontWeight: 600,
              }}
            >
              Try Again
            </button>
            <button
              onClick={() => window.location.reload()}
              style={{
                padding: '8px 16px',
                borderRadius: '6px',
                background: 'transparent',
                color: '#e5e7eb',
                border: '1px solid rgba(255, 255, 255, 0.2)',
                cursor: 'pointer',
              }}
            >
              Reload Page
            </button>
          </div>
        </div>
      );
    }

    return children;
  }
}
