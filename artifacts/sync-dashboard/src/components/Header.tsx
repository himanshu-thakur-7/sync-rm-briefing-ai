export function Header({ isConnected, latencyMs }: { isConnected: boolean; latencyMs: number | null }) {
  return (
    <header className="border-b border-border/50 bg-card/50 backdrop-blur sticky top-0 z-10">
      <div className="max-w-7xl mx-auto flex items-center justify-between h-16 px-4 md:px-6 lg:px-8">
        <div className="flex items-baseline space-x-3">
          <h1 className="text-xl font-bold tracking-tight">SYNC</h1>
          <span className="text-sm text-muted-foreground hidden sm:inline-block">RM Briefing Co-Pilot</span>
        </div>
        
        <div className="flex items-center space-x-4 text-xs font-mono">
          <div className="flex items-center space-x-2">
            <div className={`h-2 w-2 rounded-full ${isConnected ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" : "bg-destructive"}`} />
            <span className={isConnected ? "text-emerald-500" : "text-destructive"}>
              {isConnected ? "Live" : "Offline"}
            </span>
          </div>
          {latencyMs !== null && isConnected && (
            <div className="text-muted-foreground bg-secondary/50 px-2 py-1 rounded-md border border-border/50">
              {latencyMs}ms
            </div>
          )}
        </div>
      </div>
    </header>
  );
}