// Thin client for the FastAPI backend. All shop data comes from these routes,
// which go through the MCP server; the dashboard never sees the database.
import type {
  ApprovalRequest, AuditEvent, CashPosition, DeskRunResult, RunSummary, Ticket,
} from "./types";

export const API_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

function detailText(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const d = detail as Record<string, unknown>;
    if (typeof d.refused === "string") return d.refused;
    if (Array.isArray(detail)) return detail.map((x) => (x as { msg?: string }).msg ?? String(x)).join("; ");
  }
  return JSON.stringify(detail);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(`Can't reach the backend at ${API_URL}. Is uvicorn running?`, 0);
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(detailText((body as { detail?: unknown }).detail ?? res.statusText), res.status);
  return body as T;
}

export const api = {
  health: () => request<{ ok: boolean; model: string; date_today: string; busy: boolean }>("/api/health"),
  tickets: () => request<{ tickets: Ticket[]; counts: { open: number; resolved: number } }>("/api/tickets"),
  cash: () => request<CashPosition>("/api/cash"),
  approvals: (status?: string) =>
    request<{ requests: ApprovalRequest[] }>(`/api/approvals${status ? `?status=${status}` : ""}`),
  activity: (params: { ticket_id?: number; limit?: number }) => {
    const q = new URLSearchParams();
    if (params.ticket_id != null) q.set("ticket_id", String(params.ticket_id));
    q.set("limit", String(params.limit ?? 20));
    return request<{ runs: RunSummary[]; human_actions: { timestamp: string; action: string }[] }>(`/api/activity?${q}`);
  },
  runEvents: (runId: string) => request<{ run_id: string; events: AuditEvent[] }>(`/api/runs/${runId}/events`),
  approve: (id: number, approvedBy: string, note = "") =>
    request<{
      request: ApprovalRequest;
      payment: { amount: number; new_balance: number; ticket_status_after: string | null } | null;
      checking_balance_before: number | null;
      checking_balance_after: number | null;
    }>(`/api/approvals/${id}/approve`, { method: "POST", body: JSON.stringify({ approved_by: approvedBy, note }) }),
  reject: (id: number, rejectedBy: string, note = "") =>
    request<{ request: ApprovalRequest }>(`/api/approvals/${id}/reject`, {
      method: "POST", body: JSON.stringify({ rejected_by: rejectedBy, note }),
    }),
  reset: (requestedBy: string) =>
    request<{ ok: boolean; checking_balance: number }>("/api/reset", {
      method: "POST", body: JSON.stringify({ confirm: true, requested_by: requestedBy }),
    }),
};

export interface StreamHandlers {
  onEvent: (e: AuditEvent) => void;
  onResult: (r: { result: DeskRunResult; ticket_after: Ticket }) => void;
  onError: (message: string) => void;
}

/** Run the agent team on one ticket and stream every agent step as it happens (SSE over fetch). */
export async function runTicketStream(ticketId: number, h: StreamHandlers): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/tickets/${ticketId}/run/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: "{}",
    });
  } catch {
    h.onError(`Can't reach the backend at ${API_URL}. Is uvicorn running?`);
    return;
  }
  if (!res.ok || !res.body) {
    const body = await res.json().catch(() => ({}));
    h.onError(detailText((body as { detail?: unknown }).detail ?? res.statusText));
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let cut: number;
    while ((cut = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, cut);
      buffer = buffer.slice(cut + 2);
      let event = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) continue;
      const payload = JSON.parse(data);
      if (event === "audit") h.onEvent(payload as AuditEvent);
      else if (event === "result") h.onResult(payload);
      else if (event === "error") h.onError(payload.detail ?? "The run failed.");
    }
  }
}
