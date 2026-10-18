# Writing a graphics plugin

Every graphic Second Half puts on screen is a plugin. The built-in ones
(goal card, shot card, recap and so on) are React components in
`web/src/plugins/`. Anyone else can add one as a single HTML page that runs
in a sandbox. `plugins/xg-race/` is a complete example.

## 1. The manifest

Make a folder under `plugins/` named after your plugin, with a
`manifest.json`:

```json
{
  "id": "xg-race",
  "name": "xG race",
  "version": "1.0.0",
  "author": "Touchline Labs",
  "builtin": false,
  "entry": "index.html",
  "slot": "lower-third",
  "height_px": 150,
  "moments": ["momentum_swing"],
  "needs": ["xg_race"],
  "default_duration_s": 8,
  "description": "Each team's running xG total through the match, with goals marked."
}
```

| Field | Meaning |
| --- | --- |
| `id` | Same as the folder name. |
| `builtin` | `false` for outside plugins. |
| `entry` | The HTML page to load. It is the only file served from your folder. |
| `slot` | Where it goes: `lower-third` (the frame around it shows the headline, the fact-checked badge and the agents' story). |
| `height_px` | Height of your drawing area. The width is the slot's width. |
| `moments` | Which key moments it is for: `goal`, `big_chance`, `shot_speed`, `killer_pass`, `momentum_swing`, `sprint_speed`, `distance_10k`. The Director picks your plugin for these instead of the built-in graphic. |
| `needs` | The data you want. Available: `xg_race` (running xG per team, one point per shot) and `score`. |
| `default_duration_s` | How long it stays on screen. |
| `enabled` | Optional. `false` keeps it installed but unused. |

## 2. The page

Your page gets the data by `postMessage`, and that is the only thing it can
receive. Say you are ready when you load, then draw whatever arrives:

```js
window.addEventListener("message", (e) => {
  if (e.source !== window.parent || e.data?.type !== "second-half/render") return;
  const { lang, text, overlay, teams } = e.data;
  // overlay.data.xg_race, overlay.data.score ... whatever your manifest "needs"
  // teams.HOME = { name, short, color }, same for AWAY
  // lang is "en" or "es"; text is the agents' fact-checked story in the viewer's mode and language
});
window.parent.postMessage({ type: "second-half/ready" }, "*");
```

Keep the background transparent so the slot's frame shows through.

## 3. The sandbox

- The page runs in an iframe with `sandbox="allow-scripts"`: no access to
  the Second Half page, its storage or cookies, and it cannot open windows
  or navigate the page.
- The server sends it with a Content Security Policy of
  `default-src 'none'`, so it cannot load anything or call the network. Put
  your script, styles and any images (as `data:` URLs) inside the page.
- It only ever sees the data its manifest asked for.

Test it by running `python -m api`, opening a match and waiting for one of
your `moments`. `python -m agents --seed 9 --trace` shows when the Director
picks it.
