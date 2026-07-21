export interface PortraitState {
  calm: string | null;
  defensive: string | null;
  cracking: string | null;
  deceased?: string | null;
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
  is_background: boolean;
}

export interface LocationPublic {
  location_id: string;
  name: string;
  description: string;
  connected_location_ids: string[];
  visibility_type: "public" | "private";
  illustration: string | null;
  building_art?: { exterior: string | null; interior: string | null };
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
  // Visual rotation in degrees around the rect centre (matches the art's
  // camera angle). Axis-aligned x/y/width/height stay the logical bounds.
  rotation?: number;
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
  // Bounds for the internal (roofless close-up) map view; null inherits
  // map_bounds. Only canonical-overworld cases populate this.
  map_bounds_internal?: MapBounds | null;
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
  map: {
    asset: string;
    image: string;
    // Optional mosaic of the map art (rows top->bottom, cols left->right).
    // When present, renderers prefer it over the single `image`.
    image_tiles?: { cols: number; rows: number; urls: string[][] };
    zoom_image_tiles?: { threshold: number; urls: string[][] };
    width: number;
    height: number;
    definition_id?: string;
    tile_size?: number;
    grid?: { cols: number; rows: number };
    origin?: string;
    base_palette?: string;
    lighting_overlay?: string;
  };
  visual?: MapVisualContract;
  time_range: { start: string; end: string };
  locations: MapLocation[];
  agents: MapAgent[];
  events: MapEvent[];
}

export interface MapVisualObject {
  object_id: string;
  semantic_asset_id: string;
  category: string;
  location_id: string | null;
  anchor: MapPosition;
  position: MapPosition;
  state: "hidden" | "visible" | "discovered";
  marker_state: "suppressed" | "active";
  render_mode: "suppressed" | "background_prop" | "evidence_marker";
  safe_to_render: boolean;
  glyph: string | null;
  clue_ids: string[];
  overlay_ids: string[];
  damaged: boolean;
}

export interface MapLightOverlay {
  id: string;
  semantic_asset_id:
    | "light_streetlamp_pool"
    | "light_window_warm"
    | "light_window_cool"
    | "light_pub_window_glow"
    | "light_fireplace_glow";
  location_id: string | null;
  x: number;
  y: number;
  width: number;
  height: number;
  from: string;
  to: string;
  opacity?: number;
  internal_only?: boolean;
  exterior_only?: boolean;
  // Optional overrides measured against the internal (roofless interior)
  // mosaic tile, which is a different painted asset than the exterior one.
  // When present and the map is zoomed past the interior threshold, these
  // replace the exterior x/y/width/height/semantic_asset_id/opacity above.
  x_internal?: number;
  y_internal?: number;
  width_internal?: number;
  height_internal?: number;
  semantic_asset_id_internal?: MapLightOverlay["semantic_asset_id"];
  opacity_internal?: number;
}

export interface MapAmbientSprite {
  id: string;
  asset_id:
    | "water_shimmer"
    | "fish_ripple_loop"
    | "chimney_smoke"
    | "lamp_flicker"
    | "drifting_mist"
    | "birds_crossing"
    | "warm_motes";
  x: number;
  y: number;
  width: number;
  height: number;
  opacity?: number;
  from?: string;
  to?: string;
}

export interface MapVisualContract {
  mode: "canonical_pilot" | "canonical_overworld" | "case_art" | "legacy_fallback";
  definition_id: string;
  visible_location_ids: string[] | null;
  overlays: string[];
  light_overlays?: MapLightOverlay[];
  ambient_sprites?: MapAmbientSprite[];
  crop_padding_by_location?: Record<string, number>;
  object_visuals?: MapVisualObject[];
  objects: MapVisualObject[];
  adjacency: Record<string, string[]>;
  canonical_locations: Record<string, {
    bounds: MapBounds;
    bounds_internal?: MapBounds;
    position: MapPosition;
    layer: "exterior" | "interior";
    display_name?: string;
    function_tag?: string;
    building_role?: string;
    case_ids?: string[];
    parent_location_id?: string;
    zoom_behavior?: "external" | "internal" | "external_to_internal";
  }>;
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
  /** Whose whereabouts this statement pins down (the speaker, unless they spoke about someone else). */
  about_agent_id: string;
  /** false = the speaker insists that person was NOT there. */
  asserts_presence: boolean;
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

/** By default `suggestions` is empty and only `contradiction_count` is populated: the player is
 *  told a contradiction exists, not which one. Asking for the pairings is an explicit,
 *  counted hint (`reveal=true`). */
export interface ChallengeSuggestionsResponse {
  contradiction_count: number;
  revealed: boolean;
  hints_taken: number;
  suggestions: ChallengeSuggestion[];
}

export interface RevealedMemory {
  memory_id: string;
  summary: string;
}

export type TellCategory =
  | "gaze"
  | "voice"
  | "hands"
  | "posture"
  | "timing"
  | "overexplaining";

export type TellIntensity = "subtle" | "noticeable" | "strong";

export interface ObservableTell {
  tell_id: string;
  agent_id: string;
  cue: string;
  category: TellCategory;
  intensity: TellIntensity;
  source: "interview" | "challenge" | "observe";
}

/** The result of spending an Observe action on a suspect: a sharper behavioural
 *  read, built only from player-visible signals — never a lie detector. */
export interface ObservationRead {
  observation_id: string;
  agent_id: string;
  text: string;
  category: TellCategory;
  intensity: TellIntensity;
  /** How their manner compares with the remembered calm baseline. */
  baseline_state?: "noted" | "consistent" | "shifted" | "broken" | null;
}

export interface ChallengeResult {
  challenge_id: string;
  target_agent_id: string;
  challenged_claim_id: string;
  evidence_clue_ids: string[];
  evidence_claim_ids: string[];
  /** Set when the player caught two statements that cannot both be true. */
  testimony_conflict: string | null;
  outcome: ChallengeOutcome;
  response_text: string;
  deterministic_response_text?: string;
  emotional_shift: string | null;
  observable_tells: ObservableTell[];
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
  observable_tells: ObservableTell[];
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
  observable_tells?: ObservableTell[];
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

export interface EpilogueCard {
  agent_id: string;
  agent_name: string;
  text: string;
}


export interface AccusationResult {
  accusation_id: string;
  case_id: string;
  accused_agent_id: string;
  accused_name: string;
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
  epilogues: EpilogueCard[];
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

export interface LlmSettingsSaved {
  provider: "fake" | "auto" | "openai_compatible";
  base_url: string | null;
  api_key: string | null;
  model: string | null;
  dialogue_enabled: boolean;
}

export interface LlmSettingsEffective {
  provider: string;
  base_url: string | null;
  model: string | null;
  configured: boolean;
  fallback_reason: string | null;
  detected_source: string | null;
  dialogue_enabled: boolean;
}

export interface LlmSettingsResponse {
  saved: LlmSettingsSaved | null;
  effective: LlmSettingsEffective;
}

export interface LlmProbeResult {
  found: boolean;
  host_id?: string;
  endpoint?: string;
  model?: string;
  source?: string;
}

export interface LlmTestResult {
  ok: boolean;
  reply?: string;
  elapsed_ms?: number;
  nonce?: string;
  error?: string;
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
