/**
 * Shared WebSocket hook — ONE connection to /ws/dashboard for the whole app,
 * multiplexed to every component that calls useWebSocket().
 *
 * Previously each useWebSocket() opened its own socket; with the dashboard now
 * mounting several subscribers (live feed, ROI ledger, coaching overlay, CRM
 * embed panel) that meant 4+ parallel connections each with its own reconnect
 * loop — wasteful and risky on free-tier hosting. This version keeps a single
 * module-level connection with a subscriber set; the hook API is unchanged.
 *
 * Server event types handled by subscribers:
 *   history, sync_completed, call_started, call_failed, webhook_event,
 *   connection_synced, transcript_chunk, command_executed, command_failed,
 *   coaching_nudge, radar_scan, save_call_started, save_call_transferred,
 *   call_analysis_ready, morning_brief_*
 */
import { useEffect, useRef, useState } from "react";

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

// ─── Module-level shared connection state ──────────────────────────────────
type MsgHandler = (m: WebSocketMessage) => void;
type StatusHandler = (connected: boolean, latency: number | null) => void;

const messageSubs = new Set<MsgHandler>();
const statusSubs = new Set<StatusHandler>();

let socket: WebSocket | null = null;
let connected = false;
let latency: number | null = null;
let reconnectDelay = BASE_RECONNECT_MS;
let pingTimer: ReturnType<typeof setInterval> | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let starting = false;

function emitStatus() {
  for (const fn of statusSubs) fn(connected, latency);
}

function connect() {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return;
  }
  starting = true;
  const wsUrl = import.meta.env.VITE_WS_URL ?? `ws://${window.location.host}`;
  const ws = new WebSocket(`${wsUrl}/ws/dashboard`);
  socket = ws;

  ws.onopen = () => {
    starting = false;
    connected = true;
    latency = latency ?? null;
    reconnectDelay = BASE_RECONNECT_MS;
    emitStatus();
    if (pingTimer) clearInterval(pingTimer);
    pingTimer = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "ping", timestamp: performance.now() }));
      }
    }, PING_INTERVAL_MS);
  };

  ws.onmessage = (evt) => {
    let msg: WebSocketMessage;
    try { msg = JSON.parse(evt.data); } catch { return; }
    if (msg.type === "pong" && msg.timestamp !== undefined) {
      latency = Math.round(performance.now() - msg.timestamp);
      emitStatus();
      return;
    }
    for (const fn of messageSubs) {
      try { fn(msg); } catch { /* a bad subscriber must not kill the bus */ }
    }
  };

  ws.onclose = () => {
    connected = false;
    latency = null;
    emitStatus();
    if (pingTimer) { clearInterval(pingTimer); pingTimer = null; }
    // Only reconnect while something is still listening.
    if (messageSubs.size > 0 || statusSubs.size > 0) {
      if (reconnectTimer) clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(connect, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT_MS);
    }
  };

  ws.onerror = () => ws.close();
}

function teardownIfIdle() {
  if (messageSubs.size === 0 && statusSubs.size === 0) {
    if (pingTimer) { clearInterval(pingTimer); pingTimer = null; }
    if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
    if (socket) {
      try { socket.close(); } catch { /* ignore */ }
      socket = null;
    }
    connected = false;
    latency = null;
  }
}

export function useWebSocket({ onMessage }: Options) {
  const [isConnected, setIsConnected] = useState(connected);
  const [latencyMs, setLatencyMs] = useState<number | null>(latency);

  // Keep the latest onMessage in a ref so the subscriber wrapper is stable
  // (added once per mount) yet always calls the freshest closure. Without this,
  // inline onMessage handlers (which change every render) would churn the
  // subscriber set and thrash the shared socket.
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  useEffect(() => {
    const msgSub: MsgHandler = (m) => onMessageRef.current(m);
    const statusSub: StatusHandler = (c, l) => { setIsConnected(c); setLatencyMs(l); };

    messageSubs.add(msgSub);
    statusSubs.add(statusSub);

    connect();
    // Reflect current state immediately for late subscribers.
    setIsConnected(connected);
    setLatencyMs(latency);

    return () => {
      messageSubs.delete(msgSub);
      statusSubs.delete(statusSub);
      teardownIfIdle();
    };
  }, []);

  return { isConnected, latencyMs };
}
