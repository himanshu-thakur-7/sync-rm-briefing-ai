import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

interface Props {
  words: string[];
  className?: string;
  cursorClassName?: string;
  speed?: number;
  pause?: number;
}

export function TypewriterText({
  words,
  className,
  cursorClassName,
  speed = 60,
  pause = 1500,
}: Props) {
  const [text, setText] = useState("");
  const [wordIdx, setWordIdx] = useState(0);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    const current = words[wordIdx];
    if (!deleting && text === current) {
      const t = setTimeout(() => setDeleting(true), pause);
      return () => clearTimeout(t);
    }
    if (deleting && text === "") {
      setDeleting(false);
      setWordIdx((i) => (i + 1) % words.length);
      return undefined;
    }
    const t = setTimeout(() => {
      setText(deleting ? current.slice(0, text.length - 1) : current.slice(0, text.length + 1));
    }, deleting ? speed / 2 : speed);
    return () => clearTimeout(t);
  }, [text, deleting, wordIdx, words, speed, pause]);

  return (
    <span className={cn("inline-block", className)}>
      {text}
      <span className={cn("ml-0.5 inline-block h-[0.9em] w-[2px] -translate-y-[10%] bg-indigo-400 align-middle", cursorClassName)}
        style={{ animation: "blink 1s steps(2) infinite" }}
      />
      <style>{`@keyframes blink { 50% { opacity: 0; } }`}</style>
    </span>
  );
}
