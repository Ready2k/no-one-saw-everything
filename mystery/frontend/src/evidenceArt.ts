/**
 * Evidence plates are intentionally resolved client-side only after the clue
 * has been returned by the existing discovery API. This registry contains no
 * discovery state and must never be used to render hidden hotspots or markers.
 */
const CASE_005_EVIDENCE: Record<string, string> = {
  clue_belt_weapon: "/art/case_005/evidence/builders_belt.png",
  clue_staged_fire: "/art/case_005/evidence/melted_lighter.png",
  clue_clara_committee_note: "/art/case_005/evidence/scorched_letter.png",
  clue_mortgage_deed: "/art/case_005/evidence/mortgage_deed.png",
  clue_owen_ash_boots: "/art/case_005/evidence/ash_mud_boots.png",
  clue_strangulation_mark: "/art/case_005/evidence/builders_belt.png",
  clue_elias_belt_anecdote: "/art/case_005/evidence/builders_belt.png",
  clue_col_saw_no_belt: "/art/case_005/evidence/builders_belt.png",
  clue_belt_hook_gap: "/art/case_005/evidence/builders_belt.png",
  clue_property_register: "/art/case_005/evidence/mortgage_deed.png",
  clue_whitfield_is_nobody: "/art/case_005/evidence/mortgage_deed.png",
  clue_capacity_certificate: "/art/case_005/evidence/mortgage_deed.png",
  clue_col_carried_the_deed: "/art/case_005/evidence/mortgage_deed.png",
  clue_yard_books: "/art/case_005/owen_yard_office_dawn_hd.png",
  clue_clara_second_page: "/art/case_005/evidence/scorched_letter.png",
};

const CASE_010_EVIDENCE: Record<string, string> = {
  clue_ledger_page: "/art/case_010/evidence/ledger_page_case10.png",
  clue_till_weight_found: "/art/case_010/evidence/till_weight_mop_bucket.png",
  clue_blue_coat_damp: "/art/case_010/evidence/blue_coat_damp_sleeve.png",
  clue_isabella_note: "/art/case_010/evidence/isabella_folded_note.png",
};

export function evidenceArt(caseId: string | undefined, clueId: string): string | null {
  if (caseId === "case_005") return CASE_005_EVIDENCE[clueId] ?? null;
  if (caseId === "case_010") return CASE_010_EVIDENCE[clueId] ?? null;
  return null;
}
