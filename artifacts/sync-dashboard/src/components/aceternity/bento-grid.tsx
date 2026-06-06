import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface BentoItemProps {
  title: string;
  description: string;
  icon?: ReactNode;
  visual?: ReactNode;
  className?: string;
  glowColor?: string;
}

export function BentoItem({ title, description, icon, visual, className, glowColor = "rgba(99,102,241,0.2)" }: BentoItemProps) {
  return (
    <div className={cn(
      "group relative overflow-hidden rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6 transition-all duration-500",
      "hover:border-white/[0.12] hover:bg-white/[0.04]",
      className,
    )}>
      {/* Hover glow */}
      <div className="absolute inset-0 opacity-0 transition-opacity duration-500 group-hover:opacity-100"
        style={{ background: `radial-gradient(600px circle at 50% 0%, ${glowColor}, transparent 50%)` }}
      />

      <div className="relative flex h-full flex-col">
        {icon && (
          <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-white/[0.04] ring-1 ring-white/[0.08]">
            {icon}
          </div>
        )}

        {visual && <div className="mb-4">{visual}</div>}

        <h3 className="mb-2 text-base font-semibold text-white">{title}</h3>
        <p className="text-sm leading-relaxed text-slate-400">{description}</p>
      </div>
    </div>
  );
}

export function BentoGrid({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("grid grid-cols-1 gap-4 md:grid-cols-3", className)}>
      {children}
    </div>
  );
}
