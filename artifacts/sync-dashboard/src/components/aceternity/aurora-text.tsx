import { cn } from "@/lib/utils";
import { ReactNode } from "react";

interface Props {
  children: ReactNode;
  className?: string;
}

export function AuroraText({ children, className }: Props) {
  return (
    <span className={cn("relative inline-block", className)}>
      <span
        className="bg-clip-text text-transparent"
        style={{
          backgroundImage: "linear-gradient(90deg, #6366f1, #8b5cf6, #06b6d4, #6366f1)",
          backgroundSize: "200% 100%",
          animation: "aurora-shift 6s linear infinite",
        }}
      >
        {children}
      </span>
      <style>{`
        @keyframes aurora-shift {
          0% { background-position: 0% 50%; }
          100% { background-position: 200% 50%; }
        }
      `}</style>
    </span>
  );
}
