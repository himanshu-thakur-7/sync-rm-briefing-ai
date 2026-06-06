import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface Props {
  children: ReactNode;
  className?: string;
  containerClassName?: string;
  duration?: number;
}

export function MovingBorderCard({ children, className, containerClassName, duration = 3000 }: Props) {
  return (
    <div className={cn("relative overflow-hidden rounded-xl p-[1px]", containerClassName)}>
      <div
        className="absolute inset-0 rounded-xl"
        style={{
          background: "conic-gradient(from var(--angle), #6366f1, #8b5cf6, #06b6d4, #6366f1)",
          animation: `spin-border ${duration}ms linear infinite`,
        }}
      />
      <style>{`
        @property --angle { syntax: "<angle>"; initial-value: 0deg; inherits: false; }
        @keyframes spin-border { to { --angle: 360deg; } }
      `}</style>
      <div className={cn("relative rounded-xl bg-[#0a0f1e] z-10", className)}>
        {children}
      </div>
    </div>
  );
}
