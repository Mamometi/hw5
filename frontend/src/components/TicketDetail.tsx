import { CircleCheck, Hash, LoaderCircle, Play, ScrollText } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { AgentTag } from "../agents";
import { TICKET_TYPES } from "../format";
import { useElapsed } from "../hooks/useDesk";
import type { Ticket } from "../types";
import { StatePill, StatusChip } from "./StatusPill";
import { TYPE_ICONS } from "./TicketList";

interface Props {
  ticket: Ticket;
  running: boolean;
  startedAt: number | null;
  otherRunning: boolean;
  onRun: () => void;
}

const AGENT_KEYS = ["boss", "inventory", "accounting", "facilities", "customer_service"];

/** Ticket notes start with the request; agents and people append "[date who] text" lines. */
function parseNotes(notes: string | null) {
  const lines = (notes ?? "").split("\n").filter(Boolean);
  const request = lines[0] && !lines[0].startsWith("[") ? lines[0] : "";
  const log = lines
    .slice(request ? 1 : 0)
    .map((l) => /^\[(\S+) ([^\]]+)\] (.*)$/.exec(l))
    .filter((m): m is RegExpExecArray => !!m)
    .map((m) => ({ date: m[1], who: m[2], text: m[3] }));
  return { request, log };
}

const clock = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

export function TicketDetail({ ticket, running, startedAt, otherRunning, onRun }: Props) {
  const { request, log } = parseNotes(ticket.notes);
  const elapsed = useElapsed(startedAt, running);
  const Icon = TYPE_ICONS[ticket.type] ?? Hash;

  const facts: [string, string][] = [];
  if (ticket.sku) facts.push(["Item", `${ticket.qty ?? "?"} × ${ticket.sku} · size ${ticket.size}`]);
  if (ticket.invoice_id) facts.push(["Linked invoice", `#${ticket.invoice_id}`]);
  if (ticket.lease_id) facts.push(["Linked lease", `#${ticket.lease_id}`]);
  facts.push(["Received", new Date(ticket.created_at).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })]);

  const closed = ticket.state === "resolved";
  const disabled = running || otherRunning || closed;

  return (
    <motion.section
      key={ticket.id}
      className="panel detail"
      aria-labelledby="detail-title"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
    >
      <AnimatePresence>
        {running && (
          <motion.div className="detail__progress" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
        )}
      </AnimatePresence>

      <div className="detail__head">
        <span className="detail__icon"><Icon size={26} strokeWidth={1.7} aria-hidden="true" /></span>
        <div className="detail__titles">
          <div className="detail__eyebrow">Ticket #{ticket.id} · {TICKET_TYPES[ticket.type] ?? ticket.type}</div>
          <h1 className="detail__title" id="detail-title">{ticket.subject}</h1>
          <div className="detail__from">from <b>{ticket.requester}</b></div>
        </div>
        <div className="detail__status">
          <StatePill state={ticket.state} />
          <StatusChip status={ticket.status} />
        </div>
      </div>

      {request && <blockquote className="detail__request">“{request}”</blockquote>}

      <dl className="facts">
        {facts.map(([k, v]) => (
          <div className="facts__item" key={k}><dt>{k}</dt><dd>{v}</dd></div>
        ))}
      </dl>

      <div className="detail__actions">
        <motion.button
          className="btn btn--primary btn--lg btn--run"
          onClick={onRun}
          disabled={disabled}
          whileHover={disabled ? undefined : { y: -1 }}
          whileTap={disabled ? undefined : { scale: 0.98 }}
        >
          {running ? <LoaderCircle size={18} className="spin" aria-hidden="true" />
            : closed ? <CircleCheck size={18} aria-hidden="true" />
              : <Play size={16} fill="currentColor" aria-hidden="true" />}
          {running ? <>Agents working · <span className="tabular">{clock(elapsed)}</span></> : closed ? "Ticket resolved" : "Run the agent team"}
        </motion.button>
        <span className="detail__hint">
          {otherRunning && !running
            ? "Another ticket is being worked. One run at a time."
            : closed
              ? "Nothing left to do on this ticket."
              : running
                ? "Watch the team below. Hand-offs light up as they happen."
                : "The Boss reads the ticket and hands it to the right specialist."}
        </span>
      </div>

      {log.length > 0 && (
        <details className="ticket-log">
          <summary><ScrollText size={15} aria-hidden="true" />Ticket log · {log.length} {log.length === 1 ? "entry" : "entries"}</summary>
          <ol>
            {log.map((l, i) => (
              <li key={i}>
                <AgentTag name={l.who} />
                {!AGENT_KEYS.includes(l.who) && <span className="ticket-log__who">{l.who}</span>}
                <span>{l.text}</span>
              </li>
            ))}
          </ol>
        </details>
      )}
    </motion.section>
  );
}
