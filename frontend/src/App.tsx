import React, { useEffect, useState } from "react";
import {
  ArrowRight,
  BookOpen,
  CheckCircle,
  Copy,
  Eye,
  EyeSlash,
  Broadcast,
  QrCode,
  ShieldWarning,
  SignOut,
  Skull,
  SpeakerHigh,
  SpeakerSlash,
  Timer,
  Users,
  WarningOctagon,
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

  const [joinMode, setJoinMode] = useState<"landing" | "host" | "join">("landing");
  const [nicknameInput, setNicknameInput] = useState("");
  const [roomCodeInput, setRoomCodeInput] = useState("");
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  const [rulesOpen, setRulesOpen] = useState(false);
  const [soundEnabled, setSoundEnabled] = useState(false);
  const [qrExpanded, setQrExpanded] = useState(false);
  const [copiedUrl, setCopiedUrl] = useState(false);

  // Phase-local UI controls
  const [holdingReveal, setHoldingReveal] = useState(false);
  const [pinnedReveal, setPinnedReveal] = useState(false);
  const [clueDraft, setClueDraft] = useState("");
  const [selectedVoteTarget, setSelectedVoteTarget] = useState<string | null>(null);
  const [finalGuessDraft, setFinalGuessDraft] = useState("");
  const [useAiIntro, setUseAiIntro] = useState(false);

  // Auto-populate room code from ?room= query param
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const roomParam = params.get("room");
    if (roomParam) {
      setRoomCodeInput(roomParam.toUpperCase());
      if (!credentials) {
        setJoinMode("join");
      }
    }
  }, [credentials]);

  // Fetch initial network info and public state
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
        // Retry handled by WebSocket loop
      }
    };
    void fetchInitial();
  }, [credentials]);

  // Reset per-round local inputs when phase changes
  useEffect(() => {
    if (!publicState) return;
    soundCues.playPhaseTransition();
    if (publicState.phase === "ROLE_REVEAL") {
      setHoldingReveal(false);
      setPinnedReveal(false);
      setClueDraft("");
      setSelectedVoteTarget(null);
      setFinalGuessDraft("");
    } else if (publicState.phase === "VOTING" || publicState.phase === "RUNOFF") {
      setSelectedVoteTarget(null);
    } else if (publicState.phase === "FINAL_GUESS") {
      soundCues.playAccusation();
    }
  }, [publicState?.phase, publicState?.round_number]);

  const wsRef = React.useRef<WebSocket | null>(null);

  // Live WebSocket connection with automatic reconnect
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
      setErrorBanner("Reconnecting to server. Please try again in a moment.");
    }
  };

  const handleJoinSubmit = async (e: React.FormEvent, asHost: boolean) => {
    e.preventDefault();
    setErrorBanner(null);
    try {
      const resp = await fetch("/api/join", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nickname: nicknameInput,
          room_code: roomCodeInput || undefined,
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
    setJoinMode("landing");
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
      // Clipboard API unavailable on some non-HTTPS LAN contexts
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

  return (
    <div className="app-shell">
      <div className="film-grain" aria-hidden="true" />

      {/* Top Instrument Navigation Bar (Single Line, <= 72px) */}
      <header className="top-nav">
        <div className="top-nav-inner">
          <div className="brand-cluster">
            <Skull size={22} weight="regular" className="brand-icon" />
            <span className="brand-title">THE LAST CLUE</span>
            {publicState && (
              <span className="room-pill">ROOM {publicState.room_code}</span>
            )}
          </div>

          <div className="nav-actions">
            <span
              className={wsConnected ? "conn-badge conn-online" : "conn-badge conn-offline"}
              title={wsConnected ? "Connected to UNO Q Server" : "Reconnecting..."}
            >
              <Broadcast size={14} />
              {wsConnected ? "LAN LIVE" : "RECONNECTING"}
            </span>

            <button
              type="button"
              className="icon-btn"
              onClick={toggleSound}
              aria-label={soundEnabled ? "Mute sound cues" : "Enable sound cues"}
              title={soundEnabled ? "Sound cues on" : "Sound cues muted"}
            >
              {soundEnabled ? <SpeakerHigh size={18} /> : <SpeakerSlash size={18} />}
            </button>

            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => setRulesOpen(true)}
            >
              <BookOpen size={16} />
              <span>Rules</span>
            </button>

            {credentials && (
              <button
                type="button"
                className="icon-btn"
                onClick={handleLeaveRoom}
                title="Leave room"
                aria-label="Leave room"
              >
                <SignOut size={18} />
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="main-container">
        {errorBanner && (
          <div className="error-banner" role="alert">
            <WarningOctagon size={18} />
            <span>{errorBanner}</span>
            <button
              type="button"
              className="error-dismiss"
              onClick={() => setErrorBanner(null)}
            >
              Dismiss
            </button>
          </div>
        )}

        {/* SCREEN 1 & 2: Unauthenticated Landing or Join/Host Screen */}
        {!credentials ? (
          <div className="split-hero-grid">
            <section className="hero-copy-col">
              <span className="mono-tag">ARDUINO UNO Q HAUNTED GAME MASTER</span>
              <h1 className="hero-headline">
                One voice in the circle does not know the secret word.
              </h1>
              <p className="hero-subtext">
                Join over local Wi-Fi on your phone. Give one clue, expose the Imposter,
                and survive their final guess while the UNO Q 8x13 LED ghost reacts in real time.
              </p>

              {joinMode === "landing" ? (
                <div className="cta-row">
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => setJoinMode("join")}
                  >
                    <span>Join Game</span>
                    <ArrowRight size={18} />
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => setJoinMode("host")}
                  >
                    <span>Host a Game</span>
                  </button>
                </div>
              ) : (
                <form
                  className="panel join-form-panel"
                  onSubmit={(e) => handleJoinSubmit(e, joinMode === "host")}
                >
                  <div className="panel-header-row">
                    <h2 className="panel-subtitle">
                      {joinMode === "host"
                        ? "Host Investigator Session"
                        : "Join Investigator Circle"}
                    </h2>
                    <button
                      type="button"
                      className="text-link-btn"
                      onClick={() => setJoinMode("landing")}
                    >
                      Back
                    </button>
                  </div>

                  <div className="form-field">
                    <label htmlFor="nickname-input">Investigator Nickname</label>
                    <input
                      id="nickname-input"
                      type="text"
                      className="input-control"
                      maxLength={18}
                      required
                      autoFocus
                      value={nicknameInput}
                      onChange={(e) => setNicknameInput(e.target.value)}
                      placeholder="e.g. Mina, Bram, Eleanor"
                    />
                    <span className="helper-label">2 to 18 characters, unique in room</span>
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

                  <div className="cta-row">
                    <button type="submit" className="btn btn-primary full-width">
                      <span>
                        {joinMode === "host" ? "Enter as Host" : "Enter Lobby"}
                      </span>
                      <ArrowRight size={18} />
                    </button>
                  </div>
                </form>
              )}
            </section>

            <aside className="hero-hardware-col">
              {publicState?.matrix && (
                <MatrixVisualizer matrix={publicState.matrix} />
              )}

              {networkInfo && (
                <section className="panel qr-compact-panel">
                  <div className="qr-row">
                    <div
                      className="qr-box-small"
                      dangerouslySetInnerHTML={{ __html: networkInfo.qr_svg }}
                    />
                    <div className="qr-meta">
                      <span className="mono-tag">LOCAL WI-FI ACCESS</span>
                      <p className="qr-url-text">{networkInfo.join_url}</p>
                      <p className="helper-label">
                        Scan with any phone connected to the same Wi-Fi network. No internet or cloud account required.
                      </p>
                    </div>
                  </div>
                </section>
              )}
            </aside>
          </div>
        ) : (
          /* AUTHENTICATED GAMEPLAY LAYOUT */
          <div className="gameplay-layout">
            {/* Phase Status & Timer Header */}
            <section className="panel phase-banner">
              <div className="phase-banner-top">
                <div>
                  <span className="mono-tag">
                    ROUND {publicState?.round_number || 0} / PHASE: {currentPhase.replace(/_/g, " ")}
                  </span>
                  <h2 className="phase-headline">
                    {publicState?.narration || "Awaiting ritual command..."}
                  </h2>
                </div>

                {publicState?.timer_seconds_remaining !== null &&
                  publicState?.timer_seconds_remaining !== undefined && (
                    <div
                      className={
                        publicState.timer_seconds_remaining <= 10
                          ? "timer-box timer-urgent"
                          : "timer-box"
                      }
                    >
                      <Timer size={18} />
                      <span className="timer-digits">
                        {String(Math.floor(publicState.timer_seconds_remaining / 60)).padStart(
                          2,
                          "0"
                        )}
                        :
                        {String(publicState.timer_seconds_remaining % 60).padStart(
                          2,
                          "0"
                        )}
                      </span>
                    </div>
                  )}
              </div>

              {publicState?.round_intro && currentPhase !== "LOBBY" && (
                <p className="round-intro-quote">“{publicState.round_intro}”</p>
              )}
            </section>

            <div className="gameplay-columns">
              {/* Primary Interactive Stage Column */}
              <div className="stage-primary-col">
                {/* PHASE 1: LOBBY */}
                {currentPhase === "LOBBY" && publicState && (
                  <section className="panel stage-panel">
                    <div className="panel-header-row">
                      <div>
                        <span className="mono-tag">WAITING FOR INVESTIGATORS</span>
                        <h3 className="section-title">
                          Lobby ({publicState.players.filter((p) => p.connected).length} /{" "}
                          {publicState.max_players} Connected)
                        </h3>
                      </div>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() => setQrExpanded(!qrExpanded)}
                      >
                        <QrCode size={18} />
                        <span>{qrExpanded ? "Hide QR" : "Show Join QR"}</span>
                      </button>
                    </div>

                    <p className="instruction-callout">
                      At least {publicState.min_players} connected players are required to begin.{" "}
                      {publicState.host_ready
                        ? "The circle is ready. The host may start the round."
                        : `Waiting for ${Math.max(
                            0,
                            publicState.min_players -
                              publicState.players.filter((p) => p.connected).length
                          )} more player(s) to join.`}
                    </p>

                    {(qrExpanded || isHost) && networkInfo && (
                      <div className="lobby-qr-card">
                        <div
                          className="qr-svg-container"
                          dangerouslySetInnerHTML={{ __html: networkInfo.qr_svg }}
                        />
                        <div className="lobby-qr-details">
                          <span className="mono-tag">SCAN OR OPEN ON PHONE</span>
                          <div className="url-copy-row">
                            <code className="join-url-code">{networkInfo.join_url}</code>
                            <button
                              type="button"
                              className="btn btn-ghost"
                              onClick={handleCopyJoinUrl}
                            >
                              <Copy size={16} />
                              <span>{copiedUrl ? "Copied" : "Copy URL"}</span>
                            </button>
                          </div>
                          <p className="helper-label">
                            Room Code: <strong>{publicState.room_code}</strong> | Active Theme:{" "}
                            <strong>{publicState.selected_category || "Random Horror Theme"}</strong>
                          </p>
                        </div>
                      </div>
                    )}

                    <ul className="player-roster-grid" aria-label="Connected players">
                      {publicState.players.map((p) => (
                        <li
                          key={p.player_id}
                          className={
                            p.connected ? "roster-card" : "roster-card roster-disconnected"
                          }
                        >
                          <div className="roster-name-row">
                            <span className="roster-name">
                              {p.nickname}
                              {p.player_id === credentials.player_id && " (You)"}
                            </span>
                            {p.is_host && <span className="host-tag">HOST</span>}
                          </div>
                          <div className="roster-meta-row">
                            <span className="mono-score">{p.score} PTS</span>
                            <span className="conn-text">
                              {p.connected ? "Connected" : "Offline"}
                            </span>
                          </div>
                        </li>
                      ))}
                    </ul>

                    {isHost ? (
                      <div className="host-action-bar">
                        <label className="checkbox-row">
                          <input
                            type="checkbox"
                            checked={useAiIntro}
                            onChange={(e) => setUseAiIntro(e.target.checked)}
                          />
                          <span>
                            Request fresh intro from on-board UNO Q LLM (falls back to built-in pack if slow)
                          </span>
                        </label>
                        <button
                          type="button"
                          className="btn btn-primary full-width"
                          disabled={!publicState.host_ready}
                          onClick={() =>
                            sendWsAction({
                              type: "start_round",
                              use_ai_intro: useAiIntro,
                            })
                          }
                        >
                          <span>Start Horror Round</span>
                          <ArrowRight size={18} />
                        </button>
                      </div>
                    ) : (
                      <div className="waiting-box">
                        Waiting for the Host to start the round...
                      </div>
                    )}
                  </section>
                )}

                {/* PHASE 2: SECRET ROLE REVEAL */}
                {currentPhase === "ROLE_REVEAL" && publicState && privateState && (
                  <section className="panel stage-panel">
                    <span className="mono-tag">CONFIDENTIAL DOSSIER</span>
                    <h3 className="section-title">Inspect Your Secret Identity</h3>
                    <p className="instruction-callout">
                      Shield your phone screen from other players. Press and hold the shutter button
                      below (or toggle reveal) to view your role and secret information.
                    </p>

                    <div
                      className={
                        holdingReveal || pinnedReveal
                          ? privateState.role === "IMPOSTER"
                            ? "role-card role-card-imposter"
                            : "role-card role-card-survivor"
                          : "role-card role-card-concealed"
                      }
                    >
                      {holdingReveal || pinnedReveal ? (
                        <div className="role-revealed-inner">
                          <span className="role-badge">
                            {privateState.role === "IMPOSTER" ? (
                              <>
                                <ShieldWarning size={18} /> IMPOSTER
                              </>
                            ) : (
                              <>
                                <CheckCircle size={18} /> SURVIVOR
                              </>
                            )}
                          </span>

                          <div className="role-category-line">
                            CATEGORY:{" "}
                            <strong>{privateState.category || publicState.active_category}</strong>
                          </div>

                          {privateState.role === "SURVIVOR" ? (
                            <div className="secret-word-box">
                              <span className="helper-label">YOUR SECRET WORD</span>
                              <div className="secret-word-value">
                                {privateState.secret_word}
                              </div>
                            </div>
                          ) : (
                            <div className="secret-word-box imposter-warning-box">
                              <span className="helper-label">NO SECRET WORD ASSIGNED</span>
                              <p className="imposter-briefing-text">
                                {privateState.role_briefing}
                              </p>
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="role-shutter-cover">
                          <EyeSlash size={32} />
                          <p className="shutter-title">IDENTITY SEALED</p>
                          <p className="helper-label">
                            Hold button below to open shutter, release to hide immediately.
                          </p>
                        </div>
                      )}
                    </div>

                    <div className="reveal-controls-row">
                      <button
                        type="button"
                        className="btn btn-secondary full-width"
                        onMouseDown={() => setHoldingReveal(true)}
                        onMouseUp={() => setHoldingReveal(false)}
                        onMouseLeave={() => setHoldingReveal(false)}
                        onTouchStart={() => setHoldingReveal(true)}
                        onTouchEnd={() => setHoldingReveal(false)}
                      >
                        <Eye size={18} />
                        <span>Hold to Peek Role</span>
                      </button>

                      <button
                        type="button"
                        className="btn btn-ghost"
                        onClick={() => setPinnedReveal((v) => !v)}
                      >
                        <span>{pinnedReveal ? "Hide Card" : "Toggle Pin"}</span>
                      </button>
                    </div>

                    <div className="acknowledge-bar">
                      {playerMap.get(credentials.player_id)?.ready_in_reveal ? (
                        <div className="waiting-box">
                          You are ready. Waiting for remaining players (
                          {publicState.players.filter((p) => p.ready_in_reveal).length} /{" "}
                          {publicState.speaking_order.length})...
                        </div>
                      ) : (
                        <button
                          type="button"
                          className="btn btn-primary full-width"
                          onClick={() => {
                            setHoldingReveal(false);
                            setPinnedReveal(false);
                            sendWsAction({ type: "acknowledge_role" });
                          }}
                        >
                          <span>I Memorized My Role (Lock Shutter)</span>
                          <ArrowRight size={18} />
                        </button>
                      )}

                      {isHost && (
                        <button
                          type="button"
                          className="btn btn-ghost full-width"
                          onClick={() => sendWsAction({ type: "begin_clue_round" })}
                        >
                          Host Override: Skip Reveal &amp; Begin Clue Round Now
                        </button>
                      )}
                    </div>
                  </section>
                )}

                {/* PHASE 3: CLUE ROUND */}
                {currentPhase === "CLUE_ROUND" && publicState && (
                  <section className="panel stage-panel">
                    <div className="panel-header-row">
                      <div>
                        <span className="mono-tag">
                          CATEGORY: {publicState.active_category || "HORROR"}
                        </span>
                        <h3 className="section-title">
                          {publicState.current_speaker_id === credentials.player_id
                            ? "Your Turn: Submit One Short Clue"
                            : `Current Speaker: ${
                                playerMap.get(publicState.current_speaker_id || "")
                                  ?.nickname || "Waiting..."
                              }`}
                        </h3>
                      </div>
                      <span className="mono-badge">
                        CLUE {publicState.clues.length + 1} OF{" "}
                        {publicState.speaking_order.length}
                      </span>
                    </div>

                    {publicState.current_speaker_id === credentials.player_id ? (
                      <form
                        className="clue-submit-form"
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
                          <label htmlFor="clue-input">
                            Your Clue (Max 40 characters; cannot be edited after sending)
                          </label>
                          <input
                            id="clue-input"
                            type="text"
                            className="input-control"
                            maxLength={40}
                            autoFocus
                            required
                            value={clueDraft}
                            onChange={(e) => setClueDraft(e.target.value)}
                            placeholder="Write a single subtle hint..."
                          />
                          <div className="char-counter-row">
                            <span className="helper-label">
                              Prove you know the word without revealing it to the Imposter.
                            </span>
                            <span className="mono-counter">
                              {String(clueDraft.length).padStart(2, "0")}/40
                            </span>
                          </div>
                        </div>
                        <button type="submit" className="btn btn-primary full-width">
                          <span>Submit Clue to Circle</span>
                          <ArrowRight size={18} />
                        </button>
                      </form>
                    ) : (
                      <div className="waiting-box">
                        The spirits are listening to{" "}
                        <strong>
                          {playerMap.get(publicState.current_speaker_id || "")?.nickname}
                        </strong>
                        ...
                      </div>
                    )}

                    <div className="turn-order-strip">
                      <span className="helper-label">Speaking Order:</span>
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
                    </div>

                    <div className="clue-board">
                      <h4 className="panel-subtitle">Spoken Clues Log</h4>
                      {publicState.clues.length === 0 ? (
                        <p className="helper-label">No clues spoken yet.</p>
                      ) : (
                        <ul className="clue-list">
                          {publicState.clues.map((c) => (
                            <li key={c.turn_index} className="clue-row">
                              <span className="clue-turn">#{c.turn_index}</span>
                              <span className="clue-author">{c.nickname}</span>
                              <span className="clue-text">“{c.clue}”</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>

                    {isHost && (
                      <button
                        type="button"
                        className="btn btn-ghost full-width"
                        onClick={() => sendWsAction({ type: "skip_speaker" })}
                      >
                        Host Control: Skip Current Speaker (Disconnected / Inactive)
                      </button>
                    )}
                  </section>
                )}

                {/* PHASE 4: DISCUSSION */}
                {currentPhase === "DISCUSSION" && publicState && (
                  <section className="panel stage-panel">
                    <span className="mono-tag">
                      INTERROGATION WINDOW ({publicState.active_category})
                    </span>
                    <h3 className="section-title">Discuss the Clues</h3>
                    <p className="instruction-callout">
                      Review every clue below. Question anyone whose hint felt too vague or out of
                      place. When the timer expires (or when the host advances), secret voting begins.
                    </p>

                    <ul className="clue-list">
                      {publicState.clues.map((c) => (
                        <li key={c.turn_index} className="clue-row">
                          <span className="clue-turn">#{c.turn_index}</span>
                          <span className="clue-author">{c.nickname}</span>
                          <span className="clue-text">“{c.clue}”</span>
                        </li>
                      ))}
                    </ul>

                    {isHost && (
                      <button
                        type="button"
                        className="btn btn-primary full-width"
                        onClick={() => sendWsAction({ type: "begin_voting" })}
                      >
                        <span>Open Secret Voting Now</span>
                        <ArrowRight size={18} />
                      </button>
                    )}
                  </section>
                )}

                {/* PHASE 5 & RUNOFF: SECRET VOTING */}
                {(currentPhase === "VOTING" || currentPhase === "RUNOFF") &&
                  publicState && (
                    <section className="panel stage-panel">
                      <div className="panel-header-row">
                        <div>
                          <span className="mono-tag">
                            {currentPhase === "RUNOFF"
                              ? "TIE-BREAKER RUNOFF BALLOT"
                              : "SECRET BALLOT"}
                          </span>
                          <h3 className="section-title">
                            {currentPhase === "RUNOFF"
                              ? "Vote Between Tied Suspects"
                              : "Vote to Accuse the Imposter"}
                          </h3>
                        </div>
                        <span className="mono-badge">
                          BALLOTS: {publicState.votes_cast_count} /{" "}
                          {publicState.eligible_voters_count}
                        </span>
                      </div>

                      <p className="instruction-callout">
                        {currentPhase === "RUNOFF"
                          ? "The initial vote tied. Choose one of the tied suspects below. If the runoff remains tied, no one is caught and the Imposter escapes."
                          : "Select the player you suspect is the Imposter. You cannot vote for yourself, and votes remain secret until everyone has voted."}
                      </p>

                      {privateState?.has_voted_for ? (
                        <div className="waiting-box">
                          Secret ballot locked for{" "}
                          <strong>
                            {playerMap.get(privateState.has_voted_for)?.nickname ||
                              "Suspect"}
                          </strong>
                          . Waiting for remaining players...
                        </div>
                      ) : (
                        <div className="voting-stack">
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
                                const clueObj = publicState.clues.find(
                                  (c) => c.player_id === pid
                                );
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
                                    <div className="vote-target-top">
                                      <span className="roster-name">
                                        {p?.nickname || pid}
                                      </span>
                                      <span className="mono-tag">
                                        {isSelected ? "SELECTED" : "SUSPECT"}
                                      </span>
                                    </div>
                                    {clueObj && (
                                      <div className="vote-target-clue">
                                        Clue: “{clueObj.clue}”
                                      </div>
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
                            <span>Lock Secret Vote</span>
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
                          Host Control: Close Poll &amp; Tally Votes Now
                        </button>
                      )}
                    </section>
                  )}

                {/* PHASE 6: IMPOSTER FINAL GUESS */}
                {currentPhase === "FINAL_GUESS" && publicState && (
                  <section className="panel stage-panel accusation-panel">
                    <span className="mono-tag danger-text">THE IMPOSTER IS CORNERED</span>
                    <h3 className="section-title">
                      {playerMap.get(publicState.accused_player_id || "")?.nickname} Has Been
                      Discovered!
                    </h3>

                    {privateState?.can_submit_final_guess ? (
                      <form
                        className="final-guess-form"
                        onSubmit={(e) => {
                          e.preventDefault();
                          if (!finalGuessDraft.trim()) return;
                          sendWsAction({
                            type: "submit_final_guess",
                            guess: finalGuessDraft.trim(),
                          });
                        }}
                      >
                        <p className="instruction-callout">
                          You have been caught by the group, but you have{" "}
                          <strong>one final chance</strong> to steal victory. Name the Survivors'
                          secret word in category{" "}
                          <strong>{publicState.active_category}</strong>.
                        </p>

                        <div className="form-field">
                          <label htmlFor="final-guess-input">
                            Your Single Final Word Guess
                          </label>
                          <input
                            id="final-guess-input"
                            type="text"
                            className="input-control"
                            maxLength={48}
                            autoFocus
                            required
                            value={finalGuessDraft}
                            onChange={(e) => setFinalGuessDraft(e.target.value)}
                            placeholder="Enter the secret horror word..."
                          />
                        </div>

                        <button type="submit" className="btn btn-danger full-width">
                          <span>Submit Final Guess</span>
                          <ArrowRight size={18} />
                        </button>
                      </form>
                    ) : (
                      <div className="waiting-box">
                        The group caught the Imposter! Hold your breath while{" "}
                        <strong>
                          {playerMap.get(publicState.accused_player_id || "")?.nickname}
                        </strong>{" "}
                        attempts one final guess at the secret word...
                      </div>
                    )}
                  </section>
                )}

                {/* PHASE 7: RESULTS & LEADERBOARD */}
                {currentPhase === "RESULTS" && publicState?.outcome && (
                  <section className="panel stage-panel results-panel">
                    <div className="outcome-header">
                      <span
                        className={
                          publicState.outcome.winner === "SURVIVORS"
                            ? "winner-banner winner-survivors"
                            : "winner-banner winner-imposter"
                        }
                      >
                        {publicState.outcome.winner === "SURVIVORS"
                          ? "SURVIVORS WIN THE ROUND"
                          : "THE IMPOSTER WINS THE ROUND"}
                      </span>
                      <p className="outcome-summary">
                        {publicState.outcome.summary_text}
                      </p>
                    </div>

                    <div className="reveal-dossier-grid">
                      <div className="dossier-cell">
                        <span className="helper-label">SECRET WORD</span>
                        <strong className="dossier-val">
                          {publicState.outcome.secret_word}
                        </strong>
                        <span className="mono-tag">
                          {publicState.outcome.category}
                        </span>
                      </div>

                      <div className="dossier-cell">
                        <span className="helper-label">THE IMPOSTER</span>
                        <strong className="dossier-val danger-text">
                          {publicState.outcome.imposter_nickname}
                        </strong>
                        <span className="mono-tag">
                          {publicState.outcome.imposter_final_guess
                            ? `Final Guess: "${publicState.outcome.imposter_final_guess}" (${
                                publicState.outcome.imposter_guessed_correctly
                                  ? "Correct"
                                  : "Wrong"
                              })`
                            : "Escaped Without Final Guess"}
                        </span>
                      </div>
                    </div>

                    <div className="results-columns">
                      <div>
                        <h4 className="panel-subtitle">Clues &amp; Vote Breakdown</h4>
                        <ul className="clue-list">
                          {publicState.clues.map((c) => {
                            const isImp =
                              c.player_id === publicState.outcome?.imposter_id;
                            const votedForId =
                              publicState.outcome?.voter_breakdown[c.player_id];
                            const votedForName = votedForId
                              ? playerMap.get(votedForId)?.nickname
                              : "No vote";
                            return (
                              <li key={c.turn_index} className="clue-row">
                                <span className="clue-author">
                                  {c.nickname}{" "}
                                  {isImp && (
                                    <span className="imposter-inline-tag">
                                      IMPOSTER
                                    </span>
                                  )}
                                </span>
                                <span className="clue-text">“{c.clue}”</span>
                                <span className="helper-label">
                                  Voted for: {votedForName}
                                </span>
                              </li>
                            );
                          })}
                        </ul>
                      </div>

                      <div>
                        <h4 className="panel-subtitle">Cumulative Scoreboard</h4>
                        <ul className="leaderboard-list">
                          {[...publicState.players]
                            .sort((a, b) => b.score - a.score)
                            .map((p, idx) => {
                              const delta =
                                publicState.outcome?.score_deltas[p.player_id] || 0;
                              return (
                                <li key={p.player_id} className="leaderboard-row">
                                  <span>
                                    {idx + 1}. {p.nickname}
                                  </span>
                                  <div className="row-center gap-2">
                                    {delta > 0 && (
                                      <span className="score-delta">+{delta}</span>
                                    )}
                                    <strong className="mono-score">
                                      {p.score} PTS
                                    </strong>
                                  </div>
                                </li>
                              );
                            })}
                        </ul>
                      </div>
                    </div>

                    {isHost ? (
                      <div className="results-actions-row">
                        <button
                          type="button"
                          className="btn btn-primary"
                          onClick={() =>
                            sendWsAction({
                              type: "play_again",
                              use_ai_intro: useAiIntro,
                            })
                          }
                        >
                          <span>Play Next Round</span>
                          <ArrowRight size={18} />
                        </button>
                        <button
                          type="button"
                          className="btn btn-secondary"
                          onClick={() => sendWsAction({ type: "return_to_lobby" })}
                        >
                          <span>Return to Lobby</span>
                        </button>
                        <button
                          type="button"
                          className="btn btn-ghost"
                          onClick={() => sendWsAction({ type: "reset_scores" })}
                        >
                          <span>Reset Scores</span>
                        </button>
                      </div>
                    ) : (
                      <div className="waiting-box">
                        Waiting for Host to start the next round or return to lobby...
                      </div>
                    )}
                  </section>
                )}
              </div>

              {/* Secondary Hardware & Host Telemetry Column */}
              <aside className="stage-side-col">
                {publicState?.matrix && (
                  <MatrixVisualizer
                    matrix={publicState.matrix}
                    canTestHardware={isHost}
                    onTriggerTestState={handleTriggerMatrixTest}
                  />
                )}

                {privateState?.role && currentPhase !== "LOBBY" && currentPhase !== "RESULTS" && (
                  <section className="panel quick-dossier-panel">
                    <div className="panel-header-row">
                      <span className="mono-tag">YOUR PRIVATE DOSSIER</span>
                      <button
                        type="button"
                        className="btn btn-ghost"
                        onMouseDown={() => setHoldingReveal(true)}
                        onMouseUp={() => setHoldingReveal(false)}
                        onMouseLeave={() => setHoldingReveal(false)}
                        onTouchStart={() => setHoldingReveal(true)}
                        onTouchEnd={() => setHoldingReveal(false)}
                      >
                        <Eye size={16} />
                        <span>Hold to Check Word</span>
                      </button>
                    </div>
                    {holdingReveal ? (
                      <div className="quick-dossier-secret">
                        Role: <strong>{privateState.role}</strong> | Category:{" "}
                        <strong>{privateState.category}</strong>
                        {privateState.secret_word && (
                          <div>
                            Secret Word: <strong>{privateState.secret_word}</strong>
                          </div>
                        )}
                      </div>
                    ) : (
                      <p className="helper-label">
                        Hidden to prevent screen-peeking. Press and hold button above to verify your word.
                      </p>
                    )}
                  </section>
                )}

                {isHost && publicState && (
                  <HostSettingsPanel
                    game={publicState}
                    playerId={credentials.player_id}
                    token={credentials.reconnect_token}
                    onUpdateSettings={(payload) =>
                      sendWsAction({ type: "update_settings", ...payload })
                    }
                  />
                )}

                {publicState && (
                  <section className="panel sidebar-roster-panel">
                    <div className="row-center gap-2">
                      <Users size={18} />
                      <h3 className="panel-subtitle">Investigator Status</h3>
                    </div>
                    <ul className="compact-player-list">
                      {publicState.players.map((p) => (
                        <li key={p.player_id} className="compact-player-row">
                          <span>
                            {p.nickname}
                            {p.is_host ? " [HOST]" : ""}
                          </span>
                          <span className="mono-score">{p.score} pts</span>
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
              </aside>
            </div>
          </div>
        )}
      </main>

      <RulesModal open={rulesOpen} onClose={() => setRulesOpen(false)} />
    </div>
  );
};
