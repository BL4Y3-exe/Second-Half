import type { ComponentType } from "react";
import {
  GoalCard,
  MomentumBar,
  PassCard,
  PlayerTag,
  PressCard,
  RecapCard,
  ShotCard,
  StatCard,
  type PluginProps,
} from "./builtin";

/**
 * Built-in graphics, keyed by the plugin id the Director names. Each one has a manifest in
 * /plugins/<id>/manifest.json saying which stats it needs and where it goes on screen.
 */
export const BUILTIN: Record<string, ComponentType<PluginProps>> = {
  "goal-card": GoalCard,
  "shot-card": ShotCard,
  "pass-card": PassCard,
  "press-card": PressCard,
  "momentum-bar": MomentumBar,
  "stat-card": StatCard,
  "player-tag": PlayerTag,
  "recap-card": RecapCard,
};

export type { PluginProps };
