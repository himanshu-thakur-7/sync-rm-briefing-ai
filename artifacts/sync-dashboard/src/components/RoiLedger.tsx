/**
 * RoiLedger — the "money counter".
 *
 * A slim editorial band that aggregates SYNC's cumulative impact: hours saved,
 * cross-sell value surfaced, complaints caught, calls handled. Numbers count
 * up on mount and re-poll, and re-fetch whenever a call completes or a voice
 * action lands. Also hosts the stage-safe "Seed demo day" control so the
 * dashboard is never empty when you walk on stage.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Sparkles, Loader2 } from "lucide-react";
import { useWebSocket, WebSocketMessage } from "@/hooks/use-websocket";
import { useToast } from "@/hooks/use-toast";

interface Roi {
  calls_handled: number;
  hours_saved: number;
  minutes_saved: number;
  cross_sells_surfaced: number;
  cross_sell_value_inr: number;
  complaints_caught: number;
}

// Count a number up from its previous value to the next over ~600ms.
function useCountUp(target: number, decimals = 0) {
  const [val, setVal] = useState(target);
  const fromRef = useRef(target);
  useEffect(() => {
    const from = fromRef.current;
    const to = target;
    if (from === to) return;
    const start = performance.now();
    const dur = 600;
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      setVal(from + (to - from) * eased);
      if (p < 1) raf = requestAnimationFrame(tick);
      else fromRef.current = to;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target]);
  return decimals > 0 ? val.toFixed(decimals) : Math.round(val).toString();
}

function inrShort(n: number): string {
  if (n >= 10000000) return `₹${(n / 10000000).toFixed(2)} Cr`;
  if (n >= 100000) return `₹${(n / 100000).toFixed(1)} L`;
  if (n >= 1000) return `₹${(n / 1000).toFixed(0)} K`;
  return `₹${n}`;
}

export function RoiLedger() {
  const { toast } = useToast();
  const [roi, setRoi] = useState<Roi | null>(null);
  const [seeding, setSeeding] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await fetch("/api/v1/demo/roi");
      if (r.ok) setRoi(await r.json());
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Re-pull whenever the working day changes.
  useWebSocket({
    onMessage: (msg: WebSocketMessage) => {
      if (["sync_completed", "command_executed", "save_call_transferred",
           "concierge_action_executed", "morning_brief_action_executed"].includes(msg.type)) {
        load();
      }
    },
  });

  const seedDemo = async () => {
    setSeeding(true);
    try {
      const r = await fetch("/api/v1/demo/seed", { method: "POST" });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      toast({ title: "Demo day seeded", description: `${d.seeded} briefings dispatched to the feed.` });
      load();
    } catch (e: any) {
      toast({ title: "Seed failed", description: e?.message ?? String(e), variant: "destructive" });
    } finally {
      setSeeding(false);
    }
  };

  const hours = useCountUp(roi?.hours_saved ?? 0, 1);
  const value = useCountUp(roi?.cross_sell_value_inr ?? 0);
  const complaints = useCountUp(roi?.complaints_caught ?? 0);
  const calls = useCountUp(roi?.calls_handled ?? 0);

  const ITEMS = [
    { label: "Hours saved", display: hours, accent: "text-emerald-800" },
    { label: "Opportunity surfaced", display: inrShort(Number(value)), accent: "text-ink" },
    { label: "Complaints caught", display: complaints, accent: "text-amber-800" },
    { label: "Calls handled", display: calls, accent: "text-ink" },
  ];

  return (
    <section className="border border-ink/15 bg-ink text-cream">
      <div className="flex items-baseline justify-between border-b border-cream/15 px-4 py-2">
        <div className="flex items-baseline gap-2 font-edit-mono text-[10px] uppercase tracking-widest text-cream/70">
          <span className="text-cream/40">§</span>
          <span>00</span>
          <span className="text-cream/30">·</span>
          <span>The Ledger · SYNC's impact, compounding</span>
        </div>
        <button
          onClick={seedDemo}
          disabled={seeding}
          className="inline-flex items-center gap-1.5 border border-cream/30 px-2 py-1 font-edit-mono text-[9px] uppercase tracking-widest text-cream/80 hover:bg-cream hover:text-ink disabled:opacity-50"
          title="Pre-populate a believable working day for the demo"
        >
          {seeding ? <Loader2 className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />}
          Seed demo day
        </button>
      </div>

      <div className="grid grid-cols-2 divide-cream/10 md:grid-cols-4 md:divide-x">
        {ITEMS.map(({ label, display, accent }) => (
          <div key={label} className="px-5 py-4">
            <p className="font-edit-mono text-[9px] uppercase tracking-widest text-cream/50">
              {label}
            </p>
            <div className={`mt-1.5 font-display text-4xl leading-none tabular-nums ${accent === "text-ink" ? "text-cream" : accent.replace("800", "300")}`}>
              {display}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
