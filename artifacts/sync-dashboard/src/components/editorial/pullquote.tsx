/**
 * Big magazine-style pull quote — the kind The Economist breaks paragraphs with.
 */
import { ReactNode } from "react";

interface Props {
  children: ReactNode;
  attribution?: string;
}

export function PullQuote({ children, attribution }: Props) {
  return (
    <figure className="mx-auto my-12 max-w-3xl border-l-2 border-ink py-2 pl-6 md:my-16 md:pl-10">
      <blockquote className="font-serif text-2xl font-light italic leading-tight text-ink md:text-4xl">
        <span className="text-4xl leading-none text-ink/30 md:text-6xl">"</span>
        {children}
        <span className="text-4xl leading-none text-ink/30 md:text-6xl">"</span>
      </blockquote>
      {attribution && (
        <figcaption className="mt-3 font-mono text-[11px] uppercase tracking-widest text-ink/50">
          — {attribution}
        </figcaption>
      )}
    </figure>
  );
}
