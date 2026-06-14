/**
 * CopilotSidebar — the right-rail intelligence panel during a live coached call.
 *
 *   ┌──────────────────────┐
 *   │ Suggested responses  │  ← what to SAY (one-click)
 *   ├──────────────────────┤
 *   │ Risks                │  ← warn-toned nudges
 *   ├──────────────────────┤
 *   │ Opportunities        │  ← opportunity-toned nudges
 *   ├──────────────────────┤
 *   │ CRM Actions          │  ← Approve to write to Pipedrive
 *   └──────────────────────┘
 *
 * Driven entirely by the same coaching_nudge + coaching_action_suggestion
 * WS events the global CoachingOverlay uses. Different presentation: a
 * persistent sidebar instead of fleeting toasts.
 */
import { useState } from "react";
import {
  AlertTriangle, Sparkles, MessageSquare, CalendarPlus,
  Check, X, Loader2, Volume2, Copy,
} from "lucide-react";

export interface SidebarNudge {
  id: number;
  text: string;
  tone: "warn" | "opportunity" | "suggest";
  say?: string;
}

export interface SidebarAction {
  id: string;
  tool: string;
  args: Record<string, unknown>;
  preview: string;
  status: "pending" | "executing" | "done" | "skipped" | "failed";
}

interface Props {
  nudges: SidebarNudge[];
  actions: SidebarAction[];
  onApprove: (id: string, tool: string, args: Record<string, unknown>) => void;
  onSkip: (id: string) => void;
  onSayClick?: (line: string) => void;   // optional: speak it / push-to-prompter
}

export function CopilotSidebar({ nudges, actions, onApprove, onSkip, onSayClick }: Props) {
  const suggested = nudges.filter(n => !!n.say);
  const risks = nudges.filter(n => n.tone === "warn");
  const opportunities = nudges.filter(n => n.tone === "opportunity");

  return (
    <aside className="flex h-full max-h-[28rem] flex-col gap-0 border-l border-ink/20 bg-paper">
      <SidebarHeader />

      <Section
        title="Suggested responses"
        empty="No suggestions yet — SYNC will surface them as the client speaks."
        Icon={MessageSquare}
        accent="emerald"
        count={suggested.length}
      >
        {suggested.map(n => (
          <SuggestedCard key={n.id} say={n.say!} onClick={() => onSayClick?.(n.say!)} />
        ))}
      </Section>

      <Section
        title="Risks"
        empty="No risks flagged."
        Icon={AlertTriangle}
        accent="red"
        count={risks.length}
      >
        {risks.map(n => <NudgeCard key={n.id} text={n.text} tone="warn" />)}
      </Section>

      <Section
        title="Opportunities"
        empty="No openings detected."
        Icon={Sparkles}
        accent="amber"
        count={opportunities.length}
      >
        {opportunities.map(n => <NudgeCard key={n.id} text={n.text} tone="opportunity" />)}
      </Section>

      <Section
        title="CRM Actions"
        empty="Commitments will appear here, one tap to file."
        Icon={CalendarPlus}
        accent="ink"
        count={actions.filter(a => a.status === "pending").length}
      >
        {actions.map(a => (
          <ActionCard
            key={a.id}
            preview={a.preview}
            status={a.status}
            onApprove={() => onApprove(a.id, a.tool, a.args)}
            onSkip={() => onSkip(a.id)}
          />
        ))}
      </Section>
    </aside>
  );
}

function SidebarHeader() {
  return (
    <div className="border-b border-ink/15 bg-ink/[0.02] px-4 py-3">
      <div className="flex items-baseline justify-between font-edit-mono text-[10px] uppercase tracking-widest text-ink/60">
        <span>§ Live Co-Pilot</span>
        <span className="flex items-center gap-1 text-emerald-700">
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-700 opacity-70" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-700" />
          </span>
          Listening
        </span>
      </div>
      <p className="mt-1 font-serif text-[11px] italic text-ink/50">
        Ringg AI transcribes · SYNC analyzes · you approve.
      </p>
    </div>
  );
}

type Accent = "emerald" | "red" | "amber" | "ink";
const ACCENT: Record<Accent, { dot: string; chip: string; head: string }> = {
  emerald: { dot: "bg-emerald-700", chip: "border-emerald-700/40 bg-emerald-50 text-emerald-800", head: "text-emerald-800" },
  red:     { dot: "bg-red-700",     chip: "border-red-700/40 bg-red-50 text-red-800",             head: "text-red-800" },
  amber:   { dot: "bg-amber-700",   chip: "border-amber-700/40 bg-amber-50 text-amber-900",       head: "text-amber-900" },
  ink:     { dot: "bg-ink",         chip: "border-ink/30 bg-ink/[0.04] text-ink",                  head: "text-ink" },
};

function Section({ title, empty, Icon, accent, count, children }: {
  title: string; empty: string; Icon: typeof AlertTriangle; accent: Accent;
  count: number; children: React.ReactNode;
}) {
  const a = ACCENT[accent];
  return (
    <section className="border-b border-ink/10">
      <div className="flex items-center justify-between border-b border-ink/10 px-4 py-2">
        <div className={`flex items-center gap-2 font-edit-mono text-[10px] font-bold uppercase tracking-widest ${a.head}`}>
          <Icon className="h-3 w-3" />
          {title}
        </div>
        <span className={`inline-flex items-center justify-center border px-1.5 py-0.5 font-edit-mono text-[9px] font-bold tabular-nums ${count > 0 ? a.chip : "border-ink/15 bg-paper text-ink/30"}`}>
          {count}
        </span>
      </div>
      <div className="max-h-36 space-y-2 overflow-y-auto px-3 py-2">
        {count === 0 ? (
          <p className="px-1 font-serif text-[11px] italic leading-snug text-ink/40">{empty}</p>
        ) : (
          children
        )}
      </div>
    </section>
  );
}

function SuggestedCard({ say, onClick }: { say: string; onClick: () => void }) {
  const [copied, setCopied] = useState(false);
  const copy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard?.writeText(say).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  };
  return (
    <div
      onClick={onClick}
      className="group relative cursor-pointer border-l-4 border-emerald-700/60 border-y border-r border-ink/15 bg-emerald-50/40 px-2.5 py-2 transition-colors hover:bg-emerald-50"
      style={{ animation: "coachIn 0.25s ease-out both" }}
    >
      <p className="font-serif text-[13px] italic leading-snug text-ink">
        "{say}"
      </p>
      <div className="mt-1.5 flex items-center justify-between font-edit-mono text-[9px] uppercase tracking-widest text-emerald-800/80">
        <span className="inline-flex items-center gap-1">
          <Volume2 className="h-3 w-3" /> Say this
        </span>
        <button
          onClick={copy}
          className="inline-flex items-center gap-1 border border-emerald-700/40 bg-paper px-1.5 py-0.5 text-emerald-800 hover:bg-emerald-700 hover:text-paper"
        >
          {copied ? <><Check className="h-3 w-3" /> Copied</> : <><Copy className="h-3 w-3" /> Copy</>}
        </button>
      </div>
    </div>
  );
}

function NudgeCard({ text, tone }: { text: string; tone: "warn" | "opportunity" | "suggest" }) {
  const accent: Accent = tone === "warn" ? "red" : tone === "opportunity" ? "amber" : "ink";
  const a = ACCENT[accent];
  return (
    <div className={`border-l-4 border-y border-r border-ink/15 ${a.chip.replace("bg-", "bg-").replace("text-", "text-")} px-2.5 py-1.5`}
         style={{ animation: "coachIn 0.25s ease-out both" }}>
      <p className="font-serif text-[12.5px] italic leading-snug">
        {text}
      </p>
    </div>
  );
}

function ActionCard({ preview, status, onApprove, onSkip }: {
  preview: string;
  status: SidebarAction["status"];
  onApprove: () => void;
  onSkip: () => void;
}) {
  return (
    <div className="border-2 border-ink bg-paper px-2.5 py-2 shadow-sm"
         style={{ animation: "coachIn 0.25s ease-out both" }}>
      <p className="font-edit-mono text-[9px] font-bold uppercase tracking-widest text-ink/50">
        SYNC heard a commitment
      </p>
      <p className="mt-0.5 font-serif text-[13px] leading-snug text-ink">{preview}</p>
      <div className="mt-2 flex items-center gap-2">
        {status === "pending" && (
          <>
            <button onClick={onApprove}
              className="inline-flex items-center gap-1 border border-emerald-800 bg-emerald-800 px-2.5 py-1 font-edit-mono text-[9px] font-bold uppercase tracking-widest text-paper hover:bg-paper hover:text-emerald-800">
              <Check className="h-3 w-3" /> Approve · file in CRM
            </button>
            <button onClick={onSkip}
              className="inline-flex items-center gap-1 border border-ink/30 px-2.5 py-1 font-edit-mono text-[9px] uppercase tracking-widest text-ink/60 hover:bg-ink/[0.05]">
              <X className="h-3 w-3" /> Skip
            </button>
          </>
        )}
        {status === "executing" && (
          <span className="inline-flex items-center gap-1 font-edit-mono text-[9px] uppercase tracking-widest text-ink/60">
            <Loader2 className="h-3 w-3 animate-spin" /> Writing to CRM…
          </span>
        )}
        {status === "done" && (
          <span className="inline-flex items-center gap-1 font-edit-mono text-[9px] font-bold uppercase tracking-widest text-emerald-800">
            <Check className="h-3 w-3" /> Filed in Pipedrive
          </span>
        )}
        {status === "skipped" && (
          <span className="font-edit-mono text-[9px] uppercase tracking-widest text-ink/40">Skipped</span>
        )}
        {status === "failed" && (
          <span className="inline-flex items-center gap-2 font-edit-mono text-[9px] uppercase tracking-widest text-red-800">
            Failed — <button onClick={onApprove} className="underline">retry</button>
          </span>
        )}
      </div>
    </div>
  );
}
