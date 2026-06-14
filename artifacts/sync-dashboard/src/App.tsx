import { Switch, Route, Router as WouterRouter } from "wouter";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ThemeProvider } from "next-themes";
import Landing from "@/pages/Landing";
import IntegrationsIndex from "@/pages/IntegrationsIndex";
import TheDemo from "@/pages/TheDemo";
import NotFound from "@/pages/not-found";
import { ConnectionProvider } from "@/lib/connection-context";
import { PiiProvider } from "@/lib/pii-context";
import { Redirect } from "wouter";

const queryClient = new QueryClient();

function Router() {
  return (
    <Switch>
      <Route path="/" component={Landing} />
      <Route path="/dashboard"><Redirect to="/the-demo" /></Route>
      <Route path="/radar"><Redirect to="/the-demo" /></Route>
      <Route path="/morning-brief"><Redirect to="/the-demo" /></Route>
      <Route path="/the-demo" component={TheDemo} />
      <Route path="/demo" component={TheDemo} />
      <Route path="/settings/integrations" component={IntegrationsIndex} />
      <Route component={NotFound} />
    </Switch>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      {/* Forced light — the editorial cream aesthetic owns the whole app now */}
      <ThemeProvider attribute="class" defaultTheme="light" enableSystem={false} forcedTheme="light">
        <TooltipProvider>
          <ConnectionProvider>
            <PiiProvider>
              <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, "")}>
                <Router />
              </WouterRouter>
              <Toaster />
            </PiiProvider>
          </ConnectionProvider>
        </TooltipProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
