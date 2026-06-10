/**
 * CoachingOverlay — live whisper-coaching during a call.
 *
 * Subscribes to `coaching_nudge` WebSocket events and stacks short, ear-whisper
 * style cards in the bottom-right while a call is live. Each nudge auto-dismisses
 * after a few seconds. Tones:
 *   warn        → red, a risk to defuse
 *   opportunity → emerald, an opening to seize
 *   suggest     → ink, a tactical next move
 *
 * Mount once, globally (e.g. in Dashboard). It listens on its own WS connection
 * and renders nothing until a nudge arrives.
 */
import { useRef, useState } from "react";
import { AlertTriangle, Sparkles, Lightbulb, X } from "lucide-react";
import { useWebSocket, WebSocketMessage } from "@/hooks/use-websocket";
import { speakNudge } from "@/lib/whisper";

interface Nudge {
  id: number;
  text: string;
  tone: "warn" | "opportunity" | "suggest";
  callId?: string;
}

const TONE: Record<Nudge["tone"], { ring: string; chip: string; Icon: typeof AlertTriangle; label: string }> = {
  warn:        { ring: "border-red-700/50",     chip: "bg-red-50 text-red-800 border-red-700/40",       Icon: AlertTriangle, label: "Watch" },
  opportunity: { ring: "border-emerald-700/50", chip: "bg-emerald-50 text-emerald-800 border-emerald-700/40", Icon: Sparkles,   label: "Opening" },
  suggest:     { ring: "border-ink/40",         chip: "bg-ink/[0.04] text-ink/80 border-ink/30",        Icon: Lightbulb,     label: "Nudge" },
};

const NUDGE_TTL_MS = 7000;

export function CoachingOverlay() {
  const [nudges, setNudges] = useState<Nudge[]>([]);
  const seq = useRef(0);

  useWebSocket({
    onMessage: (msg: WebSocketMessage) => {
      if (msg.type !== "coaching_nudge") return;
      const tone = (["warn", "opportunity", "suggest"].includes(msg.data?.tone)
        ? msg.data.tone : "suggest") as Nudge["tone"];
      // Whisper Mode: murmur the nudge into the RM's earbud (no-op when off).
      speakNudge(msg.data?.text ?? "", tone);
      const id = ++seq.current;
      setNudges(prev => [
        { id, text: msg.data?.text ?? "", tone, callId: msg.data?.call_id },
        ...prev,
      ].slice(0, 4));
      setTimeout(() => setNudges(prev => prev.filter(n => n.id !== id)), NUDGE_TTL_MS);
    },
  });

  if (nudges.length === 0) return null;

  return (
    <div className="pointer-events-none fixed bottom-24 right-6 z-[55] flex w-[330px] max-w-[calc(100vw-2rem)] flex-col gap-2">
      {nudges.map(n => {
        const t = TONE[n.tone];
        return (
          <div
            key={n.id}
            className={`pointer-events-auto border-l-4 ${t.ring} border-y border-r border-ink/15 bg-paper p-3 shadow-xl`}
            style={{ animation: "coachIn 0.28s cubic-bezier(0.16,1,0.3,1) both" }}
          >
            <div className="flex items-center justify-between">
              <span className={`inline-flex items-center gap-1 border px-1.5 py-0.5 font-edit-mono text-[9px] font-bold uppercase tracking-widest ${t.chip}`}>
                <t.Icon className="h-3 w-3" />
                {t.label} · SYNC whispers
              </span>
              <button
                onClick={() => setNudges(prev => prev.filter(x => x.id !== n.id))}
                className="text-ink/30 hover:text-ink"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
            <p className="mt-1.5 font-serif text-[15px] italic leading-snug text-ink">
              {n.text}
            </p>
          </div>
        );
      })}
      <style>{`
        @keyframes coachIn {
          from { opacity: 0; transform: translateX(16px) scale(0.98); }
          to   { opacity: 1; transform: translateX(0)    scale(1); }
        }
      `}</style>
    </div>
  );
}
