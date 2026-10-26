import { useEffect, useRef } from "react";
import type { PluginProps } from "./builtin";

/**
 * An outside plugin. Its page runs in an iframe sandboxed to scripts only: no access to this page,
 * its storage or cookies, and the server's security policy blocks it from the network. It gets
 * the item's data by postMessage once it says it is ready, and can do nothing but draw it.
 */
export function Sandboxed({ overlay, text, meta, lang }: PluginProps) {
  const frame = useRef<HTMLIFrameElement>(null);
  const info = overlay.plugin_info!;

  useEffect(() => {
    const message = {
      type: "second-half/render",
      lang,
      text,
      overlay: { kind: overlay.kind, clock: overlay.clock, headline: overlay.headline, team: overlay.team, data: overlay.data },
      teams: Object.fromEntries(
        (["HOME", "AWAY"] as const).map((s) => [
          s,
          { name: meta.teams[s].name, short: meta.teams[s].short, color: meta.teams[s].colors[0] },
        ]),
      ),
    };
    const send = () => frame.current?.contentWindow?.postMessage(message, "*");
    const onMessage = (e: MessageEvent) => {
      if (e.source === frame.current?.contentWindow && e.data?.type === "second-half/ready") send();
    };
    window.addEventListener("message", onMessage);
    send(); // in case it was already ready (language switch)
    return () => window.removeEventListener("message", onMessage);
  }, [overlay, text, meta, lang]);

  return (
    <div className="sandboxed">
      <iframe
        ref={frame}
        src={info.entry}
        title={info.name}
        sandbox="allow-scripts"
        referrerPolicy="no-referrer"
        // The plugin's page has the browser's default light scheme. Ours is dark, and an iframe whose scheme differs
        // from its page gets an opaque white backdrop, so it is given the plugin's scheme to stay see-through.
        style={{ "--plugin-h": `${info.height_px}px`, colorScheme: "normal" } as React.CSSProperties}
      />
      <span className="credit">
        {info.name} · plugin by {info.author} · sandboxed
      </span>
    </div>
  );
}
