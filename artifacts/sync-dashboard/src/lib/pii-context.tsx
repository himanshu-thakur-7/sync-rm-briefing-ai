/**
 * PII scrub context — when enabled, names render as initials and
 * phone numbers are partially masked. Judges can demo live HubSpot
 * data without projecting real customer PII.
 */
import { createContext, useContext, useState, ReactNode, useCallback } from "react";

interface PiiContextValue {
  scrubEnabled: boolean;
  toggle: () => void;
  scrub: (value: string, type?: "name" | "phone" | "text") => string;
}

const PiiContext = createContext<PiiContextValue>({
  scrubEnabled: false,
  toggle: () => {},
  scrub: (v) => v,
});

function scrubValue(value: string, type: "name" | "phone" | "text" = "text"): string {
  if (!value) return value;
  if (type === "name") {
    return value
      .split(" ")
      .map((part) => (part[0] ?? "").toUpperCase() + ".")
      .join(" ");
  }
  if (type === "phone") {
    return value.replace(/(\+?\d{2,3})\s*\d{4,5}\s*\d{3}(\d{4})/, "$1 ***-***-$2");
  }
  // Generic text: replace sequences of 4+ digits
  return value.replace(/\b\d{4,}\b/g, "****");
}

export function PiiProvider({ children }: { children: ReactNode }) {
  const [scrubEnabled, setScrubEnabled] = useState(false);
  const toggle = useCallback(() => setScrubEnabled((v) => !v), []);
  const scrub = useCallback(
    (value: string, type?: "name" | "phone" | "text") =>
      scrubEnabled ? scrubValue(value, type) : value,
    [scrubEnabled]
  );
  return (
    <PiiContext.Provider value={{ scrubEnabled, toggle, scrub }}>
      {children}
    </PiiContext.Provider>
  );
}

export function usePii() {
  return useContext(PiiContext);
}
