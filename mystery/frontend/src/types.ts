export interface AgentPublic {
  agent_id: string;
  full_name: string;
  age: number;
  occupation: string;
  traits: string[];
  portrait: string | null;
  home_location_id: string | null;
  work_location_id: string | null;
  routine_summary: string;
  is_victim: boolean;
}

export interface LocationPublic {
  location_id: string;
  name: string;
  description: string;
  connected_location_ids: string[];
  visibility_type: "public" | "private";
}

export interface CaseOverview {
  case_id: string;
  title: string;
  overview_text: string;
  victim: AgentPublic;
  discovery_time: string;
  discovered_by: AgentPublic;
  discovery_location: LocationPublic;
  sim_start_time: string;
  murder_window: [string, string];
}

export interface EventPublic {
  event_id: string;
  time: string;
  location_id: string;
  agent_ids: string[];
  event_type: string;
  description: string;
  visibility: "public" | "public_partial" | "private";
  importance: number;
  pinned: boolean;
}

export interface CluePublic {
  clue_id: string;
  title: string;
  clue_type: string;
  description: string;
  strength: "weak" | "medium" | "strong" | "critical";
  reliability: number;
  ambiguity: "low" | "medium" | "high";
  linked_event_ids: string[];
  linked_agent_ids: string[];
  linked_location_ids: string[];
  linked_object_ids: string[];
}

export interface ClaimPublic {
  claim_id: string;
  speaker_agent_id: string;
  claim_text: string;
  claim_type: string;
  time_reference: string | null;
  location_reference_id: string | null;
  player_known_status: "claimed" | "disputed" | "confirmed";
}

export type QuestionType =
  | "alibi"
  | "timeline"
  | "last_seen_victim"
  | "relationship"
  | "evidence"
  | "location";

export interface AskResult {
  question_text: string;
  answer_text: string;
  answer_type: string;
  emotional_shift: string | null;
  new_claims: ClaimPublic[];
  revealed_clues: CluePublic[];
  suggested_followups: string[];
}

export interface TranscriptMessage {
  speaker: "player" | "agent";
  text: string;
  question_type: QuestionType | null;
  generated_claim_ids: string[];
  revealed_clue_ids: string[];
}

export type NoteType =
  | "manual"
  | "event"
  | "evidence"
  | "interview"
  | "contradiction"
  | "theory"
  | "question";

export interface Note {
  note_id: string;
  note_type: NoteType;
  title: string;
  body: string;
  linked_agent_ids: string[];
  linked_clue_ids: string[];
  linked_event_ids: string[];
  linked_claim_ids: string[];
  player_tags: string[];
  status: "open" | "unresolved" | "resolved";
  pinned_to_agent_id: string | null;
}

export type SuspicionLevel =
  | "unknown"
  | "person_of_interest"
  | "suspect"
  | "prime_suspect"
  | "likely_innocent"
  | "cleared";

export interface BoardSuspect {
  agent: AgentPublic;
  suspicion: SuspicionLevel;
  claims: ClaimPublic[];
  linked_clues: CluePublic[];
  pinned_notes: Note[];
}

export interface Board {
  suspects: BoardSuspect[];
  contradiction_notes: Note[];
  discovered_clue_count: number;
  total_discoverable_clues: number;
}

export interface InspectResult {
  location: LocationPublic;
  new_clues: CluePublic[];
  known_clues: CluePublic[];
  hint: string | null;
}
