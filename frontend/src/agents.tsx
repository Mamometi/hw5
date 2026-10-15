// Visual identity for each agent: a color from a collegiate palette, an
// emblem (Lucide icon), and a one-line role. Used everywhere an agent appears.
import { BookOpen, Landmark, MessageCircle, Package, ShieldCheck, type LucideIcon } from "lucide-react";
import type { AgentName } from "./types";

export interface AgentIdentity {
  name: AgentName;
  title: string;
  role: string;
  color: string; // strong color: avatar, borders, names
  soft: string; // tint: card backgrounds
}

export const AGENTS: Record<AgentName, AgentIdentity> = {
  boss: {
    name: "boss", title: "Boss", role: "Routes every ticket",
    color: "#00356B", soft: "#E6EDF5",
  },
  inventory: {
    name: "inventory", title: "Inventory", role: "Stock & shipping",
    color: "#3D6B35", soft: "#EAF1E7",
  },
  accounting: {
    name: "accounting", title: "Accounting", role: "Cash & pricing",
    color: "#8A6A1F", soft: "#F5EFE0",
  },
  facilities: {
    name: "facilities", title: "Facilities", role: "Lease & landlord",
    color: "#9B3B2B", soft: "#F6E9E6",
  },
  customer_service: {
    name: "customer_service", title: "Customer Service", role: "The requester's voice",
    color: "#5B4A86", soft: "#EEEAF5",
  },
};

export const AGENT_ORDER: AgentName[] = ["boss", "customer_service", "inventory", "accounting", "facilities"];

export function agentOf(name: string | null | undefined): AgentIdentity | null {
  return name && name in AGENTS ? AGENTS[name as AgentName] : null;
}

const GLYPHS: Record<AgentName, LucideIcon> = {
  boss: ShieldCheck,       // the desk lead's crest
  inventory: Package,      // goods on shelves
  accounting: BookOpen,    // the ledger
  facilities: Landmark,    // the building
  customer_service: MessageCircle, // the requester's voice
};

export function AgentGlyph({ name, size = 18 }: { name: AgentName; size?: number }) {
  const Icon = GLYPHS[name];
  return <Icon size={size} strokeWidth={1.9} aria-hidden="true" />;
}

export function AgentAvatar({ name, size = 34, pulse = false }: { name: AgentName; size?: number; pulse?: boolean }) {
  const a = AGENTS[name];
  return (
    <span
      className={`avatar${pulse ? " avatar--pulse" : ""}`}
      style={{ width: size, height: size, background: a.color, ["--agent" as string]: a.color }}
      title={a.title}
    >
      <AgentGlyph name={name} size={Math.round(size * 0.56)} />
    </span>
  );
}

export function AgentTag({ name }: { name: string | null | undefined }) {
  const a = agentOf(name);
  if (!a) return <span className="agent-tag agent-tag--system">System</span>;
  return (
    <span className="agent-tag" style={{ color: a.color, background: a.soft }}>
      <AgentGlyph name={a.name} size={13} />
      {a.title}
    </span>
  );
}
