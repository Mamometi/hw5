const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

export const money = (n: number | null | undefined) => (n == null ? "—" : usd.format(n));

export function longDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso);
  return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", year: "numeric" });
}

export function shortDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function clockTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", second: "2-digit" });
}

export const TICKET_TYPES: Record<string, string> = {
  customer_order: "Customer order",
  rent_notice: "Rent notice",
  price_override: "Price override",
};

/** Ticket status → label and tone (tone drives the color of the status pill). */
export type Tone = "new" | "progress" | "waiting" | "attention" | "done";
export const STATUS: Record<string, { label: string; tone: Tone }> = {
  open: { label: "New", tone: "new" },
  in_progress: { label: "In progress", tone: "progress" },
  waiting_on_vendor: { label: "Waiting on vendor", tone: "waiting" },
  waiting_on_customer: { label: "Waiting on customer", tone: "waiting" },
  awaiting_human_approval: { label: "Needs your approval", tone: "attention" },
  resolved: { label: "Resolved", tone: "done" },
  shipped: { label: "Shipped", tone: "done" },
};
export const statusOf = (s: string) => STATUS[s] ?? { label: s.replace(/_/g, " "), tone: "progress" as Tone };

export const REQUEST_KINDS: Record<string, string> = {
  invoice_payment: "Vendor invoice payment",
  rent_payment: "Rent payment",
  price_override: "Price override",
};

/** Plain-English verbs for each MCP tool, used in the live feed. */
export const TOOL_PHRASES: Record<string, string> = {
  get_desk_date: "checked today's desk date",
  list_open_tickets: "looked over the open tickets",
  list_tickets: "looked over all tickets",
  get_ticket: "read the ticket",
  check_customer_order_stock_and_restock_invoice: "checked stock and the restock invoice",
  verify_rent_notice_against_lease: "checked the rent notice against the lease",
  evaluate_bulk_discount_request: "worked out stock, cost and discount limits",
  get_cash_position: "reviewed the cash position",
  list_approval_requests: "reviewed requests waiting on approval",
  update_ticket_status: "updated the ticket status",
  request_payment_approval: "filed a payment request for your approval",
  request_price_override_approval: "filed a price override for your approval",
  ship_customer_order: "tried to ship the order",
  assign_ticket: "assigned the ticket",
  ask_colleague: "asked a colleague",
};
export const toolPhrase = (t: string) => TOOL_PHRASES[t] ?? `used ${t}`;

/** Where a ticket is in its life: 0 received · 1 agents on it · 2 waiting on you · 3 done. */
export const LIFECYCLE = ["Received", "Agents", "Your call", "Done"] as const;
export function lifecycleStep(status: string, hasPending: boolean): number {
  if (status === "resolved" || status === "shipped") return 3;
  if (status === "awaiting_human_approval" || hasPending) return 2;
  if (status === "open") return 0;
  return 1;
}
