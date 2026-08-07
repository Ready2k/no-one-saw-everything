# No One Saw Everything

A fair-play murder mystery game set in a Smallville-style village. The player
arrives after the murder, rewinds the morning, observes the village,
interrogates sims, collects contradictions, and builds a case on the board.

The entire game lives in [`mystery/`](mystery/) — FastAPI backend + React/Vite
frontend. See [`mystery/README.md`](mystery/README.md) for the full overview
and [`mystery/CLAUDE.md`](mystery/CLAUDE.md) for architecture and commands.

[`persona_chat_lab/`](persona_chat_lab/) is a historical research sandbox for
an interview-engine redesign (deterministic matching + optional LLM layers).
See [`persona_chat_lab/ENGINE_SPEC.md`](persona_chat_lab/ENGINE_SPEC.md).

## Quick start

```bash
cd mystery
./start.sh        # backend :8010, frontend :5179 — bootstraps venv + npm install
./stop.sh
```

## Lineage

This repository began as a fork of
[Generative Agents: Interactive Simulacra of Human Behavior](https://arxiv.org/abs/2304.03442)
(Smallville). The original simulation code (`reverie/`, `environment/`) has
been removed from every branch, including `main`; the game keeps only derived
assets (the rendered village map and sprites) and is otherwise standalone. The
original code remains recoverable from git history only.
