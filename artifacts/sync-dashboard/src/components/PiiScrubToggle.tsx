import { Eye, EyeOff } from "lucide-react";
import { usePii } from "@/lib/pii-context";
import { cn } from "@/lib/utils";

export function PiiScrubToggle() {
  const { scrubEnabled, toggle } = usePii();
  return (
    <button
      onClick={toggle}
      className={cn(
        "inline-flex h-8 w-8 items-center justify-center border transition-colors",
        scrubEnabled
          ? "border-ink bg-ink text-cream"
          : "border-ink/30 bg-paper text-ink/70 hover:bg-ink hover:text-cream"
      )}
      title={scrubEnabled ? "PII redacted — click to reveal" : "Click to redact PII for demo"}
    >
      {scrubEnabled ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
    </button>
  );
}
