// Human approvals with React 19 Actions: each request card is a <form> whose
// action approves or rejects. useFormStatus drives the button spinners, and
// useOptimistic marks the card "Paying…" immediately while the backend works.
import { Check, Hand, LoaderCircle, ShieldAlert, UserRound, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useOptimistic } from "react";
import { useFormStatus } from "react-dom";
import { AgentTag } from "../agents";
import { money, REQUEST_KINDS } from "../format";
import type { ApprovalRequest } from "../types";

interface Props {
  requests: ApprovalRequest[];
  selectedTicket: number | null;
  checking: number | null;
  approver: string;
  onApproverChange: (name: string) => void;
  onApprove: (r: ApprovalRequest) => Promise<void>;
  onReject: (r: ApprovalRequest) => Promise<void>;
  onSelectTicket: (id: number) => void;
}

const AGENT_NAMES = ["boss", "inventory", "accounting", "facilities", "customer_service"];
type Busy = { id: number; intent: "approve" | "reject" };

function Impact({ r, checking }: { r: ApprovalRequest; checking: number | null }) {
  if (r.kind === "price_override") {
    const d = (r.details ?? {}) as Record<string, number>;
    return (
      <div className="impact">
        <span>{money(d.list_price)} → <b>{money(r.amount)}</b> per unit</span>
        <span className="muted">{d.discount_pct}% off · {money(d.margin_per_unit)} margin · no money moves</span>
      </div>
    );
  }
  return (
    <div className="impact">
      <span>Checking {money(checking)} → <b>{checking == null ? "—" : money(checking - r.amount)}</b></span>
      <span className="muted">Paid from {r.account} the moment you approve</span>
    </div>
  );
}

function SubmitButtons({ r, nameOk }: { r: ApprovalRequest; nameOk: boolean }) {
  const { pending, data } = useFormStatus();
  const intent = data?.get("intent");
  return (
    <div className="request__actions">
      <motion.button
        type="submit" name="intent" value="approve"
        className="btn btn--approve" disabled={!nameOk || pending}
        whileTap={{ scale: 0.98 }}
      >
        {pending && intent === "approve" ? <LoaderCircle size={16} className="spin" aria-hidden="true" /> : <Check size={16} strokeWidth={2.6} aria-hidden="true" />}
        {r.kind === "price_override" ? "Approve price" : `Approve & pay ${money(r.amount)}`}
      </motion.button>
      <button type="submit" name="intent" value="reject" className="btn btn--ghost" disabled={!nameOk || pending}>
        {pending && intent === "reject" ? <LoaderCircle size={15} className="spin" aria-hidden="true" /> : <X size={15} aria-hidden="true" />}
        Reject
      </button>
    </div>
  );
}

export function Approvals({
  requests, selectedTicket, checking, approver, onApproverChange, onApprove, onReject, onSelectTicket,
}: Props) {
  const [busy, setBusy] = useOptimistic<Busy | null, Busy>(null, (_cur, next) => next);
  const nameOk = approver.trim().length > 0 && !AGENT_NAMES.includes(approver.trim().toLowerCase());
  const mine = requests.filter((r) => r.ticket_id === selectedTicket);
  const others = requests.filter((r) => r.ticket_id !== selectedTicket);

  function actionFor(r: ApprovalRequest) {
    return async (form: FormData) => {
      const intent = form.get("intent") === "reject" ? "reject" : "approve";
      setBusy({ id: r.id, intent });
      await (intent === "approve" ? onApprove(r) : onReject(r));
    };
  }

  return (
    <section className="panel approvals" aria-labelledby="approvals-title">
      <div className="panel__title" id="approvals-title">
        <span className="title-icon"><Hand size={15} aria-hidden="true" />Awaiting your approval</span>
        <motion.span
          key={requests.length}
          className={`panel__count${requests.length ? " panel__count--hot" : ""}`}
          initial={{ scale: 0.6 }}
          animate={{ scale: 1 }}
        >
          {requests.length}
        </motion.span>
      </div>

      <label className="approver">
        <UserRound size={16} aria-hidden="true" />
        <span>Approving as</span>
        <input value={approver} onChange={(e) => onApproverChange(e.target.value)} placeholder="Your name" aria-invalid={!nameOk} />
      </label>
      {!nameOk && <div className="approver__hint"><ShieldAlert size={13} aria-hidden="true" />Enter your own name. Agents can't approve.</div>}

      {requests.length === 0 && (
        <div className="approvals__empty">
          <Check size={20} aria-hidden="true" />
          Nothing waiting. Agents file requests here; no money moves until you approve.
        </div>
      )}

      <AnimatePresence initial={false}>
        {mine.map((r) => {
          const working = busy?.id === r.id;
          return (
            <motion.form
              key={r.id}
              action={actionFor(r)}
              layout
              className={`request request--${r.kind}${working ? " is-working" : ""}`}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, x: 40, transition: { duration: 0.25 } }}
            >
              <div className="request__top">
                <span className="request__kind">{REQUEST_KINDS[r.kind] ?? r.kind} · #{r.id}</span>
                <span className="request__amount">{money(r.amount)}{r.kind === "price_override" && <small>/unit</small>}</span>
              </div>
              <div className="request__by">Proposed by <AgentTag name={r.requested_by} /> for ticket #{r.ticket_id}</div>
              <p className="request__reason">{r.reason}</p>
              <Impact r={r} checking={checking} />
              {working && (
                <div className="request__status" role="status">
                  <LoaderCircle size={14} className="spin" aria-hidden="true" />
                  {busy.intent === "reject" ? "Rejecting…" : r.kind === "price_override" ? "Approving…" : `Paying ${money(r.amount)}…`}
                </div>
              )}
              <SubmitButtons r={r} nameOk={nameOk} />
            </motion.form>
          );
        })}
      </AnimatePresence>

      {others.length > 0 && (
        <div className="approvals__others">
          <div className="approvals__others-head">{mine.length ? "Other tickets" : "On other tickets"}</div>
          {others.map((r) => (
            <button key={r.id} className="request-mini" onClick={() => r.ticket_id && onSelectTicket(r.ticket_id)}>
              <span>{REQUEST_KINDS[r.kind] ?? r.kind} · #{r.ticket_id}</span>
              <b>{money(r.amount)}{r.kind === "price_override" ? "/unit" : ""}</b>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
