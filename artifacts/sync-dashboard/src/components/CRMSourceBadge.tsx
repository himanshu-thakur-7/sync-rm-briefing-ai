/**
 * CRMSourceBadge — editorial pill with a colored dot + provider name in mono.
 * No glow, no gradient — just a sharp-bordered chip.
 */
import { cn } from "@/lib/utils";

const PROVIDER_META: Record<string, { label: string; dot: string }> = {
  hubspot:          { label: "HubSpot",      dot: "#FF7A59" },
  salesforce:       { label: "Salesforce",   dot: "#00A1E0" },
  zoho:             { label: "Zoho",         dot: "#E74C3C" },
  dynamics:         { label: "Dynamics",     dot: "#0078D4" },
  freshworks:       { label: "Freshworks",   dot: "#10B981" },
  pipedrive:        { label: "Pipedrive",    dot: "#017737" },
  leadsquared:      { label: "LeadSquared",  dot: "#8B5CF6" },
  fake_leadsquared: { label: "LSQ Sandbox",  dot: "#B58A2D" },
  mock:             { label: "Demo",         dot: "#737373" },
};

export function CRMSourceBadge({ provider, className }: { provider: string; className?: string }) {
  const meta = PROVIDER_META[provider] ?? { label: provider, dot: "#737373" };
  return (
    <span className={cn(
      "inline-flex items-center gap-1.5 border border-ink/30 bg-paper px-1.5 py-0.5 font-edit-mono text-[9px] font-semibold uppercase tracking-widest text-ink/80",
      className
    )}>
      <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: meta.dot }} />
      {meta.label}
    </span>
  );
}

export function providerFromConnectionId(connectionId: string): string {
  for (const key of Object.keys(PROVIDER_META)) {
    if (connectionId.includes(key)) return key;
  }
  return "mock";
}
