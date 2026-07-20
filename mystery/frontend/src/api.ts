import type {
  AccusationResult,
  AskResult,
  Board,
  CaseOverview,
  ChallengeResult,
  ChallengeSuggestion,
  ChallengeSuggestionsResponse,
  ClaimPublic,
  CluePublic,
  EventPublic,
  InspectResult,
  LocationPublic,
  Note,
  ObservationRead,
  AgentPublic,
  MapReplayData,
  QuestionType,
  SuspicionLevel,
  TranscriptMessage,
  HintsResponse,
  MarkerType,
  Config,
  PlaytestSummary,
  Feedback,
  LlmSettingsResponse,
  LlmProbeResult,
  LlmTestResult,
} from "./types";

// Each browser is its own detective: an opaque token scopes every investigation
// (saves, notes, active case) to this browser on the server. Generated once and
// kept in localStorage so progress survives reloads and restarts.
function sessionToken(): string {
  const KEY = "mystery_session_id";
  try {
    let token = localStorage.getItem(KEY);
    if (!token || !/^[A-Za-z0-9_-]{8,64}$/.test(token)) {
      token = `p_${crypto.randomUUID().replace(/-/g, "")}`;
      localStorage.setItem(KEY, token);
    }
    return token;
  } catch {
    // Storage unavailable (private mode); fall back to the shared local player.
    return "local";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Session-Id": sessionToken(),
      ...(init?.headers as Record<string, string> | undefined),
    },
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `Request failed: ${res.status}`);
  }
  return res.json();
}

let activeSimStartTime: string | undefined = undefined;

export const api = {
  caseOverview: async () => {
    const data = await request<CaseOverview>("/api/case");
    activeSimStartTime = data.sim_start_time;
    return data;
  },
  agents: () => request<AgentPublic[]>("/api/agents"),
  locations: () => request<LocationPublic[]>("/api/locations"),
  events: (params: {
    time_from?: string;
    time_to?: string;
    location_id?: string;
    agent_id?: string;
  }) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v) as [string, string][]
    );
    return request<EventPublic[]>(`/api/events?${qs}`);
  },
  mapReplay: (params?: {
    start?: string;
    end?: string;
    location_id?: string;
    agent_id?: string;
    mode?: "player" | "truth";
  }) => {
    const qs = new URLSearchParams(
      Object.entries(params ?? {}).filter(([, v]) => v) as [string, string][]
    );
    return request<MapReplayData>(`/api/map/replay?${qs}`);
  },
  pinEvent: (eventId: string) =>
    request<{ pinned: boolean; new_clues: CluePublic[]; note: Note }>(
      `/api/events/${eventId}/pin`,
      { method: "POST" }
    ),
  inspect: (locationId: string) =>
    request<InspectResult>("/api/inspect", {
      method: "POST",
      body: JSON.stringify({ location_id: locationId }),
    }),
  examineBody: (agentId: string) =>
    request<InspectResult>(`/api/examine_body/${agentId}`, {
      method: "GET",
    }),
  discoverClue: (clueId: string) =>
    request<CluePublic>("/api/discover_clue", {
      method: "POST",
      body: JSON.stringify({ clue_id: clueId }),
    }),
  clues: () => request<CluePublic[]>("/api/clues"),
  ask: (payload: {
    agent_id: string;
    question_type: QuestionType;
    time_reference?: string;
    topic_clue_id?: string;
    topic_object_id?: string;
    topic_location_id?: string;
  }) =>
    request<AskResult>("/api/interview/ask", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  transcript: (agentId: string) =>
    request<TranscriptMessage[]>(`/api/interview/${agentId}`),
  /** Spend an action studying the suspect. 409s until they have given a fresh
   *  exchange (a new answer or challenge) to watch. */
  observe: (agentId: string) =>
    request<ObservationRead>("/api/interview/observe", {
      method: "POST",
      body: JSON.stringify({ agent_id: agentId }),
    }),
  freeTextAsk: (payload: { agent_id: string; question: string }) =>
    request<{
      intent: any;
      answer?: AskResult;
      challenge_suggestion?: ChallengeSuggestion;
      challenge_result?: ChallengeResult;
      fallback_message?: string;
    }>("/api/interview/free-text", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  claims: (agentId?: string) =>
    request<ClaimPublic[]>(`/api/claims${agentId ? `?agent_id=${agentId}` : ""}`),
  notes: () => request<Note[]>("/api/notes"),
  createNote: (payload: Partial<Note> & { title: string }) =>
    request<Note>("/api/notes", { method: "POST", body: JSON.stringify(payload) }),
  updateNote: (noteId: string, payload: Partial<Note>) =>
    request<Note>(`/api/notes/${noteId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteNote: (noteId: string) =>
    request<{ deleted: boolean }>(`/api/notes/${noteId}`, { method: "DELETE" }),
  setSuspicion: (agentId: string, level: SuspicionLevel) =>
    request<{ agent_id: string; level: SuspicionLevel }>("/api/suspicion", {
      method: "POST",
      body: JSON.stringify({ agent_id: agentId, level }),
    }),
  board: () => request<Board>("/api/board"),
  hints: () => request<HintsResponse>("/api/session/hints"),
  updateMarkers: (payload: { element_id: string; marker: MarkerType; action: "add" | "remove" | "clear" }) =>
    request<{ element_id: string; markers: MarkerType[] }>("/api/session/markers", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  /** `reveal` asks the game to show WHICH claim each clue disproves — an explicit, counted hint.
   *  Without it, only the contradiction count comes back. */
  challengeSuggestions: (agentId?: string, reveal = false) => {
    const qs = new URLSearchParams();
    if (agentId) qs.set("agent_id", agentId);
    if (reveal) qs.set("reveal", "true");
    const q = qs.toString();
    return request<ChallengeSuggestionsResponse>(
      `/api/challenge/suggestions${q ? `?${q}` : ""}`
    );
  },
  challenge: (payload: {
    target_agent_id: string;
    challenged_claim_id: string;
    evidence_clue_ids: string[];
    /** Another person's statement, used as evidence. */
    evidence_claim_ids?: string[];
    player_statement?: string;
  }) =>
    request<ChallengeResult>("/api/challenge", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  accuse: (payload: {
    accused_agent_id: string;
    motive_answer: string;
    method_answer: string;
    opportunity_answer: string;
    supporting_note_ids: string[];
    supporting_clue_ids: string[];
  }) =>
    request<AccusationResult>("/api/accuse", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  reveal: () => request<AccusationResult>("/api/reveal"),
  status: () =>
    request<{
      discovered_clue_count: number;
      claim_count: number;
      challenge_count: number;
      accused: boolean;
    }>("/api/status"),
  reset: () => request<{ reset: boolean }>("/api/session/reset", { method: "POST" }),
  generate: (payload: {
    case_type: string;
    difficulty: string;
    seed: number;
    activate: boolean;
    mode: "deterministic" | "llm_assisted";
    fallback_allowed: boolean;
    num_suspects?: number;
    num_locations?: number;
    theme_preset?: string;
    custom_theme?: string;
    tone?: string;
    llm_notes?: string;
    candidate_count?: number;
  }) =>
    request<{
      case_id: string;
      case_type: string;
      title: string;
      mode: string;
      fallback_used: boolean;
      fallback_reason: string;
      repair_attempts: number;
      active_session_id: string | null;
      validation: {
        valid: boolean;
        score: number;
        warnings: string[];
        errors: string[];
      };
      generation_metadata?: {
        mode: string;
        seed: number;
        num_suspects: number | null;
        num_locations: number | null;
        theme_preset: string;
        tone: string;
        fallback_used: boolean;
        repair_attempts: number;
        compaction_applied: boolean;
        pruned_agents: string[];
        remapped_locations: Record<string, string>;
        selected_seed?: number;
        best_of_n_used?: boolean;
        candidate_scores?: Array<{ seed: number; overall_score: number; is_valid: boolean }> | null;
        quality_report?: {
          suspect_distinctiveness: number;
          motive_clarity: number;
          red_herring_strength: number;
          clue_distribution: number;
          location_usage_balance: number;
          timeline_density: number;
          solution_fairness: number;
          theme_adherence: number;
          tone_consistency: number;
          overall_score: number;
          warnings: string[];
          suggested_improvements: string[];
        } | null;
      } | null;
    }>("/api/cases/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  /** Opening a case RESUMES the investigation. Pass restart to bin it and start over. */
  activate: (caseId: string, restart = false) =>
    request<{
      active_session_id: string;
      resumed: boolean;
      discovered_clue_count: number;
      accused: boolean;
    }>("/api/cases/activate", {
      method: "POST",
      body: JSON.stringify({ case_id: caseId, restart }),
    }),
  getConfig: () => request<Config>("/api/config"),
  getLlmSettings: () => request<LlmSettingsResponse>("/api/llm-settings"),
  updateLlmSettings: (payload: {
    provider: "fake" | "auto" | "openai_compatible";
    base_url?: string;
    api_key?: string;
    model?: string;
    dialogue_enabled: boolean;
  }) =>
    request<LlmSettingsResponse>("/api/llm-settings", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  probeLlm: () => request<LlmProbeResult>("/api/llm-settings/probe", { method: "POST" }),
  discoverLlmModels: (payload: { base_url: string; api_key?: string }) =>
    request<{ models: string[]; error: string | null }>("/api/llm-settings/models", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  testLlm: (payload: { base_url: string; api_key?: string; model: string }) =>
    request<LlmTestResult>("/api/llm-settings/test", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  // Re-run discovery/test against whatever is already saved server-side —
  // the client is never given the real api_key back, so it cannot resend it.
  discoverSavedLlmModels: () =>
    request<{ models: string[]; error: string | null }>("/api/llm-settings/models/saved", {
      method: "POST",
    }),
  testSavedLlm: () =>
    request<LlmTestResult>("/api/llm-settings/test/saved", { method: "POST" }),
  getPlaytestSummary: () => request<PlaytestSummary>("/api/session/playtest-summary"),
  getPlaytestExport: () => request<any>("/api/session/playtest-export"),
  submitFeedback: (payload: Feedback) => request<{ status: string }>("/api/session/feedback", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  cases: () =>
    request<
      {
        case_id: string;
        title: string;
        case_type: string;
        is_active: boolean;
        /** null when the case has never been opened. */
        progress: {
          clues_found: number;
          suspects_interviewed: number;
          notes: number;
          hints_taken: number;
          accused: boolean;
        } | null;
      }[]
    >("/api/cases"),
  generatedCases: {
    list: (params?: { sort_by?: string; tone?: string; case_type?: string; best_of_n?: boolean; fallback_used?: boolean }) => {
      const q = new URLSearchParams();
      if (params) {
        if (params.sort_by) q.set("sort_by", params.sort_by);
        if (params.tone) q.set("tone", params.tone);
        if (params.case_type) q.set("case_type", params.case_type);
        if (params.best_of_n !== undefined) q.set("best_of_n", String(params.best_of_n));
        if (params.fallback_used !== undefined) q.set("fallback_used", String(params.fallback_used));
      }
      return request<any[]>(`/api/generated_cases?${q.toString()}`);
    },
    get: (caseId: string) => request<any>(`/api/generated_cases/${caseId}`),
    activate: (caseId: string) => request<{ status: string; active_session_id: string }>(`/api/generated_cases/${caseId}/activate`, { method: "POST" }),
    regenerate: (caseId: string) => request<any>(`/api/generated_cases/${caseId}/regenerate`, { method: "POST" }),
    delete: (caseId: string) => request<{ status: string }>(`/api/generated_cases/${caseId}`, { method: "DELETE" }),
  },
  getDevMapLayout: () => request<any>("/api/dev/map-editor/layout"),
  // baseVersion is the `layout_version` the layout was last loaded/saved at;
  // the server 409s if the file has since changed (another tab/session saved
  // in the meantime) instead of silently overwriting those changes. Omit it
  // to force-save regardless (used when the user explicitly accepts the
  // overwrite after being warned).
  saveDevMapLayout: async (payload: any, baseVersion?: string): Promise<{ status: string; layout_version: string }> => {
    const res = await fetch("/api/dev/map-editor/layout", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(baseVersion ? { "X-Base-Layout-Version": baseVersion } : {}),
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      // Validation failures return detail as {errors: [...]} — surface each error
      const body = await res.json().catch(() => ({} as any));
      const detail = body?.detail;
      if (res.status === 409) {
        const err = new Error(typeof detail === "string" ? detail : "The layout changed on disk since you loaded it.");
        (err as any).conflict = true;
        throw err;
      }
      if (Array.isArray(detail?.errors) && detail.errors.length) {
        throw new Error(detail.errors.join("\n"));
      }
      throw new Error(typeof detail === "string" ? detail : `Request failed: ${res.status}`);
    }
    return res.json();
  },
};

export function minutes(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  let mins = h * 60 + m;
  if (activeSimStartTime) {
    const [sh, sm] = activeSimStartTime.split(":").map(Number);
    const startMins = sh * 60 + sm;
    if (mins < startMins) {
      mins += 1440;
    }
  }
  return mins;
}

export function hhmm(mins: number): string {
  const h = Math.floor(mins / 60) % 24;
  const m = mins % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

/** Derive a human-readable time-of-day label from an HH:MM time string.
 *  05:00–11:59 → "morning", 12:00–16:59 → "afternoon",
 *  17:00–20:59 → "evening", 21:00–04:59 → "night". */
export function timeOfDayLabel(hhmmStr: string): string {
  const h = parseInt(hhmmStr.split(":")[0], 10);
  if (h >= 5 && h < 12) return "morning";
  if (h >= 12 && h < 17) return "afternoon";
  if (h >= 17 && h < 21) return "evening";
  return "night";
}
