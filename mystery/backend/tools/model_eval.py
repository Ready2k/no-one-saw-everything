#!/usr/bin/env python3
"""Score a local model on the four axes that decide whether it can speak for a
suspect. Point it at whatever you have just pulled.

    tools/model_eval.py                          # every model the host reports
    tools/model_eval.py qwen3:8b command-r7b     # just these
    tools/model_eval.py --case case_004 -n 20

The axes, and why each one is here rather than "does it sound good":

  latency      A turn is a conversation. Ten seconds between question and
               answer is the difference between a suspect and a progress bar.
  timeline     Does it keep the clock straight? `_sanitise` check 7 refuses a
               rewrite that moves a time, because the player builds their
               timeline from testimony and `testimony.py` calls bilocation at
               five minutes. Measured: llama3.1:8b fails this 12/12.
  content      Does it still *say* what the authored line said? Acceptance is
               not usefulness — a rewrite passes every sanitiser check by
               saying nothing, and one model here answers "I don't recall him
               personally" in place of a characterising answer. Reported as
               median length against the authored line; well under 1.0 means
               the model is quietly deleting the writing.
  layer 7      Does it populate `source_claim_ids`? ENGINE_SPEC §9.3 makes
               silence fatal by design, so a model that ignores the field
               fails *every* claim-grounded turn and Layer 7 must stay off for
               it. Two of the first three models tested could not do this.
               The danger column is the safety check: a cited combination that
               gives away a solution facet must be refused.

Nothing here writes to the case library or to saved settings; the model is
overridden in-process only.
"""

import argparse
import json
import logging
import statistics
import sys
import time
import urllib.request
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from app import case_store
from app.danger_table import get_danger_table
from app.llm import config as config_module
from app.llm import dialogue_rewriter
from app.llm.config import LLMConfig, get_llm_config
from app.models import Claim


def discover_models(base_url: str) -> list[str]:
    root = base_url.rstrip("/")
    if root.endswith("/v1"):
        root = root[: -len("/v1")]
    try:
        with urllib.request.urlopen(f"{root}/api/tags", timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
        return sorted(m["name"] for m in data.get("models", []) if m.get("name"))
    except Exception as exc:  # noqa: BLE001 - a diagnostic tool reports, not raises
        print(f"could not list models at {root}: {exc}", file=sys.stderr)
        return []


def pick_probes(case) -> tuple[str, str, str]:
    """An authored answer that states times, one that does not, and a speaker.

    Chosen from the case's own interview packs rather than hardcoded, so this
    works on a generated case as well as on case_001.
    """
    from app.llm.numeric_fidelity import find_times

    timed = untimed = speaker = None
    for pack in case.interview_packs:
        for rule in pack.rules:
            text = (rule.answer_text or "").strip()
            if len(text) < 80:
                continue
            if find_times(text.lower()):
                if timed is None:
                    timed, speaker = text, pack.agent_id
            elif untimed is None:
                untimed = text
            if timed and untimed:
                break
    return timed, untimed, speaker


def pick_pairs(case, agent_id: str) -> tuple[list[str], list[str]]:
    """A recorded danger pair for this agent, and a safe pair to contrast it."""
    danger = [list(pair) for pair in get_danger_table(case) ]
    mine = next((p for p in danger if all(c.startswith(f"claim_{agent_id.split('_')[-1]}") for c in p)), None)
    if mine is None and danger:
        mine = danger[0]

    claims = claim_texts(case)
    safe = [c for c in claims if not mine or c not in mine][:2]
    return (mine or []), safe


def claim_texts(case) -> dict[str, str]:
    out: dict[str, str] = {}
    for pack in case.interview_packs:
        for rule in pack.rules:
            for claim in rule.claims:
                if claim.claim_id and claim.summary:
                    out[claim.claim_id] = claim.summary
    return out


def use_model(model: str, base_url: str, layer7: bool) -> None:
    config_module.get_llm_config = lambda: LLMConfig(
        provider="openai_compatible", base_url=base_url, api_key=None, model=model,
        timeout_seconds=180, configured=True, fallback_reason=None,
        dialogue_enabled=True, claim_reasoning_enabled=layer7,
    )


def trial(case, agent, question, deterministic, n, history=None):
    accepted, times, lengths = 0, [], []
    for _ in range(n):
        started = time.time()
        try:
            result = dialogue_rewriter.rewrite_interview_answer(
                case=case, agent=agent, question_text=question,
                deterministic_text=deterministic, allowed_facts=[],
                pressure_level=1, recent_exchange=None, emotion="neutral",
                world_state=None, is_repeat=False, session=None,
                claim_history=history,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"    error: {str(exc)[:100]}", file=sys.stderr)
            continue
        times.append(time.time() - started)
        if not result.fallback_used:
            accepted += 1
            lengths.append(len((result.rewritten_text or "").strip()))
    return accepted, times, lengths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("models", nargs="*", help="models to score (default: all on the host)")
    parser.add_argument("--base-url", default=None, help="defaults to the configured endpoint")
    parser.add_argument("--case", default="case_001")
    parser.add_argument("-n", type=int, default=12, help="samples per axis (default 12)")
    parser.add_argument("--verbose", action="store_true", help="print every rewrite")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.ERROR)

    base_url = args.base_url or get_llm_config().base_url
    if not base_url:
        print("No endpoint configured. Pass --base-url or set one in LLM Settings.",
              file=sys.stderr)
        return 2

    models = args.models or discover_models(base_url)
    if not models:
        return 2

    case = case_store.get_case(args.case)
    timed, untimed, speaker = pick_probes(case)
    if not (timed and untimed and speaker):
        print(f"{args.case} has no suitable authored answers to probe with", file=sys.stderr)
        return 2
    agent = next(a for a in case.agents if a.agent_id == speaker)
    danger_ids, safe_ids = pick_pairs(case, speaker)
    texts = claim_texts(case)

    def claims(ids):
        return [Claim(claim_id=c, speaker_agent_id=speaker, claim_text=texts.get(c, ""))
                for c in ids]

    print(f"case {args.case}, speaking as {agent.full_name}, n={args.n}")
    print(f"endpoint {base_url}")
    if not danger_ids:
        print("note: this case has no recorded danger pairs; the danger column is skipped")

    rows = []
    for model in models:
        print(f"\nscoring {model} ...", flush=True)
        use_model(model, base_url, layer7=False)
        t_ok, t_times, _ = trial(case, agent, "Where were you that morning?", timed, args.n)
        c_ok, _, c_lens = trial(case, agent, "Tell me about the victim.", untimed, max(4, args.n // 3))

        use_model(model, base_url, layer7=True)
        l7_ok, _, _ = trial(case, agent, "Tell me again, in your own words.", untimed,
                            max(4, args.n // 3), history=claims(safe_ids))
        d_refused = 0
        if danger_ids:
            # The danger axis only measures anything if the prompt actually
            # provokes the combination. Pointing a bland question at unrelated
            # deterministic text scores 0/4 refusals against a guard that is
            # working perfectly — the model simply never tried. Push it, and
            # ground it in the two claims themselves.
            provoke = ("You said both of these. Put them together and tell me "
                       "what they add up to.")
            d_ok, _, _ = trial(case, agent, provoke,
                               " ".join(texts.get(c, "") for c in danger_ids),
                               4, history=claims(danger_ids))
            d_refused = 4 - d_ok

        # No accepted rewrite means no length to compare; report it as absent
        # rather than 0.00x, which reads as "deleted everything".
        ratio = (statistics.median(c_lens) / len(untimed)) if c_lens else None
        rows.append((model,
                     statistics.median(t_times) if t_times else float("nan"),
                     f"{t_ok}/{args.n}", ratio,
                     f"{l7_ok}/{max(4, args.n // 3)}",
                     f"{d_refused}/4" if danger_ids else "n/a"))

    print(f"\n{'model':24}{'median':>8}{'timeline':>11}{'content':>9}{'L7 cite':>9}{'L7 refuse':>11}")
    print("-" * 72)
    for model, median, timeline, ratio, cite, refuse in rows:
        shown = f"{ratio:7.2f}x" if ratio is not None else "      --"
        print(f"{model:24}{median:7.1f}s{timeline:>11}{shown:>9}{cite:>9}{refuse:>11}")
    print("\ntimeline: rewrites that kept every time straight (higher is better)")
    print("content : median rewrite length against the authored line; well under")
    print("          1.00 means the model is deleting the writing, not rephrasing it")
    print("L7 cite : turns accepted with claim reasoning on. 0 means the model")
    print("          never declares source_claim_ids, so Layer 7 must stay off")
    print("L7 refuse: dangerous combinations correctly refused (want 4/4)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
