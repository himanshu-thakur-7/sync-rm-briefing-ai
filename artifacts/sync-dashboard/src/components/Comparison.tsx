export function Comparison() {
  return (
    <div className="bg-card border border-border/50 rounded-xl p-5">
      <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-4 font-mono">Process Impact</h3>
      
      <div className="space-y-4">
        <div className="relative pl-4 border-l border-destructive/30 pb-4">
          <div className="absolute w-2 h-2 bg-destructive rounded-full -left-[4.5px] top-1.5" />
          <div className="text-xs font-mono text-destructive mb-1">Before SYNC</div>
          <div className="text-sm">20 mins compiling CRM notes, missed cross-sells, unaware of recent complaints.</div>
        </div>
        
        <div className="relative pl-4 border-l border-emerald-500/30">
          <div className="absolute w-2 h-2 bg-emerald-500 rounded-full -left-[4.5px] top-1.5" />
          <div className="text-xs font-mono text-emerald-500 mb-1">With SYNC</div>
          <div className="text-sm">30 second voice brief. Key risks flagged. Context-aware pitch ready.</div>
        </div>
      </div>
    </div>
  );
}