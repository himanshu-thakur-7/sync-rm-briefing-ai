import { Eye, EyeOff } from "lucide-react";
import { usePii } from "@/lib/pii-context";
import { cn } from "@/lib/utils";

export function PiiScrubToggle() {
  const { scrubEnabled, toggle } = usePii();
  return (
    <button
      onClick={toggle}
      className={cn(
        "flex h-8 w-8 items-center justify-center rounded-lg border transition-all",
        scrubEnabled
          ? "border-indigo-500/40 bg-indigo-500/15 text-indigo-300"
          : "border-white/[0.06] bg-white/[0.03] text-slate-400 hover:bg-white/[0.06] hover:text-white"
      )}
      title={scrubEnabled ? "PII scrub ON — names masked" : "Click to mask PII for demo"}
    >
      {scrubEnabled ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
    </button>
  );
}
