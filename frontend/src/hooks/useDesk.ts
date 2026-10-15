// All dashboard state and actions in one hook: tickets, cash, approvals, the
// live agent runs, and toasts. Components only render what this returns.
import { useEffect, useRef, useState } from "react";
import { api, runTicketStream } from "../api";
import { money, REQUEST_KINDS } from "../format";
import type { ApprovalRequest, AuditEvent, CashPosition, DeskRunResult, Ticket } from "../types";

export interface RunView {
  events: AuditEvent[];
  running: boolean;
  result: DeskRunResult | null;
  error: string | null;
  live: boolean; // streamed in this session (vs. loaded from history)
  startedAt: number | null;
}

export interface Toast {
  id: number;
  tone: "ok" | "bad" | "info";
  title: string;
  text?: string;
}

export interface BalanceChange {
  before: number;
  after: number;
  label: string;
}

let toastSeq = 0;

export function useDesk() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [cash, setCash] = useState<CashPosition | null>(null);
  const [pending, setPending] = useState<ApprovalRequest[]>([]);
  const [health, setHealth] = useState<{ model: string; date_today: string } | null>(null);
  const [connected, setConnected] = useState<boolean | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [runs, setRuns] = useState<Record<number, RunView>>({});
  const [runningId, setRunningId] = useState<number | null>(null);
  const [lastChange, setLastChange] = useState<BalanceChange | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const checkedHistory = useRef(new Set<number>());

  function notify(t: Omit<Toast, "id">) {
    const id = ++toastSeq;
    setToasts((cur) => [...cur.slice(-2), { ...t, id }]);
    window.setTimeout(() => setToasts((cur) => cur.filter((x) => x.id !== id)), 6500);
  }
  function dismiss(id: number) {
    setToasts((cur) => cur.filter((x) => x.id !== id));
  }

  async function refresh() {
    try {
      const [t, c, p] = await Promise.all([api.tickets(), api.cash(), api.approvals("pending")]);
      setTickets(t.tickets);
      setCash(c);
      setPending(p.requests);
      setConnected(true);
      return t.tickets;
    } catch (e) {
      setConnected(false);
      notify({ tone: "bad", title: "Can't load the desk", text: (e as Error).message });
      return null;
    }
  }

  // First load: health, data, and select the first ticket.
  useEffect(() => {
    api.health().then(setHealth).catch(() => setConnected(false));
    refresh().then((t) => { if (t?.length) setSelected((s) => s ?? t[0].id); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Show the ticket's most recent run from the audit trail (unless one is live).
  // Runs from before the latest reset are skipped: they describe data that's gone.
  useEffect(() => {
    if (selected == null || runs[selected] || checkedHistory.current.has(selected)) return;
    const ticketId = selected;
    checkedHistory.current.add(ticketId);
    (async () => {
      try {
        const [{ runs: recent }, { human_actions }] = await Promise.all([
          api.activity({ ticket_id: ticketId, limit: 1 }),
          api.activity({ limit: 100 }),
        ]);
        const lastReset = human_actions.find((h) => h.action === "reset_database")?.timestamp;
        if (!recent.length || (lastReset && recent[0].started_at < lastReset)) return;
        const { events } = await api.runEvents(recent[0].run_id);
        setRuns((prev) => (prev[ticketId]?.live ? prev : {
          ...prev,
          [ticketId]: { events, running: false, result: null, error: null, live: false, startedAt: null },
        }));
      } catch { /* no history yet */ }
    })();
  }, [selected, runs]);

  async function runTicket(ticketId: number) {
    setRunningId(ticketId);
    setRuns((prev) => ({
      ...prev,
      [ticketId]: { events: [], running: true, result: null, error: null, live: true, startedAt: Date.now() },
    }));
    const patch = (p: Partial<RunView> | ((cur: RunView) => Partial<RunView>)) =>
      setRuns((prev) => {
        const cur = prev[ticketId];
        return { ...prev, [ticketId]: { ...cur, ...(typeof p === "function" ? p(cur) : p) } };
      });
    await runTicketStream(ticketId, {
      onEvent: (e) => patch((cur) => ({ events: [...cur.events, e] })),
      onResult: ({ result }) => {
        patch({ result });
        notify({
          tone: result.ok ? "ok" : "bad",
          title: result.ok ? `Ticket #${ticketId} worked` : `Run on #${ticketId} stopped`,
          text: result.ok
            ? `${result.usage.total_tokens.toLocaleString()} tokens across the team`
            : result.error ?? undefined,
        });
      },
      onError: (msg) => {
        patch({ error: msg });
        notify({ tone: "bad", title: "The run failed", text: msg });
      },
    });
    patch({ running: false });
    setRunningId(null);
    await refresh();
  }

  async function approve(r: ApprovalRequest, approver: string) {
    try {
      const res = await api.approve(r.id, approver.trim());
      if (res.payment && res.checking_balance_before != null && res.checking_balance_after != null) {
        setLastChange({
          before: res.checking_balance_before,
          after: res.checking_balance_after,
          label: `${REQUEST_KINDS[r.kind]} #${r.id}`,
        });
        notify({
          tone: "ok",
          title: `Paid ${money(r.amount)}`,
          text: `Checking is now ${money(res.checking_balance_after)}.`,
        });
      } else {
        notify({ tone: "ok", title: `Approved ${money(r.amount)}/unit`, text: `Ticket #${r.ticket_id} · no money moved.` });
      }
    } catch (e) {
      notify({ tone: "bad", title: "Approval failed", text: (e as Error).message });
    }
    await refresh();
  }

  async function reject(r: ApprovalRequest, approver: string) {
    try {
      await api.reject(r.id, approver.trim());
      notify({ tone: "info", title: `Rejected request #${r.id}`, text: "Nothing was paid." });
    } catch (e) {
      notify({ tone: "bad", title: "Reject failed", text: (e as Error).message });
    }
    await refresh();
  }

  async function reset(approver: string) {
    try {
      await api.reset(approver.trim());
      setRuns({});
      checkedHistory.current.clear();
      setLastChange(null);
      notify({ tone: "info", title: "Desk reset", text: "Back to the original Campus Customs data." });
    } catch (e) {
      notify({ tone: "bad", title: "Reset failed", text: (e as Error).message });
    }
    await refresh();
  }

  return {
    tickets, cash, pending, health, connected, selected, setSelected, runs, runningId,
    lastChange, toasts, dismiss, notify, refresh, runTicket, approve, reject, reset,
  };
}

export type Desk = ReturnType<typeof useDesk>;

/** The approver's name, remembered in this browser. */
export function useApprover() {
  const [name, setName] = useState(() => localStorage.getItem("cc-approver") ?? "");
  function update(next: string) {
    setName(next);
    localStorage.setItem("cc-approver", next);
  }
  return [name, update] as const;
}

/** Seconds since `start`, ticking once a second while `active`. */
export function useElapsed(start: number | null, active: boolean) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, [active]);
  return start ? Math.max(0, Math.floor((now - start) / 1000)) : 0;
}
