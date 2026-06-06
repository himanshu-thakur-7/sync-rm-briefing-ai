import { useEffect, useRef, useState, useCallback } from "react";
import { BriefingLog } from "@workspace/api-client-react";

export type WebSocketMessage = 
  | { type: "history"; data: BriefingLog[] }
  | { type: "sync_completed"; data: BriefingLog }
  | { type: "call_started"; data: { call_id: string; client_name: string; rm_name: string } };

interface UseWebSocketOptions {
  onMessage: (message: WebSocketMessage) => void;
}

export function useWebSocket({ onMessage }: UseWebSocketOptions) {
  const [isConnected, setIsConnected] = useState(false);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const pingIntervalRef = useRef<number | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttemptRef = useRef(0);
  const onMessageRef = useRef(onMessage);

  onMessageRef.current = onMessage;

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/dashboard`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      reconnectAttemptRef.current = 0;
      
      pingIntervalRef.current = window.setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          const start = performance.now();
          ws.send(JSON.stringify({ type: "ping", timestamp: start }));
        }
      }, 30000);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "pong" && data.timestamp) {
          setLatencyMs(Math.round(performance.now() - data.timestamp));
        } else {
          onMessageRef.current(data);
        }
      } catch (err) {
        console.error("Failed to parse WS message", err);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      
      const backoff = Math.min(1000 * Math.pow(2, reconnectAttemptRef.current), 5000);
      reconnectAttemptRef.current++;
      
      reconnectTimeoutRef.current = window.setTimeout(() => {
        connect();
      }, backoff);
    };

    ws.onerror = (error) => {
      console.error("WebSocket error", error);
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) wsRef.current.close();
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    };
  }, [connect]);

  return { isConnected, latencyMs };
}