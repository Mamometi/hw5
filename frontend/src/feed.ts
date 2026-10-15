// Turns raw audit events into what the dashboard shows: a readable activity
// feed, each agent's live state, and (once a run ends) each agent's contribution.
import { AGENT_ORDER } from "./agents";
import { toolPhrase } from "./format";
import type { AgentName, AuditEvent, SpecialistReport, TicketOutcome } from "./types";

export type FeedKind = "start" | "pickup" | "thinking" | "tool" | "handoff" | "handback" | "report" | "warn" | "end" | "human";

export interface FeedItem {
  id: string;
  kind: FeedKind;
  at: string;
  agent: AgentName | null;
  to?: AgentName | null;
  title: string;
  detail?: string;
  tool?: string;
  ok?: boolean | null;
  depth?: number;
}

export type AgentState = "idle" | "working" | "waiting" | "done";

export interface AgentContribution {
  agent: AgentName;
  summary: string;
  actions: string[];
  findings: string[];
  approvals: { request_id: number | null; kind: string; amount: number | null; summary: string }[];
  blockers: string[];
  customerMessage: string | null;
  tools: string[];
  handoffsOut: { to: AgentName; task: string }[];
  askedBy: AgentName | null;
}

const short = (s: unknown, n = 220) => {
  const t = typeof s === "string" ? s : JSON.stringify(s ?? "");
  return t.length > n ? `${t.slice(0, n).trimEnd()}…` : t;
};

function resultSummary(content: string | undefined): { ok: boolean; text: string } {
  if (!content) return { ok: true, text: "" };
  try {
    const v = JSON.parse(content);
    if (v && typeof v === "object" && v.ok === false) return { ok: false, text: String(v.refused ?? v.error ?? "Refused") };
    if (v && typeof v === "object" && typeof v.request_id === "number") {
      return { ok: true, text: `Request #${v.request_id} filed${v.amount != null ? ` · $${Number(v.amount).toFixed(2)}` : ""}` };
    }
  } catch { /* not JSON */ }
  return { ok: true, text: "" };
}

export function buildFeed(events: AuditEvent[]): FeedItem[] {
  const items: FeedItem[] = [];
  const toolItems = new Map<string, FeedItem>();
  for (const e of events) {
    const d = e.details ?? {};
    const base = { id: e.event_id, at: e.timestamp, agent: e.agent, depth: Math.max(0, e.delegation_chain.length - 1) };
    switch (e.kind) {
      case "run_start":
        items.push({ ...base, kind: "start", title: "The desk opened this ticket", detail: d.message });
        break;
      case "agent_start":
        if (e.agent !== "boss") items.push({ ...base, kind: "pickup", title: "picked up the task" });
        break;
      case "model_response":
        if (d.text) items.push({ ...base, kind: "thinking", title: "is thinking", detail: short(d.text, 280) });
        break;
      case "tool_call": {
        if (d.tool === "final_result" || d.tool === "assign_ticket" || d.tool === "ask_colleague") break;
        const item: FeedItem = { ...base, kind: "tool", title: toolPhrase(d.tool), tool: d.tool, ok: null };
        items.push(item);
        toolItems.set(d.tool_call_id, item);
        break;
      }
      case "tool_result": {
        const item = toolItems.get(d.tool_call_id);
        if (item) {
          const r = resultSummary(d.content);
          item.ok = d.ok === false ? false : r.ok;
          if (r.text) item.detail = r.text;
        }
        break;
      }
      case "delegation":
        items.push({ ...base, kind: "handoff", agent: d.from_agent, to: d.to_agent, title: "handed off to", detail: short(d.task, 320) });
        break;
      case "delegation_result":
        items.push({
          ...base, kind: "handback", agent: e.agent, to: d.to_agent, title: "reported back to",
          detail: short(d.report?.summary ?? d.error ?? "", 320), ok: d.status === "done",
        });
        break;
      case "decision":
        if (e.agent === "boss") items.push({ ...base, kind: "report", title: "wrapped up the desk report", detail: short(d.output?.tickets?.[0]?.summary ?? "", 320) });
        break;
      case "limit_reached":
        items.push({ ...base, kind: "warn", title: "hit a limit", detail: short(d.reason) });
        break;
      case "error":
        items.push({ ...base, kind: "warn", title: "ran into an error", detail: short(d.error) });
        break;
      case "run_end":
        items.push({
          ...base, kind: "end", title: d.ok ? "Run complete" : "Run stopped",
          detail: `${d.delegations ?? 0} hand-offs · ${(d.usage?.total_tokens ?? 0).toLocaleString()} tokens`,
          ok: !!d.ok,
        });
        break;
    }
  }
  return items;
}

/** Who is doing what right now: working (its turn), waiting (on a colleague it asked), done. */
export function agentStates(events: AuditEvent[]): Record<AgentName, AgentState> {
  const state = Object.fromEntries(AGENT_ORDER.map((a) => [a, "idle"])) as Record<AgentName, AgentState>;
  const stack: AgentName[] = [];
  for (const e of events) {
    if (e.kind === "agent_start" && e.agent) {
      if (stack.length) state[stack[stack.length - 1]] = "waiting";
      stack.push(e.agent);
      state[e.agent] = "working";
    } else if (e.kind === "decision" && e.agent) {
      const i = stack.lastIndexOf(e.agent);
      if (i !== -1) stack.splice(i, 1);
      state[e.agent] = "done";
      if (stack.length) state[stack[stack.length - 1]] = "working";
    } else if ((e.kind === "run_end" || e.kind === "error") && !e.agent) {
      for (const a of stack) state[a] = "done";
      stack.length = 0;
    }
  }
  return state;
}

export function currentAgent(events: AuditEvent[]): AgentName | null {
  const s = agentStates(events);
  return AGENT_ORDER.find((a) => s[a] === "working") ?? null;
}

/** One card per agent that took part: what it reported, what it did, which tools it used. */
export function contributions(events: AuditEvent[]): { agents: AgentContribution[]; outcome: TicketOutcome | null; cashSummary: string | null } {
  const byAgent = new Map<AgentName, AgentContribution>();
  const get = (a: AgentName) => {
    if (!byAgent.has(a)) {
      byAgent.set(a, {
        agent: a, summary: "", actions: [], findings: [], approvals: [], blockers: [],
        customerMessage: null, tools: [], handoffsOut: [], askedBy: null,
      });
    }
    return byAgent.get(a)!;
  };
  let outcome: TicketOutcome | null = null;
  let cashSummary: string | null = null;

  for (const e of events) {
    const d = e.details ?? {};
    if (e.kind === "agent_start" && e.agent) {
      const c = get(e.agent);
      if (e.delegation_chain.length > 1) c.askedBy = e.delegation_chain[e.delegation_chain.length - 2];
    } else if (e.kind === "tool_call" && e.agent && !["final_result", "assign_ticket", "ask_colleague"].includes(d.tool)) {
      const c = get(e.agent);
      if (!c.tools.includes(d.tool)) c.tools.push(d.tool);
    } else if (e.kind === "delegation") {
      get(d.from_agent).handoffsOut.push({ to: d.to_agent, task: d.task });
    } else if (e.kind === "decision" && e.agent && d.output) {
      if (e.agent === "boss") {
        outcome = (d.output.tickets?.[0] as TicketOutcome) ?? null;
        cashSummary = d.output.cash_summary ?? null;
        get("boss").summary = outcome?.summary ?? "";
      } else {
        const r = d.output as SpecialistReport;
        const c = get(e.agent);
        // An agent can be asked more than once; keep every report.
        c.summary = c.summary ? `${c.summary} ${r.summary}` : r.summary;
        c.actions.push(...(r.actions_taken ?? []));
        c.findings.push(...(r.findings ?? []));
        c.approvals.push(...(r.needs_human_approval ?? []));
        c.blockers.push(...(r.blocked_by ?? []));
        c.customerMessage = r.customer_message ?? c.customerMessage;
      }
    }
  }
  const agents = AGENT_ORDER.filter((a) => byAgent.has(a)).map((a) => byAgent.get(a)!);
  return { agents, outcome, cashSummary };
}

export interface DelegationEdge {
  from: AgentName;
  to: AgentName;
  status: "active" | "done" | "error";
  task: string;
}

/** Every hand-off in the run, and whether it's still out (active) or has reported back. */
export function delegationEdges(events: AuditEvent[]): DelegationEdge[] {
  const edges: DelegationEdge[] = [];
  const open: DelegationEdge[] = [];
  for (const e of events) {
    const d = e.details ?? {};
    if (e.kind === "delegation") {
      const edge: DelegationEdge = { from: d.from_agent, to: d.to_agent, status: "active", task: d.task };
      edges.push(edge);
      open.push(edge);
    } else if (e.kind === "delegation_result") {
      const i = open.findIndex((x) => x.to === e.agent && x.from === d.to_agent);
      if (i !== -1) {
        open[i].status = d.status === "done" ? "done" : "error";
        open.splice(i, 1);
      }
    } else if (e.kind === "run_end") {
      for (const x of open) x.status = "error";
      open.length = 0;
    }
  }
  return edges;
}
