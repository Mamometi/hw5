import { Check } from "lucide-react";
import { statusOf } from "../format";

/** Two indicators: the simple open/resolved state, and the detailed stage the ticket is at. */
export function StatePill({ state }: { state: "open" | "resolved" }) {
  return (
    <span className={`state state--${state}`}>
      {state === "resolved" ? <Check size={12} strokeWidth={3} aria-hidden="true" /> : <span className="state__dot" />}
      {state === "resolved" ? "Resolved" : "Open"}
    </span>
  );
}

export function StatusChip({ status }: { status: string }) {
  const s = statusOf(status);
  return <span className={`chip chip--${s.tone}`}>{s.label}</span>;
}
