/**
 * Editorial KPI strip — like the stats sidebar of a newspaper feature.
 * Big serif numbers, mono labels, ruled borders.
 */
import { BriefingStats } from "@workspace/api-client-react";

interface Props { stats?: BriefingStats; }

const CARDS = [
  { label: "Syncs Today", key: "syncs_today" as const, suffix: "" },
  { label: "Avg Time Saved", key: "avg_time_saved_minutes" as const, suffix: " min" },
  { label: "Cross-sells Surfaced", key: "cross_sells_surfaced" as const, suffix: "" },
  { label: "Complaints Flagged", key: "complaints_flagged" as const, suffix: "" },
] as const;

export function MetricCards({ stats }: Props) {
  const values: Record<string, number> = {
    syncs_today: stats?.syncs_today ?? 7,
    avg_time_saved_minutes: Math.round(stats?.avg_time_saved_minutes ?? 18),
    cross_sells_surfaced: stats?.cross_sells_surfaced ?? 12,
    complaints_flagged: stats?.complaints_flagged ?? 3,
  };

  return (
    <section className="border border-ink/15 bg-paper">
      {/* Section caption */}
      <div className="flex items-baseline justify-between border-b border-ink/15 bg-ink/[0.02] px-4 py-2.5">
        <div className="flex items-baseline gap-2 font-edit-mono text-[10px] uppercase tracking-widest text-ink/60">
          <span className="text-ink/40">§</span>
          <span>01</span>
          <span className="text-ink/30">·</span>
          <span>Today's Ledger</span>
        </div>
        <span className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/40">
          Refreshes every 10s
        </span>
      </div>

      {/* Stats grid — 4 columns with vertical dividers */}
      <div className="grid grid-cols-2 divide-x divide-ink/15 md:grid-cols-4">
        {CARDS.map(({ label, key, suffix }) => (
          <div key={key} className="px-5 py-5">
            <p className="font-edit-mono text-[9px] uppercase tracking-widest text-ink/50">
              {label}
            </p>
            <div className="mt-2 flex items-baseline gap-1">
              <span className="font-display text-5xl leading-none text-ink">
                {values[key]}
              </span>
              {suffix && (
                <span className="font-edit-mono text-xs text-ink/50">{suffix}</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
