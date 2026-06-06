import { useState } from "react";
import { useListClients, useSyncNow } from "@workspace/api-client-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2 } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";

export function SyncPanel() {
  const { data: clients, isLoading: clientsLoading } = useListClients();
  const [selectedClient, setSelectedClient] = useState<string>("");
  const [rmPhone, setRmPhone] = useState("");
  const [rmName, setRmName] = useState("Himanshu");
  
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewText, setPreviewText] = useState("");

  const syncMutation = useSyncNow();

  const handleSync = () => {
    if (!selectedClient || !rmPhone || !rmName) return;

    syncMutation.mutate(
      { data: { client_id: selectedClient, rm_phone: rmPhone, rm_name: rmName } },
      {
        onSuccess: (data) => {
          setPreviewText(data.briefing_preview);
          setPreviewOpen(true);
        }
      }
    );
  };

  const isPending = syncMutation.isPending;
  const isSuccess = syncMutation.isSuccess;

  return (
    <>
      <div className="bg-card border border-primary/20 shadow-[0_0_30px_rgba(var(--primary),0.05)] rounded-xl p-5 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 blur-3xl rounded-full" />
        
        <h2 className="text-lg font-bold mb-5 flex items-center relative">
          <svg className="w-5 h-5 mr-2 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinelinejoin="round">
            <path d="m22 8-6 4 6 4V8Z"/><rect width="14" height="12" x="2" y="6" rx="2" ry="2"/>
          </svg>
          SYNC A CLIENT
        </h2>
        
        <div className="space-y-4 relative">
          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground font-mono uppercase">Client</Label>
            <Select value={selectedClient} onValueChange={setSelectedClient} disabled={clientsLoading || isPending}>
              <SelectTrigger className="w-full bg-background/50">
                <SelectValue placeholder={clientsLoading ? "Loading clients..." : "Select client..."} />
              </SelectTrigger>
              <SelectContent>
                {clients?.map(client => (
                  <SelectItem key={client.client_id} value={client.client_id}>
                    <div className="flex items-center justify-between w-full">
                      <span>{client.name}</span>
                      <span className="text-xs text-muted-foreground ml-2">{client.company}</span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground font-mono uppercase">RM Name</Label>
            <Input 
              placeholder="Your name" 
              value={rmName} 
              onChange={(e) => setRmName(e.target.value)}
              disabled={isPending}
              className="bg-background/50"
            />
          </div>

          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground font-mono uppercase">RM Phone</Label>
            <Input 
              placeholder="+1 (555) 000-0000" 
              value={rmPhone} 
              onChange={(e) => setRmPhone(e.target.value)}
              disabled={isPending}
              className="bg-background/50 font-mono"
            />
          </div>

          <Button 
            className={`w-full font-bold tracking-wide mt-2 ${isSuccess && !isPending ? "bg-emerald-600 hover:bg-emerald-700 text-white" : ""}`}
            onClick={handleSync}
            disabled={!selectedClient || !rmPhone || !rmName || isPending}
          >
            {isPending ? (
              <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Calling...</>
            ) : isSuccess ? (
              "Sync Delivered ✓"
            ) : (
              "Sync Now"
            )}
          </Button>
        </div>
      </div>

      <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
        <DialogContent className="sm:max-w-[500px] border-border bg-card">
          <DialogHeader>
            <DialogTitle className="font-mono text-sm uppercase text-muted-foreground tracking-wider mb-2">Briefing Preview</DialogTitle>
            <DialogDescription className="text-foreground text-sm whitespace-pre-wrap leading-relaxed">
              {previewText}
            </DialogDescription>
          </DialogHeader>
        </DialogContent>
      </Dialog>
    </>
  );
}