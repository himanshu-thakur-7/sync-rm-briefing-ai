import { GlowCard } from "./aceternity/glow-card";
import { X, Check } from "lucide-react";

const WITHOUT = [
  "15–20 min CRM reading",
  "Complaints missed 40% of the time",
  "Generic product pitch",
  "Touchpoint never logged",
  "No audit trail",
];
const WITH = [
  "30-second voice briefing",
  "Every complaint surfaced",
  "Context-aware, life-tied pitch",
  "Auto-logged to CRM",
  "Full briefing audit trail",
];

export function Comparison() {
  return (
    <GlowCard glowColor="rgba(99,102,241,0.15)" className="overflow-hidden">
      <div className="grid grid-cols-2 divide-x divide-white/[0.06]">
        <div className="p-4">
          <div className="mb-3 flex items-center gap-2">
            <div className="flex h-5 w-5 items-center justify-center rounded-full bg-slate-500/15">
              <X className="h-3 w-3 text-slate-500" />
            </div>
            <span className="text-[10px] font-bold uppercase tracking-widest text-slate-600">Without SYNC</span>
          </div>
          <ul className="space-y-2">
            {WITHOUT.map((t, i) => (
              <li key={i} className="flex items-start gap-2 text-[11px] text-slate-600">
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-slate-600" />{t}
              </li>
            ))}
          </ul>
        </div>
        <div className="relative p-4">
          <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-transparent" />
          <div className="relative">
            <div className="mb-3 flex items-center gap-2">
              <div className="flex h-5 w-5 items-center justify-center rounded-full bg-indigo-500/15 ring-1 ring-indigo-500/30">
                <Check className="h-3 w-3 text-indigo-400" />
              </div>
              <span className="text-[10px] font-bold uppercase tracking-widest text-indigo-400">With SYNC</span>
            </div>
            <ul className="space-y-2">
              {WITH.map((t, i) => (
                <li key={i} className="flex items-start gap-2 text-[11px] text-slate-300">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-indigo-500" />{t}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
      <div className="border-t border-white/[0.06] bg-white/[0.01] px-4 py-3">
        <div className="flex items-center justify-between text-[10px]">
          <span className="text-slate-600">50 RMs × 3 meetings/day × 18 min</span>
          <span className="font-bold text-indigo-400">₹15/sync · ROI Week 1</span>
        </div>
      </div>
    </GlowCard>
  );
}
