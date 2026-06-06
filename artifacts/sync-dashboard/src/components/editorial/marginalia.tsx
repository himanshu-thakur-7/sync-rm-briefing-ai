/**
 * Editorial-style margin note — a footnote that sits in the right margin
 * on large screens, collapses inline on mobile.
 */
import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface Props {
  number?: string | number;
  children: ReactNode;
  className?: string;
}

export function Marginalia({ number, children, className }: Props) {
  return (
    <aside className={cn("relative mt-4 border-l-2 border-amber-700/40 bg-amber-50/40 py-2 pl-3 text-sm italic leading-relaxed text-ink/70 md:absolute md:right-[-220px] md:top-0 md:mt-0 md:w-[190px] md:border-l-0 md:bg-transparent md:pl-0", className)}>
      {number && (
        <sup className="mr-1 font-mono text-[10px] not-italic text-amber-800">[{number}]</sup>
      )}
      {children}
    </aside>
  );
}
