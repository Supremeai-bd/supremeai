/**
 * SupremeAI WebSocket Manager Service
 *
 * Manages WebSocket connections for real-time communication between
 * frontend and backend services, including dashboard metrics updates,
 * live logs streaming, and agent status monitoring.
 *
 * Features:
 * - Automatic reconnection with exponential backoff
 * - Message queue for offline buffering
 * - Heartbeat mechanism for connection health
 * - Event-driven architecture
 */

interface WebSocketEventHandlers {
  onOpen?: (event: Event) => void;
  onClose?: (event: CloseEvent) => void;
  onError?: (event: Event) => void;
  onMessage?: (event: MessageEvent) => void;
  onReconnect?: () => void;
  onMaxRetries?: () => void;
}

class WebSocketManager {
  private socket: WebSocket | null = null;
  private url: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectInterval = 1000; // Start with 1 second
  private heartbeatInterval: number | null = null;
  private heartbeatTimeout: number | null = null;
  private heartbeatTimeoutDuration = 5000; // 5 seconds
  private reconnectTimer: number | null = null;
  private messageQueue: Array<{data: string | ArrayBuffer | Blob}> = [];
  private isConnected = false;
  private eventHandlers: WebSocketEventHandlers = {};
  private listeners: Map<string, Set<(data: any) => void>> = new Map();

  constructor(url: string, eventHandlers: WebSocketEventHandlers = {}) {
    this.url = url;
    this.eventHandlers = eventHandlers;
  }

  /**
   * Connect to the WebSocket server
   */
  public connect(): void {
    if (this.socket && (this.socket.readyState === WebSocket.CONNECTING || this.socket.readyState === WebSocket.OPEN)) {
      console.warn('WebSocket is already connecting or connected');
      return;
    }

    try {
      this.socket = new WebSocket(this.url);
      this.setupEventListeners();
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      this.handleReconnect();
    }
  }

  /**
   * Disconnect from the WebSocket server
   */
  public disconnect(): void {
    this.isConnected = false;

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }

    if (this.heartbeatTimeout) {
      clearTimeout(this.heartbeatTimeout);
      this.heartbeatTimeout = null;
    }

    if (this.socket) {
      this.socket.close(1000, 'Client disconnected');
      this.socket = null;
    }
  }

  /**
   * Send a message through the WebSocket
   */
  public send(data: string | ArrayBuffer | Blob): void {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      // Queue the message if not connected
      this.messageQueue.push({ data });
      return;
    }

    this.socket.send(data);
  }

  /**
   * Send a structured message with event type
   */
  public sendEvent(eventType: string, payload: any): void {
    const message = JSON.stringify({ type: eventType, payload, timestamp: Date.now() });
    this.send(message);
  }

  /**
   * Subscribe to specific events
   */
  public subscribe(eventType: string, callback: (data: any) => void): void {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, new Set());
    }

    this.listeners.get(eventType)?.add(callback);
  }

  /**
   * Unsubscribe from specific events
   */
  public unsubscribe(eventType: string, callback: (data: any) => void): void {
    const eventListeners = this.listeners.get(eventType);
    if (eventListeners) {
      eventListeners.delete(callback);
      if (eventListeners.size === 0) {
        this.listeners.delete(eventType);
      }
    }
  }

  /**
   * Get connection status
   */
  public getStatus(): { connected: boolean; readyState: number | null; queuedMessages: number } {
    return {
      connected: this.isConnected,
      readyState: this.socket?.readyState ?? null,
      queuedMessages: this.messageQueue.length
    };
  }

  /**
   * Setup WebSocket event listeners
   */
  private setupEventListeners(): void {
    if (!this.socket) return;

    this.socket.onopen = (event: Event) => {
      this.isConnected = true;
      this.reconnectAttempts = 0; // Reset attempts on successful connection

      // Process any queued messages
      this.processQueuedMessages();

      // Start heartbeat
      this.startHeartbeat();

      // Call user handler
      this.eventHandlers.onOpen?.(event);
    };

    this.socket.onclose = (event: CloseEvent) => {
      this.isConnected = false;
      console.log(`WebSocket closed: ${event.code} - ${event.reason}`);

      // Clear heartbeat intervals
      if (this.heartbeatInterval) {
        clearInterval(this.heartbeatInterval);
        this.heartbeatInterval = null;
      }

      if (this.heartbeatTimeout) {
        clearTimeout(this.heartbeatTimeout);
        this.heartbeatTimeout = null;
      }

      // Call user handler
      this.eventHandlers.onClose?.(event);

      // Attempt to reconnect
      if (event.code !== 1000) { // 1000 means normal closure
        this.handleReconnect();
      }
    };

    this.socket.onerror = (event: Event) => {
      console.error('WebSocket error:', event);

      // Call user handler
      this.eventHandlers.onError?.(event);
    };

    this.socket.onmessage = (event: MessageEvent) => {
      try {
        const message = JSON.parse(event.data);

        // Handle system messages
        if (message.type === 'pong') {
          // Heartbeat response received
          if (this.heartbeatTimeout) {
            clearTimeout(this.heartbeatTimeout);
            this.heartbeatTimeout = null;
          }
          return;
        }

        // Emit to event listeners
        if (message.type && this.listeners.has(message.type)) {
          const callbacks = this.listeners.get(message.type);
          callbacks?.forEach(callback => {
            try {
              callback(message.payload);
            } catch (error) {
              console.error(`Error in event listener for ${message.type}:`, error);
            }
          });
        }

        // Call general message handler
        this.eventHandlers.onMessage?.(event);
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
        // Call general message handler for non-JSON messages
        this.eventHandlers.onMessage?.(event);
      }
    };
  }

  /**
   * Process queued messages when connection is established
   */
  private processQueuedMessages(): void {
    while (this.messageQueue.length > 0) {
      const { data } = this.messageQueue.shift()!;
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        this.socket.send(data);
      }
    }
  }

  /**
   * Handle reconnection with exponential backoff
   */
  private handleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      this.eventHandlers.onMaxRetries?.();
      return;
    }

    this.reconnectAttempts++;
    const delay = Math.min(this.reconnectInterval * Math.pow(2, this.reconnectAttempts - 1), 30000); // Max 30 seconds

    console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts}) in ${delay}ms`);

    this.eventHandlers.onReconnect?.();

    this.reconnectTimer = window.setTimeout(() => {
      this.connect();
    }, delay) as unknown as number;
  }

  /**
   * Start heartbeat mechanism to check connection health
   */
  private startHeartbeat(): void {
    // Clear existing heartbeat
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
    }

    this.heartbeatInterval = window.setInterval(() => {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        // Send ping
        this.sendEvent('ping', { timestamp: Date.now() });

        // Set timeout for pong response
        this.heartbeatTimeout = window.setTimeout(() => {
          console.warn('Heartbeat timeout - connection may be lost');
          // Close the connection to trigger reconnection
          this.socket?.close(4000, 'Heartbeat timeout');
        }, this.heartbeatTimeoutDuration) as unknown as number;
      }
    }, 30000) as unknown as number; // Send ping every 30 seconds
  }
}

export default WebSocketManager;
