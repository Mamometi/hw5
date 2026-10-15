// The agent team as an org chart. The Boss sits on top, the four specialists
// below. Every hand-off in the run is drawn as an edge in the receiving
// agent's color. An edge still waiting for a reply animates, with a dot
// travelling along it. On narrow screens it falls back to a simple list.
import { motion } from "motion/react";
import { useLayoutEffect, useRef, useState } from "react";
import { AGENTS, AgentAvatar } from "../agents";
import type { AgentState, DelegationEdge } from "../feed";
import type { AgentName } from "../types";

const SPECIALISTS: AgentName[] = ["customer_service", "inventory", "accounting", "facilities"];
const LABEL: Record<AgentState, string> = {
  idle: "Standing by",
  working: "Working",
  waiting: "Waiting on colleague",
  done: "Done",
};
const HEIGHT = 380;
const BOSS_Y = 64;
const ROW_Y = 250;

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, width] as const;
}

function Node({ name, state, x, y }: { name: AgentName; state: AgentState; x: number; y: number }) {
  const a = AGENTS[name];
  return (
    <motion.div
      className={`graph-node graph-node--${state}`}
      style={{ left: x, top: y, x: "-50%", y: "-50%", ["--agent" as string]: a.color, ["--agent-soft" as string]: a.soft }}
      animate={{ scale: state === "working" ? 1.04 : 1 }}
      transition={{ type: "spring", stiffness: 300, damping: 20 }}
    >
      <AgentAvatar name={name} size={40} pulse={state === "working"} />
      <div className="graph-node__name">{a.title}</div>
      <div className="graph-node__role">{a.role}</div>
      <div className={`graph-node__state graph-node__state--${state}`}><span className="graph-node__dot" />{LABEL[state]}</div>
    </motion.div>
  );
}

export function TeamGraph({ states, edges }: { states: Record<AgentName, AgentState>; edges: DelegationEdge[] }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const compact = width > 0 && width < 560;

  const pos: Record<AgentName, { x: number; y: number }> = {
    boss: { x: width / 2, y: BOSS_Y },
    ...Object.fromEntries(SPECIALISTS.map((n, i) => [n, { x: width * (0.125 + 0.25 * i), y: ROW_Y }])),
  } as Record<AgentName, { x: number; y: number }>;

  function path(from: AgentName, to: AgentName) {
    const a = pos[from];
    const b = pos[to];
    if (from === "boss" || to === "boss") {
      const top = from === "boss" ? a : b;
      const bottom = from === "boss" ? b : a;
      const y1 = top.y + 58;
      const y2 = bottom.y - 58;
      const mid = (y1 + y2) / 2;
      return `M ${top.x} ${y1} C ${top.x} ${mid}, ${bottom.x} ${mid}, ${bottom.x} ${y2}`;
    }
    // Specialist → specialist: an arc below the row, so it never crosses a card.
    const y = a.y + 58;
    const dip = y + 26 + Math.abs(b.x - a.x) * 0.06;
    return `M ${a.x} ${y} C ${a.x} ${dip}, ${b.x} ${dip}, ${b.x} ${y}`;
  }

  if (compact) {
    return (
      <div ref={ref} className="graph-list">
        {(["boss", ...SPECIALISTS] as AgentName[]).map((n) => (
          <div key={n} className={`graph-list__row graph-node--${states[n]}`} style={{ ["--agent" as string]: AGENTS[n].color }}>
            <AgentAvatar name={n} size={30} pulse={states[n] === "working"} />
            <b style={{ color: AGENTS[n].color }}>{AGENTS[n].title}</b>
            <span className={`graph-node__state graph-node__state--${states[n]}`}><span className="graph-node__dot" />{LABEL[states[n]]}</span>
          </div>
        ))}
      </div>
    );
  }

  // One drawn edge per agent pair; the latest hand-off between them decides its look.
  const byPair = new Map<string, DelegationEdge & { count: number }>();
  for (const e of edges) {
    const key = `${e.from}>${e.to}`;
    byPair.set(key, { ...e, count: (byPair.get(key)?.count ?? 0) + 1 });
  }

  return (
    <div ref={ref} className="graph" style={{ height: HEIGHT }}>
      {width > 0 && (
        <>
          <svg className="graph__edges" width={width} height={HEIGHT} aria-hidden="true">
            {/* The reporting lines: faint until used. */}
            {SPECIALISTS.map((n) => (
              <path key={n} d={path("boss", n)} className="edge edge--base" />
            ))}
            {[...byPair.values()].map((e) => {
              const d = path(e.from, e.to);
              const color = AGENTS[e.to].color;
              return (
                <g key={`${e.from}>${e.to}`}>
                  <motion.path
                    d={d}
                    className={`edge edge--${e.status}`}
                    stroke={color}
                    initial={{ pathLength: 0 }}
                    animate={{ pathLength: 1 }}
                    transition={{ duration: 0.7, ease: "easeInOut" }}
                  />
                  {e.status === "active" && (
                    <circle r="5" fill={color} className="edge__pulse">
                      <animateMotion dur="1.4s" repeatCount="indefinite" path={d} />
                    </circle>
                  )}
                </g>
              );
            })}
          </svg>
          <Node name="boss" state={states.boss} x={pos.boss.x} y={pos.boss.y} />
          {SPECIALISTS.map((n) => <Node key={n} name={n} state={states[n]} x={pos[n].x} y={pos[n].y} />)}
        </>
      )}
    </div>
  );
}
