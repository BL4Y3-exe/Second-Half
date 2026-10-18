# Agent prompts

System prompts for the agents that call a language model (Storyteller,
Persona, Recap). In mock mode the scripted model ignores them and fills
templates from the same facts. The Spotter, Analyst, Fact-checker and
Director are plain code: they decide, look things up and verify, so they
need no model and cannot hallucinate.
