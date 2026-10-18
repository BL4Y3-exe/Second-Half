import { tr } from "../i18n";
import { BUILTIN } from "../plugins/registry";
import type { Lang, Meta, Mode, Overlay, Side } from "../types";
import type { OnAir } from "../useOverlaySchedule";

interface Props {
  onAir: Record<string, OnAir>;
  meta: Meta;
  mode: Mode;
  lang: Lang;
}

/** The viewer's version of an item: their language and mode, falling back to English analyst. */
export function textFor(ov: Overlay, lang: Lang, mode: Mode): string {
  return ov.text?.[lang]?.[mode] ?? ov.text?.en?.[mode] ?? ov.story;
}

function headline(ov: Overlay, lang: Lang): string {
  if (ov.fallback) return tr(lang, "stat");
  if (ov.kind === "goal") return tr(lang, "goal");
  if (ov.kind === "momentum_swing" && ov.data.team_short) return `${tr(lang, "momentum")} · ${ov.data.team_short}`;
  return tr(lang, ov.kind);
}

function LowerThird({ item, meta, mode, lang }: { item: OnAir; meta: Meta; mode: Mode; lang: Lang }) {
  const ov = item.overlay;
  const Plugin = BUILTIN[ov.plugin] ?? BUILTIN["stat-card"];
  const text = textFor(ov, lang, mode);
  const team = ov.team ? meta.teams[ov.team as Side] : null;
  return (
    <div
      className={`lower-third kind-${ov.kind}${ov.fallback ? " fallback" : ""}`}
      style={{ "--team": team?.colors[0] ?? "var(--accent)", "--dur": `${ov.duration_s}s` } as React.CSSProperties}
    >
      <div className="lt-head">
        <span className="lt-tag">{headline(ov, lang)}</span>
        <span className="lt-clock">{ov.clock}</span>
        <span className={`lt-check${ov.fallback ? " warn" : ""}`}>
          {ov.fallback ? tr(lang, "stat_card") : `✓ ${tr(lang, "fact_checked")}`}
        </span>
      </div>
      <div className="lt-body">
        <Plugin overlay={ov} text={text} meta={meta} lang={lang} />
      </div>
      {!ov.fallback && <p className="lt-text">{text}</p>}
      <div className="lt-timer" />
    </div>
  );
}

/** Puts whatever the schedule says is on air into its slot over the pitch. */
export function OverlayLayer({ onAir, meta, mode, lang }: Props) {
  const lower = onAir["lower-third"];
  const pitchItem = onAir["pitch"];
  const full = onAir["full-screen"];
  const PlayerTag = BUILTIN["player-tag"];
  return (
    <>
      {lower && (
        <div className="slot-lower-third" key={lower.overlay.id}>
          <LowerThird item={lower} meta={meta} mode={mode} lang={lang} />
        </div>
      )}
      {pitchItem && (
        <div className="slot-corner" key={pitchItem.overlay.id}>
          <PlayerTag overlay={pitchItem.overlay} text={textFor(pitchItem.overlay, lang, mode)} meta={meta} lang={lang} />
        </div>
      )}
      {full && (
        <div className="slot-full-screen" key={full.overlay.id}>
          {(() => {
            const Plugin = BUILTIN[full.overlay.plugin] ?? BUILTIN["recap-card"];
            return <Plugin overlay={full.overlay} text={textFor(full.overlay, lang, mode)} meta={meta} lang={lang} />;
          })()}
        </div>
      )}
    </>
  );
}
