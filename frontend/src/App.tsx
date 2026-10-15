import { Activity, Network, RotateCcw } from "lucide-react";
import { AnimatePresence, MotionConfig } from "motion/react";
import { ActivityFeed } from "./components/ActivityFeed";
import { Approvals } from "./components/Approvals";
import { CashPanel } from "./components/CashPanel";
import { Contributions } from "./components/Contributions";
import { Header } from "./components/Header";
import { StatePill } from "./components/StatusPill";
import { TeamGraph } from "./components/TeamGraph";
import { TicketDetail } from "./components/TicketDetail";
import { TicketList } from "./components/TicketList";
import { Toasts } from "./components/Toasts";
import { agentStates, buildFeed, contributions, delegationEdges } from "./feed";
import { useApprover, useDesk } from "./hooks/useDesk";
import type { DeskRunResult } from "./types";

export default function App() {
  const desk = useDesk();
  const [approver, setApprover] = useApprover();

  // React Compiler memoizes these derived values; no useMemo needed.
  const ticket = desk.tickets.find((t) => t.id === desk.selected) ?? null;
  const view = desk.selected != null ? desk.runs[desk.selected] : undefined;
  const events = view?.events ?? [];
  const feed = buildFeed(events);
  const states = agentStates(events);
  const edges = delegationEdges(events);
  const contrib = contributions(events);
  const finished = !!view && !view.running && events.some((e) => e.kind === "run_end");
  const usage = view?.result?.usage
    ?? (events.find((e) => e.kind === "run_end")?.details.usage as DeskRunResult["usage"] | undefined)
    ?? null;

  async function reset() {
    if (!approver.trim()) {
      desk.notify({ tone: "bad", title: "Who's resetting?", text: "Enter your name under Approvals first." });
      return;
    }
    if (window.confirm("Reset the working database to the original data? Payments, approvals and ticket progress will be undone. The audit trail is kept.")) {
      await desk.reset(approver);
    }
  }

  return (
    <MotionConfig reducedMotion="user">
      <Header
        dateToday={desk.health?.date_today ?? desk.cash?.date_today ?? null}
        model={desk.health?.model ?? null}
        connected={desk.connected}
        stats={{
          open: desk.tickets.filter((t) => t.state === "open").length,
          needsYou: desk.pending.length,
          resolved: desk.tickets.filter((t) => t.state === "resolved").length,
          checking: desk.cash?.checking_balance ?? null,
        }}
      />

      <main className="layout">
        <aside className="col col--left">
          <TicketList tickets={desk.tickets} selectedId={desk.selected} runningId={desk.runningId} onSelect={desk.setSelected} />
          <div className="legend">
            <div className="legend__title">Status key</div>
            <div><StatePill state="open" /> still being worked</div>
            <div><StatePill state="resolved" /> nothing left to do</div>
            <div><span className="chip chip--attention">Needs your approval</span> waiting on you</div>
            <div><span className="chip chip--waiting">Waiting on vendor</span> waiting on someone else</div>
          </div>
        </aside>

        <div className="col col--main">
          {ticket ? (
            <TicketDetail
              ticket={ticket}
              running={desk.runningId === ticket.id}
              startedAt={view?.startedAt ?? null}
              otherRunning={desk.runningId !== null && desk.runningId !== ticket.id}
              onRun={() => desk.runTicket(ticket.id)}
            />
          ) : (
            <section className="panel"><div className="skeleton" /></section>
          )}

          <section className="panel" aria-labelledby="team-title">
            <div className="panel__title" id="team-title">
              <span className="title-icon"><Network size={15} aria-hidden="true" />The agent team</span>
              {view?.running && <span className="panel__count panel__count--live"><span className="live-dot" />Live</span>}
              {!view?.running && edges.length > 0 && <span className="panel__count">{edges.length} hand-offs</span>}
            </div>
            <TeamGraph states={states} edges={edges} />
          </section>

          <AnimatePresence>
            {finished && contrib.agents.length > 0 && (
              <Contributions key={view?.result?.run_id ?? events[0]?.run_id} agents={contrib.agents} outcome={contrib.outcome} usage={usage} />
            )}
          </AnimatePresence>

          <section className="panel" aria-labelledby="feed-title">
            <div className="panel__title" id="feed-title">
              <span className="title-icon"><Activity size={15} aria-hidden="true" />{view?.running ? "Live activity" : "Agent activity"}</span>
              {!view?.live && events.length > 0 && <span className="panel__count">Last run</span>}
            </div>
            <ActivityFeed
              items={feed}
              running={!!view?.running}
              emptyText={view?.running ? "Starting the desk…" : "No runs yet for this ticket. Press “Run the agent team” to watch the agents work."}
            />
            {view?.error && <div className="error-box">{view.error}</div>}
          </section>
        </div>

        <aside className="col col--right">
          <CashPanel cash={desk.cash} lastChange={desk.lastChange} />
          <Approvals
            requests={desk.pending}
            selectedTicket={desk.selected}
            checking={desk.cash?.checking_balance ?? null}
            approver={approver}
            onApproverChange={setApprover}
            onApprove={(r) => desk.approve(r, approver)}
            onReject={(r) => desk.reject(r, approver)}
            onSelectTicket={desk.setSelected}
          />
          <section className="panel reset">
            <div className="panel__title"><span className="title-icon"><RotateCcw size={15} aria-hidden="true" />Practice mode</span></div>
            <p className="muted small">Start over from the original Campus Customs data. The audit trail is kept.</p>
            <button className="btn btn--ghost btn--block" onClick={reset} disabled={desk.runningId !== null}>
              <RotateCcw size={15} aria-hidden="true" />Reset working database
            </button>
          </section>
        </aside>
      </main>

      <Toasts toasts={desk.toasts} onDismiss={desk.dismiss} />
    </MotionConfig>
  );
}
