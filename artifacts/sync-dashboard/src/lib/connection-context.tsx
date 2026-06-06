/**
 * Active CRM connection context.
 * Provides the selected connection_id across the whole app.
 * Switching via ConnectionSwitcher updates this context and all queries re-fetch.
 */
import { createContext, useContext, useState, ReactNode } from "react";

interface ConnectionContextValue {
  connectionId: string;
  setConnectionId: (id: string) => void;
  isSandbox: boolean;
}

const ConnectionContext = createContext<ConnectionContextValue>({
  connectionId: "conn_lsq_sandbox",
  setConnectionId: () => {},
  isSandbox: true,
});

const SANDBOX_PROVIDERS = new Set(["fake_leadsquared", "mock"]);

export function ConnectionProvider({ children }: { children: ReactNode }) {
  const [connectionId, setConnectionId] = useState("conn_lsq_sandbox");

  // Determine if sandbox from the id suffix (cheap client-side heuristic;
  // the full provider check happens in ConnectionSwitcher via the API).
  const isSandbox = connectionId.includes("lsq_sandbox") || connectionId.includes("mock");

  return (
    <ConnectionContext.Provider value={{ connectionId, setConnectionId, isSandbox }}>
      {children}
    </ConnectionContext.Provider>
  );
}

export function useConnection() {
  return useContext(ConnectionContext);
}
