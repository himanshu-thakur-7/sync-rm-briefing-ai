import { useState } from "react";
import { BriefingLog } from "@workspace/api-client-react";
import { Badge } from "@/components/ui/badge";

export function LiveFeed({ briefings }: { briefings: BriefingLog[] }) {
  return (
    <div className="bg-card border border-border/50 rounded-xl overflow-hidden flex flex-col h-full min-h-[500px]">
      <div className="border-b border-border/50 p-4 bg-secondary/20 flex justify-between items-center">
        <h2 className="font-semibold text-sm flex items-center">
          <span className="w-1.5 h-1.5 bg-primary rounded-full mr-2" />
          Live Feed
        </h2>
        <span className="text-xs text-muted-foreground font-mono">{briefings.length} events</span>
      </div>
      
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {briefings.length === 0 ? (
          <div className="h-full flex items-center justify-center text-sm text-muted-foreground">
            Waiting for events...
          </div>
        ) : (
          briefings.map((log, i) => (
            <div 
              key={log.briefing_id} 
              className="bg-background border border-border/50 rounded-lg p-4 text-sm animate-in slide-in-from-top-2 fade-in duration-300"
              style={{ animationDelay: `${i * 50}ms` }}
            >
              <div className="flex justify-between items-start mb-2">
                <div className="flex items-center space-x-2">
                  <span className="font-bold">{log.client_name}</span>
                  <span className="text-muted-foreground text-xs">sync'd by {log.rm_name}</span>
                </div>
                <div className="flex items-center space-x-2">
                  <RiskBadge score={log.risk_score} />
                  <span className="text-xs text-muted-foreground font-mono">{log.duration_seconds}s</span>
                </div>
              </div>
              
              <div className="text-muted-foreground mb-3 text-xs md:text-sm line-clamp-2">
                {log.suggested_pitch}
              </div>
              
              {log.key_flags.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {log.key_flags.map((flag, idx) => (
                    <span key={idx} className="text-[10px] bg-secondary text-secondary-foreground px-1.5 py-0.5 rounded font-mono border border-border/50">
                      {flag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function RiskBadge({ score }: { score: string }) {
  const getColors = () => {
    switch (score) {
      case 'very_low': return 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20';
      case 'low': return 'bg-blue-500/10 text-blue-500 border-blue-500/20';
      case 'medium': return 'bg-amber-500/10 text-amber-500 border-amber-500/20';
      case 'watch': return 'bg-orange-500/10 text-orange-500 border-orange-500/20';
      case 'high': return 'bg-red-500/10 text-red-500 border-red-500/20';
      default: return 'bg-secondary text-secondary-foreground border-border';
    }
  };

  return (
    <Badge variant="outline" className={`${getColors()} font-mono text-[10px] uppercase rounded-sm px-1.5`}>
      {score.replace('_', ' ')}
    </Badge>
  );
}