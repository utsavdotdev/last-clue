export type GamePhase =
  | "LOBBY"
  | "ROLE_REVEAL"
  | "CLUE_ROUND"
  | "DISCUSSION"
  | "VOTING"
  | "RUNOFF"
  | "FINAL_GUESS"
  | "RESULTS";

export type PlayerRole = "SURVIVOR" | "IMPOSTER";

export type WinnerSide = "SURVIVORS" | "IMPOSTER";

export type WinReason =
  | "IMPOSTER_CAUGHT_WRONG_GUESS"
  | "IMPOSTER_CAUGHT_GUESSED_WORD"
  | "IMPOSTER_ESCAPED_VOTE"
  | "IMPOSTER_ESCAPED_RUNOFF_TIE";

export type GhostMatrixState =
  | "BOOT"
  | "LOBBY"
  | "ROLES_ASSIGNED"
  | "CLUE_PHASE"
  | "VOTING_PHASE"
  | "RUNOFF"
  | "IMPOSTER_DISCOVERED"
  | "SURVIVORS_WIN"
  | "IMPOSTER_WINS"
  | "IDLE";

export type AIStatusState = "READY" | "GENERATING" | "FALLBACK" | "DISABLED";

export interface ClueSubmission {
  player_id: string;
  nickname: string;
  clue: string;
  turn_index: number;
  round_pass: number;
}

export interface PublicPlayerView {
  player_id: string;
  nickname: string;
  connected: boolean;
  score: number;
  ready_in_reveal: boolean;
  has_submitted_clue: boolean;
  has_voted: boolean;
  is_host: boolean;
}

export interface RoundOutcomeView {
  winner: WinnerSide;
  reason: WinReason;
  secret_word: string;
  category: string;
  imposter_id: string;
  imposter_nickname: string;
  accused_id: string | null;
  accused_nickname: string | null;
  imposter_final_guess: string | null;
  imposter_guessed_correctly: boolean;
  vote_counts: Record<string, number>;
  voter_breakdown: Record<string, string>;
  score_deltas: Record<string, number>;
  summary_text: string;
}

export interface AIStatusView {
  status: AIStatusState;
  model: string;
  hardware_mode: "uno_q_bridge" | "simulated";
  detail: string;
  custom_words_count: number;
}

export interface MatrixPreviewView {
  state: GhostMatrixState;
  state_code: number;
  generation: number;
  hardware_connected: boolean;
  label: string;
  pixels: number[];
}

export interface PublicGameState {
  room_code: string;
  phase: GamePhase;
  round_number: number;
  clue_round_number: number;
  min_players: number;
  max_players: number;
  players: PublicPlayerView[];
  host_ready: boolean;
  selected_category: string | null;
  available_categories: string[];
  active_category: string | null;
  round_intro: string;
  narration: string;
  speaking_order: string[];
  current_speaker_id: string | null;
  clues: ClueSubmission[];
  runoff_candidates: string[];
  accused_player_id: string | null;
  votes_cast_count: number;
  eligible_voters_count: number;
  outcome: RoundOutcomeView | null;
  ai_status: AIStatusView;
  matrix: MatrixPreviewView;
}

export interface PrivatePlayerPayload {
  player_id: string;
  nickname: string;
  is_host: boolean;
  role: PlayerRole | null;
  category: string | null;
  secret_word: string | null;
  role_briefing: string | null;
  has_voted_for: string | null;
  can_submit_final_guess: boolean;
}

export interface NetworkInfo {
  room_code: string;
  port: number;
  lan_ips: string[];
  join_url: string;
  qr_svg: string;
  hardware_connected: boolean;
}

export interface StoredCredentials {
  player_id: string;
  nickname: string;
  room_code: string;
  reconnect_token: string;
  is_host: boolean;
}
