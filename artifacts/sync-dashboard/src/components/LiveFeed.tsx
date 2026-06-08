/**
 * Editorial Live Feed — like the "Dispatches" column of a newspaper.
 * Each briefing is a wire-story style row: timestamp · risk pill · RM → Client · pitch.
 */
import { useState } from "react";
import { BriefingLog } from "@workspace/api-client-react";
import { CheckCircle2, FileText } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { CRMSourceBadge, providerFromConnectionId } from "./CRMSourceBadge";
import { PostCallIntelligence } from "./PostCallIntelligence";
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
      <section className="flex h-full min-h-[520px] flex-col border border-ink/15 bg-paper">
        {/* Section header */}
        <div className="flex items-baseline justify-between border-b border-ink/15 bg-ink/[0.02] px-4 py-2.5">
          <div className="flex items-baseline gap-2 font-edit-mono text-[10px] uppercase tracking-widest text-ink/60">
            <span className="text-ink/40">§</span>
            <span>03</span>
            <span className="text-ink/30">·</span>
            <span>Dispatches · Live Feed</span>
          </div>
          <div className="flex items-center gap-2 font-edit-mono text-[10px] uppercase tracking-widest text-ink/40">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-700 opacity-60" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-700" />
            </span>
            <span>{briefings.length} dispatches</span>
          </div>
        </div>

        {/* Table head — hidden on mobile (rows render as cards there) */}
        <div className="hidden grid-cols-12 gap-2 border-b border-ink/15 bg-ink/[0.01] px-4 py-1.5 font-edit-mono text-[9px] uppercase tracking-widest text-ink/40 md:grid">
          <span className="col-span-2">Time</span>
          <span className="col-span-2">Risk</span>
          <span className="col-span-5">Briefing</span>
          <span className="col-span-2 text-right">Duration</span>
          <span className="col-span-1 text-right">·</span>
        </div>

        {/* Feed */}
        <div className="flex-1 divide-y divide-ink/10 overflow-y-auto">
          {briefings.length === 0 ? (
            <div className="flex h-full items-center justify-center py-12">
              <p className="font-serif text-sm italic text-ink/40">No dispatches yet — fire a sync to see them here.</p>
            </div>
          ) : briefings.map((log, i) => (
            <article
              key={log.briefing_id}
              onClick={() => openTranscript(log)}
              className="group flex cursor-pointer flex-col gap-3 px-4 py-4 transition-colors hover:bg-ink/[0.02] md:grid md:grid-cols-12 md:gap-2"
              style={{ animation: `dispatchSlide 0.3s ease-out ${i * 30}ms backwards` }}
            >
              {/* Mobile header strip — time, risk, complaint, duration on one line */}
              <div className="flex flex-wrap items-center justify-between gap-2 md:hidden">
                <div className="flex items-center gap-2">
                  <span className="font-edit-mono text-[11px] font-semibold text-ink">{formatTime(log.timestamp)}</span>
                  <RiskBadge score={log.risk_score} />
                  {hasComplaint(log) && (
                    <span className="border border-amber-700/40 bg-amber-50 px-1.5 py-0.5 font-edit-mono text-[9px] font-bold uppercase tracking-widest text-amber-900">
                      ⚠
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-display text-base leading-none text-ink">
                    {Math.round(log.duration_seconds || 0)}<span className="text-[10px] font-edit-mono">s</span>
                  </span>
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-700" />
                </div>
              </div>

              {/* Time (md+ column) */}
              <div className="hidden md:col-span-2 md:flex md:flex-col md:gap-0.5">
                <span className="font-edit-mono text-[11px] font-semibold text-ink">{formatTime(log.timestamp)}</span>
                <CRMSourceBadge provider={provider} className="w-fit" />
              </div>

              {/* Risk + complaint (md+ column) */}
              <div className="hidden md:col-span-2 md:flex md:flex-col md:gap-1">
                <RiskBadge score={log.risk_score} />
                {hasComplaint(log) && (
                  <span className="border border-amber-700/40 bg-amber-50 px-1.5 py-0.5 text-center font-edit-mono text-[9px] font-bold uppercase tracking-widest text-amber-900">
                    ⚠ Complaint
                  </span>
                )}
              </div>

              {/* Main body — full width on mobile, col-span-5 on md+ */}
              <div className="md:col-span-5">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 font-serif text-sm">
                  <span className="font-semibold text-ink">{scrub(log.rm_name, "name")}</span>
                  <span className="text-ink/40">→</span>
                  <span className="font-semibold text-ink">{scrub(log.client_name, "name")}</span>
                  <CRMSourceBadge provider={provider} className="md:hidden" />
                </div>
                {log.suggested_pitch && (
                  <p className="mt-1 line-clamp-2 font-serif text-[12px] italic leading-snug text-ink/60">
                    "{log.suggested_pitch}"
                  </p>
                )}
                {log.key_flags.length > 0 && (
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {log.key_flags.slice(0, 4).map((f, idx) => (
                      <span key={idx} className="border border-ink/15 bg-paper px-1 py-0.5 font-edit-mono text-[9px] uppercase text-ink/60">
                        {f.replaceAll("_", " ")}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Duration (md+ only) */}
              <div className="hidden text-right md:col-span-2 md:block">
                <div className="font-display text-xl leading-none text-ink">
                  {Math.round(log.duration_seconds || 0)}<span className="text-xs font-edit-mono">s</span>
                </div>
                {log.latency_ms && (
                  <div className="mt-0.5 font-edit-mono text-[9px] uppercase tracking-widest text-ink/40">
                    {log.latency_ms}ms
                  </div>
                )}
              </div>

              {/* Status (md+ only) */}
              <div className="hidden md:col-span-1 md:flex md:flex-col md:items-end md:justify-between md:gap-1">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-700" />
                <button
                  onClick={(e) => { e.stopPropagation(); openTranscript(log); }}
                  className="opacity-0 transition-opacity group-hover:opacity-100"
                  title="View transcript"
                >
                  <FileText className="h-3.5 w-3.5 text-ink/60 hover:text-ink" />
                </button>
              </div>
            </article>
          ))}
        </div>

        <style>{`
          @keyframes dispatchSlide {
            from { opacity: 0; transform: translateY(-4px); }
            to { opacity: 1; transform: translateY(0); }
          }
        `}</style>
      </section>

      {/* Transcript dialog */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="rounded-none border-ink bg-paper sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/60">
              § Verbatim Transcript
            </DialogTitle>
            {active && (
              <DialogDescription className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/40">
                {scrub(active.rm_name, "name")} → {scrub(active.client_name, "name")} · {formatTime(active.timestamp)} · {Math.round(active.duration_seconds || 0)}s
              </DialogDescription>
            )}
          </DialogHeader>
          <div className="mt-1 max-h-52 overflow-y-auto border-l-2 border-ink bg-ink/[0.02] py-3 pl-4 font-serif text-sm italic leading-relaxed text-ink/90">
            {loading
              ? <span className="animate-pulse text-ink/40">Loading transcript…</span>
              : <p className="whitespace-pre-wrap">{transcript}</p>}
          </div>
          {active && <PostCallIntelligence callId={active.call_id} />}
        </DialogContent>
      </Dialog>
    </>
  );
}

function RiskBadge({ score }: { score: string }) {
  const m: Record<string, string> = {
    very_low: "border-emerald-700/40 bg-emerald-50 text-emerald-800",
    low:      "border-blue-700/40 bg-blue-50 text-blue-800",
    medium:   "border-amber-600/40 bg-amber-50 text-amber-800",
    watch:    "border-orange-700/40 bg-orange-50 text-orange-800",
    high:     "border-red-700/40 bg-red-50 text-red-800",
  };
  return (
    <span className={`border px-1.5 py-0.5 text-center font-edit-mono text-[9px] font-bold uppercase tracking-widest ${m[score] ?? "border-ink/30 text-ink/60"}`}>
      {score.replace("_", " ")}
    </span>
  );
}

function formatTime(ts: string) {
  return new Intl.DateTimeFormat("en-IN", { hour: "numeric", minute: "2-digit", hour12: true }).format(new Date(ts));
}

function hasComplaint(log: BriefingLog) {
  return log.key_flags.some(f => f.toLowerCase().includes("complaint"));
}
