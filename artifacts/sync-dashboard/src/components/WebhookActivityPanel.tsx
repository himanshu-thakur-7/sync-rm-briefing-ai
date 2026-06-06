import { useRef, useEffect } from "react";
import { Zap } from "lucide-react";
import { GlowCard } from "./aceternity/glow-card";
import { cn } from "@/lib/utils";

export interface WebhookEventEntry {
  id: number;
  source: string;
  event_type: string;
  call_id?: string;
  status: "received" | "processing" | "processed" | "error";
  received_at: string;
}

const STATUS_STYLE: Record<string, string> = {
  received:   "bg-slate-500/15 text-slate-400",
  processing: "bg-amber-500/15 text-amber-400 animate-pulse",
  processed:  "bg-emerald-500/15 text-emerald-400",
  error:      "bg-red-500/15 text-red-400",
};

export function WebhookActivityPanel({ events }: { events: WebhookEventEntry[] }) {
  const listRef = useRef<HTMLDivElement>(null);
  useEffect(() => { if (listRef.current) listRef.current.scrollTop = 0; }, [events]);

  return (
    <GlowCard glowColor="rgba(251,191,36,0.15)" className="flex h-full min-h-[300px] flex-col">
      <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3.5">
        <div className="flex items-center gap-2">
          <Zap className="h-3.5 w-3.5 text-amber-400" />
          <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">Webhook Activity</span>
        </div>
        <span className="font-mono text-[10px] text-slate-600">{events.length}</span>
      </div>
      <div ref={listRef} className="flex-1 space-y-1.5 overflow-y-auto p-3">
        {events.length === 0 ? (
          <p className="py-8 text-center text-[11px] text-slate-700">Events appear as calls are made.</p>
        ) : events.map(evt => (
          <div
            key={evt.id}
            className="animate-in fade-in slide-in-from-top-1 flex items-center justify-between gap-2 rounded-md border border-white/[0.04] bg-white/[0.02] px-3 py-2 text-[11px] duration-200"
          >
            <div className="min-w-0">
              <span className="font-mono font-semibold text-slate-300">{evt.event_type}</span>
              {evt.call_id && (
                <span className="ml-1 font-mono text-[9px] text-slate-700">{evt.call_id.slice(0, 10)}…</span>
              )}
              <div className="text-[9px] text-slate-700">{new Date(evt.received_at).toLocaleTimeString("en-IN")}</div>
            </div>
            <span className={cn("shrink-0 rounded px-1.5 py-0.5 text-[9px] font-bold uppercase", STATUS_STYLE[evt.status])}>
              {evt.status}
            </span>
          </div>
        ))}
      </div>
    </GlowCard>
  );
}
