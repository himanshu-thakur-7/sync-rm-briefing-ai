/**
 * Post-Call Intelligence — editorial render of a CallAnalysis.
 * Sentiment bar, objections, commitments, churn-delta arrow, next-best-action
 * with an "Execute in CRM" button. Fetches by call_id; also accepts inline data.
 */
import { useEffect, useState } from "react";
import { Loader2, ArrowDownRight, ArrowRight, ArrowUpRight, Check } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

export interface CallAnalysis {
  call_id: string;
  client_id?: string;
  call_kind: string;
  sentiment_label: string;
  sentiment_score: number;
  objections: string[];
  commitments: Array<{ party?: string; text: string; due?: string }>;
  churn_delta: number;
  churn_label: string;
  next_best_action: { title?: string; tool?: string; args?: any; reason?: string };
  summary: string;
  nba_executed?: boolean;
  nba_action_id?: string;
}

interface Props {
  callId: string;
  initial?: CallAnalysis | null;
}

export function PostCallIntelligence({ callId, initial }: Props) {
  const { toast } = useToast();
  const [analysis, setAnalysis] = useState<CallAnalysis | null>(initial ?? null);
  const [loading, setLoading] = useState(!initial);
  const [executing, setExecuting] = useState(false);
  const [executed, setExecuted] = useState(initial?.nba_executed ?? false);

  useEffect(() => {
    if (initial) { setAnalysis(initial); setExecuted(!!initial.nba_executed); setLoading(false); return; }
    let cancelled = false;
    let tries = 0;
    const poll = async () => {
      try {
        const r = await fetch(`/api/v1/calls/sync-now/${callId}/analysis`);
        if (r.ok) {
          const data = await r.json();
          if (!cancelled) { setAnalysis(data); setExecuted(!!data.nba_executed); setLoading(false); }
          return;
        }
      } catch { /* ignore */ }
      tries += 1;
      if (tries < 20 && !cancelled) setTimeout(poll, 1500);
      else if (!cancelled) setLoading(false);
    };
    poll();
    return () => { cancelled = true; };
  }, [callId, initial]);

  const executeNba = async () => {
    setExecuting(true);
    try {
      const r = await fetch(`/api/v1/calls/sync-now/${callId}/analysis/execute-nba`, { method: "POST" });
      if (r.ok) {
        const d = await r.json();
        setExecuted(true);
        toast({ title: "✓ Logged to CRM", description: `${d.tool} created${d.action_id ? ` · ${String(d.action_id).slice(0, 8)}` : ""}` });
      } else {
        toast({ title: "Execution failed", description: await r.text(), variant: "destructive" });
      }
    } catch (e: any) {
      toast({ title: "Execution failed", description: e.message, variant: "destructive" });
    } finally {
      setExecuting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 border-t border-ink/15 pt-4 font-edit-mono text-[10px] uppercase tracking-widest text-ink/40">
        <Loader2 className="h-3 w-3 animate-spin" /> Analyzing call…
      </div>
    );
  }
  if (!analysis) {
    return (
      <div className="border-t border-ink/15 pt-4 font-serif text-sm italic text-ink/40">
        Post-call intelligence will appear here once the call completes.
      </div>
    );
  }

  const nba = analysis.next_best_action || {};

  return (
    <div className="space-y-4 border-t border-ink/15 pt-4">
      <p className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/50">
        § Post-Call Intelligence
      </p>

      {/* Summary */}
      {analysis.summary && (
        <p className="font-serif text-sm italic leading-snug text-ink/80">"{analysis.summary}"</p>
      )}

      {/* Sentiment + churn row */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="font-edit-mono text-[9px] uppercase tracking-widest text-ink/40">Sentiment</p>
          <div className="mt-1.5 flex items-center gap-2">
            <div className="h-1.5 flex-1 bg-ink/10">
              <div className="h-full bg-ink" style={{ width: `${analysis.sentiment_score}%` }} />
            </div>
            <span className="font-edit-mono text-[10px] text-ink/70">{analysis.sentiment_score}</span>
          </div>
          <p className="mt-1 font-serif text-xs capitalize text-ink/70">
            {analysis.sentiment_label.replace(/_/g, " ")}
          </p>
        </div>
        <div>
          <p className="font-edit-mono text-[9px] uppercase tracking-widest text-ink/40">Churn Risk</p>
          <ChurnDelta label={analysis.churn_label} />
        </div>
      </div>

      {/* Objections */}
      {analysis.objections?.length > 0 && (
        <div>
          <p className="font-edit-mono text-[9px] uppercase tracking-widest text-ink/40">Objections</p>
          <ul className="mt-1 space-y-0.5">
            {analysis.objections.map((o, i) => (
              <li key={i} className="font-serif text-xs text-ink/70">— {o}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Commitments */}
      {analysis.commitments?.length > 0 && (
        <div>
          <p className="font-edit-mono text-[9px] uppercase tracking-widest text-ink/40">Commitments</p>
          <ul className="mt-1 space-y-0.5">
            {analysis.commitments.map((c, i) => (
              <li key={i} className="font-serif text-xs text-ink/70">
                <span className="font-edit-mono text-[9px] uppercase text-ink/40">{c.party ?? "—"}:</span>{" "}
                {c.text}{c.due ? ` (${c.due})` : ""}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Next best action */}
      {nba.title && (
        <div className="border border-ink/20 bg-ink/[0.015] p-3">
          <p className="font-edit-mono text-[9px] uppercase tracking-widest text-ink/40">Next Best Action</p>
          <p className="mt-1 font-serif text-sm font-semibold text-ink">{nba.title}</p>
          {nba.reason && <p className="mt-0.5 font-serif text-xs italic text-ink/60">{nba.reason}</p>}
          <button
            onClick={executeNba}
            disabled={executing || executed}
            className={`mt-3 inline-flex items-center gap-2 border-2 px-4 py-2 font-edit-mono text-[10px] uppercase tracking-widest transition-colors disabled:opacity-60 ${
              executed
                ? "border-emerald-700 bg-emerald-50 text-emerald-800"
                : "border-ink bg-ink text-cream hover:bg-paper hover:text-ink"
            }`}
          >
            {executing ? <Loader2 className="h-3 w-3 animate-spin" />
              : executed ? <Check className="h-3 w-3" />
              : null}
            {executed ? "Logged to CRM" : `Execute in CRM (${nba.tool ?? "action"})`}
          </button>
        </div>
      )}
    </div>
  );
}

function ChurnDelta({ label }: { label: string }) {
  const map: Record<string, { icon: any; cls: string; text: string }> = {
    reduced:   { icon: ArrowDownRight, cls: "text-emerald-700", text: "Reduced" },
    unchanged: { icon: ArrowRight,     cls: "text-ink/50",      text: "Unchanged" },
    increased: { icon: ArrowUpRight,   cls: "text-red-700",     text: "Increased" },
  };
  const m = map[label] ?? map.unchanged;
  const Icon = m.icon;
  return (
    <div className={`mt-1.5 flex items-center gap-1.5 ${m.cls}`}>
      <Icon className="h-4 w-4" />
      <span className="font-serif text-sm">{m.text}</span>
    </div>
  );
}
