// Client-side meta-progression: detective rank and per-case history.
// Everything lives in localStorage — no accounts, no server persistence.

import type { AccusationResult } from "./types";

export interface CaseHistoryEntry {
  accusation_id: string;
  case_id: string;
  case_title: string;
  score: number;
  detective_rating: string;
  accused_name: string;
  killer_correct: boolean;
  fell_for_red_herring: boolean;
  duration_min: number | null;
  completed_at: string; // ISO timestamp
}

const HISTORY_KEY = "mystery_case_history";
const startedKey = (caseId: string) => `mystery_case_started_${caseId}`;

export function getHistory(): CaseHistoryEntry[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    return raw ? (JSON.parse(raw) as CaseHistoryEntry[]) : [];
  } catch {
    return [];
  }
}

/** Record a completed accusation; replays of the same reveal are deduped. */
export function recordCaseResult(result: AccusationResult, caseTitle: string): void {
  const history = getHistory();
  const key = `${result.case_id}:${result.accusation_id}`;
  if (history.some((h) => `${h.case_id}:${h.accusation_id}` === key)) return;
  history.push({
    accusation_id: result.accusation_id,
    case_id: result.case_id,
    case_title: caseTitle,
    score: result.score,
    detective_rating: result.detective_rating,
    accused_name: result.accused_name,
    killer_correct: result.killer_correct,
    fell_for_red_herring:
      !result.killer_correct &&
      result.red_herring_explanations.some(
        (h) => h.agent_id === result.accused_agent_id
      ),
    duration_min: caseDurationMin(result.case_id),
    completed_at: new Date().toISOString(),
  });
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
}

export function clearHistory(): void {
  localStorage.removeItem(HISTORY_KEY);
}

// --- Detective rank -------------------------------------------------------

export interface DetectiveRank {
  title: string;
  solved: number;
  played: number;
}

export function getRank(history: CaseHistoryEntry[] = getHistory()): DetectiveRank {
  const solved = history.filter((h) => h.killer_correct).length;
  const title = solved >= 3 ? "Ace" : solved >= 1 ? "Detective" : "Rookie";
  return { title, solved, played: history.length };
}

// --- Case timing ----------------------------------------------------------

/** Stamp the moment a case's investigation begins (first load only). */
export function markCaseStarted(caseId: string): void {
  if (!localStorage.getItem(startedKey(caseId))) {
    localStorage.setItem(startedKey(caseId), String(Date.now()));
  }
}

export function clearCaseStarted(caseId: string): void {
  localStorage.removeItem(startedKey(caseId));
}

function caseDurationMin(caseId: string): number | null {
  const started = Number(localStorage.getItem(startedKey(caseId)));
  if (!started) return null;
  return Math.max(1, Math.round((Date.now() - started) / 60000));
}

// --- Shareable case-closed card (text form) --------------------------------

export function shareText(result: AccusationResult, caseTitle: string): string {
  const mark = (ok: boolean) => (ok ? "✓" : "✕");
  const duration = caseDurationMin(result.case_id);
  const lines = [
    `🔍 No One Saw Everything — ${caseTitle}`,
    `${result.verdict} · ${result.score}/100 (${result.detective_rating})`,
    `Killer ${mark(result.killer_correct)}  Motive ${mark(result.motive_correct)}  Method ${mark(result.method_correct)}  Opportunity ${mark(result.opportunity_correct)}`,
    `Evidence strength: ${Math.round(result.evidence_score * 100)}%`,
  ];
  if (duration != null) lines.push(`Time on the case: ${duration} min`);
  const fellForHerring =
    !result.killer_correct &&
    result.red_herring_explanations.some((h) => h.agent_id === result.accused_agent_id);
  lines.push(
    fellForHerring ? "Fell for the red herring 🎣" : "Didn't fall for the red herring 🧠"
  );
  return lines.join("\n");
}
