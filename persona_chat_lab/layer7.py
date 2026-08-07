"""Layer 7 — LLM claim-reasoning extension (ENGINE_SPEC.md §9), generative
half only.

Deliberately excludes §9.1-9.3's danger table / citation cap / combination-
leak rejection. Those exist in the shipped game to stop the model
synthesising a true-but-hidden inference from two individually-safe claims —
but this sandbox's Owen/Priya case has no hidden solution to protect (Clara,
the actual killer, was kept out of it; see personas.py's module docstring).
There is nothing here for a citation guard to guard against, so building one
would test machinery this case can't exercise. What's here is the other
half of §9's job: synthesising an in-voice answer from claims a player has
already earned this session, for a question Layer 4's fact bank wasn't
authored to answer directly.

Network calls live here, not in engine.py — engine.py's own module
docstring ("no LLM, no network calls") stays true regardless of whether
this layer is enabled or reachable.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from claims import Claim

BASE_URL = os.environ.get("PERSONA_LAB_LLM_BASE_URL", "http://Desktop-HomePC.local:11434/v1")
MODEL = os.environ.get("PERSONA_LAB_LLM_MODEL", "llama3.1:8b")
ENABLED = os.environ.get("PERSONA_LAB_CLAIM_REASONING_ENABLED", "false").lower() == "true"

_TIMEOUT_SECONDS = 10
_MAX_TOKENS = 150
_MAX_REPLY_CHARS = 600  # hard cap — a rambling generation must not break the UI


def _format_claims(claims: list[Claim]) -> str:
    lines = []
    for c in claims:
        when = f" (at {c.time_reference})" if c.time_reference else ""
        lines.append(f"- [{c.topic}]{when} {c.claim_text}")
    return "\n".join(lines)


def _build_messages(*, full_name: str, occupation: str, voice_card: str,
                     claims: list[Claim], question: str) -> list[dict]:
    first_name = full_name.split()[0]
    system = (
        f"You are {full_name}, a {occupation.lower()} being interviewed by a "
        f"detective investigating a murder.\n\n"
        f"Voice: {voice_card}\n\n"
        f"You may ONLY use the facts listed below. Do not invent new names, "
        f"times, locations, or events beyond what is stated. If the "
        f"detective's question genuinely cannot be answered by connecting "
        f"the facts below, say so in character rather than inventing "
        f"something. Reply with a single short in-character line — no "
        f"stage directions, no narration, just what {first_name} would say."
    )
    user = (
        f"Facts you have already told the detective this conversation:\n"
        f"{_format_claims(claims)}\n\n"
        f"Detective's question: {question}\n\n"
        f"Answer in character, grounded only in the facts above."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _call_ollama(messages: list[dict]) -> str | None:
    body = json.dumps({
        "model": MODEL,
        "messages": messages,
        "max_tokens": _MAX_TOKENS,
        "temperature": 0.7,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return payload["choices"][0]["message"]["content"]
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError,
            KeyError, IndexError):
        # Best-effort only — an unreachable/misconfigured model must degrade
        # to the deterministic deflect, never break the chat request. Same
        # spirit as ENGINE_SPEC.md §11's fallback contract.
        return None


def try_claim_reasoning(*, full_name: str, occupation: str, voice_card: str,
                         claims: list[Claim], question: str) -> str | None:
    """Best-effort in-character answer synthesised from already-revealed
    claims, or None if disabled, under-claimed, unreachable, or the model
    returned something unusable. Never raises."""
    if not ENABLED or len(claims) < 2:
        return None

    messages = _build_messages(
        full_name=full_name, occupation=occupation, voice_card=voice_card,
        claims=claims, question=question,
    )
    reply = _call_ollama(messages)
    if not reply:
        return None

    reply = reply.strip().strip('"')
    if not reply:
        return None
    return reply[:_MAX_REPLY_CHARS]
