import { ArrowRight, CircleCheck, CircleX, Flag, Sparkles, TriangleAlert, Wrench } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useDeferredValue, useEffect, useRef, useState } from "react";
import { AGENTS, AgentAvatar, AgentGlyph, AgentTag } from "../agents";
import type { FeedItem } from "../feed";
import { clockTime } from "../format";

type Filter = "all" | "handoffs" | "tools" | "thinking";
const FILTERS: { key: Filter; label: string; match: (k: FeedItem["kind"]) => boolean }[] = [
  { key: "all", label: "Everything", match: () => true },
  { key: "handoffs", label: "Hand-offs", match: (k) => k === "handoff" || k === "handback" },
  { key: "tools", label: "MCP tools", match: (k) => k === "tool" },
  { key: "thinking", label: "Thinking", match: (k) => k === "thinking" },
];

interface Props {
  items: FeedItem[];
  running: boolean;
  emptyText: string;
}

const enter = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.22, ease: "easeOut" as const },
};

function Handoff({ it }: { it: FeedItem }) {
  const from = it.agent ? AGENTS[it.agent] : null;
  const to = it.to ? AGENTS[it.to] : null;
  const back = it.kind === "handback";
  return (
    <div className={`handoff${back ? " handoff--back" : ""}`} style={{ ["--from" as string]: from?.color, ["--to" as string]: to?.color }}>
      <div className="handoff__agents">
        {it.agent && <AgentAvatar name={it.agent} size={30} />}
        <span className="handoff__arrow" aria-hidden="true"><ArrowRight size={18} /></span>
        {it.to && <AgentAvatar name={it.to} size={30} />}
      </div>
      <div className="handoff__body">
        <div className="handoff__title">
          <span className="handoff__label">{back ? "Reported back" : "Hand-off"}</span>
          <span style={{ color: from?.color }}>{from?.title}</span>
          <ArrowRight size={13} className="muted" aria-hidden="true" />
          <span style={{ color: to?.color }}>{to?.title}</span>
          <time className="feed__time">{clockTime(it.at)}</time>
        </div>
        {it.detail && <p className="handoff__task">{it.detail}</p>}
      </div>
    </div>
  );
}

function Row({ it, running }: { it: FeedItem; running: boolean }) {
  const time = <time className="feed__time">{clockTime(it.at)}</time>;
  if (it.kind === "handoff" || it.kind === "handback") return <Handoff it={it} />;
  if (it.kind === "start" || it.kind === "end") {
    const bad = it.kind === "end" && it.ok === false;
    return (
      <div className={`milestone milestone--${it.kind}${bad ? " is-bad" : ""}`}>
        {it.kind === "start" ? <Flag size={15} aria-hidden="true" /> : bad ? <CircleX size={16} aria-hidden="true" /> : <CircleCheck size={16} aria-hidden="true" />}
        <b>{it.title}</b>
        {it.detail && <span className="muted">· {it.detail}</span>}
        {time}
      </div>
    );
  }
  if (it.kind === "warn") {
    return (
      <div className="milestone milestone--warn">
        <TriangleAlert size={16} aria-hidden="true" />
        <AgentTag name={it.agent} /> {it.title}{time}
        {it.detail && <p className="feed__detail">{it.detail}</p>}
      </div>
    );
  }
  const a = it.agent ? AGENTS[it.agent] : null;
  return (
    <div className={`step step--${it.kind}`} style={{ ["--agent" as string]: a?.color ?? "var(--ink-2)" }}>
      <span className="step__glyph">{it.agent ? <AgentGlyph name={it.agent} size={14} /> : <Sparkles size={14} />}</span>
      <div className="step__body">
        <div className="step__line">
          <b style={{ color: a?.color }}>{a?.title ?? "Desk"}</b> {it.title}
          {it.kind === "tool" && it.tool && <code className="tool"><Wrench size={11} aria-hidden="true" />{it.tool}</code>}
          {it.kind === "tool" && it.ok === true && <CircleCheck size={15} className="ok" aria-label="Succeeded" />}
          {it.kind === "tool" && it.ok === false && <span className="bad">refused</span>}
          {it.kind === "tool" && it.ok === null && running && <span className="spinner spinner--xs" />}
          {time}
        </div>
        {it.detail && <p className={`feed__detail${it.kind === "thinking" ? " feed__detail--quote" : ""}`}>{it.detail}</p>}
      </div>
    </div>
  );
}

export function ActivityFeed({ items, running, emptyText }: Props) {
  const [filter, setFilter] = useState<Filter>("all");
  // While a run streams in, keep typing/clicking responsive: React renders the
  // newest list when it has a moment, not on every single event.
  const deferred = useDeferredValue(items);
  const end = useRef<HTMLLIElement>(null);
  const active = FILTERS.find((f) => f.key === filter)!;
  const shown = deferred.filter((it) => active.match(it.kind));

  useEffect(() => {
    if (running) end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [shown.length, running]);

  return (
    <>
      <div className="seg" role="tablist" aria-label="Filter activity">
        {FILTERS.map((f) => {
          const count = f.key === "all" ? deferred.length : deferred.filter((it) => f.match(it.kind)).length;
          return (
            <button key={f.key} role="tab" aria-selected={filter === f.key} className="seg__btn" onClick={() => setFilter(f.key)}>
              {filter === f.key && <motion.span layoutId="seg-pill" className="seg__pill" transition={{ type: "spring", stiffness: 500, damping: 38 }} />}
              <span className="seg__text">{f.label}<span className="seg__count">{count}</span></span>
            </button>
          );
        })}
      </div>

      {items.length === 0 ? (
        <div className="feed feed--empty">
          <Sparkles size={22} aria-hidden="true" />
          <span>{emptyText}</span>
        </div>
      ) : (
        <ol className="feed" aria-live="polite">
          <AnimatePresence initial={false}>
            {shown.map((it) => (
              <motion.li
                key={it.id}
                layout="position"
                className={`feed__item feed__item--${it.kind}`}
                style={{ ["--depth" as string]: it.depth ?? 0 }}
                {...enter}
              >
                <Row it={it} running={running} />
              </motion.li>
            ))}
          </AnimatePresence>
          <li ref={end} className="feed__end" aria-hidden="true" />
        </ol>
      )}
    </>
  );
}
