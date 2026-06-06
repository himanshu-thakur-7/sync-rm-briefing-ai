import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface Props {
  children: ReactNode;
  className?: string;
  reverse?: boolean;
  pauseOnHover?: boolean;
  duration?: number;
}

export function Marquee({ children, className, reverse = false, pauseOnHover = true, duration = 30 }: Props) {
  return (
    <div className={cn("group flex overflow-hidden [--gap:2rem] gap-[--gap]", className)}>
      {Array(2).fill(0).map((_, i) => (
        <div
          key={i}
          className={cn(
            "flex shrink-0 justify-around gap-[--gap]",
            pauseOnHover && "group-hover:[animation-play-state:paused]",
            reverse ? "animate-marquee-reverse" : "animate-marquee"
          )}
          style={{ animationDuration: `${duration}s` }}
        >
          {children}
        </div>
      ))}
      <style>{`
        @keyframes marquee { from { transform: translateX(0); } to { transform: translateX(calc(-100% - var(--gap))); } }
        @keyframes marquee-reverse { from { transform: translateX(calc(-100% - var(--gap))); } to { transform: translateX(0); } }
        .animate-marquee { animation: marquee linear infinite; }
        .animate-marquee-reverse { animation: marquee-reverse linear infinite; }
      `}</style>
    </div>
  );
}
