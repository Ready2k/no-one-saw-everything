"""Reference scenarios for LLM-assisted case generation (Phase 1: plot outline).

These are lightweight story-bible sketches, NOT full case templates — they carry
no locations, clue graph, or timeline, and are never used by the deterministic
generator (generator.py), which still fills the single canonical
data/templates/<case_type>.json for its structural spine.

Their only job is to give generate_llm_case's plot-outline prompt several
different "shapes" a case_type can take, so the LLM invents a fresh scenario
each run instead of converging on one recurring plot. They are shown to the
model as inspiration only; the prompt instructs it not to copy them.
"""

REFERENCE_SCENARIOS: dict[str, list[dict]] = {
    "blackmail": [
        {
            "title": "The Ledger Behind the Bar",
            "motive_variant": "The victim was quietly blackmailing the killer over a fraudulent insurance claim from years earlier, and had just raised the price of their silence.",
            "victim_rationale": "The victim kept a private ledger of the payments and had started hinting to others that they 'knew things' about several people in town, enjoying the leverage.",
            "killer_rationale": "The killer had been paying to keep the old fraud buried, but a licence renewal or background check meant exposure now would cost them everything, and the victim's new demand was the last straw.",
            "scene_description": "{discovered_by_name} found {VICTIM_NAME} slumped near the till at {murder_location}, a {WEAPON_NAME} nearby and the cash drawer still open, as though someone had been searching for something.",
        },
        {
            "title": "Portrait of a Lie",
            "motive_variant": "The victim discovered the killer had authenticated a forged piece years ago and used the secret to demand a cut of the killer's ongoing sales.",
            "victim_rationale": "The victim had proof — a receipt, a photograph, a letter — that the killer knowingly sold a forgery to a trusting client, and treated the blackmail as a standing arrangement rather than a one-time payoff.",
            "killer_rationale": "A licensing board inquiry was already underway; if the forgery came out now, the killer would lose their livelihood and reputation, not just money.",
            "scene_description": "{discovered_by_name} discovered {VICTIM_NAME} at {murder_location}, a {WEAPON_NAME} close by, with papers scattered across the floor as if someone had been rifling through a file.",
        },
        {
            "title": "The Anonymous Tip",
            "motive_variant": "The victim had photographic proof of the killer's affair and threatened to send it to the killer's spouse and business partner unless paid.",
            "victim_rationale": "The victim had grown bolder with each payment, escalating the demand and setting a hard deadline for the next one.",
            "killer_rationale": "The affair coming out now would cost the killer their marriage and their standing in a business deal that depended on their partner's trust.",
            "scene_description": "{discovered_by_name} found {VICTIM_NAME} at {murder_location}; a {WEAPON_NAME} lay nearby, and a torn envelope was found close to the body.",
        },
    ],
    "debt": [
        {
            "title": "Markers Due at Midnight",
            "motive_variant": "The killer owed the victim a large gambling debt, and the victim had begun threatening to collect it from the killer's family or employer instead.",
            "victim_rationale": "The victim ran a private book and treated the debt as collateral to be called in whenever it suited them, using the threat of exposure as leverage.",
            "killer_rationale": "The killer had no way to pay and could not survive the debt becoming public — it would cost them their job, their marriage, or both.",
            "scene_description": "{discovered_by_name} found {VICTIM_NAME} at {murder_location}, a {WEAPON_NAME} nearby and a small notebook of figures left open on a table.",
        },
        {
            "title": "The Co-signed Loan",
            "motive_variant": "The victim co-signed a loan for the killer's failing business, and when it collapsed, began demanding repayment and threatening to report irregularities on the loan application.",
            "victim_rationale": "The victim's own finances depended on being repaid, and they had stopped believing the killer's excuses about a slow recovery.",
            "killer_rationale": "The killer could not repay the loan, and a fraud report over the application would end any chance of starting over.",
            "scene_description": "{discovered_by_name} found {VICTIM_NAME} at {murder_location}; a {WEAPON_NAME} was nearby, along with a stack of unopened letters from a bank.",
        },
        {
            "title": "Borrowed From the Family Pot",
            "motive_variant": "The victim, trustee of a shared family fund, had quietly covered a debt the killer ran up, and now wanted it repaid before the rest of the family found out where the money had gone.",
            "victim_rationale": "The victim felt entitled to be repaid privately and had started dropping hints to relatives that something about the fund 'didn't add up'.",
            "killer_rationale": "If the family learned the killer had taken from the shared fund, it would end their standing in the family for good, on top of the money they still owed.",
            "scene_description": "{discovered_by_name} found {VICTIM_NAME} at {murder_location}, a {WEAPON_NAME} left nearby, next to an open ledger book.",
        },
    ],
    "betrayal": [
        {
            "title": "Partners in Name Only",
            "motive_variant": "The victim, the killer's business partner, was secretly negotiating to sell the company to a rival and cut the killer out entirely.",
            "victim_rationale": "The victim believed the killer would never agree to the sale and planned to present it as a done deal rather than risk a fight.",
            "killer_rationale": "The killer found out the morning of the murder and realized years of work were about to be sold out from under them without a say.",
            "scene_description": "{discovered_by_name} found {VICTIM_NAME} at {murder_location}, a {WEAPON_NAME} nearby, with a half-signed contract left on the desk.",
        },
        {
            "title": "The Whistleblower",
            "motive_variant": "The victim had promised to keep the killer's wrongdoing quiet, but was about to hand over evidence of it to an inspector or reporter that same day.",
            "victim_rationale": "The victim had wrestled with the decision for weeks and finally decided loyalty could not outweigh the harm being covered up.",
            "killer_rationale": "The killer learned the report was imminent and saw it as the end of their career, or worse, and could not let it go out.",
            "scene_description": "{discovered_by_name} found {VICTIM_NAME} at {murder_location}; a {WEAPON_NAME} lay nearby, and a sealed envelope addressed to an official was found close by.",
        },
        {
            "title": "Stolen Credit",
            "motive_variant": "The victim was about to accept sole credit — and a major contract or award — for work the killer had actually created alongside them.",
            "victim_rationale": "The victim had quietly rewritten the history of the project over months, downplaying the killer's role until it was almost erased.",
            "killer_rationale": "The killer had one last chance to stop the announcement before the theft became permanent and irreversible.",
            "scene_description": "{discovered_by_name} found {VICTIM_NAME} at {murder_location}, a {WEAPON_NAME} nearby, next to a folder of drafts and notes.",
        },
    ],
}


def format_reference_scenarios(case_type: str) -> str:
    """Render the case_type's reference scenarios as few-shot prompt text.

    Falls back to the blackmail set if case_type has no entries, since the
    caller always passes one of the schema's Literal case_type values.
    """
    scenarios = REFERENCE_SCENARIOS.get(case_type, REFERENCE_SCENARIOS["blackmail"])
    blocks = []
    for i, s in enumerate(scenarios, start=1):
        blocks.append(
            f"""Example {i}: "{s['title']}"
- motive_variant: {s['motive_variant']}
- victim_rationale: {s['victim_rationale']}
- killer_rationale: {s['killer_rationale']}
- scene_description: {s['scene_description']}"""
        )
    return "\n\n".join(blocks)
