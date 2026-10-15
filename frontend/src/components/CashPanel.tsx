import { CalendarClock, Landmark, Receipt, TriangleAlert, Wallet } from "lucide-react";
import { animate, AnimatePresence, motion, useMotionValue, useTransform } from "motion/react";
import { useEffect } from "react";
import { money, shortDate } from "../format";
import type { BalanceChange } from "../hooks/useDesk";
import type { CashPosition } from "../types";

interface Props {
  cash: CashPosition | null;
  lastChange: BalanceChange | null;
}

/** After a payment the balance counts down from the old figure and lands exactly on the new one. */
function Balance({ value }: { value: number }) {
  const shown = useMotionValue(value);
  const text = useTransform(shown, (v) => money(v));
  useEffect(() => {
    const controls = animate(shown, value, { duration: 0.9, ease: [0.2, 0.8, 0.2, 1] });
    return () => controls.stop();
  }, [shown, value]);
  return <motion.span className="cash__balance" aria-live="polite">{text}</motion.span>;
}

export function CashPanel({ cash, lastChange }: Props) {
  if (!cash) {
    return (
      <section className="panel cash">
        <div className="panel__title">Checking account</div>
        <div className="skeleton" />
      </section>
    );
  }

  const balance = cash.checking_balance ?? 0;
  const after = cash.cash_after_all_obligations;
  const scale = Math.max(balance, cash.total_obligations, 1);
  const owedPct = Math.min(100, (cash.total_obligations / scale) * 100);
  const tight = after < 500;

  return (
    <section className="panel cash" aria-labelledby="cash-title">
      <div className="panel__title" id="cash-title"><span className="title-icon"><Wallet size={15} aria-hidden="true" />Checking account</span></div>
      <Balance value={balance} />
      <div className="cash__asof">Balance as of {shortDate(cash.as_of)} · desk date {shortDate(cash.date_today)}</div>

      <AnimatePresence mode="popLayout">
        {lastChange && (
          <motion.div
            key={`${lastChange.before}-${lastChange.after}`}
            className="cash__change"
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0 }}
          >
            <span className="cash__change-label">{lastChange.label}</span>
            <span className="cash__change-row">
              <span>{money(lastChange.before)} → <b>{money(lastChange.after)}</b></span>
              <span className="cash__delta">−{money(lastChange.before - lastChange.after)}</span>
            </span>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="cash__bar" role="img" aria-label={`Owed ${money(cash.total_obligations)} of ${money(balance)}`}>
        <motion.span className="cash__bar-owed" initial={false} animate={{ width: `${owedPct}%` }} transition={{ duration: 0.8, ease: "easeInOut" }} />
      </div>
      <div className="cash__bar-legend">
        <span><i className="sw sw--owed" />Owed {money(cash.total_obligations)}</span>
        <span><i className="sw sw--free" />Left {money(after)}</span>
      </div>

      <div className="ledger">
        <div className="ledger__head">Owed &amp; coming due</div>
        {cash.unpaid_invoices.length === 0 && cash.rent_due_within_window.length === 0 && (
          <div className="ledger__empty">Nothing owed in the next 30 days.</div>
        )}
        <AnimatePresence initial={false}>
          {cash.unpaid_invoices.map((inv) => (
            <motion.div layout className="ledger__row" key={`inv-${inv.id}`} exit={{ opacity: 0, height: 0 }}>
              <span className="ledger__icon"><Receipt size={15} aria-hidden="true" /></span>
              <div className="ledger__main">
                <div className="ledger__what">Invoice {inv.id} · {inv.vendor_name}</div>
                <div className="ledger__sub">
                  {inv.description} ·{" "}
                  {inv.days_overdue > 0
                    ? <span className="flag flag--late">{inv.days_overdue} days overdue</span>
                    : <>due {shortDate(inv.due_date)}</>}
                </div>
              </div>
              <div className="ledger__amt">{money(inv.amount)}</div>
            </motion.div>
          ))}
          {cash.rent_due_within_window.map((l) => (
            <motion.div layout className="ledger__row" key={`rent-${l.id}`} exit={{ opacity: 0, height: 0 }}>
              <span className="ledger__icon"><Landmark size={15} aria-hidden="true" /></span>
              <div className="ledger__main">
                <div className="ledger__what">Rent · {l.space_name}</div>
                <div className="ledger__sub">
                  {l.landlord} · <span className={`flag ${l.days_until_due <= 3 ? "flag--soon" : ""}`}>
                    <CalendarClock size={11} aria-hidden="true" /> due {shortDate(l.next_due)}
                    {l.days_until_due >= 0 ? ` (in ${l.days_until_due} days)` : ""}
                  </span>
                </div>
              </div>
              <div className="ledger__amt">{money(l.monthly_rent)}</div>
            </motion.div>
          ))}
        </AnimatePresence>
        <div className={`ledger__total${tight ? " ledger__total--tight" : ""}`}>
          <span>If everything is paid</span>
          <b>{money(after)}</b>
        </div>
        {tight && <div className="ledger__note"><TriangleAlert size={13} aria-hidden="true" />Cash is tight. Every approval counts.</div>}
      </div>
    </section>
  );
}
