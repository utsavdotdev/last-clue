import React, { useEffect, useState } from "react";
import {
  ArrowRight,
  ArrowsClockwise,
  BookOpen,
  Check,
  Copy,
  Eye,
  EyeSlash,
  GearSix,
  QrCode,
  ShieldWarning,
  SignOut,
  Skull,
  SpeakerHigh,
  SpeakerSlash,
  WarningOctagon,
  X,
} from "@phosphor-icons/react";
import { HostSettingsPanel } from "./components/HostSettingsPanel";
import { MatrixVisualizer } from "./components/MatrixVisualizer";
import { RulesModal } from "./components/RulesModal";
import { soundCues } from "./services/sound";
import type {
  GhostMatrixState,
  NetworkInfo,
  PrivatePlayerPayload,
  PublicGameState,
  StoredCredentials,
} from "./types/game";

const STORAGE_KEY = "last_clue_session_v1";

export const App: React.FC = () => {
  const [credentials, setCredentials] = useState<StoredCredentials | null>(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? (JSON.parse(raw) as StoredCredentials) : null;
    } catch {
      return null;
    }
  });

  const [publicState, setPublicState] = useState<PublicGameState | null>(null);
  const [privateState, setPrivateState] = useState<PrivatePlayerPayload | null>(null);
  const [networkInfo, setNetworkInfo] = useState<NetworkInfo | null>(null);
  const [wsConnected, setWsConnected] = useState(false);

  const [nicknameInput, setNicknameInput] = useState("");
  const [roomCodeInput, setRoomCodeInput] = useState("");
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  const [rulesOpen, setRulesOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [soundEnabled, setSoundEnabled] = useState(false);
  const [qrOpen, setQrOpen] = useState(false);
  const [copiedUrl, setCopiedUrl] = useState(false);

  // Gameplay local UI states
  const [cardRevealed, setCardRevealed] = useState(false);
  const [peekWordOpen, setPeekWordOpen] = useState(false);
  const [clueDraft, setClueDraft] = useState("");
  const [selectedVoteTarget, setSelectedVoteTarget] = useState<string | null>(null);
  const [finalGuessDraft, setFinalGuessDraft] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const roomParam = params.get("room");
    if (roomParam) {
      setRoomCodeInput(roomParam.toUpperCase());
    }
  }, []);

  useEffect(() => {
    const fetchInitial = async () => {
      try {
        const [netResp, stateResp] = await Promise.all([
          fetch("/api/network"),
          fetch(
            credentials
              ? `/api/state?player_id=${encodeURIComponent(
                  credentials.player_id
                )}&token=${encodeURIComponent(credentials.reconnect_token)}`
              : "/api/state"
          ),
        ]);
        if (netResp.ok) {
          const netData = (await netResp.json()) as NetworkInfo;
          setNetworkInfo(netData);
          if (!roomCodeInput) {
            setRoomCodeInput(netData.room_code);
          }
        }
        if (stateResp.ok) {
          const stData = await stateResp.json();
          setPublicState(stData.public);
          if (stData.private) {
            setPrivateState(stData.private);
          }
        }
      } catch {
        // Reconnect loop handles state
      }
    };
    void fetchInitial();
  }, [credentials]);

  useEffect(() => {
    if (!publicState) return;
    soundCues.playPhaseTransition();
    setPeekWordOpen(false);
    if (publicState.phase === "ROLE_REVEAL") {
      setCardRevealed(false);
      setClueDraft("");
      setSelectedVoteTarget(null);
      setFinalGuessDraft("");
    } else if (publicState.phase === "VOTING" || publicState.phase === "RUNOFF") {
      setSelectedVoteTarget(null);
    } else if (publicState.phase === "FINAL_GUESS") {
      soundCues.playAccusation();
    }
  }, [publicState?.phase, publicState?.round_number, publicState?.clue_round_number]);

  const wsRef = React.useRef<WebSocket | null>(null);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let timer: number | null = null;
    let cancelled = false;

    const openSocket = () => {
      if (cancelled) return;
      const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
      const query = credentials
        ? `?player_id=${encodeURIComponent(
            credentials.player_id
          )}&token=${encodeURIComponent(credentials.reconnect_token)}`
        : "";
      socket = new WebSocket(`${proto}//${window.location.host}/ws${query}`);
      wsRef.current = socket;

      socket.onopen = () => {
        setWsConnected(true);
      };

      socket.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          if (data.type === "state_sync") {
            setPublicState(data.public);
            setPrivateState(data.private || null);
          } else if (data.type === "error") {
            setErrorBanner(data.message);
          }
        } catch {
          // Ignore malformed frame
        }
      };

      socket.onclose = (ev) => {
        setWsConnected(false);
        if (ev.code === 4001) {
          localStorage.removeItem(STORAGE_KEY);
          setCredentials(null);
          setPrivateState(null);
          return;
        }
        if (!cancelled) {
          timer = window.setTimeout(openSocket, 1400);
        }
      };
    };

    openSocket();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
      if (socket) socket.close();
    };
  }, [credentials]);

  const sendWsAction = (payload: Record<string, unknown>) => {
    setErrorBanner(null);
    soundCues.playTap();
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(payload));
    } else {
      setErrorBanner("Reconnecting... Try again in a moment.");
    }
  };

  const handleJoin = async (asHost: boolean) => {
    setErrorBanner(null);
    if (!nicknameInput.trim()) {
      setErrorBanner("Enter your nickname first.");
      return;
    }
    try {
      const resp = await fetch("/api/join", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nickname: nicknameInput.trim(),
          room_code: roomCodeInput.trim() || undefined,
          as_host: asHost,
        }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        setErrorBanner(data.detail || "Unable to join room.");
        return;
      }
      const creds: StoredCredentials = {
        player_id: data.player_id,
        nickname: data.nickname,
        room_code: data.room_code,
        reconnect_token: data.reconnect_token,
        is_host: data.is_host,
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(creds));
      setCredentials(creds);
    } catch {
      setErrorBanner("Network error while joining room.");
    }
  };

  const handleLeaveRoom = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "leave_room" }));
    }
    localStorage.removeItem(STORAGE_KEY);
    setCredentials(null);
    setPrivateState(null);
  };

  const toggleSound = () => {
    const next = !soundEnabled;
    setSoundEnabled(next);
    soundCues.enabled = next;
    if (next) soundCues.playTap();
  };

  const handleCopyJoinUrl = async () => {
    if (!networkInfo) return;
    try {
      await navigator.clipboard.writeText(networkInfo.join_url);
      setCopiedUrl(true);
      setTimeout(() => setCopiedUrl(false), 2000);
    } catch {
      // Ignore clipboard failures on non-HTTPS LAN
    }
  };

  const handleTriggerMatrixTest = (state: GhostMatrixState) => {
    sendWsAction({ type: "test_matrix_state", state });
  };

  const isHost = Boolean(privateState?.is_host || credentials?.is_host);
  const currentPhase = publicState?.phase || "LOBBY";
  const playerMap = new Map(
    (publicState?.players || []).map((p) => [p.player_id, p])
  );
  const connectedCount = (publicState?.players || []).filter((p) => p.connected).length;

  return (
    <div className="app-shell">
      {/* Compact Party-Game Header */}
      <header className="top-nav">
        <div className="top-nav-inner">
          <div className="brand-cluster">
            <Skull size={20} weight="fill" className="brand-icon" />
            <span className="brand-title">The Last Clue</span>
            {publicState && (
              <span className="room-pill">{publicState.room_code}</span>
            )}
          </div>

          <div className="nav-actions">
            <span
              className={wsConnected ? "status-dot dot-online" : "status-dot dot-offline"}
              title={wsConnected ? "Connected" : "Reconnecting"}
            />

            {credentials && privateState?.role && currentPhase !== "LOBBY" && currentPhase !== "ROLE_REVEAL" && currentPhase !== "RESULTS" && (
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => setPeekWordOpen((v) => !v)}
              >
                <Eye size={15} />
                <span>My Card</span>
              </button>
            )}

            <button
              type="button"
              className="icon-btn"
              onClick={() => setDrawerOpen(true)}
              aria-label="UNO Q Matrix & Settings"
              title="UNO Q Matrix & Settings"
            >
              <GearSix size={18} />
            </button>

            <button
              type="button"
              className="icon-btn"
              onClick={toggleSound}
              aria-label={soundEnabled ? "Mute sound" : "Enable sound"}
            >
              {soundEnabled ? <SpeakerHigh size={18} /> : <SpeakerSlash size={18} />}
            </button>

            <button
              type="button"
              className="icon-btn"
              onClick={() => setRulesOpen(true)}
              aria-label="How to Play"
              title="How to Play"
            >
              <BookOpen size={18} />
            </button>

            {credentials && (
              <button
                type="button"
                className="icon-btn"
                onClick={handleLeaveRoom}
                aria-label="Leave room"
                title="Leave room"
              >
                <SignOut size={18} />
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Centered Mobile-First Stage */}
      <main className="party-container">
        {errorBanner && (
          <div className="error-banner" role="alert">
            <WarningOctagon size={18} />
            <span>{errorBanner}</span>
            <button
              type="button"
              className="error-dismiss"
              onClick={() => setErrorBanner(null)}
            >
              <X size={16} />
            </button>
          </div>
        )}

        {/* Quick Peek Popover during Clue / Discussion / Voting */}
        {peekWordOpen && privateState?.role && (
          <div className="peek-card-banner">
            <div>
              <span className="mono-tag">{privateState.category}</span>
              {privateState.role === "IMPOSTER" ? (
                <strong className="danger-text">You are the IMPOSTER</strong>
              ) : (
                <strong>
                  Word: <span className="cyan-text">{privateState.secret_word}</span>
                </strong>
              )}
            </div>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => setPeekWordOpen(false)}
            >
              Hide
            </button>
          </div>
        )}

        {/* SCREEN 1: JOIN / HOST SCREEN */}
        {!credentials ? (
          <section className="card-screen">
            <div className="hero-header">
              <span className="mono-pill">MULTIPLAYER HORROR WORD GAME</span>
              <h1 className="screen-title">Guess the Imposter</h1>
              <p className="screen-subtitle">
                Everyone gets the same secret horror word except one player. Give clues,
                blend in, and expose the Imposter.
              </p>
            </div>

            <form
              className="stack-form"
              onSubmit={(e) => {
                e.preventDefault();
                void handleJoin(false);
              }}
            >
              <div className="form-field">
                <label htmlFor="nickname-input">Your Name</label>
                <input
                  id="nickname-input"
                  type="text"
                  className="input-control"
                  maxLength={18}
                  required
                  autoFocus
                  value={nicknameInput}
                  onChange={(e) => setNicknameInput(e.target.value)}
                  placeholder="Enter your name"
                />
              </div>

              <div className="form-field">
                <label htmlFor="room-code-input">Room Code</label>
                <input
                  id="room-code-input"
                  type="text"
                  className="input-control mono-input"
                  maxLength={8}
                  value={roomCodeInput}
                  onChange={(e) => setRoomCodeInput(e.target.value.toUpperCase())}
                  placeholder={publicState?.room_code || "HAUNT6"}
                />
              </div>

              <div className="action-stack">
                <button type="submit" className="btn btn-primary full-width">
                  <span>Join Game</span>
                  <ArrowRight size={18} />
                </button>
                <button
                  type="button"
                  className="btn btn-secondary full-width"
                  onClick={() => void handleJoin(true)}
                >
                  <span>Host Game</span>
                </button>
              </div>
            </form>
          </section>
        ) : (
          <>
            {/* PHASE 1: LOBBY */}
            {currentPhase === "LOBBY" && publicState && (
              <section className="card-screen">
                <div className="screen-top-row">
                  <div>
                    <span className="mono-tag">ROOM {publicState.room_code}</span>
                    <h1 className="screen-title">Lobby</h1>
                  </div>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => setQrOpen((v) => !v)}
                  >
                    <QrCode size={16} />
                    <span>{qrOpen ? "Hide QR" : "Invite QR"}</span>
                  </button>
                </div>

                {qrOpen && networkInfo && (
                  <div className="qr-invite-box">
                    <div
                      className="qr-svg-wrap"
                      dangerouslySetInnerHTML={{ __html: networkInfo.qr_svg }}
                    />
                    <div className="qr-invite-meta">
                      <code className="join-url-code">{networkInfo.join_url}</code>
                      <button
                        type="button"
                        className="btn btn-ghost btn-sm"
                        onClick={handleCopyJoinUrl}
                      >
                        <Copy size={14} />
                        <span>{copiedUrl ? "Copied" : "Copy Link"}</span>
                      </button>
                    </div>
                  </div>
                )}

                {isHost && (
                  <div className="form-field">
                    <label htmlFor="lobby-category">Theme</label>
                    <select
                      id="lobby-category"
                      className="input-control"
                      value={publicState.selected_category || "random"}
                      onChange={(e) =>
                        sendWsAction({
                          type: "update_settings",
                          selected_category: e.target.value,
                        })
                      }
                    >
                      <option value="random">Random Horror Theme</option>
                      {publicState.available_categories.map((cat) => (
                        <option key={cat} value={cat}>
                          {cat}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                <div className="section-block">
                  <div className="row-between">
                    <span className="field-label">
                      Players ({connectedCount}/{publicState.max_players})
                    </span>
                    <span className="helper-label">Need {publicState.min_players}+ to start</span>
                  </div>

                  <ul className="player-list">
                    {publicState.players.map((p) => (
                      <li
                        key={p.player_id}
                        className={
                          p.connected ? "player-chip" : "player-chip player-chip-offline"
                        }
                      >
                        <span className="player-chip-name">
                          {p.nickname}
                          {p.player_id === credentials.player_id && " (You)"}
                        </span>
                        <div className="row-center gap-2">
                          {p.is_host && <span className="host-tag">HOST</span>}
                          {p.score > 0 && <span className="mono-score">{p.score} pts</span>}
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>

                {isHost ? (
                  <button
                    type="button"
                    className="btn btn-primary full-width"
                    disabled={!publicState.host_ready}
                    onClick={() => sendWsAction({ type: "start_round" })}
                  >
                    <span>
                      {publicState.host_ready
                        ? "Start Game"
                        : `Waiting for ${Math.max(
                            0,
                            publicState.min_players - connectedCount
                          )} more...`}
                    </span>
                    <ArrowRight size={18} />
                  </button>
                ) : (
                  <div className="status-banner">Waiting for host to start the game...</div>
                )}
              </section>
            )}

            {/* PHASE 2: SECRET ROLE REVEAL (imposter.app style tap/hold card) */}
            {currentPhase === "ROLE_REVEAL" && publicState && privateState && (
              <section className="card-screen">
                <div className="center-header">
                  <span className="mono-pill">
                    {privateState.category || publicState.active_category}
                  </span>
                  <h1 className="screen-title">Your Secret Role</h1>
                  <p className="screen-subtitle">
                    Tap your card to reveal. Make sure no one else sees your screen.
                  </p>
                </div>

                <button
                  type="button"
                  className={
                    cardRevealed
                      ? privateState.role === "IMPOSTER"
                        ? "tap-role-card tap-role-imposter"
                        : "tap-role-card tap-role-survivor"
                      : "tap-role-card tap-role-hidden"
                  }
                  onClick={() => setCardRevealed((v) => !v)}
                >
                  {cardRevealed ? (
                    <div className="tap-role-content">
                      <span className="role-pill">
                        {privateState.role === "IMPOSTER" ? (
                          <>
                            <ShieldWarning size={16} /> IMPOSTER
                          </>
                        ) : (
                          <>
                            <Check size={16} /> SURVIVOR
                          </>
                        )}
                      </span>

                      {privateState.role === "SURVIVOR" ? (
                        <>
                          <span className="helper-label">SECRET WORD</span>
                          <div className="hero-word">{privateState.secret_word}</div>
                          <span className="tap-hint">Tap card to hide</span>
                        </>
                      ) : (
                        <>
                          <div className="hero-word imposter-word">BLUFF</div>
                          <p className="imposter-short-hint">
                            You do not know the secret word. Use the category (
                            <strong>{privateState.category}</strong>) to blend in.
                          </p>
                          <span className="tap-hint">Tap card to hide</span>
                        </>
                      )}
                    </div>
                  ) : (
                    <div className="tap-role-content">
                      <EyeSlash size={36} className="muted-icon" />
                      <span className="tap-card-title">Tap to Reveal Card</span>
                      <span className="tap-hint">Keep hidden from other players</span>
                    </div>
                  )}
                </button>

                {playerMap.get(credentials.player_id)?.ready_in_reveal ? (
                  <div className="status-banner">
                    Ready ({publicState.players.filter((p) => p.ready_in_reveal).length}/
                    {publicState.speaking_order.length})
                  </div>
                ) : (
                  <button
                    type="button"
                    className="btn btn-primary full-width"
                    onClick={() => {
                      setCardRevealed(false);
                      sendWsAction({ type: "acknowledge_role" });
                    }}
                  >
                    <span>Got It, Ready</span>
                    <ArrowRight size={18} />
                  </button>
                )}

                {isHost && (
                  <button
                    type="button"
                    className="btn btn-ghost full-width"
                    onClick={() => sendWsAction({ type: "begin_clue_round" })}
                  >
                    Start Clue Round Now
                  </button>
                )}
              </section>
            )}

            {/* PHASE 3: CLUE ROUND */}
            {currentPhase === "CLUE_ROUND" && publicState && (
              <section className="card-screen">
                <div className="screen-top-row">
                  <div>
                    <span className="mono-tag">
                      CLUE ROUND {publicState.clue_round_number} ·{" "}
                      {publicState.active_category}
                    </span>
                    <h1 className="screen-title">
                      {publicState.current_speaker_id === credentials.player_id
                        ? "Your Turn"
                        : `${
                            playerMap.get(publicState.current_speaker_id || "")
                              ?.nickname || "Player"
                          }'s Turn`}
                    </h1>
                  </div>
                </div>

                {publicState.current_speaker_id === credentials.player_id ? (
                  <form
                    className="stack-form"
                    onSubmit={(e) => {
                      e.preventDefault();
                      if (!clueDraft.trim()) return;
                      sendWsAction({
                        type: "submit_clue",
                        clue: clueDraft.trim(),
                      });
                      setClueDraft("");
                    }}
                  >
                    <div className="form-field">
                      <input
                        id="clue-input"
                        type="text"
                        className="input-control input-large"
                        maxLength={40}
                        autoFocus
                        required
                        value={clueDraft}
                        onChange={(e) => setClueDraft(e.target.value)}
                        placeholder="Enter one-word or short clue..."
                      />
                    </div>
                    <button type="submit" className="btn btn-primary full-width">
                      <span>Submit Clue</span>
                      <ArrowRight size={18} />
                    </button>
                  </form>
                ) : (
                  <div className="status-banner">
                    Waiting for{" "}
                    <strong>
                      {playerMap.get(publicState.current_speaker_id || "")?.nickname}
                    </strong>{" "}
                    to give a clue...
                  </div>
                )}

                <div className="speaker-pills">
                  {publicState.speaking_order.map((pid, idx) => {
                    const p = playerMap.get(pid);
                    const isCurrent = pid === publicState.current_speaker_id;
                    return (
                      <span
                        key={pid}
                        className={
                          p?.has_submitted_clue
                            ? "speaker-chip speaker-done"
                            : isCurrent
                            ? "speaker-chip speaker-active"
                            : "speaker-chip"
                        }
                      >
                        {idx + 1}. {p?.nickname || pid}
                      </span>
                    );
                  })}
                </div>

                {publicState.clues.length > 0 && (
                  <div className="section-block">
                    <span className="field-label">Submitted Clues</span>
                    <ul className="clue-list">
                      {publicState.clues.map((c) => (
                        <li key={c.turn_index} className="clue-row">
                          <span className="clue-author">
                            {c.nickname}
                            {publicState.clue_round_number > 1 && (
                              <span className="clue-pass-tag">R{c.round_pass}</span>
                            )}
                          </span>
                          <span className="clue-text">{c.clue}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {isHost && (
                  <button
                    type="button"
                    className="btn btn-ghost full-width"
                    onClick={() => sendWsAction({ type: "skip_speaker" })}
                  >
                    Skip Inactive Speaker
                  </button>
                )}
              </section>
            )}

            {/* PHASE 4: POST-CLUE DECISION (Start Voting vs Another Clue Round) */}
            {currentPhase === "DISCUSSION" && publicState && (
              <section className="card-screen">
                <div className="screen-top-row">
                  <div>
                    <span className="mono-tag">
                      CLUE ROUND {publicState.clue_round_number} COMPLETE ·{" "}
                      {publicState.active_category}
                    </span>
                    <h1 className="screen-title">Ready to Vote?</h1>
                  </div>
                </div>

                <p className="screen-subtitle">
                  Discuss the clues below. Vote now to accuse the Imposter, or play another
                  clue round for more information.
                </p>

                <ul className="clue-list">
                  {publicState.clues.map((c) => (
                    <li key={c.turn_index} className="clue-row">
                      <span className="clue-author">
                        {c.nickname}
                        {publicState.clue_round_number > 1 && (
                          <span className="clue-pass-tag">R{c.round_pass}</span>
                        )}
                      </span>
                      <span className="clue-text">{c.clue}</span>
                    </li>
                  ))}
                </ul>

                {isHost ? (
                  <div className="action-stack">
                    <button
                      type="button"
                      className="btn btn-primary full-width"
                      onClick={() => sendWsAction({ type: "begin_voting" })}
                    >
                      <span>Start Voting</span>
                      <ArrowRight size={18} />
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary full-width"
                      onClick={() => sendWsAction({ type: "another_clue_round" })}
                    >
                      <ArrowsClockwise size={18} />
                      <span>Another Clue Round</span>
                    </button>
                  </div>
                ) : (
                  <div className="status-banner">
                    Host is choosing: <strong>Start Voting</strong> or{" "}
                    <strong>Another Clue Round</strong>...
                  </div>
                )}
              </section>
            )}

            {/* PHASE 5 & RUNOFF: SECRET VOTING */}
            {(currentPhase === "VOTING" || currentPhase === "RUNOFF") &&
              publicState && (
                <section className="card-screen">
                  <div className="screen-top-row">
                    <div>
                      <span className="mono-tag">
                        {currentPhase === "RUNOFF" ? "TIE-BREAKER RUNOFF" : "SECRET VOTE"}
                      </span>
                      <h1 className="screen-title">Who is the Imposter?</h1>
                    </div>
                    <span className="mono-badge">
                      {publicState.votes_cast_count}/{publicState.eligible_voters_count} Voted
                    </span>
                  </div>

                  {privateState?.has_voted_for ? (
                    <div className="status-banner">
                      Vote locked for{" "}
                      <strong>
                        {playerMap.get(privateState.has_voted_for)?.nickname || "Player"}
                      </strong>
                      . Waiting for others...
                    </div>
                  ) : (
                    <div className="action-stack">
                      <div className="vote-targets-grid">
                        {publicState.speaking_order
                          .filter((pid) => pid !== credentials.player_id)
                          .filter(
                            (pid) =>
                              currentPhase !== "RUNOFF" ||
                              publicState.runoff_candidates.includes(pid)
                          )
                          .map((pid) => {
                            const p = playerMap.get(pid);
                            const playerClues = publicState.clues
                              .filter((c) => c.player_id === pid)
                              .map((c) => c.clue)
                              .join(" · ");
                            const isSelected = selectedVoteTarget === pid;
                            return (
                              <button
                                key={pid}
                                type="button"
                                className={
                                  isSelected
                                    ? "vote-target-btn vote-target-selected"
                                    : "vote-target-btn"
                                }
                                onClick={() => setSelectedVoteTarget(pid)}
                              >
                                <div className="row-between">
                                  <span className="vote-name">{p?.nickname || pid}</span>
                                  {isSelected && <Check size={18} className="danger-text" />}
                                </div>
                                {playerClues && (
                                  <div className="vote-target-clue">{playerClues}</div>
                                )}
                              </button>
                            );
                          })}
                      </div>

                      <button
                        type="button"
                        className="btn btn-danger full-width"
                        disabled={!selectedVoteTarget}
                        onClick={() => {
                          if (!selectedVoteTarget) return;
                          sendWsAction({
                            type: "cast_vote",
                            target_id: selectedVoteTarget,
                          });
                        }}
                      >
                        <span>Submit Vote</span>
                        <ArrowRight size={18} />
                      </button>
                    </div>
                  )}

                  {isHost && (
                    <button
                      type="button"
                      className="btn btn-ghost full-width"
                      onClick={() => sendWsAction({ type: "finalize_voting" })}
                    >
                      Tally Votes Now
                    </button>
                  )}
                </section>
              )}

            {/* PHASE 6: IMPOSTER FINAL GUESS */}
            {currentPhase === "FINAL_GUESS" && publicState && (
              <section className="card-screen">
                <div className="center-header">
                  <span className="mono-pill danger-pill">IMPOSTER CAUGHT</span>
                  <h1 className="screen-title">
                    {playerMap.get(publicState.accused_player_id || "")?.nickname} Was Caught!
                  </h1>
                </div>

                {privateState?.can_submit_final_guess ? (
                  <form
                    className="stack-form"
                    onSubmit={(e) => {
                      e.preventDefault();
                      if (!finalGuessDraft.trim()) return;
                      sendWsAction({
                        type: "submit_final_guess",
                        guess: finalGuessDraft.trim(),
                      });
                    }}
                  >
                    <p className="screen-subtitle">
                      Guess the secret word in{" "}
                      <strong>{publicState.active_category}</strong> to steal the win.
                    </p>

                    <div className="form-field">
                      <input
                        id="final-guess-input"
                        type="text"
                        className="input-control input-large"
                        maxLength={48}
                        autoFocus
                        required
                        value={finalGuessDraft}
                        onChange={(e) => setFinalGuessDraft(e.target.value)}
                        placeholder="Guess the secret word..."
                      />
                    </div>

                    <button type="submit" className="btn btn-danger full-width">
                      <span>Submit Final Guess</span>
                      <ArrowRight size={18} />
                    </button>
                  </form>
                ) : (
                  <div className="status-banner">
                    Waiting for{" "}
                    <strong>
                      {playerMap.get(publicState.accused_player_id || "")?.nickname}
                    </strong>{" "}
                    to guess the secret word...
                  </div>
                )}
              </section>
            )}

            {/* PHASE 7: RESULTS & REPLAY */}
            {currentPhase === "RESULTS" && publicState?.outcome && (
              <section className="card-screen">
                <div className="center-header">
                  <span
                    className={
                      publicState.outcome.winner === "SURVIVORS"
                        ? "winner-banner winner-survivors"
                        : "winner-banner winner-imposter"
                    }
                  >
                    {publicState.outcome.winner === "SURVIVORS"
                      ? "SURVIVORS WIN"
                      : "IMPOSTER WINS"}
                  </span>
                  <p className="outcome-summary">{publicState.outcome.summary_text}</p>
                </div>

                <div className="reveal-dossier-grid">
                  <div className="dossier-cell">
                    <span className="helper-label">SECRET WORD</span>
                    <strong className="dossier-val cyan-text">
                      {publicState.outcome.secret_word}
                    </strong>
                    <span className="mono-tag">{publicState.outcome.category}</span>
                  </div>

                  <div className="dossier-cell">
                    <span className="helper-label">IMPOSTER</span>
                    <strong className="dossier-val danger-text">
                      {publicState.outcome.imposter_nickname}
                    </strong>
                    {publicState.outcome.imposter_final_guess && (
                      <span className="mono-tag">
                        Guessed: “{publicState.outcome.imposter_final_guess}”
                      </span>
                    )}
                  </div>
                </div>

                <div className="section-block">
                  <span className="field-label">Scores</span>
                  <ul className="player-list">
                    {[...publicState.players]
                      .sort((a, b) => b.score - a.score)
                      .map((p, idx) => {
                        const delta =
                          publicState.outcome?.score_deltas[p.player_id] || 0;
                        return (
                          <li key={p.player_id} className="player-chip">
                            <span>
                              {idx + 1}. {p.nickname}
                              {p.player_id === publicState.outcome?.imposter_id && (
                                <span className="imposter-inline-tag">IMPOSTER</span>
                              )}
                            </span>
                            <div className="row-center gap-2">
                              {delta > 0 && <span className="score-delta">+{delta}</span>}
                              <strong className="mono-score">{p.score} pts</strong>
                            </div>
                          </li>
                        );
                      })}
                  </ul>
                </div>

                {isHost ? (
                  <div className="action-stack">
                    <button
                      type="button"
                      className="btn btn-primary full-width"
                      onClick={() => sendWsAction({ type: "play_again" })}
                    >
                      <span>Play Again</span>
                      <ArrowRight size={18} />
                    </button>
                    <div className="row-split">
                      <button
                        type="button"
                        className="btn btn-secondary full-width"
                        onClick={() => sendWsAction({ type: "return_to_lobby" })}
                      >
                        Lobby
                      </button>
                      <button
                        type="button"
                        className="btn btn-ghost full-width"
                        onClick={() => sendWsAction({ type: "reset_scores" })}
                      >
                        Reset Scores
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="status-banner">
                    Waiting for host to start the next round...
                  </div>
                )}
              </section>
            )}
          </>
        )}
      </main>

      {/* UNO Q 8x13 LED Matrix & Host Settings Modal Sheet */}
      {drawerOpen && (
        <div
          className="modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-label="UNO Q Hardware & Host Settings"
        >
          <div className="modal-sheet">
            <div className="modal-header">
              <h2 className="section-title">UNO Q Matrix &amp; Settings</h2>
              <button
                type="button"
                className="icon-btn"
                onClick={() => setDrawerOpen(false)}
                aria-label="Close settings"
              >
                <X size={20} />
              </button>
            </div>

            {publicState?.matrix && (
              <MatrixVisualizer
                matrix={publicState.matrix}
                canTestHardware={isHost}
                onTriggerTestState={handleTriggerMatrixTest}
                compact
              />
            )}

            {isHost && publicState && credentials && (
              <HostSettingsPanel
                game={publicState}
                playerId={credentials.player_id}
                token={credentials.reconnect_token}
                onUpdateSettings={(payload) =>
                  sendWsAction({ type: "update_settings", ...payload })
                }
              />
            )}
          </div>
        </div>
      )}

      <RulesModal open={rulesOpen} onClose={() => setRulesOpen(false)} />
    </div>
  );
};
