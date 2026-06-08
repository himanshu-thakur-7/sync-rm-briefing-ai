/**
 * ConciergePanel — § The Concierge Line.
 *
 * Shows the inbound phone number the RM can dial to get a briefing on any
 * client by voice. Companion to the outbound SyncPanel — both belong to
 * the "RM ↔ SYNC" surface, not the "SYNC ↔ Client" save-call surface.
 */
import { useEffect, useState } from "react";
import { Phone, Sparkles } from "lucide-react";

interface Info {
  agent_id: string;
  inbound_number: string;
  configured: boolean;
}

export function ConciergePanel() {
  const [info, setInfo] = useState<Info | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/v1/concierge/info")
      .then(r => r.ok ? r.json() : null)
      .then((d: Info | null) => setInfo(d))
      .catch(() => setInfo(null))
      .finally(() => setLoading(false));
  }, []);

  // Pretty-print +917678456033 → "+91 76784 56033"
  const formatPhone = (raw: string): string => {
    const digits = raw.replace(/\D/g, "");
    if (digits.length === 12 && digits.startsWith("91"))
      return `+91 ${digits.slice(2, 7)} ${digits.slice(7)}`;
    if (digits.length === 10) return `+91 ${digits.slice(0, 5)} ${digits.slice(5)}`;
    return raw;
  };

  return (
    <section className="border border-ink/15 bg-paper">
      <div className="flex items-baseline justify-between border-b border-ink/15 bg-ink/[0.02] px-4 py-2.5">
        <div className="flex items-baseline gap-2 font-edit-mono text-[10px] uppercase tracking-widest text-ink/60">
          <Phone className="h-3 w-3 text-emerald-700" />
          <span>§</span>
          <span>07</span>
          <span className="text-ink/30">·</span>
          <span>The Concierge Line</span>
        </div>
        <span className="font-edit-mono text-[10px] uppercase tracking-widest text-emerald-700">
          Inbound · Live
        </span>
      </div>

      <div className="p-4">
        {loading ? (
          <div className="h-12 animate-pulse bg-ink/5" />
        ) : !info?.configured ? (
          <div>
            <p className="font-serif text-[13px] italic leading-relaxed text-ink/60">
              Inbound concierge not configured yet. Set <span className="font-edit-mono">RINGG_INBOUND_NUMBER</span> in <span className="font-edit-mono">.env</span> with the phone number printed on your dashboard, restart, and you'll see the number to dial here.
            </p>
          </div>
        ) : (
          <div>
            <p className="font-serif text-[13px] leading-relaxed text-ink/80">
              Dial this number and run your CRM by voice — get briefings,
              log notes, create tasks, schedule follow-ups, update complaints.
            </p>
            <div className="mt-3 border border-ink bg-paper-2/40 px-4 py-3 text-center">
              <div className="font-display text-3xl tabular-nums text-ink">
                {formatPhone(info.inbound_number)}
              </div>
              <div className="mt-1 font-edit-mono text-[9px] uppercase tracking-widest text-ink/50">
                SYNC Concierge Line
              </div>
            </div>
            <div className="mt-3 space-y-1 font-serif text-[12px] italic leading-snug text-ink/60">
              <div>
                <Sparkles className="mr-1 inline h-3 w-3 text-amber-700" />
                "Tell me about Vikram." <span className="text-ink/40">→ live briefing</span>
              </div>
              <div>
                <Sparkles className="mr-1 inline h-3 w-3 text-amber-700" />
                "Create a task with Priya for Thursday at 10."{" "}
                <span className="text-ink/40">→ logged in Pipedrive</span>
              </div>
              <div>
                <Sparkles className="mr-1 inline h-3 w-3 text-amber-700" />
                "Mark Amit's complaint as resolved."{" "}
                <span className="text-ink/40">→ updated</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
