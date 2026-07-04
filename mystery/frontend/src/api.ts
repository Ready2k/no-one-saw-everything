import type {
  AccusationResult,
  AskResult,
  Board,
  CaseOverview,
  ChallengeResult,
  ChallengeSuggestion,
  ClaimPublic,
  CluePublic,
  EventPublic,
  InspectResult,
  LocationPublic,
  Note,
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
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
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
  challengeSuggestions: (agentId?: string) =>
    request<ChallengeSuggestion[]>(
      `/api/challenge/suggestions${agentId ? `?agent_id=${agentId}` : ""}`
    ),
  challenge: (payload: {
    target_agent_id: string;
    challenged_claim_id: string;
    evidence_clue_ids: string[];
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
    }>("/api/cases/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  activate: (caseId: string) =>
    request<{ active_session_id: string }>("/api/cases/activate", {
      method: "POST",
      body: JSON.stringify({ case_id: caseId }),
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
    request<{ models: string[] }>("/api/llm-settings/models", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getPlaytestSummary: () => request<PlaytestSummary>("/api/session/playtest-summary"),
  getPlaytestExport: () => request<any>("/api/session/playtest-export"),
  submitFeedback: (payload: Feedback) => request<{ status: string }>("/api/session/feedback", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  cases: () => request<{ case_id: string; title: string; case_type: string }[]>("/api/cases"),
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
