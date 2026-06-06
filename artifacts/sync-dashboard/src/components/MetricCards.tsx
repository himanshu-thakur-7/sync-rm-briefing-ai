import { BriefingStats } from "@workspace/api-client-react";
import { GlowCard } from "./aceternity/glow-card";
import { AnimatedCounter } from "./aceternity/animated-counter";
import { PhoneCall, Clock, Sparkles, ShieldAlert } from "lucide-react";

interface Props { stats?: BriefingStats; }

const CARDS = [
  {
    label: "Syncs Today",
    key: "syncs_today" as const,
    icon: PhoneCall,
    suffix: "",
    color: "#6366f1",
    glow: "rgba(99,102,241,0.3)",
    bg: "from-indigo-500/10 to-transparent",
  },
  {
    label: "Avg Time Saved",
    key: "avg_time_saved_minutes" as const,
    icon: Clock,
    suffix: " min",
    color: "#8b5cf6",
    glow: "rgba(139,92,246,0.3)",
    bg: "from-violet-500/10 to-transparent",
  },
  {
    label: "Cross-sells Surfaced",
    key: "cross_sells_surfaced" as const,
    icon: Sparkles,
    suffix: "",
    color: "#06b6d4",
    glow: "rgba(6,182,212,0.3)",
    bg: "from-cyan-500/10 to-transparent",
  },
  {
    label: "Complaints Flagged",
    key: "complaints_flagged" as const,
    icon: ShieldAlert,
    suffix: "",
    color: "#f97316",
    glow: "rgba(249,115,22,0.3)",
    bg: "from-orange-500/10 to-transparent",
  },
] as const;

export function MetricCards({ stats }: Props) {
  const values: Record<string, number> = {
    syncs_today: stats?.syncs_today ?? 7,
    avg_time_saved_minutes: Math.round(stats?.avg_time_saved_minutes ?? 18),
    cross_sells_surfaced: stats?.cross_sells_surfaced ?? 12,
    complaints_flagged: stats?.complaints_flagged ?? 3,
  };

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {CARDS.map(({ label, key, icon: Icon, suffix, color, glow, bg }) => (
        <GlowCard key={key} glowColor={glow} intensity={0.12} className="p-5">
          <div className={`absolute inset-0 rounded-xl bg-gradient-to-br ${bg} opacity-50`} />
          <div className="relative">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">{label}</span>
              <div className="flex h-7 w-7 items-center justify-center rounded-lg"
                style={{ background: `${color}15`, border: `1px solid ${color}30` }}>
                <Icon className="h-3.5 w-3.5" style={{ color }} />
              </div>
            </div>
            <div className="text-3xl font-bold tracking-tight text-white">
              <AnimatedCounter target={values[key]} suffix={suffix} />
            </div>
          </div>
        </GlowCard>
      ))}
    </div>
  );
}
