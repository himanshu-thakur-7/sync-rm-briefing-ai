import { useRef, useState, ReactNode } from "react";
import { cn } from "@/lib/utils";

interface Props {
  children: ReactNode;
  className?: string;
  glowColor?: string;
  intensity?: number;
}

export function GlowCard({ children, className, glowColor = "rgba(99,102,241,0.4)", intensity = 0.15 }: Props) {
  const divRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ x: 0, y: 0, opacity: 0 });

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!divRef.current) return;
    const rect = divRef.current.getBoundingClientRect();
    setPos({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
      opacity: intensity,
    });
  };

  const handleMouseLeave = () => setPos(p => ({ ...p, opacity: 0 }));

  return (
    <div
      ref={divRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      className={cn("relative overflow-hidden rounded-xl border border-white/[0.06] bg-white/[0.02] backdrop-blur-sm transition-all duration-300 hover:border-white/[0.12]", className)}
    >
      {/* Spotlight effect */}
      <div
        className="pointer-events-none absolute inset-0 rounded-xl transition-opacity duration-300"
        style={{
          opacity: pos.opacity,
          background: `radial-gradient(600px circle at ${pos.x}px ${pos.y}px, ${glowColor}, transparent 40%)`,
        }}
      />
      {/* Animated border glow on hover */}
      <div className="pointer-events-none absolute inset-0 rounded-xl opacity-0 transition-opacity duration-500 group-hover:opacity-100"
        style={{ background: `radial-gradient(400px circle at ${pos.x}px ${pos.y}px, ${glowColor}, transparent 60%)` }}
      />
      {children}
    </div>
  );
}
