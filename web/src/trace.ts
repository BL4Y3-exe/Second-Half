import type { Overlay, TraceStep, Trigger } from "./types";

export const AGENTS: Record<string, string> = {
  spotter: "Spotter",
  analyst: "Analyst",
  storyteller: "Storyteller",
  fact_checker: "Fact-checker",
  director: "Director",
  persona: "Persona",
  recap: "Recap",
  test: "Demo test",
};

/** One flagged (or passed-over) moment and every handoff the agents made on it. */
export interface Moment {
  id: string;
  t: number;
  clock: string;
  label: string;
  steps: TraceStep[];
  overlay?: Overlay; // what went on air, if anything
  trigger?: Trigger; // the stats trigger behind it, while the page still holds it
}

export function groupMoments(trace: TraceStep[], overlays: Overlay[], triggers: Trigger[]): Moment[] {
  const byId = new Map<string, Moment>();
  for (const step of trace) {
    let m = byId.get(step.moment_id);
    if (!m) {
      m = { id: step.moment_id, t: step.t, clock: step.clock, label: step.summary, steps: [] };
      byId.set(step.moment_id, m);
    }
    m.steps.push(step);
  }
  const aired = new Map(overlays.map((o) => [o.moment_id, o]));
  const fired = new Map(triggers.map((tr) => [tr.id, tr]));
  for (const m of byId.values()) {
    m.overlay = aired.get(m.id);
    m.trigger = fired.get(m.id);
  }
  return [...byId.values()].sort((a, b) => a.t - b.t);
}

export const caught = (s: TraceStep) => s.agent === "fact_checker" && s.status === "rejected";

export type OutcomeClass = "ok" | "rejected" | "fallback" | "skipped" | "pending";

export function outcome(m: Moment): { text: string; cls: OutcomeClass } {
  const last = m.steps[m.steps.length - 1];
  if (m.steps[0].action === "passed over") return { text: "passed over", cls: "skipped" };
  const dropped = m.steps.find((s) => s.action === "dropped");
  if (dropped) return { text: dropped.summary.startsWith("too late") ? "too late" : "held back", cls: "skipped" };
  if (m.steps.some((s) => s.status === "fallback")) return { text: "stat card", cls: "fallback" };
  const scripted = m.steps.some((s) => s.agent === "recap" && s.action === "no answer");
  if (scripted) return { text: "scripted line", cls: "fallback" };
  if (m.steps.some((s) => s.agent === "test")) return { text: "planted & caught", cls: "rejected" };
  if (m.steps.some(caught)) return { text: "caught & fixed", cls: "rejected" };
  if (last.agent === "persona" || last.action === "scheduled") return { text: "on air", cls: "ok" };
  return { text: "working…", cls: "pending" };
}

/** The running totals for the whole match: [label, count, class]. */
export function totals(trace: TraceStep[], moments: Moment[]): [string, number, string][] {
  const count = (pred: (s: TraceStep) => boolean) => trace.filter(pred).length;
  const firstTime = moments.filter((m) => m.steps.find((s) => s.agent === "fact_checker")?.status === "ok").length;
  const out: [string, number, string][] = [
    ["moments", count((s) => s.action === "flagged"), ""],
    ["approved first time", firstTime, "ok"],
    ["wrong numbers caught", count(caught), "rejected"],
    ["stat-card fallbacks", count((s) => s.status === "fallback"), "fallback"],
    ["held back", count((s) => s.status === "skipped"), "skipped"],
  ];
  const planted = count((s) => s.status === "planted");
  if (planted > 0) out.push(["planted by the demo switch", planted, "planted"]);
  return out;
}

export function duration(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)} s`;
  return ms >= 1 ? `${Math.round(ms)} ms` : "<1 ms";
}

/** "says 25 m, but match data has 16 m (distance_m)" → ["25 m", "16 m"], for each problem in a rejection. */
export function mismatches(step: TraceStep): [string, string][] {
  const problems = (step.detail.problems as string[] | undefined) ?? step.summary.split("; ");
  const out: [string, string][] = [];
  for (const p of problems) {
    const m = /says (.+?), but match data has (.+?)(?: \(|$)/.exec(p);
    if (m) out.push([m[1], m[2]]);
  }
  return out;
}

/** A few words on what one step did, for the strip under the Living Room screen. */
export function gist(step: TraceStep): string {
  const { agent, action, summary, detail } = step;
  if (agent === "spotter") return action === "flagged" ? "flagged it" : action;
  if (agent === "analyst") {
    const calls = (detail.tool_calls as string[] | undefined)?.length;
    const numbers = /(\d+) numbers/.exec(summary)?.[1];
    return calls && numbers ? `${calls} tools · ${numbers} numbers` : summary;
  }
  if (agent === "storyteller") {
    if (action === "drafted") return "draft 1";
    const n = /\((\d+)\)/.exec(action)?.[1];
    return n ? `draft ${n}` : action;
  }
  if (agent === "test") return `planted ${String(detail.now ?? "")}`.trim();
  if (agent === "fact_checker") {
    if (step.status === "rejected") return "sent it back";
    const n = (detail.checked as string[] | undefined)?.length ?? /(\d+)/.exec(summary)?.[1];
    return n ? `all ${n} match` : "approved";
  }
  if (agent === "director") {
    if (action === "scheduled") {
      const card = summary.split(" in the ")[0];
      const arrows = /(\d+) arrows?/.exec(summary)?.[0];
      return arrows ? `${card} · ${arrows}` : card;
    }
    return action;
  }
  if (agent === "persona") {
    const m = /(\d+) viewer modes in (.+?)(?:;|$)/.exec(summary);
    return m ? `${Number(m[1]) * m[2].split(",").length} versions` : action;
  }
  return action;
}
