/**
 * "The Demo" — the single flagship arc the judges run.
 *
 *   Greeting → priority lookup → "shall I connect Vikram?" → conference bridge
 *   → RM speaks live, OpenAI-voiced client replies → SYNC whispers coaching
 *   → commitment cards → one-tap approve → real Pipedrive write → recap.
 *
 * Two entry points:
 *   "Run the demo"  — fully scripted theater (no phone, no credits, browser-only)
 *   "Call the agent" — opens the Ringg web-call widget; identical arc on real telephony
 *
 * Every line in the bridge runs through the REAL coaching engine, so the
 * whispers + commitment detections are computed live (not scripted).
 */
import { useEffect, useRef, useState } from "react";
import { useLocation } from "wouter";
import {
  ArrowLeft, Headphones, Phone, PhoneOff, Mic, SendHorizontal, Settings,
  AlertTriangle, Sparkles, Lightbulb, CalendarPlus, Check, Loader2, X,
  PanelRightOpen,
} from "lucide-react";
import { useWebSocket, WebSocketMessage } from "@/hooks/use-websocket";
import { playChime, setTheaterActive, speakDialogue, whisperSupported } from "@/lib/whisper";
import { WebCallWidget } from "@/components/WebCallWidget";
import { CoachingOverlay } from "@/components/CoachingOverlay";
import { CopilotSidebar } from "@/components/CopilotSidebar";
import { TwilioCallControls } from "@/components/TwilioCallControls";
import { CRMEmbedRail } from "@/components/CRMEmbedPanel";
import { useConnection } from "@/lib/connection-context";
import { providerFromConnectionId } from "@/components/CRMSourceBadge";

type Phase =
  | "idle"
  | "ringing"
  | "concierge"     // RM ↔ SYNC concierge (briefing + priority)
  | "bridging"      // SYNC dials the client; brief ring
  | "bridge"        // RM speaks, client (OpenAI) replies, whispers fire
  | "wrapup"
  | "ended";

interface Nudge { text: string; tone: "warn" | "opportunity" | "suggest"; }
interface ActionSuggestion { id: string; tool: string; args: Record<string, unknown>; preview: string; }
type ActionState = "pending" | "executing" | "done" | "skipped" | "failed";
interface Entry {
  kind: "line" | "nudge" | "action" | "event";
  speaker?: string; text: string; tone?: string;
  id?: string; tool?: string; args?: Record<string, unknown>;
}

interface BridgeOpenEvent {
  bridge_id: string; client_id: string; client_name: string;
  client_brief: string; connection_id: string;
  mode?: string; call_key?: string; client_phone?: string;
}

const TONE_META: Record<string, { cls: string; Icon: typeof AlertTriangle; label: string }> = {
  warn:        { cls: "border-red-700/50 bg-red-50 text-red-900",             Icon: AlertTriangle, label: "Watch" },
  opportunity: { cls: "border-emerald-700/50 bg-emerald-50 text-emerald-900", Icon: Sparkles,      label: "Opening" },
  suggest:     { cls: "border-ink/40 bg-ink/[0.04] text-ink",                 Icon: Lightbulb,     label: "Nudge" },
};

const RM_VOICE = { pitch: 0.85, rate: 1.0 };
const SYNC_VOICE = { pitch: 1.0, rate: 1.04 };
const CLIENT_FALLBACK_VOICE = { pitch: 1.12, rate: 0.97 };

const hasBrowserSTT = typeof window !== "undefined"
  && ("webkitSpeechRecognition" in window || "SpeechRecognition" in window);

export default function TheDemo() {
  const [, navigate] = useLocation();
  const { connectionId } = useConnection();
  const [embedOpen, setEmbedOpen] = useState(false);

  const [phase, setPhase] = useState<Phase>("idle");
  const [entries, setEntries] = useState<Entry[]>([]);
  const [actionStatus, setActionStatus] = useState<Record<string, ActionState>>({});
  const [sidebarNudges, setSidebarNudges] = useState<{ id: number; text: string; tone: "warn"|"opportunity"|"suggest"; say?: string }[]>([]);
  const [sidebarActions, setSidebarActions] = useState<{ id: string; tool: string; args: Record<string, unknown>; preview: string }[]>([]);
  const nudgeSeq = useRef(0);

  const [rmName, setRmName] = useState(
    (import.meta.env.VITE_DEMO_rmName as string) ?? "Himanshu"
  );
  const [liveClient, setLiveClient] = useState(false);
  const [clientPhone, setClientPhone] = useState(
    (import.meta.env.VITE_DEMO_CLIENT_PHONE as string) ?? ""
  );
  const [speaking, setSpeaking] = useState<"sync" | "rm" | "client" | "whisper" | null>(null);
  const [bridge, setBridge] = useState<BridgeOpenEvent | null>(null);
  const [bridgeMode, setBridgeMode] = useState<"simulated" | "twilio">("simulated");
  const [rmListening, setRmListening] = useState(false);
  const [rmInterim, setRmInterim] = useState("");
  const [rmText, setRmText] = useState("");

  const callIdRef = useRef<string>("");
  const nudgeQueue = useRef<Nudge[]>([]);
  const actionQueue = useRef<ActionSuggestion[]>([]);
  const stopRef = useRef(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const sttRef = useRef<any>(null);

  // Sync phone field to backend so start_call_with uses it (not the env var).
  useEffect(() => {
    fetch("/api/v1/demo/phone", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone: clientPhone }),
    }).catch(() => {});
  }, [clientPhone]);

  // Subscribe to coaching + bridge events. We accept events for our own arc's
  // call_id AND any bridge_open / coaching event from a Ringg widget call —
  // a widget-call bridge_open is the trigger that auto-activates this UI even
  // when the user never pressed "Run the demo".
  useWebSocket({
    onMessage: (msg: WebSocketMessage) => {
      const id = msg.data?.call_id;
      const isOurs = !!id && id === callIdRef.current;

      if (msg.type === "bridge_open") {
        // Always store the bridge data — it carries the client brief.
        const data = msg.data as BridgeOpenEvent;
        setBridge(data);
        if (data.mode === "twilio") setBridgeMode("twilio");
        else setBridgeMode("simulated");
        // If we're idle (i.e. the trigger came from the Ringg widget, not our
        // scripted arc), auto-enter bridge mode using the data from the event.
        if (phase === "idle" || phase === "ended") {
          callIdRef.current = (data.mode === "twilio" && data.call_key)
            ? data.call_key
            : (id || `widget_${Date.now()}`);
          if (data.mode === "twilio") {
            runTwilioBridge(data);
          } else {
            runWidgetBridge(data);
          }
        }
        return;
      }

      // For coaching events, gate on our call_id only when we have one.
      // Without that filter the page would catch coaching from unrelated calls;
      // with the auto-bridge above setting callIdRef, the widget path is covered.
      if (!isOurs) return;

      if (msg.type === "transcript_chunk") {
        const raw = (msg.data?.text ?? "") as string;
        const colonIdx = raw.indexOf(":");
        if (colonIdx > 0) {
          const speaker = raw.slice(0, colonIdx).trim();
          const text = raw.slice(colonIdx + 1).trim();
          if (text) {
            setEntries(prev => [...prev, { kind: "line", speaker, text }]);
          }
        }
        return;
      }

      if (msg.type === "coaching_nudge") {
        const tone = (["warn", "opportunity", "suggest"].includes(msg.data?.tone)
          ? msg.data.tone : "suggest") as Nudge["tone"];
        const text = msg.data?.text ?? "";
        const say = (msg.data?.say ?? "").toString().trim();
        nudgeQueue.current.push({ text, tone });
        // Also persist into the sidebar so the RM can glance at it later.
        const sid = ++nudgeSeq.current;
        setSidebarNudges(prev => [{ id: sid, text, tone, say: say || undefined }, ...prev].slice(0, 12));
      } else if (msg.type === "coaching_action_suggestion") {
        const id = msg.data?.suggestion_id ?? Math.random().toString(36).slice(2, 10);
        const action = {
          id,
          tool: msg.data?.tool ?? "",
          args: msg.data?.args ?? {},
          preview: msg.data?.preview ?? "",
        };
        actionQueue.current.push(action);
        setSidebarActions(prev => [action, ...prev].slice(0, 8));
      }
    },
  });

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [entries]);

  useEffect(() => {
    if (phase === "idle" || phase === "ended") return;
    setTheaterActive(true);
    return () => { setTheaterActive(false); };
  }, [phase]);

  const sleep = (ms: number) => new Promise(r => setTimeout(r, ms));

  // Ringg's web widget owns the mic + speakers while its call is active,
  // blocking Web Speech API in the bridge phase. The Ringg SDK exposes no
  // documented end-call API, so we try every plausible global hook and then
  // fall back to ripping the widget's DOM nodes out — the user sees a clean
  // "Ringg call ended" event and the mic is freed for the bridge.
  const teardownRinggWidget = async (): Promise<void> => {
    const w = window as any;
    // Try known hook names first.
    for (const fn of ["unloadAgent", "endAgent", "destroyAgent", "removeAgent",
                      "dvAgentUnload", "dvAgentDestroy"]) {
      try { if (typeof w[fn] === "function") w[fn](); } catch {}
    }
    try { w.dvAgent?.unload?.(); w.dvAgent?.destroy?.(); w.dvAgent?.close?.(); } catch {}

    // DOM fallback: nuke anything the CDN injected.
    // First, stop any media tracks inside iframes before removing them —
    // removing the iframe node alone doesn't always release the mic immediately.
    const selectors = [
      '[class*="dv-agent"]', '[id*="dv-agent"]',
      '[class*="ringg"]', '[id*="ringg"]',
      'iframe[src*="ringg.ai"]', 'iframe[src*="desivocal"]',
      'iframe[src*="agents-cdn"]',
    ];
    document.querySelectorAll(selectors.join(",")).forEach(el => {
      try {
        const iframe = el as HTMLIFrameElement;
        if (iframe.contentWindow) {
          // Try to stop any MediaStreams the iframe's context holds.
          const iframeNav = (iframe.contentWindow as any).navigator;
          if (iframeNav?.mediaDevices?.getUserMedia) {
            iframeNav.mediaDevices.getUserMedia({ audio: true })
              .then((s: MediaStream) => s.getTracks().forEach((t: MediaStreamTrack) => t.stop()))
              .catch(() => {});
          }
        }
      } catch { /* cross-origin iframe — can't reach in, removal will have to suffice */ }
      try { (el as HTMLElement).remove(); } catch {}
    });
    // Also remove any non-iframe widget containers (divs, shadow hosts).
    document.querySelectorAll('[class*="dv-agent"], [id*="dv-agent"], [class*="ringg"], [id*="ringg"]').forEach(el => {
      try { (el as HTMLElement).remove(); } catch {}
    });
    // Reset the load guard so a subsequent retry can re-inject if needed.
    delete (window as any).__ringgWidgetLoaded;
    // Wait for the browser to fully release the mic device after iframe removal.
    await sleep(500);
    // Cut any orphaned media streams the widget left holding the mic.
    if (typeof navigator !== "undefined" && navigator.mediaDevices) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach(t => t.stop());
      } catch { /* user already denied; nothing to free */ }
    }
    // Cancel any in-flight TTS so the bridge has a clean audio surface.
    if (whisperSupported()) window.speechSynthesis.cancel();
    await sleep(500);
  };

  const ringTone = async () => {
    try {
      const ctx = new AudioContext();
      for (const at of [0, 0.45]) {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.frequency.value = 425;
        gain.gain.setValueAtTime(0.07, ctx.currentTime + at);
        gain.gain.setValueAtTime(0.0001, ctx.currentTime + at + 0.35);
        osc.connect(gain).connect(ctx.destination);
        osc.start(ctx.currentTime + at); osc.stop(ctx.currentTime + at + 0.36);
      }
      await sleep(1100);
      ctx.close();
    } catch { /* nope */ }
  };

  const playBlob = (blob: Blob): Promise<void> => new Promise(resolve => {
    const url = URL.createObjectURL(blob);
    const a = new Audio(url);
    audioRef.current = a;
    const done = () => { URL.revokeObjectURL(url); audioRef.current = null; resolve(); };
    a.onended = done; a.onerror = done;
    a.play().catch(done);
  });

  const playUrl = (url: string): Promise<void> => new Promise(resolve => {
    const a = new Audio(url); audioRef.current = a;
    const done = () => { audioRef.current = null; resolve(); };
    a.onended = done; a.onerror = done;
    a.play().catch(done);
  });

  const fetchSyncAudio = async (text: string): Promise<Blob | null> => {
    try {
      const r = await fetch("/api/v1/coached-calls/tts", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, speaker: "sync" }),
      });
      if (!r.ok) return null;
      return await r.blob();
    } catch { return null; }
  };

  const postLine = (speaker: string, text: string) =>
    fetch(`/api/v1/coached-calls/simulate/${callIdRef.current}/line`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ speaker, text }),
    }).catch(() => { /* sim keeps playing */ });

  const drain = async () => {
    while (nudgeQueue.current.length > 0 && !stopRef.current) {
      const n = nudgeQueue.current.shift()!;
      setSpeaking("whisper");
      await playChime(n.tone);
      setEntries(prev => [...prev, { kind: "nudge", text: n.text, tone: n.tone }]);
      await sleep(700);
      setSpeaking(null);
    }
    while (actionQueue.current.length > 0 && !stopRef.current) {
      const a = actionQueue.current.shift()!;
      await playChime("opportunity");
      setActionStatus(s => ({ ...s, [a.id]: "pending" }));
      setEntries(prev => [...prev, {
        kind: "action", id: a.id, tool: a.tool, args: a.args, text: a.preview,
      }]);
      await sleep(500);
    }
  };

  const approveAction = async (id: string, tool: string, args: Record<string, unknown>) => {
    setActionStatus(s => ({ ...s, [id]: "executing" }));
    try {
      const r = await fetch("/api/v1/voice/commands/execute", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tool,
          args: { ...args, connection_id: bridge?.connection_id, client_id: bridge?.client_id },
          confirm: true,
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const result = await r.json();
      if (result?.status === "failed" || result?.error) throw new Error(result.error || "rejected");
      setActionStatus(s => ({ ...s, [id]: "done" }));
    } catch { setActionStatus(s => ({ ...s, [id]: "failed" })); }
  };

  // ── Concierge segment: SYNC voices, scripted RM lines we narrate aloud ──
  const sayAsSync = async (text: string) => {
    setEntries(prev => [...prev, { kind: "line", speaker: "SYNC", text }]);
    setSpeaking("sync");
    postLine("sync", text);
    const blob = await fetchSyncAudio(text);
    if (blob && !stopRef.current) await playBlob(blob);
    else if (!stopRef.current) await speakDialogue(text, SYNC_VOICE);
    setSpeaking(null);
  };

  const fetchRMAudio = async (text: string): Promise<Blob | null> => {
    try {
      const r = await fetch("/api/v1/coached-calls/tts", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, speaker: "rm" }),
      });
      if (!r.ok) return null;
      return await r.blob();
    } catch { return null; }
  };

  const sayAsRM = async (text: string) => {
    setEntries(prev => [...prev, { kind: "line", speaker: rmName, text }]);
    setSpeaking("rm");
    postLine("rm", text);
    const blob = await fetchRMAudio(text);
    if (blob && !stopRef.current) await playBlob(blob);
    else if (!stopRef.current) await speakDialogue(text, RM_VOICE);
    setSpeaking(null);
  };

  const sayAsClient = async (text: string, audioUrl?: string) => {
    setEntries(prev => [...prev, { kind: "line", speaker: bridge?.client_name?.split(" ")[0] ?? "Client", text }]);
    setSpeaking("client");
    postLine("client", text);
    if (audioUrl && !stopRef.current) await playUrl(audioUrl);
    else if (!stopRef.current) await speakDialogue(text, CLIENT_FALLBACK_VOICE);
    setSpeaking(null);
  };

  // ── Bridge: live RM voice via Web Speech API ────────────────────────────
  // Press-and-hold model. The button holder calls beginTalk() on press-down,
  // we capture interim transcripts the whole time, and endTalk() on release
  // resolves the promise with what was heard. No silent timeouts, no canned
  // fallback lines polluting the conversation. If the user hasn't pressed,
  // bridge waits indefinitely (with the "your turn" indicator on).
  const heardResolverRef = useRef<((s: string) => void) | null>(null);
  const heardBufferRef = useRef<string>("");

  const beginTalk = () => {
    if (!hasBrowserSTT) return;
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const r = new SR();
    sttRef.current = r;
    r.continuous = true; r.interimResults = true; r.lang = "en-IN";
    heardBufferRef.current = "";
    r.onresult = (e: any) => {
      let interim = "";
      let finalText = "";
      for (let k = e.resultIndex; k < e.results.length; k++) {
        const res = e.results[k];
        if (res.isFinal) finalText += res[0].transcript + " ";
        else interim += res[0].transcript;
      }
      if (finalText) heardBufferRef.current += finalText;
      setRmInterim((heardBufferRef.current + interim).trim());
    };
    r.onerror = () => { /* swallow — user can release + try again */ };
    try { r.start(); setRmListening(true); } catch { /* already started */ }
  };

  const endTalk = () => {
    try { sttRef.current?.stop(); } catch {}
    setRmListening(false);
    const said = (heardBufferRef.current + " " + rmInterim).trim();
    setRmInterim("");
    heardBufferRef.current = "";
    const resolver = heardResolverRef.current;
    heardResolverRef.current = null;
    if (resolver) {
      resolver(said);
    } else if (said && bridgeMode === "twilio") {
      const key = bridge?.call_key || callIdRef.current;
      if (key) {
        fetch(`/api/v1/coached-calls/simulate/${key}/line`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ speaker: "rm", text: said }),
        }).catch(() => {});
      } else {
        setEntries(prev => [...prev, { kind: "line", speaker: rmName, text: said }]);
      }
    }
  };

  const sendRmText = () => {
    const text = rmText.trim();
    if (!text) return;
    setRmText("");
    const key = bridge?.call_key || callIdRef.current;
    if (key) {
      fetch(`/api/v1/coached-calls/simulate/${key}/line`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ speaker: "rm", text }),
      }).catch(() => {});
    }
  };

  // Wait for the user to press-and-release the Talk button. Resolves with
  // whatever was captured. Times out at 60 s as a last-resort safety net.
  const awaitRmTurn = (): Promise<string> => new Promise(resolve => {
    heardResolverRef.current = resolve;
    setTimeout(() => {
      const r = heardResolverRef.current;
      if (r) { heardResolverRef.current = null; r(""); }
    }, 60_000);
  });

  // Scripted RM lines for the fully automated demo bridge. Each line is sent
  // to the OpenAI client agent, which replies in-character. This way the demo
  // runs end-to-end without anyone touching the mic.
  const AUTO_RM_LINES = [
    `Hi, this is ${rmName} from Acme. Do you have two minutes?`,
    "I was looking at your account this morning and wanted to talk about the business loan EMIs.",
    "I completely understand. There is actually a way to bring your monthly outgo down quite a bit.",
    "How about this — I will hold a slot Thursday at four PM and walk you through the numbers. No commitment.",
    "Perfect, locking it in. I will send the details. Thanks, talk Thursday!",
  ];

  const startBridge = async (b: BridgeOpenEvent, autoPlay = false) => {
    // Open the OpenAI role-play session for the client.
    const r = await fetch(`/api/v1/client-agent/${b.bridge_id}/start`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ client_id: b.client_id, client_name: b.client_name,
                             brief: b.client_brief, connection_id: b.connection_id }),
    });
    const j = await r.json();
    const opener = j?.opener;
    if (opener?.text) {
      await sayAsClient(opener.text,
        opener.audio_ready
          ? `/api/v1/client-agent/${b.bridge_id}/audio/${opener.turn_id}.mp3`
          : undefined);
      await drain();
    }

    if (autoPlay) {
      // Fully scripted: play each RM line, get client reply, repeat.
      for (const rmLine of AUTO_RM_LINES) {
        if (stopRef.current) break;
        await sayAsRM(rmLine);
        await drain();
        if (stopRef.current) break;

        const turn = await fetch(`/api/v1/client-agent/${b.bridge_id}/turn`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ rm_text: rmLine }),
        }).then(r => r.ok ? r.json() : null).catch(() => null);
        if (!turn?.text) break;
        await sayAsClient(turn.text,
          turn.audio_ready
            ? `/api/v1/client-agent/${b.bridge_id}/audio/${turn.turn_id}.mp3`
            : undefined);
        await drain();
      }
    } else {
      // Interactive: press-and-hold mic for each RM turn.
      for (let i = 0; i < 6; i++) {
        if (stopRef.current) break;
        const said = (await awaitRmTurn()).trim();
        if (stopRef.current) break;
        if (!said) continue;
        setEntries(prev => [...prev, { kind: "line", speaker: rmName, text: said }]);
        postLine("rm", said);

        const turn = await fetch(`/api/v1/client-agent/${b.bridge_id}/turn`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ rm_text: said }),
        }).then(r => r.ok ? r.json() : null).catch(() => null);
        if (!turn?.text) break;
        await sayAsClient(turn.text,
          turn.audio_ready
            ? `/api/v1/client-agent/${b.bridge_id}/audio/${turn.turn_id}.mp3`
            : undefined);
        await drain();
      }
    }

    // Cleanup the role-play session.
    fetch(`/api/v1/client-agent/${b.bridge_id}/end`, { method: "POST" }).catch(() => {});
  };

  // ── Test-only: skip straight to Twilio call without Ringg widget ────
  const testTwilioCall = async () => {
    stopRef.current = false;
    setEntries([]); setActionStatus({});
    setSidebarNudges([]); setSidebarActions([]);
    nudgeQueue.current = []; actionQueue.current = [];
    setBridgeMode("twilio");

    const phone = clientPhone || "+917678456033";
    const callKey = `test_${Date.now().toString(36)}`;
    setPhase("bridging");
    setEntries(prev => [...prev, {
      kind: "event", text: `Dialing ${phone} via Twilio — SYNC is listening.`,
    }]);

    try {
      const bd: BridgeOpenEvent = {
        bridge_id: callKey, client_id: "",
        client_name: "Client",
        client_brief: "", connection_id: "conn_test",
        mode: "twilio", call_key: callKey, client_phone: phone,
      };
      setBridge(bd);
      callIdRef.current = callKey;
      setPhase("bridge");
    } catch (err: any) {
      console.error("[TestTwilio] failed:", err);
      setEntries(prev => [...prev, {
        kind: "event", text: `[TEST] Error: ${err.message}`,
      }]);
      setPhase("ended");
    }
  };

  // ── Twilio bridge: real phone call, no OpenAI client agent ──────────
  const runTwilioBridge = async (b: BridgeOpenEvent) => {
    stopRef.current = false;
    setEntries([]); setActionStatus({});
    setSidebarNudges([]); setSidebarActions([]);
    nudgeQueue.current = []; actionQueue.current = [];
    setBridgeMode("twilio");

    await teardownRinggWidget();

    setPhase("bridging");
    setEntries(prev => [...prev, {
      kind: "event",
      text: `Dialing ${(b.client_name || "the client").split(" ")[0]} on their phone — SYNC is listening for coaching.`,
    }]);
    await ringTone(); await ringTone();
    if (stopRef.current) return;
    setPhase("bridge");
    // TwilioCallControls handles the actual call — we just stay in bridge
    // phase until the call ends (onCallEnded callback).
  };

  const onTwilioCallEnded = () => {
    if (callIdRef.current) {
      fetch(`/api/v1/coached-calls/simulate/${callIdRef.current}/end`, { method: "POST" }).catch(() => {});
    }
    setPhase("wrapup");
    setTimeout(() => {
      setPhase("ended");
      reloadRinggWidget();
    }, 2000);
  };

  const reloadRinggWidget = () => {
    const w = window as any;
    w.__ringgWidgetLoaded = false;
    const agentId = import.meta.env.VITE_RINGG_WIDGET_AGENT_ID;
    const xApiKey = import.meta.env.VITE_RINGG_WIDGET_KEY;
    if (!agentId || !xApiKey || typeof w.loadAgent !== "function") return;
    try {
      w.loadAgent({
        agentId, xApiKey, defaultTab: "audio", hideTabSelector: true,
        title: "Call SYNC",
        description: "Talk to your CRM — briefings, tasks, meetings, by voice.",
        variables: { company_name: "Acme", rm_name: rmName },
        buttons: {},
      });
    } catch {}
  };

  // ── The arc ────────────────────────────────────────────────────────────
  // Widget-triggered bridge: the user is on a live Ringg widget call and the
  // agent just fired start_call_with. Skip the briefing prologue (already
  // happened in the widget) and go straight to the bridge phase.
  const runWidgetBridge = async (b: BridgeOpenEvent) => {
    stopRef.current = false;
    setEntries([]); setActionStatus({});
    setSidebarNudges([]); setSidebarActions([]);
    nudgeQueue.current = []; actionQueue.current = [];
    setPhase("bridging");
    setEntries(prev => [...prev, {
      kind: "event",
      text: `Ending the Ringg call — bringing ${(b.client_name || "the client").split(" ")[0]} on the line.`,
    }]);

    // CRITICAL: the Ringg widget owns the microphone while its call is alive,
    // which blocks Web Speech API in the bridge. Tear the widget down so the
    // mic is freed before we ask the RM to speak.
    await teardownRinggWidget();

    // Start a proper simulate session so the line POSTs in startBridge() route
    // through the coaching engine and broadcast whispers + action suggestions.
    try {
      const r = await fetch("/api/v1/coached-calls/simulate/start", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: b.client_id, client_name: b.client_name,
          rm_name: rmName, connection_id: b.connection_id, scenario: "coached",
        }),
      });
      if (r.ok) {
        const j = await r.json();
        callIdRef.current = j.call_id;          // tagged so WS handler accepts coaching events
      }
    } catch { /* keep going — bridge still plays, whispers may not fire */ }

    await ringTone(); await ringTone();
    if (stopRef.current) return;
    setPhase("bridge");
    await startBridge(b, false);
    if (stopRef.current) return;
    // End the simulate session so post-call analysis runs.
    if (callIdRef.current) {
      fetch(`/api/v1/coached-calls/simulate/${callIdRef.current}/end`, { method: "POST" }).catch(() => {});
    }
    setPhase("wrapup");
    await sleep(700);
    await sayAsSync("Call wrapped. I've logged a recap and updated the radar.");
    setPhase("ended");
  };

  const runArc = async () => {
    stopRef.current = false;
    setEntries([]); setActionStatus({}); setBridge(null);
    nudgeQueue.current = []; actionQueue.current = [];

    setPhase("ringing");
    const startResp = await fetch("/api/v1/coached-calls/simulate/start", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rm_name: rmName, scenario: "standup" }),
    });
    if (!startResp.ok) { setPhase("idle"); return; }
    const startJson = await startResp.json();
    callIdRef.current = startJson.call_id;

    await ringTone();
    if (stopRef.current) return;
    setPhase("concierge");

    // 1. Concierge: greeting + asks the day
    await sayAsSync(`Good morning ${rmName}! You've got two meetings on the books and a few flags overnight. Want the rundown?`);
    await sayAsRM("Yes — go ahead, what's on my plate today?");
    await sayAsSync("Two client meetings, three follow-ups due, and one save-call I've been holding for your approval.");

    // 2. RM asks for top priority. The agent calls /top_priority server-side.
    await sayAsRM("Skip the rundown — what's my top priority right now?");
    let top: { client_name: string; client_id: string; spoken: string; play_id?: string } | null = null;
    try {
      const t = await fetch("/api/v1/ringg-tools/top_priority", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ call_id: callIdRef.current }),
      });
      if (t.ok) {
        const j = await t.json();
        top = { client_name: j.client_name, client_id: j.client_id, spoken: j.spoken, play_id: j.play_id };
      }
    } catch { /* keep arc moving */ }
    const topName = top?.client_name ?? "Vikram Desai";
    const topSpoken = top?.spoken ?? `Your top priority is ${topName} — CRITICAL urgency. Missed two EMIs, credit card maxed. The play is a restructure that saves him about three lakh.`;
    await sayAsSync(topSpoken);

    // 3. The proactive offer + RM accepts.
    await sayAsSync(`Want me to call ${topName.split(" ")[0]} for you? I'll bring him on the line and stay to listen.`);
    await sayAsRM("Yes — connect me with him.");

    // 4. SYNC kicks off the bridge — server broadcasts bridge_open via WS.
    setPhase("bridging");
    let bridgeData: BridgeOpenEvent | null = null;
    let isTwilioMode = false;
    try {
      const r = await fetch("/api/v1/ringg-tools/start_call_with", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          call_id: callIdRef.current,
          client_hint: topName,
          live_mode: liveClient,
          client_phone: liveClient ? clientPhone : undefined,
        }),
      });
      if (r.ok) {
        const j = await r.json();
        await sayAsSync(j.spoken);
        isTwilioMode = j.mode === "twilio";
        bridgeData = {
          bridge_id: j.bridge_id, client_id: j.client_id, client_name: j.client_name,
          client_brief: "", connection_id: "conn_pipedrive_demo",
          mode: j.mode, call_key: j.call_key,
          client_phone: clientPhone || undefined,
        };
        if (isTwilioMode) {
          setBridgeMode("twilio");
          if (j.call_key) callIdRef.current = j.call_key;
        }
        setBridge(bridgeData);
        // The WS broadcast usually arrives first with the brief — wait briefly.
        for (let i = 0; i < 30 && !bridge; i++) await sleep(50);
      }
    } catch { /* run with what we have */ }
    setEntries(prev => [...prev, {
      kind: "event",
      text: liveClient
        ? `Dialing ${topName.split(" ")[0]} on ${clientPhone || "the configured number"} — your phone will ring shortly.`
        : `Dialing ${topName.split(" ")[0]}…`,
    }]);
    await ringTone(); await ringTone();
    if (stopRef.current) return;

    // 5. The bridge — live whisper coaching while you and the client converse.
    setPhase("bridge");

    if (isTwilioMode) {
      // Twilio mode: TwilioCallControls component handles the real call.
      // We stay in "bridge" phase until onTwilioCallEnded fires.
      return;
    }

    await startBridge(bridge ?? bridgeData!, true);

    if (stopRef.current) return;
    setPhase("wrapup");
    await sleep(700);
    await sayAsSync("Call wrapped. I've logged a recap and updated the radar. Have a great rest of your day.");
    await fetch(`/api/v1/coached-calls/simulate/${callIdRef.current}/end`, { method: "POST" }).catch(() => {});
    setPhase("ended");
  };

  const hangUp = async () => {
    stopRef.current = true;
    // Release the mic if we were listening + resolve any pending RM-turn await.
    try { sttRef.current?.stop(); } catch {}
    setRmListening(false); setRmInterim("");
    if (heardResolverRef.current) { heardResolverRef.current(""); heardResolverRef.current = null; }
    if (whisperSupported()) window.speechSynthesis.cancel();
    audioRef.current?.pause(); audioRef.current = null;
    if (callIdRef.current) {
      fetch(`/api/v1/coached-calls/simulate/${callIdRef.current}/end`, { method: "POST" }).catch(() => {});
    }
    setPhase("ended");
  };

  const live = phase !== "idle" && phase !== "ended";
  const showSidebar = live || sidebarNudges.length > 0 || sidebarActions.length > 0;

  return (
    <div className="min-h-screen bg-paper-grain text-ink antialiased">
      <div className="border-b border-ink/15 bg-paper">
        <div className="mx-auto flex h-8 max-w-[1100px] items-center justify-between px-4 font-edit-mono text-[10px] uppercase tracking-widest text-ink/60 md:px-6">
          <button onClick={() => navigate("/")} className="inline-flex items-center gap-1.5 hover:text-ink">
            <ArrowLeft className="h-3 w-3" /> Home
          </button>
          <div className="flex items-center gap-3">
            <button onClick={() => navigate("/settings/integrations")} className="inline-flex items-center gap-1 hover:text-ink">
              <Settings className="h-3 w-3" /> Integrations
            </button>
            <span className="text-ink/30">·</span>
            <span>§ The Demo</span>
          </div>
        </div>
      </div>

      <main className="mx-auto max-w-[1100px] px-4 py-10 md:px-6 md:py-12">
        <header className="border-b border-ink/15 pb-6">
          <p className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/50">
            § Submission · Voice AI Buildathon
          </p>
          <h1 className="mt-2 font-display text-5xl leading-[0.95] text-ink md:text-6xl">
            One call. <em className="italic">Every</em> feature.
          </h1>
          <p className="mt-3 max-w-2xl font-serif text-lg italic leading-snug text-ink/70">
            The RM calls SYNC for the morning rundown, asks for today's top priority,
            and asks SYNC to dial the at-risk client. The client picks up. The RM
            speaks live. SYNC listens, whispers coaching, and turns the agreed
            meeting into a real Pipedrive calendar event — without anyone touching a screen.
          </p>
          {live && (
            <div className="mt-6">
              <button
                onClick={hangUp}
                className="inline-flex items-center gap-2 border-2 border-red-800 bg-red-800 px-6 py-3 font-edit-mono text-[11px] uppercase tracking-widest text-paper hover:bg-paper hover:text-red-800"
              >
                <PhoneOff className="h-3.5 w-3.5" /> End the demo
              </button>
            </div>
          )}
          {!live && (
            <div className="mt-6 flex flex-wrap items-center gap-3 border border-ink/15 bg-paper px-4 py-3">
              <div className="flex items-center gap-2">
                <label className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/50">RM Name</label>
                <input
                  value={rmName}
                  onChange={(e) => setRmName(e.target.value)}
                  placeholder="Your name"
                  className="w-40 border border-ink/30 bg-paper px-3 py-1.5 font-serif text-[13px] text-ink focus:border-ink focus:outline-none"
                />
              </div>
              <div className="flex items-center gap-2">
                <label className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/50">Phone</label>
                <input
                  value={clientPhone}
                  onChange={(e) => setClientPhone(e.target.value)}
                  placeholder="+91 9XXXX XXXXX"
                  className="w-48 border border-ink/30 bg-paper px-3 py-1.5 font-edit-mono text-[11px] tabular-nums text-ink focus:border-ink focus:outline-none"
                />
              </div>
              <p className="basis-full font-serif text-[10px] italic text-ink/40">
                Use the floating <Phone className="inline h-3 w-3" /> widget to call SYNC. The RM name flows into the greeting, transcript labels, and Ringg agent variables.
              </p>
            </div>
          )}
        </header>

        {/* Phase strip */}
        <div className="mt-5 grid grid-cols-4 gap-2">
          {(["concierge", "bridging", "bridge", "wrapup"] as Phase[]).map((step, i) => {
            const order = ["concierge", "bridging", "bridge", "wrapup"];
            const idx = order.indexOf(phase as string);
            const active = idx === i;
            const done = idx > i;
            return (
              <div key={step}
                className={`border-l-4 bg-paper px-3 py-2 font-edit-mono text-[10px] uppercase tracking-widest ${
                  active ? "border-emerald-700 text-ink" :
                  done ? "border-ink/70 text-ink/60" : "border-ink/15 text-ink/35"
                }`}>
                <div>{`0${i + 1}`}</div>
                <div className="mt-0.5 font-bold">
                  {step === "concierge" ? "Briefing" :
                   step === "bridging" ? "Bridging" :
                   step === "bridge" ? "On the call" : "Wrap-up"}
                </div>
              </div>
            );
          })}
        </div>

        {/* Transcript + co-pilot sidebar (sidebar only renders during a call) */}
        <div className={`mt-6 grid gap-4 ${showSidebar ? "md:grid-cols-[1fr_320px]" : "grid-cols-1"}`}>
          <div ref={scrollRef} className="h-[28rem] overflow-y-auto border border-ink/15 bg-ink/[0.015] p-4">
            {phase === "idle" && (
              <p className="flex h-full items-center justify-center text-center font-serif text-base italic text-ink/40">
                Press “Run the demo” — the whole arc plays in about ninety seconds, with live whispers and a real Pipedrive write at the end.
              </p>
            )}
            <div className="space-y-2">
              {entries.map((e, i) =>
                e.kind === "line" ? (
                  <p key={i} className="font-serif text-[14px] leading-snug text-ink/90">
                    <span className={`font-edit-mono text-[10px] font-bold uppercase tracking-widest ${
                      e.speaker === "SYNC" ? "text-emerald-800" :
                      e.speaker === rmName ? "text-ink/70" : "text-amber-800"
                    }`}>{e.speaker}</span>
                    {"  "}{e.text}
                  </p>
                ) : e.kind === "event" ? (
                  <div key={i} className="border-2 border-dashed border-ink/30 bg-amber-50/60 px-3 py-2 text-center font-edit-mono text-[10px] uppercase tracking-widest text-amber-900">
                    📞 {e.text}
                  </div>
                ) : e.kind === "nudge" ? (
                  <NudgeRow key={i} text={e.text} tone={e.tone ?? "suggest"} />
                ) : (
                  <ActionRow key={e.id ?? i}
                    preview={e.text} status={actionStatus[e.id ?? ""] ?? "pending"}
                    onApprove={() => approveAction(e.id!, e.tool!, e.args ?? {})}
                    onSkip={() => setActionStatus(s => ({ ...s, [e.id!]: "skipped" }))} />
                )
              )}
            </div>
          </div>

          {/* Right rail — live intelligence (persists after call ends) */}
          {showSidebar && (
            <CopilotSidebar
              nudges={sidebarNudges}
              actions={sidebarActions.map(a => ({
                ...a,
                status: actionStatus[a.id] ?? "pending",
              }))}
              onApprove={(id, tool, args) => approveAction(id, tool, args)}
              onSkip={(id) => setActionStatus(s => ({ ...s, [id]: "skipped" }))}
              onSayClick={(line) => {
                // Optional: speak it aloud so the RM can hear the suggested line
                // through the earbud. (User can also just read it on-screen.)
                try {
                  const u = new SpeechSynthesisUtterance(line);
                  u.rate = 1.0; u.pitch = 0.95;
                  window.speechSynthesis.speak(u);
                } catch { /* no-op */ }
              }}
            />
          )}
        </div>

        {/* Call controls during the bridge phase */}
        {phase === "bridge" && bridgeMode === "twilio" && bridge?.call_key && (
          <TwilioCallControls
            callKey={bridge.call_key}
            clientPhone={bridge.client_phone || clientPhone}
            clientName={bridge.client_name || "Client"}
            onCallEnded={onTwilioCallEnded}
          />
        )}
        {phase === "bridge" && bridgeMode === "twilio" && (
          <div className="mt-4 flex flex-col items-center gap-2 border-t border-ink/15 pt-4">
            <p className="font-serif text-[11px] italic text-ink/50">
              Your browser mic feeds the call. Speak naturally — SYNC transcribes both sides automatically.
            </p>
            <div className="flex w-full max-w-lg items-center gap-2">
              <input
                value={rmText}
                onChange={(e) => setRmText(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") sendRmText(); }}
                placeholder="Type as RM (press Enter to send)…"
                className="flex-1 border border-ink/30 bg-paper px-3 py-2 font-edit-mono text-[12px] text-ink focus:border-ink focus:outline-none"
              />
              <button
                onClick={sendRmText}
                disabled={!rmText.trim()}
                className="inline-flex items-center gap-1.5 border-2 border-ink bg-ink px-4 py-2 font-edit-mono text-[11px] uppercase tracking-widest text-cream hover:bg-paper hover:text-ink disabled:opacity-40"
              >
                <SendHorizontal className="h-3.5 w-3.5" /> Send
              </button>
            </div>
          </div>
        )}
        {phase === "bridge" && bridgeMode !== "twilio" && (
          <div className="mt-4 flex flex-col items-center gap-2 border-t border-ink/15 pt-4">
            <button
              onMouseDown={beginTalk}
              onMouseUp={endTalk}
              onMouseLeave={() => { if (rmListening) endTalk(); }}
              onTouchStart={(e) => { e.preventDefault(); beginTalk(); }}
              onTouchEnd={(e) => { e.preventDefault(); endTalk(); }}
              disabled={!hasBrowserSTT}
              className={`inline-flex items-center gap-2 border-2 px-6 py-3 font-edit-mono text-[11px] uppercase tracking-widest transition-colors disabled:opacity-40 ${
                rmListening
                  ? "border-emerald-700 bg-emerald-700 text-paper"
                  : "border-ink bg-ink text-cream hover:bg-paper hover:text-ink"
              }`}
              title="Press and hold to talk as the RM"
            >
              <Mic className={`h-4 w-4 ${rmListening ? "animate-pulse" : ""}`} />
              {rmListening ? "Listening… release to send" : "Hold to talk"}
            </button>
            {rmInterim && (
              <p className="max-w-xl text-center font-serif text-[13px] italic leading-snug text-ink/70">
                "{rmInterim}"
              </p>
            )}
            {!hasBrowserSTT && (
              <p className="text-center font-serif text-[11px] italic text-red-800">
                This browser doesn't support live mic capture — use Chrome on desktop.
              </p>
            )}
          </div>
        )}

        {/* Widget pointer */}
        
      </main>

      {/* CRM embed rail */}
      {embedOpen && bridge?.client_id && (
        <div className="fixed inset-y-0 right-0 z-[60] w-full max-w-[440px] border-l-2 border-ink bg-paper shadow-2xl">
          <div className="flex h-full flex-col">
            <div className="flex items-center justify-between border-b border-ink bg-ink/[0.02] px-4 py-3">
              <span className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/70">
                § CRM Contact View
              </span>
              <button
                onClick={() => setEmbedOpen(false)}
                className="flex h-6 w-6 items-center justify-center border border-ink/30 text-ink/60 hover:bg-ink hover:text-paper"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
            <div className="flex-1 overflow-hidden">
              <CRMEmbedRail
                connections={[{ id: connectionId, provider: providerFromConnectionId(connectionId), label: connectionId }]}
                clientId={bridge.client_id}
                defaultProvider={providerFromConnectionId(connectionId)}
                onClose={() => setEmbedOpen(false)}
              />
            </div>
          </div>
        </div>
      )}

      {/* Floating "Open CRM view" button — visible when a client is active */}
      {!embedOpen && bridge?.client_id && (
        <div className="fixed bottom-6 right-20 z-30">
          <button
            onClick={() => setEmbedOpen(true)}
            className="inline-flex items-center gap-2 border-2 border-ink bg-paper px-4 py-2.5 font-edit-mono text-[10px] uppercase tracking-widest text-ink shadow-lg transition-colors hover:bg-ink hover:text-cream"
          >
            <PanelRightOpen className="h-3 w-3" />
            Open in CRM
          </button>
        </div>
      )}

      {/* Live whisper coaching — renders nudge cards globally during a real
          widget call (transcripts come via Ringg webhooks → coaching engine). */}
      <CoachingOverlay />

      {/* Ringg web-call widget */}
      <WebCallWidget />
    </div>
  );
}

function NudgeRow({ text, tone }: { text: string; tone: string }) {
  const t = TONE_META[tone] ?? TONE_META.suggest;
  return (
    <div className={`flex items-start gap-2 border-l-4 border-y border-r px-2.5 py-1.5 ${t.cls}`}>
      <Headphones className="mt-0.5 h-3 w-3 shrink-0" />
      <div className="min-w-0">
        <span className="font-edit-mono text-[9px] font-bold uppercase tracking-widest opacity-70">
          <t.Icon className="mr-1 inline h-3 w-3" />{t.label} · SYNC whispers
        </span>
        <p className="font-serif text-[13px] italic leading-snug">{text}</p>
      </div>
    </div>
  );
}

function ActionRow({ preview, status, onApprove, onSkip }: {
  preview: string; status: ActionState; onApprove: () => void; onSkip: () => void;
}) {
  return (
    <div className="flex items-start gap-2 border-2 border-ink bg-paper px-2.5 py-2 shadow-sm">
      <CalendarPlus className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink/70" />
      <div className="min-w-0 flex-1">
        <span className="font-edit-mono text-[9px] font-bold uppercase tracking-widest text-ink/50">
          SYNC heard a commitment
        </span>
        <p className="font-serif text-[13px] leading-snug text-ink">{preview}</p>
        <div className="mt-1.5 flex items-center gap-2">
          {status === "pending" && (
            <>
              <button onClick={onApprove}
                className="inline-flex items-center gap-1 border border-emerald-800 bg-emerald-800 px-2.5 py-1 font-edit-mono text-[9px] font-bold uppercase tracking-widest text-paper hover:bg-paper hover:text-emerald-800">
                <Check className="h-3 w-3" /> Approve · file in CRM
              </button>
              <button onClick={onSkip}
                className="inline-flex items-center gap-1 border border-ink/30 px-2.5 py-1 font-edit-mono text-[9px] uppercase tracking-widest text-ink/60 hover:bg-ink/[0.05]">
                <X className="h-3 w-3" /> Skip
              </button>
            </>
          )}
          {status === "executing" && (
            <span className="inline-flex items-center gap-1 font-edit-mono text-[9px] uppercase tracking-widest text-ink/60">
              <Loader2 className="h-3 w-3 animate-spin" /> Writing to CRM…
            </span>
          )}
          {status === "done" && (
            <span className="inline-flex items-center gap-1 font-edit-mono text-[9px] font-bold uppercase tracking-widest text-emerald-800">
              <Check className="h-3 w-3" /> Filed in Pipedrive
            </span>
          )}
          {status === "skipped" && (
            <span className="font-edit-mono text-[9px] uppercase tracking-widest text-ink/40">Skipped</span>
          )}
          {status === "failed" && (
            <span className="inline-flex items-center gap-2 font-edit-mono text-[9px] uppercase tracking-widest text-red-800">
              Failed — <button onClick={onApprove} className="underline">retry</button>
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
