# SaaS Readiness Roadmap

This roadmap records which architectural improvements are worthwhile as the
game grows, and—equally importantly—when they are worth doing. It is not a
case for rewriting the current game: the current architecture deliberately
optimises for a self-hosted, single-backend deployment with fair, deterministic
mystery logic.

For deferred implementation details already identified during the production
hardening work, see [`PRODUCTION_TODO.md`](../PRODUCTION_TODO.md). The
deployment contract for the current system is in
[`deployment.md`](deployment.md).

## Current, intentional boundaries

- The API runs as **one backend instance / one Uvicorn worker**. Player
  investigations are held in process and persisted as per-player JSON saves.
  Per-player locks prevent state contamination inside that process.
- An opaque browser session token separates local players, but it is not a
  full account or identity system.
- Case truth, scoring, clues, and state transitions are deterministic. LLMs
  can only rewrite selected dialogue for flavour and must fall back to authored
  text when they fail or their response is rejected.
- Case bundles are data-driven, while the shared village map and its art
  registry retain some application-level configuration.

These are reasonable trade-offs for local play, a private demo, a home-server
deployment, or a small closed playtest. They should be described honestly in
release material rather than treated as hidden defects.

## Decision triggers

| Trigger | Apply these changes | Why then |
| --- | --- | --- |
| Local, private, or single-host deployment | Keep the current design; run the existing test, backup, and Docker checks. | A shared datastore and account platform add operational cost without solving a user problem at this scale. |
| Public beta with accounts or players returning across devices | Add authentication, secure server-managed sessions, access controls, retention/deletion rules, and supportable backup/restore. | A browser-held opaque token is useful for anonymous local separation, but it is not an account, recovery, or customer-data model. |
| Multiple API replicas, multiple Uvicorn workers, or reliable high availability | Move sessions, rate limits, generated-case metadata, and relevant caches to shared services (normally Postgres plus Redis); make API instances stateless. | Process dictionaries and JSON files cannot coordinate writes or invalidate caches across replicas. Running more than one current worker can create divergent investigations. |
| Material concurrent load, paid usage, or an availability commitment | Add load tests, capacity targets, metrics/alerts, tracing, job queues for expensive generation, and disaster-recovery exercises. | “Scales” must be demonstrated against a defined workload and recovery objective, not inferred from a local prototype. |
| Public LLM-backed interaction or a stronger no-spoiler guarantee | Reduce free-form model output authority: use structured/allowlisted dialogue slots where practical, retain deterministic fallback, and test real providers with prompt-injection and adversarial corpora. | The existing schema validation and sanitisation are useful layers, but heuristic checks cannot prove that arbitrary natural language will never disclose a hidden inference. |
| Frequent new maps, licensed art packs, or a content team | Move map/asset registry data into versioned declarative manifests with schema validation and authoring tools; keep game truth separate from visual assets. | The current registry is workable for a small curated village, but code edits become a bottleneck when content changes independently of engineering. |

## Recommended work, in order

### 1. Complete the single-instance deployment contract

Before a public launch, resolve the existing operational follow-ups: separate
immutable shipped case data from mutable saves/generated content, run a real
Docker build-and-smoke test, and document backup and upgrade procedures. This
improves reliability without changing the game model.

### 2. Introduce identity only when the product needs it

For a public account-based game, replace the browser token as the primary
authority with authenticated identities and server-managed secure sessions.
Define data retention, deletion, and recovery behaviour alongside the feature.
Do not add this merely to make a local game look enterprise-shaped.

### 3. Make state horizontally scalable only when replicas are needed

Use a migration rather than a wholesale rewrite:

1. Define repository interfaces around investigation state, rate limiting, and
   generated-case metadata.
2. Move durable investigation state to Postgres with migrations and
   transaction/concurrency semantics.
3. Put short-lived coordination, rate limits, and cache invalidation in Redis.
4. Run integration tests against more than one API process before permitting
   multiple replicas in deployment.

This work is essential for high availability or meaningful concurrent traffic;
it is unnecessary for the documented one-instance mode.

### 4. Continue tightening the LLM boundary

The deterministic engine must remain the only authority for truth, discoveries,
claims, scores, and reveal gates. Treat LLM output as presentation only.

Where dialogue quality permits, have the model choose from a limited structured
set of tones, beats, and approved fact references, then render player-visible
text from trusted templates. Retain the current rejection-and-fallback path for
any free-form rewrites. Add provider-version regression tests and adversarial
tests to measure rejection rate, leakage attempts, and fallback behaviour.

The goal is risk reduction, not an inaccurate claim of perfect LLM safety.

### 5. Decouple map content incrementally

The hand-authored case bundles are a gameplay strength: mysteries require
deliberate clue graphs and consistent facts. The improvement is not to replace
authored content with uncontrolled generation. Instead, make map placements,
asset IDs, and per-case visual overrides declarative, validated, and reviewable
without changing Python/TypeScript implementation code.

## Acceptance criteria for a SaaS launch

Do not advertise multi-instance or SaaS readiness until all applicable items
below are true:

- Sessions and rate limits are shared and durable across replicas.
- Authentication, authorization, recovery, retention, and deletion are
  implemented for player data.
- Backups and restoration have been exercised, not merely documented.
- Load, failure, and multi-replica consistency tests meet written capacity and
  availability targets.
- LLM behaviour is monitored, rate-limited, evaluated against adversarial
  inputs, and cannot change deterministic game state or reveal-gate decisions.
- Content-manifest validation runs in CI, including every shipped case and map.

## What this roadmap does not conclude

The use of authored case data, a documented original spec source, prompts, or
LLM-assisted development is not by itself evidence of poor engineering. The
relevant question is whether the system is appropriate for its promised
operating model. Today it is appropriate for single-instance deployments; the
work above defines the threshold for expanding that promise.
