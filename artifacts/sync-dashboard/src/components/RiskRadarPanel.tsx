/**
 * Compact Risk Radar widget for the dashboard's left column.
 * Shows the top critical/high plays and links to the full Watchlist.
 */
import { useEffect, useState, useCallback } from "react";
import { useLocation } from "wouter";
import { Radar, Loader2, ArrowRight, Phone } from "lucide-react";
import { useConnection } from "@/lib/connection-context";
import { usePii } from "@/lib/pii-context";
import { useToast } from "@/hooks/use-toast";

interface Play {
  id: number; client_name: string; trigger_type: string;
  urgency: string; objective: string; status: string;
}

export function RiskRadarPanel() {
  const [, navigate] = useLocation();
  const { connectionId } = useConnection();
  const { scrub } = usePii();
  const { toast } = useToast();
  const [plays, setPlays] = useState<Play[]>([]);
  const [scanning, setScanning] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await fetch(`/api/v1/radar/plays?connection=${connectionId}`);
      if (r.ok) setPlays(await r.json());
    } catch { /* ignore */ }
  }, [connectionId]);

  useEffect(() => { load(); }, [load]);

  const scan = async () => {
    setScanning(true);
    try {
      const r = await fetch(`/api/v1/radar/scan?connection=${connectionId}`, { method: "POST" });
      if (r.ok) {
        const data = await r.json();
        setPlays(data);
        toast({ title: "Radar scan complete", description: `${data.length} flagged.` });
      }
    } finally { setScanning(false); }
  };

  const top = plays
    .filter(p => ["queued", "calling", "transferred", "completed"].includes(p.status))
    .slice(0, 3);
  const critical = plays.filter(p => p.urgency === "CRITICAL" && p.status === "queued").length;

  return (
    <section className="border border-ink/15 bg-paper">
      <div className="flex items-baseline justify-between border-b border-ink/15 bg-ink/[0.02] px-4 py-2.5">
        <div className="flex items-baseline gap-2 font-edit-mono text-[10px] uppercase tracking-widest text-ink/60">
          <span className="text-ink/40">§</span><span>06</span>
          <span className="text-ink/30">·</span><span>Risk Radar</span>
        </div>
        {critical > 0 && (
          <span className="border border-red-700/40 bg-red-50 px-1.5 py-0.5 font-edit-mono text-[9px] font-bold uppercase tracking-widest text-red-800">
            {critical} critical
          </span>
        )}
      </div>

      <div className="p-4">
        {top.length === 0 ? (
          <p className="font-serif text-sm italic text-ink/50">
            Scan the book to flag at-risk clients for autonomous save calls.
          </p>
        ) : (
          <div className="space-y-2.5">
            {top.map(p => (
              <div key={p.id} className="flex items-start justify-between gap-2 border-b border-ink/10 pb-2.5 last:border-b-0">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <UrgencyDot urgency={p.urgency} />
                    <span className="truncate font-serif text-sm font-semibold text-ink">
                      {scrub(p.client_name, "name")}
                    </span>
                  </div>
                  <p className="mt-0.5 line-clamp-1 font-serif text-xs italic text-ink/60">{p.objective}</p>
                </div>
                {p.status === "queued" ? (
                  <Phone className="mt-1 h-3 w-3 shrink-0 text-ink/40" />
                ) : (
                  <span className="mt-0.5 shrink-0 font-edit-mono text-[9px] uppercase tracking-widest text-emerald-800">
                    {p.status === "calling" ? "● live" : p.status === "transferred" ? "→ xfer" : "✓"}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}

        <div className="mt-4 flex items-center gap-2">
          <button
            onClick={scan}
            disabled={scanning}
            className="inline-flex flex-1 items-center justify-center gap-2 border-2 border-ink bg-ink px-3 py-2 font-edit-mono text-[10px] uppercase tracking-widest text-cream transition-colors hover:bg-paper hover:text-ink disabled:opacity-60"
          >
            {scanning ? <Loader2 className="h-3 w-3 animate-spin" /> : <Radar className="h-3 w-3" />}
            {scanning ? "Scanning" : "Scan"}
          </button>
          <button
            onClick={() => navigate("/radar")}
            className="inline-flex items-center justify-center gap-1 border border-ink/30 px-3 py-2 font-edit-mono text-[10px] uppercase tracking-widest text-ink/70 hover:bg-ink hover:text-cream"
          >
            Watchlist <ArrowRight className="h-3 w-3" />
          </button>
        </div>
      </div>
    </section>
  );
}

function UrgencyDot({ urgency }: { urgency: string }) {
  const m: Record<string, string> = {
    CRITICAL: "bg-red-700", HIGH: "bg-orange-700", MEDIUM: "bg-amber-600", LOW: "bg-ink/40",
  };
  return <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${m[urgency] ?? "bg-ink/40"}`} />;
}
