/**
 * Editorial webhook log — looks like a printed server log on cream paper.
 * Monospaced timestamps, ink text, status pills in editorial colors.
 */
import { useRef, useEffect } from "react";
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
  received:   "border-ink/30 bg-paper text-ink/70",
  processing: "border-amber-700/40 bg-amber-50 text-amber-900",
  processed:  "border-emerald-700/40 bg-emerald-50 text-emerald-800",
  error:      "border-red-700/40 bg-red-50 text-red-800",
};

export function WebhookActivityPanel({ events }: { events: WebhookEventEntry[] }) {
  const listRef = useRef<HTMLDivElement>(null);
  useEffect(() => { if (listRef.current) listRef.current.scrollTop = 0; }, [events]);

  return (
    <section className="flex h-full min-h-[300px] flex-col border border-ink/15 bg-paper">
      <div className="flex items-baseline justify-between border-b border-ink/15 bg-ink/[0.02] px-4 py-2.5">
        <div className="flex items-baseline gap-2 font-edit-mono text-[10px] uppercase tracking-widest text-ink/60">
          <span className="text-ink/40">§</span>
          <span>04</span>
          <span className="text-ink/30">·</span>
          <span>Webhook Log</span>
        </div>
        <span className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/40">
          {events.length} events
        </span>
      </div>

      <div ref={listRef} className="flex-1 divide-y divide-ink/10 overflow-y-auto">
        {events.length === 0 ? (
          <p className="py-12 text-center font-serif text-sm italic text-ink/40">
            Events will print here as calls fire.
          </p>
        ) : events.map(evt => (
          <div
            key={evt.id}
            className="grid grid-cols-12 gap-2 px-3 py-2.5 font-edit-mono text-[11px]"
            style={{ animation: "logSlide 0.3s ease-out backwards" }}
          >
            <span className="col-span-3 text-ink/50">
              {new Date(evt.received_at).toLocaleTimeString("en-IN", { hour12: false })}
            </span>
            <span className="col-span-6 truncate text-ink">{evt.event_type}</span>
            <span className={cn("col-span-3 border px-1.5 py-0 text-center text-[9px] font-bold uppercase tracking-widest", STATUS_STYLE[evt.status])}>
              {evt.status}
            </span>
            {evt.call_id && (
              <span className="col-span-12 truncate font-edit-mono text-[9px] text-ink/30 -mt-0.5">
                · {evt.call_id}
              </span>
            )}
          </div>
        ))}
      </div>

      <style>{`@keyframes logSlide { from { opacity: 0; transform: translateY(-3px); } to { opacity: 1; transform: translateY(0); } }`}</style>
    </section>
  );
}
