import type { MatchEvent, Meta, Trigger } from "../types";

type Names = Map<string, string>;

const SHOWN = new Set([
  "kickoff", "shot", "goal", "save", "block", "foul", "substitution", "half_time", "full_time", "interception", "tackle",
]);

function describe(ev: MatchEvent, names: Names, meta: Meta): string | null {
  const who = (id: unknown) => names.get(String(id)) ?? "";
  const score = (s: unknown) => {
    const sc = s as { HOME: number; AWAY: number };
    return `${meta.teams.HOME.short} ${sc.HOME}-${sc.AWAY} ${meta.teams.AWAY.short}`;
  };
  switch (ev.type) {
    case "kickoff":
      return `Kickoff, ${meta.teams[ev.team!].name}`;
    case "goal":
      return `GOAL! ${who(ev.player)}${ev.assist ? `, assisted by ${who(ev.assist)}` : ""}. ${score(ev.score)}`;
    case "shot": {
      if (ev.outcome === "goal") return null;
      const xg = (ev.stats as { xg?: number } | undefined)?.xg;
      const out = { saved: "saved", blocked: "blocked", off_target: "off target" }[String(ev.outcome)];
      return `${who(ev.player)} shoots from ${Math.round(Number(ev.distance_m))} m, ${out}${xg !== undefined ? ` (${xg.toFixed(2)} xG)` : ""}`;
    }
    case "save":
      return null;
    case "block":
      return null;
    case "tackle":
      return ev.outcome === "won" ? `${who(ev.player)} wins the ball from ${who(ev.on)}` : null;
    case "interception":
      return null;
    case "foul":
      return `Foul by ${who(ev.player)} on ${who(ev.on)}${ev.card ? ", yellow card" : ""}`;
    case "substitution":
      return `Substitution: ${who(ev.player_in)} on for ${who(ev.player_out)}`;
    case "half_time":
      return `Half time. ${score(ev.score)}`;
    case "full_time":
      return `Full time. ${score(ev.score)}`;
    default:
      return null;
  }
}

interface Item {
  key: string;
  clock: string;
  text: string;
  kind: string;
  side?: string;
}

export function EventFeed({ meta, events, triggers }: { meta: Meta; events: MatchEvent[]; triggers: Trigger[] }) {
  const names: Names = new Map(
    (["HOME", "AWAY"] as const).flatMap((s) => meta.teams[s].players.map((p) => [p.id, p.name] as const)),
  );
  const items: (Item & { t: number })[] = [];
  for (const ev of events) {
    if (!SHOWN.has(ev.type)) continue;
    const text = describe(ev, names, meta);
    if (text) items.push({ key: ev.id, t: ev.t, clock: ev.clock, text, kind: ev.type, side: ev.team });
  }
  for (const tr of triggers) {
    if (tr.kind === "goal") continue; // the goal event already says it
    items.push({ key: tr.id, t: tr.t + 0.01, clock: tr.clock, text: tr.label, kind: "trigger", side: tr.team ?? undefined });
  }
  items.sort((a, b) => b.t - a.t);
  return (
    <div className="panel feed">
      <h3>Match feed</h3>
      <ol>
        {items.slice(0, 40).map((it) => (
          <li key={it.key} className={`item ${it.kind}`}>
            <span className="t">{it.clock}</span>
            <span
              className="side"
              style={{ background: it.side ? meta.teams[it.side as "HOME" | "AWAY"].colors[0] : "transparent" }}
            />
            <span className="text">{it.text}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
