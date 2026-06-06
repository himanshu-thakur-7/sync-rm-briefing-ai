/**
 * Hand-sketched arrow — for editorial annotations on the page.
 * Adds a "scribbled by an editor" feel.
 */
import { cn } from "@/lib/utils";

interface Props { className?: string; rotate?: number; }

export function HandwrittenArrow({ className, rotate = 0 }: Props) {
  return (
    <svg
      viewBox="0 0 120 80"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={cn("text-amber-700/80", className)}
      style={{ transform: `rotate(${rotate}deg)` }}
    >
      <path
        d="M 10 60 Q 30 10, 60 35 T 100 50"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        fill="none"
      />
      <path
        d="M 100 50 L 92 42 M 100 50 L 92 58"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        fill="none"
      />
    </svg>
  );
}
