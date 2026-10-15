import { Landmark, ShoppingBag, Tag, type LucideIcon } from "lucide-react";
import { LayoutGroup, motion } from "motion/react";
import { LIFECYCLE, lifecycleStep, TICKET_TYPES } from "../format";
import type { Ticket } from "../types";
import { StatePill, StatusChip } from "./StatusPill";

export const TYPE_ICONS: Record<string, LucideIcon> = {
  customer_order: ShoppingBag,
  rent_notice: Landmark,
  price_override: Tag,
};

interface Props {
  tickets: Ticket[];
  selectedId: number | null;
  runningId: number | null;
  onSelect: (id: number) => void;
}

function Lifecycle({ step, waiting }: { step: number; waiting: boolean }) {
  return (
    <div className="lifecycle" aria-label={`Stage: ${LIFECYCLE[step]}`}>
      {LIFECYCLE.map((label, i) => (
        <div
          key={label}
          className={`lifecycle__step${i < step ? " is-past" : ""}${i === step ? " is-now" : ""}${i === step && waiting ? " is-waiting" : ""}`}
          title={label}
        >
          <span className="lifecycle__dot" />
          <span className="lifecycle__label">{label}</span>
        </div>
      ))}
    </div>
  );
}

export function TicketList({ tickets, selectedId, runningId, onSelect }: Props) {
  const open = tickets.filter((t) => t.state === "open").length;
  return (
    <nav className="panel tickets" aria-label="Tickets">
      <div className="panel__title">
        Tickets
        <span className="panel__count">{open} open · {tickets.length - open} resolved</span>
      </div>
      <LayoutGroup>
        <ul className="ticket-list">
          {tickets.length === 0 && [0, 1, 2].map((i) => <li key={i} className="skeleton skeleton--card" />)}
          {tickets.map((t) => {
            const pending = t.approval_requests.filter((r) => r.status === "pending").length;
            const Icon = TYPE_ICONS[t.type] ?? Tag;
            const selected = t.id === selectedId;
            const step = lifecycleStep(t.status, pending > 0);
            return (
              <li key={t.id}>
                <button
                  className={`ticket-card ticket-card--${t.state}${selected ? " is-selected" : ""}`}
                  onClick={() => onSelect(t.id)}
                  aria-current={selected ? "true" : undefined}
                >
                  {selected && (
                    <motion.span
                      layoutId="ticket-selection"
                      className="ticket-card__selection"
                      transition={{ type: "spring", stiffness: 420, damping: 34 }}
                    />
                  )}
                  <div className="ticket-card__top">
                    <span className="ticket-card__icon"><Icon size={16} aria-hidden="true" /></span>
                    <span className="ticket-card__id">#{t.id}</span>
                    <StatePill state={t.state} />
                  </div>
                  <div className="ticket-card__subject">{t.subject}</div>
                  <div className="ticket-card__meta">{TICKET_TYPES[t.type] ?? t.type} · {t.requester}</div>
                  <Lifecycle step={step} waiting={t.status.startsWith("waiting_on")} />
                  <div className="ticket-card__foot">
                    <StatusChip status={t.status} />
                    {runningId === t.id && <span className="running-tag"><span className="spinner" />Agents working</span>}
                    {pending > 0 && runningId !== t.id && <span className="approval-tag">{pending} awaiting you</span>}
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      </LayoutGroup>
    </nav>
  );
}
