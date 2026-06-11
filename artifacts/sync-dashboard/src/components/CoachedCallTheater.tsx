/**
 * CoachedCallTheater — a one-click, self-contained demo of a coached call.
 *
 * Plays a scripted RM ↔ client conversation with two TTS voices, but every
 * line is POSTed to the backend as it's spoken and runs through the REAL
 * emit_transcript_chunk → coaching pipeline. The whisper nudges that appear
 * (and are spoken into the ear) are computed live by the coaching engine —
 * not pre-scripted — so judges see the genuine loop without placing a call.
 *
 * Audio sequencing: the theater owns the SpeechSynthesis queue while open
 * (setTheaterActive suppresses the global speakNudge). After each dialogue
 * line finishes, any queued nudges play as whispers before the next line.
 */
import { useEffect, useRef, useState } from "react";
import { Headphones, PhoneOff, Play, AlertTriangle, Sparkles, Lightbulb, CalendarPlus, Check, Loader2, X } from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { useWebSocket, WebSocketMessage } from "@/hooks/use-websocket";
import { playChime, setTheaterActive, speakDialogue, whisperSupported } from "@/lib/whisper";

interface ScriptLine { speaker: "rm" | "client"; text: string; }
interface Nudge { text: string; tone: "warn" | "opportunity" | "suggest"; }
interface ActionSuggestion { id: string; tool: string; args: Record<string, unknown>; preview: string; }
interface TranscriptEntry {
  kind: "line" | "nudge" | "action";
  speaker?: string; text: string; tone?: string;
  id?: string; tool?: string; args?: Record<string, unknown>;
}
type ActionState = "pending" | "executing" | "done" | "skipped" | "failed";

interface Props {
  open: boolean;
  onClose: () => void;
  clientId: string;
  clientName: string;
  rmName: string;
  connectionId: string;
}

// Distinct voice profiles — same underlying voice, different pitch/rate reads
// clearly as two people on every browser without voice-name guessing.
const RM_VOICE = { pitch: 0.85, rate: 1.0 };
const CLIENT_VOICE = { pitch: 1.12, rate: 0.97 };

const TONE_META: Record<string, { cls: string; Icon: typeof AlertTriangle; label: string }> = {
  warn:        { cls: "border-red-700/50 bg-red-50 text-red-900",             Icon: AlertTriangle, label: "Watch" },
  opportunity: { cls: "border-emerald-700/50 bg-emerald-50 text-emerald-900", Icon: Sparkles,      label: "Opening" },
  suggest:     { cls: "border-ink/40 bg-ink/[0.04] text-ink",                 Icon: Lightbulb,     label: "Nudge" },
};

export function CoachedCallTheater({ open, onClose, clientId, clientName, rmName, connectionId }: Props) {
  const [phase, setPhase] = useState<"idle" | "ringing" | "live" | "ended">("idle");
  const [entries, setEntries] = useState<TranscriptEntry[]>([]);
  const [speaking, setSpeaking] = useState<"rm" | "client" | "whisper" | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [nudgeCount, setNudgeCount] = useState(0);
  const [actionStatus, setActionStatus] = useState<Record<string, ActionState>>({});

  const callIdRef = useRef<string>("");
  const nudgeQueue = useRef<Nudge[]>([]);
  const actionQueue = useRef<ActionSuggestion[]>([]);
  const stopRef = useRef(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const premiumTtsRef = useRef(false);

  // ── Natural voices (ElevenLabs via backend proxy, cached server-side). ──
  // Falls back to browser speechSynthesis per-line when the key isn't set
  // or a fetch fails, so the sim always plays.
  const fetchAudio = async (text: string, speaker: "rm" | "client"): Promise<Blob | null> => {
    if (!premiumTtsRef.current) return null;
    try {
      const r = await fetch("/api/v1/coached-calls/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // client_name lets the backend pick a gender-appropriate client voice
        body: JSON.stringify({ text, speaker, client_name: clientName }),
      });
      if (!r.ok) return null;
      return await r.blob();
    } catch { return null; }
  };

  const playBlob = (blob: Blob): Promise<void> => new Promise(resolve => {
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audioRef.current = audio;
    const done = () => { URL.revokeObjectURL(url); audioRef.current = null; resolve(); };
    audio.onended = done;
    audio.onerror = done;
    audio.play().catch(done);
  });

  // Collect live nudges + action suggestions for OUR call from the shared socket.
  useWebSocket({
    onMessage: (msg: WebSocketMessage) => {
      if (!callIdRef.current || msg.data?.call_id !== callIdRef.current) return;
      if (msg.type === "coaching_nudge") {
        const tone = (["warn", "opportunity", "suggest"].includes(msg.data?.tone)
          ? msg.data.tone : "suggest") as Nudge["tone"];
        nudgeQueue.current.push({ text: msg.data?.text ?? "", tone });
      } else if (msg.type === "coaching_action_suggestion") {
        actionQueue.current.push({
          id: msg.data?.suggestion_id ?? Math.random().toString(36).slice(2, 10),
          tool: msg.data?.tool ?? "",
          args: msg.data?.args ?? {},
          preview: msg.data?.preview ?? "",
        });
      }
    },
  });

  // Call timer.
  useEffect(() => {
    if (phase !== "live") return;
    const t = setInterval(() => setElapsed(e => e + 1), 1000);
    return () => clearInterval(t);
  }, [phase]);

  // Auto-scroll transcript.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [entries]);

  // Own the audio while open; hard-stop everything on close.
  useEffect(() => {
    if (open) { setTheaterActive(true); return; }
    setTheaterActive(false);
    stopRef.current = true;
    if (whisperSupported()) window.speechSynthesis.cancel();
    audioRef.current?.pause();
    audioRef.current = null;
  }, [open]);

  const ringTone = async () => {
    try {
      const ctx = new AudioContext();
      for (const at of [0, 0.45]) {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.frequency.value = 425;             // Indian ringback tone frequency
        gain.gain.setValueAtTime(0.08, ctx.currentTime + at);
        gain.gain.setValueAtTime(0.0001, ctx.currentTime + at + 0.35);
        osc.connect(gain).connect(ctx.destination);
        osc.start(ctx.currentTime + at);
        osc.stop(ctx.currentTime + at + 0.36);
      }
      await new Promise(r => setTimeout(r, 1100));
      ctx.close();
    } catch { /* no ring is fine */ }
  };

  // Whispers are chime + card only — SYNC's tips land silently in the eye,
  // never read aloud over the conversation.
  const drainNudges = async () => {
    while (nudgeQueue.current.length > 0 && !stopRef.current) {
      const n = nudgeQueue.current.shift()!;
      setNudgeCount(c => c + 1);
      setSpeaking("whisper");
      await playChime(n.tone);
      setEntries(prev => [...prev, { kind: "nudge", text: n.text, tone: n.tone }]);
      await new Promise(res => setTimeout(res, 900));
      setSpeaking(null);
    }
    // Detected commitments surface as approval cards — the RM one-clicks and
    // the activity is written to the live CRM through the voice-command path.
    while (actionQueue.current.length > 0 && !stopRef.current) {
      const a = actionQueue.current.shift()!;
      await playChime("opportunity");
      setActionStatus(s => ({ ...s, [a.id]: "pending" }));
      setEntries(prev => [...prev, {
        kind: "action", id: a.id, tool: a.tool, args: a.args, text: a.preview,
      }]);
      await new Promise(res => setTimeout(res, 600));
    }
  };

  const approveAction = async (id: string, tool: string, args: Record<string, unknown>) => {
    setActionStatus(s => ({ ...s, [id]: "executing" }));
    try {
      const r = await fetch("/api/v1/voice/commands/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tool,
          args: { ...args, connection_id: connectionId, client_id: clientId },
          confirm: true,
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const result = await r.json();
      if (result?.status === "failed" || result?.error) throw new Error(result.error || "rejected");
      setActionStatus(s => ({ ...s, [id]: "done" }));
    } catch {
      setActionStatus(s => ({ ...s, [id]: "failed" }));
    }
  };

  const run = async () => {
    stopRef.current = false;
    setEntries([]); setElapsed(0); setNudgeCount(0); setActionStatus({});
    nudgeQueue.current = [];
    actionQueue.current = [];
    setPhase("ringing");

    try {
      const r = await fetch("/api/v1/coached-calls/simulate/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client_id: clientId, client_name: clientName, rm_name: rmName, connection_id: connectionId }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const { call_id, script, labels, premium_tts } = await r.json() as
        { call_id: string; script: ScriptLine[]; labels: { rm: string; client: string }; premium_tts?: boolean };
      callIdRef.current = call_id;
      premiumTtsRef.current = !!premium_tts;

      // Prefetch one line ahead so natural-voice playback has no gaps
      // (sequential, not parallel — free-tier providers cap concurrency).
      let nextAudio: Promise<Blob | null> = fetchAudio(script[0].text, script[0].speaker);

      await ringTone();
      if (stopRef.current) return;
      setPhase("live");

      for (let i = 0; i < script.length; i++) {
        if (stopRef.current) break;
        const line = script[i];
        const audioPromise = nextAudio;
        const label = line.speaker === "rm" ? labels.rm : labels.client;
        setEntries(prev => [...prev, { kind: "line", speaker: label, text: line.text }]);
        setSpeaking(line.speaker);
        // Post to the real coaching pipeline while the line is being spoken —
        // the nudge computes in parallel, exactly like a live call.
        fetch(`/api/v1/coached-calls/simulate/${call_id}/line`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ speaker: line.speaker, text: line.text }),
        }).catch(() => { /* sim keeps playing even if a post drops */ });

        const blob = await audioPromise;
        nextAudio = i + 1 < script.length
          ? fetchAudio(script[i + 1].text, script[i + 1].speaker)
          : Promise.resolve(null);

        if (blob && !stopRef.current) {
          await playBlob(blob);
        } else if (!stopRef.current) {
          await speakDialogue(line.text, line.speaker === "rm" ? RM_VOICE : CLIENT_VOICE);
        }
        setSpeaking(null);
        if (stopRef.current) break;
        await drainNudges();
        await new Promise(res => setTimeout(res, 350));
      }

      // Let any last in-flight nudge land, then close out.
      await new Promise(res => setTimeout(res, 1200));
      await drainNudges();
      await fetch(`/api/v1/coached-calls/simulate/${call_id}/end`, { method: "POST" }).catch(() => {});
    } catch {
      // Backend unreachable — end gracefully rather than hanging the dialog.
    } finally {
      if (!stopRef.current) setPhase("ended");
    }
  };

  const hangUp = async () => {
    stopRef.current = true;
    if (whisperSupported()) window.speechSynthesis.cancel();
    audioRef.current?.pause();
    audioRef.current = null;
    if (callIdRef.current) {
      fetch(`/api/v1/coached-calls/simulate/${callIdRef.current}/end`, { method: "POST" }).catch(() => {});
    }
    setPhase("ended");
  };

  const close = () => { hangUp(); setPhase("idle"); onClose(); };
  const clientFirst = clientName.split(" ")[0] || clientName;

  return (
    <Dialog open={open} onOpenChange={(o) => !o && close()}>
      <DialogContent className="rounded-none border-ink bg-paper sm:max-w-[620px]">
        <DialogHeader>
          <DialogTitle className="flex items-center justify-between font-edit-mono text-[10px] uppercase tracking-widest text-ink/60">
            <span>§ Coached Call · Live Simulation</span>
            {phase === "live" && (
              <span className="tabular-nums text-emerald-800">
                ● {String(Math.floor(elapsed / 60)).padStart(2, "0")}:{String(elapsed % 60).padStart(2, "0")}
              </span>
            )}
          </DialogTitle>
          <DialogDescription className="font-serif text-[12px] italic text-ink/60">
            Two AI voices play the call; every line streams through SYNC's real
            coaching engine — the whispers below are computed live, not scripted.
          </DialogDescription>
        </DialogHeader>

        {/* Speakers */}
        <div className="grid grid-cols-2 gap-3">
          <SpeakerCard name={rmName} role="Relationship Manager" active={speaking === "rm"} />
          <SpeakerCard name={clientName} role="Client" active={speaking === "client"} />
        </div>

        {/* Transcript + nudges */}
        <div ref={scrollRef} className="h-64 overflow-y-auto border border-ink/15 bg-ink/[0.015] p-3">
          {phase === "idle" && (
            <p className="flex h-full items-center justify-center text-center font-serif text-sm italic text-ink/40">
              Press play. {clientFirst}'s line will ring, the conversation runs,
              and SYNC whispers coaching as it hears trouble — or opportunity.
            </p>
          )}
          {phase === "ringing" && (
            <p className="flex h-full items-center justify-center font-edit-mono text-[11px] uppercase tracking-widest text-ink/50 animate-pulse">
              Ringing {clientFirst}…
            </p>
          )}
          <div className="space-y-2">
            {entries.map((e, i) =>
              e.kind === "line" ? (
                <p key={i} className="font-serif text-[13px] leading-snug text-ink/90">
                  <span className="font-edit-mono text-[10px] font-bold uppercase tracking-widest text-ink/45">{e.speaker}</span>
                  {"  "}{e.text}
                </p>
              ) : e.kind === "nudge" ? (
                <NudgeRow key={i} text={e.text} tone={e.tone ?? "suggest"} />
              ) : (
                <ActionRow
                  key={e.id ?? i}
                  preview={e.text}
                  status={actionStatus[e.id ?? ""] ?? "pending"}
                  onApprove={() => approveAction(e.id!, e.tool!, e.args ?? {})}
                  onSkip={() => setActionStatus(s => ({ ...s, [e.id!]: "skipped" }))}
                />
              )
            )}
          </div>
          {phase === "ended" && (
            <p className="mt-3 border-t border-ink/15 pt-2 text-center font-edit-mono text-[10px] uppercase tracking-widest text-ink/50">
              Call ended · {nudgeCount} live whisper{nudgeCount === 1 ? "" : "s"} · post-call intelligence filing now
            </p>
          )}
        </div>

        {/* Controls */}
        <div className="flex justify-center gap-2">
          {(phase === "idle" || phase === "ended") ? (
            <button
              onClick={run}
              className="inline-flex items-center gap-2 border-2 border-ink bg-ink px-6 py-2.5 font-edit-mono text-[11px] uppercase tracking-widest text-cream hover:bg-paper hover:text-ink"
            >
              <Play className="h-3.5 w-3.5" />
              {phase === "ended" ? "Replay the call" : "Start the call"}
            </button>
          ) : (
            <button
              onClick={hangUp}
              className="inline-flex items-center gap-2 border-2 border-red-800 bg-red-800 px-6 py-2.5 font-edit-mono text-[11px] uppercase tracking-widest text-paper hover:bg-paper hover:text-red-800"
            >
              <PhoneOff className="h-3.5 w-3.5" /> Hang up
            </button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function SpeakerCard({ name, role, active }: { name: string; role: string; active: boolean }) {
  return (
    <div className={`border p-3 transition-colors ${active ? "border-ink bg-ink/[0.04]" : "border-ink/15 bg-paper"}`}>
      <div className="flex items-center gap-2">
        <span className="relative flex h-2 w-2">
          {active && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-700 opacity-60" />}
          <span className={`relative inline-flex h-2 w-2 rounded-full ${active ? "bg-emerald-700" : "bg-ink/20"}`} />
        </span>
        <span className="truncate font-serif text-sm font-semibold text-ink">{name}</span>
      </div>
      <p className="mt-0.5 font-edit-mono text-[9px] uppercase tracking-widest text-ink/45">{role}</p>
    </div>
  );
}

function ActionRow({ preview, status, onApprove, onSkip }: {
  preview: string; status: ActionState; onApprove: () => void; onSkip: () => void;
}) {
  return (
    <div className="flex items-start gap-2 border-2 border-ink bg-paper px-2.5 py-2 shadow-sm"
         style={{ animation: "coachIn 0.25s ease-out both" }}>
      <CalendarPlus className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink/70" />
      <div className="min-w-0 flex-1">
        <span className="font-edit-mono text-[9px] font-bold uppercase tracking-widest text-ink/50">
          SYNC heard a commitment
        </span>
        <p className="font-serif text-[13px] leading-snug text-ink">{preview}</p>
        <div className="mt-1.5 flex items-center gap-2">
          {status === "pending" && (
            <>
              <button
                onClick={onApprove}
                className="inline-flex items-center gap-1 border border-emerald-800 bg-emerald-800 px-2.5 py-1 font-edit-mono text-[9px] font-bold uppercase tracking-widest text-paper hover:bg-paper hover:text-emerald-800"
              >
                <Check className="h-3 w-3" /> Approve · file in CRM
              </button>
              <button
                onClick={onSkip}
                className="inline-flex items-center gap-1 border border-ink/30 px-2.5 py-1 font-edit-mono text-[9px] uppercase tracking-widest text-ink/60 hover:bg-ink/[0.05]"
              >
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
              Failed —
              <button onClick={onApprove} className="underline underline-offset-2 hover:text-red-900">retry</button>
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function NudgeRow({ text, tone }: { text: string; tone: string }) {
  const t = TONE_META[tone] ?? TONE_META.suggest;
  return (
    <div className={`flex items-start gap-2 border-l-4 border-y border-r px-2.5 py-1.5 ${t.cls}`}
         style={{ animation: "coachIn 0.25s ease-out both" }}>
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
