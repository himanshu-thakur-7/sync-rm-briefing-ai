import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";

export function BackgroundBeams({ className }: { className?: string }) {
  const beams = [
    { left: "14%", top: "0%", width: 1, delay: 0, duration: 7 },
    { left: "28%", top: "0%", width: 1, delay: 2, duration: 9 },
    { left: "43%", top: "0%", width: 1, delay: 4, duration: 6 },
    { left: "57%", top: "0%", width: 1, delay: 1, duration: 8 },
    { left: "71%", top: "0%", width: 1, delay: 3, duration: 7 },
    { left: "85%", top: "0%", width: 1, delay: 5, duration: 9 },
  ];

  return (
    <div className={cn("absolute inset-0 overflow-hidden pointer-events-none", className)}>
      {beams.map((beam, i) => (
        <div
          key={i}
          className="absolute top-0 h-full opacity-20"
          style={{
            left: beam.left,
            width: `${beam.width}px`,
            background: "linear-gradient(to bottom, transparent 0%, #6366f1 30%, #8b5cf6 60%, transparent 100%)",
            animation: `beamFall ${beam.duration}s ease-in-out ${beam.delay}s infinite`,
          }}
        />
      ))}
      <style>{`
        @keyframes beamFall {
          0% { transform: translateY(-100%); opacity: 0; }
          20% { opacity: 0.2; }
          80% { opacity: 0.15; }
          100% { transform: translateY(100vh); opacity: 0; }
        }
      `}</style>
    </div>
  );
}
