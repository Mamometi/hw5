import { CalendarDays, Cpu, Hand, Inbox, CircleCheck, Wallet } from "lucide-react";
import { longDate, money } from "../format";

export function Crest({ size = 42 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden="true" className="crest">
      <path d="M20 2.5 5 7.5v11.2C5 28 11.4 35 20 37.5 28.6 35 35 28 35 18.7V7.5z" fill="#fff" />
      <path d="M20 5.2 7.6 9.3v9.4c0 7.7 5.2 13.6 12.4 16 7.2-2.4 12.4-8.3 12.4-16V9.3z" fill="#00356B" />
      <path d="M12.5 14.5h15M12.5 14.5v1.2M27.5 14.5v1.2" stroke="#fff" strokeWidth="1.2" />
      <text x="20" y="26.5" textAnchor="middle" fontFamily="Georgia, 'Times New Roman', serif" fontSize="10.5" fontWeight="700" fill="#fff" letterSpacing=".5">CC</text>
    </svg>
  );
}

interface Props {
  dateToday: string | null;
  model: string | null;
  connected: boolean | null;
  stats: { open: number; needsYou: number; resolved: number; checking: number | null };
}

export function Header({ dateToday, model, connected, stats }: Props) {
  return (
    <header className="masthead">
      <div className="masthead__inner">
        <div className="brand">
          <Crest />
          <div>
            <div className="brand__name">Campus Customs</div>
            <div className="brand__sub">Operations Desk · Chapel Street, New Haven</div>
          </div>
        </div>
        <div className="masthead__meta">
          <div className="meta-item">
            <CalendarDays size={16} aria-hidden="true" />
            <div><span className="meta-label">Desk date</span><span className="meta-value">{dateToday ? longDate(dateToday) : "—"}</span></div>
          </div>
          <div className="meta-item">
            <Cpu size={16} aria-hidden="true" />
            <div><span className="meta-label">Agent model</span><span className="meta-value">{model ?? "—"}</span></div>
          </div>
          <div className={`conn conn--${connected === null ? "unknown" : connected ? "up" : "down"}`} role="status">
            <span className="conn__dot" />
            {connected === null ? "Connecting…" : connected ? "Backend connected" : "Backend offline"}
          </div>
        </div>
      </div>
      <div className="statbar">
        <div className="statbar__inner">
          <div className="stat"><Inbox size={16} aria-hidden="true" /><b>{stats.open}</b> open</div>
          <div className={`stat${stats.needsYou ? " stat--hot" : ""}`}><Hand size={16} aria-hidden="true" /><b>{stats.needsYou}</b> waiting on you</div>
          <div className="stat"><CircleCheck size={16} aria-hidden="true" /><b>{stats.resolved}</b> resolved</div>
          <div className="stat stat--money"><Wallet size={16} aria-hidden="true" />Checking <b>{money(stats.checking)}</b></div>
        </div>
      </div>
    </header>
  );
}
