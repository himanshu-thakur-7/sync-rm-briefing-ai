/**
 * Bloomberg-terminal-style market ticker bar.
 * Sits at the very top of the landing page above the masthead.
 */
import { cn } from "@/lib/utils";

const ITEMS = [
  { label: "SYNC", value: "v2.0.0", delta: "+ NEW" },
  { label: "INTEGRATIONS", value: "7", delta: "HUBSPOT · SF · ZOHO · DYNAMICS · FRESHWORKS · LSQ" },
  { label: "AVG LATENCY", value: "742ms", delta: "▼ 1.2s" },
  { label: "CALL COST", value: "₹14.82", delta: "▼ 3%" },
  { label: "PREP TIME SAVED", value: "18 min", delta: "▲ per RM" },
  { label: "CROSS-SELL LIFT", value: "3.2x", delta: "▲ baseline" },
  { label: "COMPLAINTS FLAGGED", value: "100%", delta: "▲ from 60%" },
  { label: "POWERED BY", value: "RINGG AI", delta: "GrowthX Buildathon" },
];

export function Ticker({ className }: { className?: string }) {
  return (
    <div className={cn("relative overflow-hidden border-y border-ink/15 bg-ink text-cream", className)}>
      <div className="flex animate-ticker whitespace-nowrap py-2 font-mono text-[11px] uppercase tracking-wider">
        {[...ITEMS, ...ITEMS, ...ITEMS].map((item, i) => (
          <div key={i} className="flex shrink-0 items-center gap-2 px-6">
            <span className="text-cream/50">{item.label}</span>
            <span className="font-semibold">{item.value}</span>
            <span className="text-amber-300/80">{item.delta}</span>
            <span className="text-cream/30">·</span>
          </div>
        ))}
      </div>
      <style>{`
        @keyframes ticker {
          from { transform: translateX(0); }
          to { transform: translateX(-33.333%); }
        }
        .animate-ticker { animation: ticker 80s linear infinite; }
      `}</style>
    </div>
  );
}
