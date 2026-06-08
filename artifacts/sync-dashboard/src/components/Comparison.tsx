/**
 * Editorial before/after table — small footer-info-box style.
 */
import { X, Check } from "lucide-react";

const ROWS = [
  { label: "Prep time", without: "15–20 min", with: "30 sec" },
  { label: "Complaints", without: "Missed 40%", with: "100% flagged" },
  { label: "Pitch", without: "Generic", with: "Context-tied" },
  { label: "CRM log", without: "Rarely", with: "Auto-logged" },
];

export function Comparison() {
  return (
    <section className="border border-ink/15 bg-paper">
      <div className="border-b border-ink/15 bg-ink/[0.02] px-4 py-2.5">
        <div className="flex items-baseline gap-2 font-edit-mono text-[10px] uppercase tracking-widest text-ink/60">
          <span className="text-ink/40">§</span>
          <span>05</span>
          <span className="text-ink/30">·</span>
          <span>Before / After</span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[360px] font-edit-mono text-[11px]">
          <thead>
            <tr className="border-b border-ink/15 text-left text-[9px] uppercase tracking-widest text-ink/40">
              <th className="whitespace-nowrap px-3 py-2 font-normal sm:px-4">Metric</th>
              <th className="whitespace-nowrap px-3 py-2 font-normal sm:px-4">
                <span className="inline-flex items-center gap-1">
                  <X className="h-2.5 w-2.5" /> Without
                </span>
              </th>
              <th className="whitespace-nowrap px-3 py-2 font-normal sm:px-4">
                <span className="inline-flex items-center gap-1 text-ink/80">
                  <Check className="h-2.5 w-2.5" /> With Sync
                </span>
              </th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row, i) => (
              <tr key={i} className="border-b border-ink/10 last:border-b-0 odd:bg-ink/[0.015]">
                <td className="whitespace-nowrap px-3 py-2.5 text-ink/60 sm:px-4">{row.label}</td>
                <td className="whitespace-nowrap px-3 py-2.5 text-ink/50 line-through sm:px-4">{row.without}</td>
                <td className="whitespace-nowrap px-3 py-2.5 font-semibold text-ink sm:px-4">{row.with}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="border-t border-ink/15 bg-ink/[0.01] px-4 py-2 font-edit-mono text-[10px] uppercase tracking-widest text-ink/50">
        ₹14.82 / sync · ROI from Week 1
      </div>
    </section>
  );
}
