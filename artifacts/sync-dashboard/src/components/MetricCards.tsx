import { BriefingStats } from "@workspace/api-client-react";
import { useEffect, useState } from "react";

function AnimatedNumber({ value }: { value: number }) {
  const [displayValue, setDisplayValue] = useState(value);

  useEffect(() => {
    setDisplayValue(value);
  }, [value]);

  return <span>{displayValue}</span>;
}

export function MetricCards({ stats }: { stats?: BriefingStats }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <Card title="Syncs Today" value={stats?.syncs_today ?? 0} />
      <Card title="Avg Time Saved" value={`${stats?.avg_time_saved_minutes ?? 0}m`} />
      <Card title="Cross-sells Surfaced" value={stats?.cross_sells_surfaced ?? 0} />
      <Card title="Complaints Flagged" value={stats?.complaints_flagged ?? 0} />
    </div>
  );
}

function Card({ title, value }: { title: string; value: number | string }) {
  return (
    <div className="bg-card border border-border/50 rounded-xl p-4 md:p-5 flex flex-col justify-between hover:border-primary/30 transition-colors">
      <span className="text-xs md:text-sm font-medium text-muted-foreground mb-2">{title}</span>
      <span className="text-2xl md:text-3xl font-mono tracking-tight font-bold">
        {typeof value === 'number' ? <AnimatedNumber value={value} /> : value}
      </span>
    </div>
  );
}