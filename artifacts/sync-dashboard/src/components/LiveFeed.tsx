import { useState } from "react";
import { BriefingLog } from "@workspace/api-client-react";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, Clock3, UserRound, FileText } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { GlowCard } from "./aceternity/glow-card";
import { CRMSourceBadge, providerFromConnectionId } from "./CRMSourceBadge";
import { useConnection } from "@/lib/connection-context";
import { usePii } from "@/lib/pii-context";

export function LiveFeed({ briefings }: { briefings: BriefingLog[] }) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState<BriefingLog | null>(null);
  const [transcript, setTranscript] = useState("");
  const [loading, setLoading] = useState(false);
  const { connectionId } = useConnection();
  const { scrub } = usePii();
  const provider = providerFromConnectionId(connectionId);

  const openTranscript = async (log: BriefingLog) => {
    setActive(log); setOpen(true); setTranscript(""); setLoading(true);
    try {
      const r = await fetch(`/api/v1/calls/sync-now/${log.call_id}`);
      if (r.ok) { const d = await r.json(); setTranscript(d.transcript || "No transcript available yet."); }
      else setTranscript("Transcript not available.");
    } catch { setTranscript("Could not load transcript."); }
    finally { setLoading(false); }
  };

  return (
    <>
      <GlowCard glowColor="rgba(99,102,241,0.2)" className="flex h-full min-h-[520px] flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/[0.06] px-5 py-4">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            <span className="text-xs font-semibold uppercase tracking-widest text-slate-400">Live Feed</span>
          </div>
          <span className="font-mono text-[11px] text-slate-600">{briefings.length} events</span>
        </div>

        {/* Feed */}
        <div className="flex-1 space-y-2 overflow-y-auto p-4">
          {briefings.length === 0 ? (
            <div className="flex h-full items-center justify-center">
              <p className="text-sm text-slate-600">Waiting for events…</p>
            </div>
          ) : briefings.map((log, i) => (
            <div
              key={log.briefing_id}
              className="group animate-in fade-in slide-in-from-top-2 cursor-pointer rounded-lg border border-white/[0.04] bg-white/[0.02] p-4 transition-all duration-200 hover:border-white/[0.08] hover:bg-white/[0.04]"
              style={{ animationDelay: `${i * 40}ms` }}
            >
              {/* Top row */}
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <span className="font-mono text-[10px] text-slate-600">{formatTime(log.timestamp)}</span>
                <RiskBadge score={log.risk_score} />
                <CRMSourceBadge provider={provider} />
                {hasComplaint(log) && (
                  <Badge variant="outline" className="rounded border-amber-500/30 bg-amber-500/10 text-[10px] font-semibold uppercase text-amber-400">
                    ⚠ Complaint
                  </Badge>
                )}
              </div>

              {/* RM → Client */}
              <div className="mb-2 flex items-center gap-2 text-sm">
                <UserRound className="h-3.5 w-3.5 shrink-0 text-slate-600" />
                <span className="font-semibold text-white">{scrub(log.rm_name, "name")}</span>
                <span className="text-slate-600">→</span>
                <span className="font-semibold text-slate-300">{scrub(log.client_name, "name")}</span>
                <div className="ml-auto flex items-center gap-1.5 text-[11px] text-slate-600">
                  <Clock3 className="h-3 w-3" />
                  <span className="font-mono">{Math.round(log.duration_seconds || 0)}s</span>
                  {log.latency_ms && <span className="rounded bg-white/[0.03] px-1.5 py-0.5 font-mono">{log.latency_ms}ms</span>}
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                  <button
                    onClick={() => openTranscript(log)}
                    className="ml-1 opacity-0 transition-opacity group-hover:opacity-100"
                  >
                    <FileText className="h-3.5 w-3.5 text-slate-500 hover:text-slate-300" />
                  </button>
                </div>
              </div>

              {/* Pitch */}
              {log.suggested_pitch && (
                <p className="mb-2 line-clamp-2 text-[11px] italic text-slate-500">{log.suggested_pitch}</p>
              )}

              {/* Flags */}
              {log.key_flags.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {log.key_flags.slice(0, 4).map((f, idx) => (
                    <span key={idx} className="rounded border border-white/[0.04] bg-white/[0.02] px-1.5 py-0.5 font-mono text-[10px] text-slate-600">
                      {f.replaceAll("_", " ")}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </GlowCard>

      {/* Transcript dialog */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="border-white/[0.08] bg-[#0d1117] sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="text-xs font-semibold uppercase tracking-widest text-slate-400">Briefing Transcript</DialogTitle>
            {active && (
              <DialogDescription className="text-[11px] text-slate-600">
                {scrub(active.rm_name, "name")} → {scrub(active.client_name, "name")} · {formatTime(active.timestamp)} · {Math.round(active.duration_seconds || 0)}s
              </DialogDescription>
            )}
          </DialogHeader>
          <div className="mt-1 max-h-60 overflow-y-auto rounded-lg border border-white/[0.06] bg-white/[0.02] p-4 text-sm leading-relaxed text-slate-300">
            {loading ? <span className="animate-pulse text-slate-600">Loading transcript…</span> : <p className="whitespace-pre-wrap">{transcript}</p>}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

function RiskBadge({ score }: { score: string }) {
  const colors: Record<string, string> = {
    very_low: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    low:      "bg-blue-500/10 text-blue-400 border-blue-500/20",
    medium:   "bg-amber-500/10 text-amber-400 border-amber-500/20",
    watch:    "bg-orange-500/10 text-orange-400 border-orange-500/20",
    high:     "bg-red-500/10 text-red-400 border-red-500/20",
  };
  return (
    <Badge variant="outline" className={`rounded px-1.5 font-mono text-[10px] uppercase ${colors[score] ?? "bg-slate-500/10 text-slate-400"}`}>
      {score.replace("_", " ")}
    </Badge>
  );
}

function formatTime(ts: string) {
  return new Intl.DateTimeFormat("en-IN", { hour: "numeric", minute: "2-digit", hour12: true }).format(new Date(ts));
}

function hasComplaint(log: BriefingLog) {
  return log.key_flags.some(f => f.toLowerCase().includes("complaint"));
}
