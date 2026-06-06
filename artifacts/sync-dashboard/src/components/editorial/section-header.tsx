/**
 * Magazine-style numbered section header.
 * "§ 01 · The Briefing — A 45-second voice call before every client meeting."
 */
import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface Props {
  num: string;
  kicker?: string;
  title: ReactNode;
  className?: string;
}

export function SectionHeader({ num, kicker, title, className }: Props) {
  return (
    <div className={cn("border-t border-ink py-6 md:py-10", className)}>
      <div className="mx-auto max-w-content">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:gap-8">
          {/* Section number — like § 01 */}
          <div className="flex shrink-0 items-baseline gap-2 font-mono text-xs uppercase tracking-widest text-ink/60">
            <span className="text-ink/40">§</span>
            <span>{num}</span>
            {kicker && (
              <>
                <span className="text-ink/30">·</span>
                <span>{kicker}</span>
              </>
            )}
          </div>
          {/* Section title */}
          <h2 className="font-serif text-3xl font-medium leading-[1.1] tracking-tight text-ink md:text-5xl">
            {title}
          </h2>
        </div>
      </div>
    </div>
  );
}
