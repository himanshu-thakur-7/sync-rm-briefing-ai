/**
 * Editorial statistic table — feels like the back of an Economist article.
 * No animated counters. Just clean data with ruled lines.
 */
interface Row {
  label: string;
  before: string;
  after: string;
  delta?: string;
}

interface Props {
  rows: Row[];
  caption?: string;
  source?: string;
}

export function DataTable({ rows, caption, source }: Props) {
  return (
    <figure className="border border-ink/15 bg-paper">
      {caption && (
        <figcaption className="border-b border-ink/15 bg-ink/[0.02] px-4 py-3 font-mono text-[10px] uppercase tracking-widest text-ink/60">
          Table 1 · {caption}
        </figcaption>
      )}
      <table className="w-full font-mono text-[12px]">
        <thead>
          <tr className="border-b border-ink/15 text-left text-[10px] uppercase tracking-widest text-ink/50">
            <th className="px-4 py-2 font-normal">Metric</th>
            <th className="px-4 py-2 font-normal">Without SYNC</th>
            <th className="px-4 py-2 font-normal">With SYNC</th>
            <th className="px-4 py-2 text-right font-normal">Δ</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-ink/10 last:border-b-0 odd:bg-ink/[0.015]">
              <td className="px-4 py-3 text-ink/90">{row.label}</td>
              <td className="px-4 py-3 text-ink/60 line-through">{row.before}</td>
              <td className="px-4 py-3 font-semibold text-ink">{row.after}</td>
              <td className="px-4 py-3 text-right font-medium text-emerald-700">{row.delta ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {source && (
        <div className="border-t border-ink/15 px-4 py-2 font-mono text-[10px] uppercase tracking-widest text-ink/40">
          {source}
        </div>
      )}
    </figure>
  );
}
