/**
 * WebSocket hook with exponential back-off reconnect + latency ping.
 * Handles all server event types:
 *   history, sync_completed, call_started, call_failed,
 *   webhook_event, connection_synced, transcript_chunk,
 *   command_executed, command_failed
 */
import { useCallback, useEffect, useRef, useState } from "react";

export interface WebSocketMessage {
  type: string;
  data?: any;
  timestamp?: number;
}

interface Options {
  onMessage: (message: WebSocketMessage) => void;
}

const BASE_RECONNECT_MS = 1000;
const MAX_RECONNECT_MS = 5000;
const PING_INTERVAL_MS = 30_000;

export function useWebSocket({ onMessage }: Options) {
  const [isConnected, setIsConnected] = useState(false);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectDelay = useRef(BASE_RECONNECT_MS);
  const pingTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  const connect = useCallback(() => {
    const wsUrl = import.meta.env.VITE_WS_URL ?? `ws://${window.location.host}`;
    const ws = new WebSocket(`${wsUrl}/ws/dashboard`);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      reconnectDelay.current = BASE_RECONNECT_MS;

      pingTimer.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "ping", timestamp: performance.now() }));
        }
      }, PING_INTERVAL_MS);
    };

    ws.onmessage = (evt) => {
      try {
        const msg: WebSocketMessage = JSON.parse(evt.data);
        if (msg.type === "pong" && msg.timestamp !== undefined) {
          setLatencyMs(Math.round(performance.now() - msg.timestamp));
          return;
        }
        onMessageRef.current(msg);
      } catch {
        // ignore malformed frames
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      setLatencyMs(null);
      if (pingTimer.current) clearInterval(pingTimer.current);
      reconnectTimer.current = setTimeout(() => {
        connect();
      }, reconnectDelay.current);
      reconnectDelay.current = Math.min(reconnectDelay.current * 2, MAX_RECONNECT_MS);
    };

    ws.onerror = () => ws.close();
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (pingTimer.current) clearInterval(pingTimer.current);
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { isConnected, latencyMs };
}
