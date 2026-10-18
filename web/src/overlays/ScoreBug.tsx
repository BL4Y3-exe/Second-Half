import type { Meta, Snapshot } from "../types";

export function ScoreBug({ meta, snapshot, clock }: { meta: Meta; snapshot: Snapshot | null; clock: string }) {
  const { HOME: home, AWAY: away } = meta.teams;
  const score = snapshot?.score ?? { HOME: 0, AWAY: 0 };
  return (
    <div className="scorebug">
      <span className="chip" style={{ background: home.colors[0], color: home.colors[1] }} />
      <span className="abbr">{home.short}</span>
      <span className="score">
        {score.HOME}<span className="dash">-</span>{score.AWAY}
      </span>
      <span className="abbr">{away.short}</span>
      <span className="chip" style={{ background: away.colors[0], color: away.colors[1] }} />
      <span className="clock">{clock}</span>
    </div>
  );
}
