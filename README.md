# No One Saw Everything

A fair-play murder mystery game set in a Smallville-style village. The player
arrives after the murder, rewinds the morning, observes the village,
interrogates sims, collects contradictions, and builds a case on the board.

The entire game lives in [`mystery/`](mystery/) — FastAPI backend + React/Vite
frontend. See [`mystery/README.md`](mystery/README.md) for the full overview
and [`mystery/CLAUDE.md`](mystery/CLAUDE.md) for architecture and commands.

## Quick start

```bash
cd mystery
./start.sh        # backend :8010, frontend :5173 — bootstraps venv + npm install
./stop.sh
```

## Lineage

This repository began as a fork of
[Generative Agents: Interactive Simulacra of Human Behavior](https://arxiv.org/abs/2304.03442)
(Smallville). The original simulation code (`reverie/`, `environment/`) has
been removed from this branch; the game keeps only derived assets (the rendered
village map and sprites) and is otherwise standalone. The original code remains
available in the git history and on `main`.
