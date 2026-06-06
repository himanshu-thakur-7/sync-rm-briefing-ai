import { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  shimmerColor?: string;
  shimmerSize?: string;
  borderRadius?: string;
  background?: string;
  className?: string;
}

export function ShimmerButton({
  children,
  shimmerColor = "#6366f1",
  shimmerSize = "0.05em",
  borderRadius = "0.5rem",
  background = "radial-gradient(ellipse 80% 50% at 50% 120%, #1e1b4b, #0f172a)",
  className,
  ...props
}: Props) {
  return (
    <button
      style={{ "--shimmer-color": shimmerColor, "--cut": shimmerSize, "--border-radius": borderRadius, background } as any}
      className={cn(
        "group relative z-0 flex cursor-pointer items-center justify-center gap-2 overflow-hidden whitespace-nowrap px-6 py-3 text-white",
        "rounded-[--border-radius] border border-white/10",
        "transform-gpu transition-all duration-300 ease-in-out active:translate-y-px",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        "hover:scale-[1.02] hover:shadow-[0_0_30px_rgba(99,102,241,0.3)]",
        className,
      )}
      {...props}
    >
      {/* Shimmer layer */}
      <div
        className="absolute inset-0 overflow-hidden rounded-[--border-radius]"
        style={{ maskImage: `radial-gradient(${shimmerSize} ${shimmerSize} at 50% 50%, #fff ${parseFloat(shimmerSize) * 100}%, transparent 100%)` }}
      >
        <div className="animate-shimmer absolute inset-0 h-full w-full"
          style={{
            background: `conic-gradient(from 0deg, transparent 0%, ${shimmerColor} 10%, transparent 20%)`,
            animation: "shimmer-spin 3s linear infinite",
          }}
        />
      </div>
      <style>{`
        @keyframes shimmer-spin {
          0% { transform: rotate(0deg) scale(2); }
          100% { transform: rotate(360deg) scale(2); }
        }
      `}</style>
      <span className="relative z-10 flex items-center gap-2">{children}</span>
    </button>
  );
}
