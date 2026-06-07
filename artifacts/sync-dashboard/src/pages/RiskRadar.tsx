/**
 * Risk Radar — "§ The Watchlist".
 * Editorial autonomous-save-call console: scan the portfolio, place outbound
 * AI calls to at-risk clients, watch the loop close.
 */
import { useEffect, useState, useCallback } from "react";
import { useLocation } from "wouter";
import { ArrowLeft, Loader2, Radar, Phone, X, AlertTriangle } from "lucide-react";
import { useConnection } from "@/lib/connection-context";
import { usePii } from "@/lib/pii-context";
import { useWebSocket, WebSocketMessage } from "@/hooks/use-websocket";
import { useToast } from "@/hooks/use-toast";

interface Play {
  id: number;
  client_id: string;
  client_name: string;
  trigger_type: string;
  urgency: string;
  objective: string;
  talking_points: string[];
  rationale: string;
  matched_triggers: string[];
  status: string;
  call_id?: string;
  outcome?: string;
}

const TRIGGER_LABEL: Record<string, string> = {
  npa_risk: "NPA Risk",
  aging_complaint: "Aging Complaint",
  emi_overdue_soon: "EMI Due Soon",
  winback: "Win-back",
  proactive_crosssell: "Cross-sell",
};

export default function RiskRadar() {
  const [, navigate] = useLocation();
  const { connectionId } = useConnection();
  const { scrub } = usePii();
  const { toast } = useToast();
  const [plays, setPlays] = useState<Play[]>([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [autopilot, setAutopilot] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await fetch(`/api/v1/radar/plays?connection=${connectionId}`);
      if (r.ok) setPlays(await r.json());
    } catch { /* ignore */ }
    setLoading(false);
  }, [connectionId]);

  useEffect(() => { load(); }, [load]);

  const handleWs = (msg: WebSocketMessage) => {
    if (["save_call_started", "save_call_transferred", "call_analysis_ready", "radar_scan", "command_executed"].includes(msg.type)) {
      load();
    }
  };
  useWebSocket({ onMessage: handleWs });

  const runScan = async () => {
    setScanning(true);
    try {
      const r = await fetch(`/api/v1/radar/scan?connection=${connectionId}`, { method: "POST" });
      if (r.ok) {
        const data = await r.json();
        setPlays(data);
        toast({ title: "Radar scan complete", description: `${data.length} client${data.length === 1 ? "" : "s"} flagged.` });
      }
    } catch (e: any) {
      toast({ title: "Scan failed", description: e.message, variant: "destructive" });
    } finally {
      setScanning(false);
    }
  };

  const placeCall = async (play: Play) => {
    try {
      const r = await fetch(`/api/v1/radar/plays/${play.id}/call`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
      });
      if (r.ok) {
        toast({ title: "Save call placed", description: `Calling ${scrub(play.client_name, "name")}…` });
        load();
      } else {
        toast({ title: "Call failed", description: await r.text(), variant: "destructive" });
      }
    } catch (e: any) {
      toast({ title: "Call failed", description: e.message, variant: "destructive" });
    }
  };

  const dismiss = async (play: Play) => {
    await fetch(`/api/v1/radar/plays/${play.id}/dismiss`, { method: "POST" });
    load();
  };

  const toggleAutopilot = async () => {
    const next = !autopilot;
    setAutopilot(next);
    await fetch(`/api/v1/radar/autopilot`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: next, connection_id: connectionId }),
    });
    toast({
      title: next ? "Autopilot ON" : "Autopilot OFF",
      description: next ? "SYNC will auto-place CRITICAL save calls." : "Autonomous calling paused.",
      variant: next ? "default" : "default",
    });
  };

  const critical = plays.filter(p => p.urgency === "CRITICAL" && p.status === "queued").length;

  return (
    <div className="min-h-screen bg-paper-grain text-ink antialiased">
      {/* Top strip */}
      <div className="border-b border-ink/15 bg-paper">
        <div className="mx-auto flex h-8 max-w-[1100px] items-center justify-between px-4 font-edit-mono text-[10px] uppercase tracking-widest text-ink/60 md:px-6">
          <button onClick={() => navigate("/dashboard")} className="inline-flex items-center gap-1.5 hover:text-ink">
            <ArrowLeft className="h-3 w-3" /> Back to the Briefing Desk
          </button>
          <span>§ The Watchlist</span>
        </div>
      </div>

      <main className="mx-auto max-w-[1100px] px-4 py-10 md:px-6 md:py-14">
        {/* Title */}
        <header className="border-b border-ink/15 pb-8">
          <p className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/50">
            § Autonomous Save Calls
          </p>
          <h1 className="mt-2 flex items-center gap-3 font-display text-5xl leading-[0.95] text-ink md:text-6xl">
            <Radar className="h-10 w-10 text-ink/70" />
            The <em className="italic">Watchlist</em>.
          </h1>
          <p className="mt-3 max-w-2xl font-serif text-lg italic leading-snug text-ink/70">
            SYNC scans the whole book of clients, flags the ones at risk, and can
            place a warm outbound AI call — then hand off to the human RM.
          </p>

          {/* Controls */}
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <button
              onClick={runScan}
              disabled={scanning}
              className="inline-flex items-center gap-2 border-2 border-ink bg-ink px-5 py-2.5 font-edit-mono text-[11px] uppercase tracking-widest text-cream transition-colors hover:bg-paper hover:text-ink disabled:opacity-60"
            >
              {scanning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Radar className="h-3.5 w-3.5" />}
              {scanning ? "Scanning…" : "Run Radar Scan"}
            </button>

            <button
              onClick={toggleAutopilot}
              className={`inline-flex items-center gap-2 border-2 px-5 py-2.5 font-edit-mono text-[11px] uppercase tracking-widest transition-colors ${
                autopilot
                  ? "border-amber-700 bg-amber-100 text-amber-900"
                  : "border-ink/30 bg-paper text-ink/70 hover:bg-ink hover:text-cream"
              }`}
            >
              Autopilot {autopilot ? "ON" : "OFF"}
            </button>

            {critical > 0 && (
              <span className="inline-flex items-center gap-1.5 border border-red-700/40 bg-red-50 px-2.5 py-1 font-edit-mono text-[10px] font-bold uppercase tracking-widest text-red-800">
                <AlertTriangle className="h-3 w-3" /> {critical} critical
              </span>
            )}
          </div>

          {autopilot && (
            <p className="mt-3 font-serif text-xs italic text-amber-800">
              ⚠ Autopilot places <strong>real outbound calls</strong> to flagged clients without confirmation.
            </p>
          )}
        </header>

        {/* Plays */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="h-5 w-5 animate-spin text-ink/40" />
          </div>
        ) : plays.length === 0 ? (
          <p className="mt-10 font-serif text-base italic text-ink/50">
            No plays yet. Run a radar scan to flag at-risk clients.
          </p>
        ) : (
          <div className="mt-8 border-y border-ink/15 divide-y divide-ink/15">
            {plays.map(play => (
              <PlayRow
                key={play.id}
                play={play}
                scrubName={(n) => scrub(n, "name")}
                onCall={() => placeCall(play)}
                onDismiss={() => dismiss(play)}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

function PlayRow({
  play, scrubName, onCall, onDismiss,
}: {
  play: Play;
  scrubName: (n: string) => string;
  onCall: () => void;
  onDismiss: () => void;
}) {
  const isActive = ["calling", "transferred", "completed"].includes(play.status);
  return (
    <div className="grid grid-cols-12 gap-4 py-5">
      {/* Urgency + client */}
      <div className="col-span-12 md:col-span-3">
        <UrgencyPill urgency={play.urgency} />
        <p className="mt-2 font-display text-2xl leading-tight text-ink">{scrubName(play.client_name)}</p>
        <div className="mt-1 flex flex-wrap gap-1">
          {play.matched_triggers.map(t => (
            <span key={t} className="border border-ink/15 bg-paper px-1.5 py-0.5 font-edit-mono text-[9px] uppercase tracking-widest text-ink/60">
              {TRIGGER_LABEL[t] ?? t}
            </span>
          ))}
        </div>
      </div>

      {/* Objective + rationale */}
      <div className="col-span-12 md:col-span-6">
        <p className="font-serif text-base text-ink">{play.objective}</p>
        <p className="mt-1 font-serif text-sm italic text-ink/60">{play.rationale}</p>
        {play.talking_points?.length > 0 && (
          <ul className="mt-2 space-y-0.5">
            {play.talking_points.slice(0, 3).map((tp, i) => (
              <li key={i} className="font-serif text-xs text-ink/55">— {tp}</li>
            ))}
          </ul>
        )}
        {play.outcome && (
          <p className="mt-2 font-edit-mono text-[10px] uppercase tracking-widest text-emerald-800">
            ✓ {play.outcome}
          </p>
        )}
      </div>

      {/* Status / actions */}
      <div className="col-span-12 flex items-start gap-2 md:col-span-3 md:justify-end">
        {isActive ? (
          <StatusBadge status={play.status} />
        ) : play.status === "dismissed" ? (
          <span className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/40">Dismissed</span>
        ) : (
          <>
            <button
              onClick={onCall}
              className="inline-flex items-center gap-1.5 border-2 border-ink bg-ink px-3 py-2 font-edit-mono text-[10px] uppercase tracking-widest text-cream transition-colors hover:bg-paper hover:text-ink"
            >
              <Phone className="h-3 w-3" /> Save Call
            </button>
            <button
              onClick={onDismiss}
              className="inline-flex items-center justify-center border border-ink/30 px-2 py-2 text-ink/50 hover:bg-ink hover:text-cream"
              title="Dismiss"
            >
              <X className="h-3 w-3" />
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function UrgencyPill({ urgency }: { urgency: string }) {
  const m: Record<string, string> = {
    CRITICAL: "border-red-700/40 bg-red-50 text-red-800",
    HIGH: "border-orange-700/40 bg-orange-50 text-orange-800",
    MEDIUM: "border-amber-600/40 bg-amber-50 text-amber-800",
    LOW: "border-ink/30 bg-ink/[0.02] text-ink/60",
  };
  return (
    <span className={`inline-block border px-2 py-0.5 font-edit-mono text-[9px] font-bold uppercase tracking-widest ${m[urgency] ?? m.LOW}`}>
      {urgency}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const m: Record<string, { cls: string; text: string; pulse?: boolean }> = {
    calling: { cls: "border-amber-700/40 bg-amber-50 text-amber-900", text: "● Calling…", pulse: true },
    transferred: { cls: "border-blue-700/40 bg-blue-50 text-blue-800", text: "→ Transferred" },
    completed: { cls: "border-emerald-700/40 bg-emerald-50 text-emerald-800", text: "✓ Completed" },
  };
  const s = m[status] ?? { cls: "border-ink/30 text-ink/60", text: status };
  return (
    <span className={`border px-2.5 py-1 font-edit-mono text-[10px] font-bold uppercase tracking-widest ${s.cls} ${s.pulse ? "animate-pulse" : ""}`}>
      {s.text}
    </span>
  );
}
