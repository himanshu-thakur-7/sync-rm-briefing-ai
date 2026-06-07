/**
 * Compact Morning Brief widget for the dashboard.
 * Shows the next scheduled standup and links to /morning-brief.
 */
import { useEffect, useState, useCallback } from "react";
import { useLocation } from "wouter";
import { Sunrise, ArrowRight, Phone, Loader2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

interface Schedule {
  id: number;
  rm_name: string;
  hour_local: number;
  minute_local: number;
  enabled: boolean;
  next_call_at: string | null;
}

function formatTimeUntil(iso: string | null): string {
  if (!iso) return "—";
  const ms = new Date(iso).getTime() - Date.now();
  if (ms <= 0) return "now";
  const h = Math.floor(ms / 3_600_000);
  const m = Math.floor((ms % 3_600_000) / 60_000);
  if (h >= 24) return `in ${Math.floor(h / 24)}d ${h % 24}h`;
  return `in ${h}h ${m}m`;
}

export function MorningBriefPanel() {
  const [, navigate] = useLocation();
  const { toast } = useToast();
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await fetch("/api/v1/morning-brief/schedules");
      if (!r.ok) {
        setSchedules([]);
        return;
      }
      const s = await r.json();
      setSchedules(Array.isArray(s) ? s : []);
    } catch {
      setSchedules([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 60_000);
    return () => clearInterval(interval);
  }, [load]);

  const trigger = async (id: number) => {
    setTriggering(id);
    try {
      const r = await fetch(`/api/v1/morning-brief/schedules/${id}/trigger`, { method: "POST" });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      toast({
        title: "Standup placed",
        description: `Call ${(d.call_id ?? "").slice(0, 12)} — watch the live feed.`,
      });
    } catch (e: any) {
      toast({ title: "Trigger failed", description: e?.message ?? String(e), variant: "destructive" });
    } finally {
      setTriggering(null);
    }
  };

  const upcoming = schedules.filter(s => s.enabled && s.next_call_at).sort((a, b) =>
    new Date(a.next_call_at!).getTime() - new Date(b.next_call_at!).getTime()
  );
  const next = upcoming[0];

  return (
    <section className="border border-ink/15 bg-paper">
      <div className="flex items-baseline justify-between border-b border-ink/15 bg-ink/[0.02] px-4 py-2.5">
        <div className="flex items-baseline gap-2 font-edit-mono text-[10px] uppercase tracking-widest text-ink/60">
          <Sunrise className="h-3 w-3 text-amber-700" />
          <span>§</span>
          <span>06</span>
          <span className="text-ink/30">·</span>
          <span>Daily Standup</span>
        </div>
        <button onClick={() => navigate("/morning-brief")}
          className="inline-flex items-center gap-1 font-edit-mono text-[10px] uppercase tracking-widest text-ink/50 hover:text-ink">
          Manage <ArrowRight className="h-3 w-3" />
        </button>
      </div>

      <div className="p-4">
        {loading ? (
          <div className="flex justify-center py-4">
            <Loader2 className="h-4 w-4 animate-spin text-ink/40" />
          </div>
        ) : !next ? (
          <div>
            <p className="font-serif text-sm italic text-ink/50">
              No standups scheduled.
            </p>
            <button onClick={() => navigate("/morning-brief")}
              className="mt-3 w-full border-2 border-ink bg-ink px-3 py-2 font-edit-mono text-[10px] uppercase tracking-widest text-cream hover:bg-paper hover:text-ink">
              Schedule one
            </button>
          </div>
        ) : (
          <div>
            <div className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/40">
              Next call
            </div>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="font-display text-3xl leading-none text-ink tabular-nums">
                {String(next.hour_local).padStart(2, "0")}:{String(next.minute_local).padStart(2, "0")}
              </span>
              <span className="font-serif text-sm italic text-ink/60">
                {formatTimeUntil(next.next_call_at)}
              </span>
            </div>
            <div className="mt-1 font-edit-mono text-[10px] uppercase tracking-widest text-ink/50">
              {next.rm_name}
            </div>
            <button
              onClick={() => trigger(next.id)}
              disabled={triggering === next.id}
              className="mt-3 w-full inline-flex items-center justify-center gap-1.5 border-2 border-ink bg-paper px-3 py-2 font-edit-mono text-[10px] uppercase tracking-widest text-ink hover:bg-ink hover:text-cream disabled:opacity-50"
            >
              {triggering === next.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <Phone className="h-3 w-3" />}
              Trigger now
            </button>
            {upcoming.length > 1 && (
              <p className="mt-2 text-center font-edit-mono text-[9px] uppercase tracking-widest text-ink/40">
                + {upcoming.length - 1} more scheduled
              </p>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
