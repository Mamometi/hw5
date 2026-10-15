// Shapes returned by the FastAPI backend (backend/main.py, backend/models.py).

export type AgentName = "boss" | "inventory" | "accounting" | "facilities" | "customer_service";

export interface ApprovalRequest {
  id: number;
  kind: "invoice_payment" | "rent_payment" | "price_override";
  ticket_id: number | null;
  ref_id: number | null;
  amount: number;
  account: string | null;
  details: Record<string, unknown> | null;
  reason: string;
  requested_by: string;
  status: "pending" | "approved" | "rejected" | "executed";
  decided_by: string | null;
  decision_note: string | null;
  created_at: string;
  decided_at: string | null;
}

export interface Ticket {
  id: number;
  type: string;
  requester: string;
  subject: string;
  sku: string | null;
  size: string | null;
  qty: number | null;
  lease_id: number | null;
  invoice_id: number | null;
  status: string;
  state: "open" | "resolved";
  notes: string | null;
  created_at: string;
  approval_requests: Pick<ApprovalRequest, "id" | "kind" | "ref_id" | "amount" | "status" | "requested_by" | "decided_by" | "created_at">[];
}

export interface CashPosition {
  checking_balance: number | null;
  as_of: string | null;
  date_today: string;
  cash_accounts: { name: string; balance: number; date: string }[];
  payment_requests_awaiting_human: {
    id: number; kind: string; ticket_id: number | null; ref_id: number | null;
    amount: number; account: string; status: string; requested_by: string;
  }[];
  unpaid_invoices: {
    id: number; amount: number; due_date: string; status: string; description: string;
    vendor_name: string | null; days_overdue: number;
  }[];
  rent_due_within_window: {
    id: number; space_name: string; landlord: string; monthly_rent: number; next_due: string; days_until_due: number;
  }[];
  total_obligations: number;
  cash_after_all_obligations: number;
}

export interface AuditEvent {
  event_id: string;
  run_id: string;
  seq: number;
  timestamp: string;
  agent: AgentName | null;
  kind:
    | "run_start" | "agent_start" | "model_response" | "tool_call" | "tool_result"
    | "delegation" | "delegation_result" | "decision" | "limit_reached" | "error"
    | "run_end" | "human_action";
  ticket_id: number | null;
  delegation_chain: AgentName[];
  details: Record<string, any>;
}

export interface RunSummary {
  run_id: string;
  started_at: string;
  ended_at?: string;
  message: string | null;
  ticket_ids: number[] | null;
  ok: boolean | null;
  error?: string | null;
  delegations?: number;
  total_tokens?: number;
}

export interface ApprovalNeeded {
  request_id: number | null;
  kind: string;
  amount: number | null;
  summary: string;
}

export interface SpecialistReport {
  ticket_id: number | null;
  summary: string;
  findings: string[];
  actions_taken: string[];
  blocked_by: string[];
  needs_human_approval: ApprovalNeeded[];
  recommended_next_steps: string[];
  customer_message: string | null;
}

export interface TicketOutcome {
  ticket_id: number;
  ticket_type: string;
  handled_by: AgentName[];
  status_after: string;
  summary: string;
  human_decisions_needed: ApprovalNeeded[];
  customer_message: string | null;
}

export interface DeskReport {
  date_today: string;
  tickets: TicketOutcome[];
  cash_summary: string;
  human_action_items: string[];
}

export interface RunUsage {
  requests: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  tool_calls: number;
  by_agent: Record<string, { requests: number; input_tokens: number; output_tokens: number; tool_calls: number }>;
}

export interface DeskRunResult {
  run_id: string;
  ok: boolean;
  report: DeskReport | null;
  error: string | null;
  usage: RunUsage;
}
