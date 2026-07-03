export interface PortraitState {
  calm: string | null;
  defensive: string | null;
  cracking: string | null;
}

export interface AgentPublic {
  agent_id: string;
  full_name: string;
  age: number;
  occupation: string;
  traits: string[];
  portrait: string | null;
  portrait_art: PortraitState | null;
  sprite_asset: string | null;
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
  scene_description: string;
}

export interface MapPosition {
  x: number;
  y: number;
}

export interface MapBounds {
  x: number;
  y: number;
  width: number;
  height: number;
}

export type VisualEventType =
  | "agent_move"
  | "agent_present"
  | "object_marker"
  | "sound_marker"
  | "body_discovery"
  | "unknown_figure"
  | "hidden_activity"
  | "conversation_marker"
  | "clue_marker";

export interface MapLocation extends LocationPublic {
  map_position: MapPosition | null;
  map_bounds: MapBounds | null;
  visual_layer: "exterior" | "interior" | null;
}

export interface MapAgent extends AgentPublic {
  sprite_id: string;
  sprite_asset: string;
}

export interface MapEvent {
  event_id: string;
  time: string;
  location_id: string;
  agent_ids: string[];
  event_type: string;
  description: string;
  visibility: "public" | "public_partial" | "private" | "hidden";
  importance: number;
  visual_event_type: VisualEventType;
  from_location_id: string | null;
  to_location_id: string | null;
  pinned?: boolean;
  was_hidden?: boolean;
}

export interface MapReplayData {
  case_id: string;
  mode: "player" | "truth";
  map: { asset: string; image: string; width: number; height: number };
  time_range: { start: string; end: string };
  locations: MapLocation[];
  agents: MapAgent[];
  events: MapEvent[];
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

export type ClaimStatus =
  | "claimed"
  | "disputed"
  | "reframed"
  | "confirmed"
  | "resolved";

export interface ClaimPublic {
  claim_id: string;
  speaker_agent_id: string;
  claim_text: string;
  claim_type: string;
  time_reference: string | null;
  location_reference_id: string | null;
  player_known_status: ClaimStatus;
}

export type ChallengeOutcome =
  | "deny"
  | "deflect"
  | "reframe"
  | "partial_admission"
  | "reveal_innocent_secret"
  | "contradiction_locked";

export interface ChallengeSuggestion {
  target_agent_id: string;
  challenged_claim_id: string;
  claim_text: string;
  claim_status: ClaimStatus;
  evidence_clue_id: string;
  evidence_title: string;
}

export interface RevealedMemory {
  memory_id: string;
  summary: string;
}

export interface ChallengeResult {
  challenge_id: string;
  target_agent_id: string;
  challenged_claim_id: string;
  evidence_clue_ids: string[];
  outcome: ChallengeOutcome;
  response_text: string;
  deterministic_response_text?: string;
  emotional_shift: string | null;
  new_claims: ClaimPublic[];
  revealed_clues: CluePublic[];
  revealed_memories: RevealedMemory[];
  pressure_delta: number;
  pressure_level: number;
  created_note_ids: string[];
  duplicate: boolean;
  llm_rewrite_used?: boolean;
  llm_rewrite_fallback?: boolean;
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
  deterministic_answer_text?: string;
  answer_type: string;
  emotional_shift: string | null;
  new_claims: ClaimPublic[];
  revealed_clues: CluePublic[];
  suggested_followups: string[];
  llm_rewrite_used?: boolean;
  llm_rewrite_fallback?: boolean;
}

export interface TranscriptMessage {
  speaker: "player" | "agent";
  text: string;
  deterministic_text?: string;
  question_type: QuestionType | null;
  generated_claim_ids: string[];
  revealed_clue_ids: string[];
  llm_rewrite_used?: boolean;
  llm_rewrite_fallback?: boolean;
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
  pressure: number;
  claims: ClaimPublic[];
  linked_clues: CluePublic[];
  pinned_notes: Note[];
}

export type MarkerType =
  | "important"
  | "theory"
  | "red_herring"
  | "cleared"
  | "suspect"
  | "prime_suspect"
  | "open_question";

export interface Board {
  suspects: BoardSuspect[];
  contradiction_notes: Note[];
  discovered_clue_count: number;
  total_discoverable_clues: number;
  readiness_hints: string[];
  case_board_markers: Record<string, MarkerType[]>;
}

export interface HintsResponse {
  readiness_hints: string[];
  tutorial_hints: string[];
}

export interface ClueHotspot {
  clue_id: string;
  x: number;
  y: number;
  radius: number;
  discovery_text?: string;
  title: string;
}

export interface InspectResult {
  location: MapLocation;
  new_clues: CluePublic[];
  hidden_clues: ClueHotspot[];
  known_clues: CluePublic[];
  hint: string | null;
}

export interface TimelineEntry {
  time: string;
  description: string;
  location_name: string;
}

export interface RedHerringExplanation {
  agent_id: string;
  agent_name: string;
  looked_suspicious_because: string;
  actually_innocent_because: string;
}

export interface AccusationResult {
  accusation_id: string;
  case_id: string;
  score: number;
  killer_correct: boolean;
  motive_correct: boolean;
  method_correct: boolean;
  opportunity_correct: boolean;
  evidence_score: number;
  missed_key_clues: string[];
  false_assumptions: string[];
  explanation: string;
  verdict: string;
  true_killer_id: string;
  true_killer_name: string;
  true_motive: string;
  true_method: string;
  true_timeline: TimelineEntry[];
  key_clues_found: string[];
  key_clues_missed: string[];
  red_herring_explanations: RedHerringExplanation[];
  player_evidence_used: string[];
  detective_rating: string;
}

export interface Config {
  playtest_mode: boolean;
  llm_dialogue_enabled: boolean;
  llm_generation_available: boolean;
  llm_model: string | null;
  llm_detected_source: string | null;
}

export interface PlaytestSummary {
  case_id: string;
  case_title: string;
  case_type: string;
  mode: string;
  telemetry_event_count: number;
  player_action_count: number;
  discovered_clues: number;
  visible_clues: number;
  interviews: number;
  free_text_questions: number;
  challenges_suggested: number;
  challenges_executed: number;
  notes_created: number;
  markers_used: number;
  accusation_submitted: boolean;
  score: number | null;
  detective_rating: string | null;
}

export interface Feedback {
  understood_goal: "yes" | "mostly" | "no";
  rewind_made_sense: "yes" | "mostly" | "no";
  hints_helpfulness: "too_little" | "about_right" | "too_much" | "spoiled";
  difficulty: "too_easy" | "about_right" | "too_hard" | "confusing";
  final_reveal_fair: "yes" | "mostly" | "no";
  suspected_before_reveal: string | null;
  most_confusing_part: string | null;
  best_part: string | null;
  worst_part: string | null;
  clues_that_felt_unfair: string | null;
  free_text: string | null;
  enjoyment_score: number;
  confidence_score: number;
}
