import { ArrowRight, Hand, ListChecks, MessageSquareQuote, Wrench } from "lucide-react";
import { motion } from "motion/react";
import { AGENTS, AgentAvatar, AgentTag } from "../agents";
import type { AgentContribution } from "../feed";
import { money, REQUEST_KINDS, TOOL_PHRASES } from "../format";
import type { TicketOutcome } from "../types";
import { StatusChip } from "./StatusPill";

interface Props {
  agents: AgentContribution[];
  outcome: TicketOutcome | null;
  usage: { total_tokens: number; by_agent: Record<string, { tool_calls: number }> } | null;
}

const clip = (s: string, n = 150) => (s.length > n ? `${s.slice(0, n).trimEnd()}…` : s);

export function Contributions({ agents, outcome, usage }: Props) {
  const specialists = agents.filter((a) => a.agent !== "boss");
  const boss = agents.find((a) => a.agent === "boss");
  return (
    <motion.section
      className="panel contributions"
      aria-labelledby="contrib-title"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
    >
      <div className="panel__title" id="contrib-title">
        What each agent contributed
        {usage && <span className="panel__count">{usage.total_tokens.toLocaleString()} tokens</span>}
      </div>

      {outcome && (
        <div className="outcome">
          <div className="outcome__head">
            <span className="outcome__label">Outcome</span>
            <StatusChip status={outcome.status_after} />
          </div>
          <p className="outcome__summary">{outcome.summary}</p>
          {boss && boss.handoffsOut.length > 0 && (
            <div className="outcome__route">
              <AgentAvatar name="boss" size={22} />
              <span>The Boss assigned this to</span>
              {boss.handoffsOut.map((h, i) => <AgentTag key={i} name={h.to} />)}
            </div>
          )}
        </div>
      )}

      <motion.div
        className="contrib-grid"
        initial="hidden"
        animate="shown"
        variants={{ shown: { transition: { staggerChildren: 0.08 } } }}
      >
        {specialists.map((c) => {
          const a = AGENTS[c.agent];
          return (
            <motion.article
              key={c.agent}
              className="contrib"
              style={{ ["--agent" as string]: a.color, ["--agent-soft" as string]: a.soft }}
              variants={{ hidden: { opacity: 0, y: 10 }, shown: { opacity: 1, y: 0 } }}
            >
              <header className="contrib__head">
                <AgentAvatar name={c.agent} size={36} />
                <div>
                  <div className="contrib__name">{a.title}</div>
                  <div className="contrib__by">
                    {c.askedBy ? <>Brought in by <b>{AGENTS[c.askedBy].title}</b></> : <b>Lead</b>}
                    {usage?.by_agent[c.agent] && <> · {usage.by_agent[c.agent].tool_calls} tool calls</>}
                  </div>
                </div>
              </header>
              <p className="contrib__summary">{c.summary}</p>

              {c.actions.length > 0 && (
                <>
                  <div className="contrib__sub"><ListChecks size={13} aria-hidden="true" />Did</div>
                  <ul className="contrib__list">{c.actions.map((x, i) => <li key={i}>{x}</li>)}</ul>
                </>
              )}
              {c.handoffsOut.length > 0 && (
                <>
                  <div className="contrib__sub"><ArrowRight size={13} aria-hidden="true" />Handed off</div>
                  <ul className="contrib__list contrib__list--plain">
                    {c.handoffsOut.map((h, i) => <li key={i}><AgentTag name={h.to} /> {clip(h.task)}</li>)}
                  </ul>
                </>
              )}
              {c.approvals.length > 0 && (
                <>
                  <div className="contrib__sub"><Hand size={13} aria-hidden="true" />Needs your decision</div>
                  <ul className="contrib__list">
                    {c.approvals.map((x, i) => (
                      <li key={i}>
                        <b>{REQUEST_KINDS[x.kind] ?? x.kind}{x.request_id ? ` #${x.request_id}` : ""}</b>
                        {x.amount != null && <> · {x.kind === "price_override" ? `${money(x.amount)}/unit` : money(x.amount)}</>}
                      </li>
                    ))}
                  </ul>
                </>
              )}
              {c.customerMessage && (
                <>
                  <div className="contrib__sub"><MessageSquareQuote size={13} aria-hidden="true" />Draft reply · not sent</div>
                  <blockquote className="contrib__quote">{c.customerMessage}</blockquote>
                </>
              )}
              {c.tools.length > 0 && (
                <div className="contrib__tools">
                  <Wrench size={12} aria-hidden="true" />
                  {c.tools.map((t) => <span key={t} className="tool-chip" title={TOOL_PHRASES[t] ?? t}>{t}</span>)}
                </div>
              )}
            </motion.article>
          );
        })}
      </motion.div>
    </motion.section>
  );
}
