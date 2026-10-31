import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowsClockwise,
  BookOpen,
  Check,
  Copy,
  Eye,
  EyeSlash,
  GearSix,
  SignOut,
  SpeakerHigh,
  SpeakerSlash,
  Users,
  WarningCircle,
  WifiHigh,
  X,
} from "@phosphor-icons/react";
import { GhostBackground } from "./components/atmosphere/GhostBackground";
import { GhostMascot } from "./components/GhostMascot";
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

const AVATAR_PALETTE = [
  "#0070f3",
  "#e11d38",
  "#1f7a36",
  "#c26d0b",
  "#0d9488",
  "#1d5fbf",
  "#be123c",
  "#15803d",
  "#b45309",
  "#0f766e",
];

function avatarColor(index: number): string {
  return AVATAR_PALETTE[index % AVATAR_PALETTE.length];
}

/**
 * Copy text to clipboard across both HTTPS and plain HTTP LAN URLs
 * (e.g. http://192.168.x.x:8765 on Arduino UNO Q where navigator.clipboard is undefined).
 */
async function copyTextReliable(text: string): Promise<boolean> {
  if (!text) return false;
  try {
    if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // Fall through to textarea execCommand fallback
  }

  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.top = "-9999px";
    ta.style.left = "-9999px";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    ta.setSelectionRange(0, text.length);
    const copied = document.execCommand("copy");
    document.body.removeChild(ta);
    return copied;
  } catch {
    return false;
  }
}

export const App: React.FC = () => {
  const urlRoomParam = React.useMemo(() => {
    if (typeof window === "undefined") return null;
    const raw = new URLSearchParams(window.location.search).get("room");
    return raw ? raw.trim().toUpperCase() : null;
  }, []);

  const [credentials, setCredentials] = useState<StoredCredentials | null>(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw) as StoredCredentials;
      if (urlRoomParam && parsed.room_code.toUpperCase() !== urlRoomParam) {
        localStorage.removeItem(STORAGE_KEY);
        return null;
      }
      return parsed;
    } catch {
      return null;
    }
  });

  const [publicState, setPublicState] = useState<PublicGameState | null>(null);
  const [privateState, setPrivateState] = useState<PrivatePlayerPayload | null>(null);
  const [networkInfo, setNetworkInfo] = useState<NetworkInfo | null>(null);
  const [wsConnected, setWsConnected] = useState(false);

  const [entryMode, setEntryMode] = useState<"join" | "host">("join");
  const [nicknameInput, setNicknameInput] = useState("");
  const [roomCodeInput, setRoomCodeInput] = useState(urlRoomParam || "");
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const [isSubmittingJoin, setIsSubmittingJoin] = useState(false);

  const [rulesOpen, setRulesOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [copiedUrl, setCopiedUrl] = useState(false);
  const [copiedCode, setCopiedCode] = useState(false);
  const [customHostIp, setCustomHostIp] = useState("");
  const [editingIp, setEditingIp] = useState(false);

  // Gameplay local UI states
  const [cardRevealed, setCardRevealed] = useState(false);
  const [secretPeekOpen, setSecretPeekOpen] = useState(false);
  const [clueDraft, setClueDraft] = useState("");
  const [selectedVoteTarget, setSelectedVoteTarget] = useState<string | null>(null);
  const [finalGuessDraft, setFinalGuessDraft] = useState("");

  // Track previous counts/turns for sound cues
  const prevPlayerCountRef = useRef<number>(0);
  const prevClueCountRef = useRef<number>(0);
  const prevSpeakerIdRef = useRef<string | null>(null);

  const fetchNetworkInfo = useCallback(
    async (roomOverride?: string, hostOverride?: string) => {
      try {
        const params = new URLSearchParams();
        const targetRoom = roomOverride || publicState?.room_code || urlRoomParam;
        if (targetRoom) params.set("room", targetRoom);
        const hostVal = hostOverride !== undefined ? hostOverride : customHostIp;
        if (hostVal.trim()) params.set("host", hostVal.trim());
        const query = params.toString() ? `?${params.toString()}` : "";
        const netResp = await fetch(`/api/network${query}`);
        if (netResp.ok) {
          const netData = (await netResp.json()) as NetworkInfo;
          setNetworkInfo(netData);
          if (!urlRoomParam && !roomCodeInput) {
            setRoomCodeInput(netData.room_code);
          }
        }
      } catch {
        // Handled by reconnect
      }
    },
    [customHostIp, publicState?.room_code, roomCodeInput, urlRoomParam]
  );

  // Initial fetch of network info and public state
  useEffect(() => {
    const fetchInitial = async () => {
      try {
        const stateUrl = credentials
          ? `/api/state?player_id=${encodeURIComponent(
              credentials.player_id
            )}&token=${encodeURIComponent(credentials.reconnect_token)}`
          : "/api/state";
        const stateResp = await fetch(stateUrl);
        if (stateResp.ok) {
          const stData = await stateResp.json();
          setPublicState(stData.public);
          if (stData.private) {
            setPrivateState(stData.private);
          }
          await fetchNetworkInfo(stData.public?.room_code);
        } else {
          await fetchNetworkInfo();
        }
      } catch {
        // Retry handled by WebSocket loop
      }
    };
    void fetchInitial();
  }, [credentials]);

  // Keep QR and join URL synchronized whenever the active room_code changes
  useEffect(() => {
    if (publicState?.room_code) {
      void fetchNetworkInfo(publicState.room_code);
      if (!urlRoomParam) {
        setRoomCodeInput(publicState.room_code);
      }
    }
  }, [publicState?.room_code]);

  // Phase transition sound effects and local state resets
  useEffect(() => {
    if (!publicState) return;
    setSecretPeekOpen(false);
    if (publicState.phase === "ROLE_REVEAL") {
      soundCues.playPhaseTransition();
      setCardRevealed(false);
      setClueDraft("");
      setSelectedVoteTarget(null);
      setFinalGuessDraft("");
    } else if (publicState.phase === "CLUE_ROUND" || publicState.phase === "DISCUSSION") {
      soundCues.playPhaseTransition();
    } else if (publicState.phase === "VOTING" || publicState.phase === "RUNOFF") {
      soundCues.playPhaseTransition();
      setSelectedVoteTarget(null);
    } else if (publicState.phase === "FINAL_GUESS") {
      soundCues.playAccusation();
    } else if (publicState.phase === "RESULTS") {
      if (publicState.outcome?.winner === "SURVIVORS") {
        soundCues.playVictorySurvivors();
      } else {
        soundCues.playVictoryImposter();
      }
    }
  }, [publicState?.phase, publicState?.round_number, publicState?.clue_round_number]);

  // Player join, clue submitted, and active turn sound cues
  useEffect(() => {
    if (!publicState) return;
    const connectedNow = publicState.players.filter((p) => p.connected).length;
    if (
      publicState.phase === "LOBBY" &&
      prevPlayerCountRef.current > 0 &&
      connectedNow > prevPlayerCountRef.current
    ) {
      soundCues.playPlayerJoin();
    }
    prevPlayerCountRef.current = connectedNow;

    if (
      publicState.phase === "CLUE_ROUND" &&
      publicState.clues.length > prevClueCountRef.current
    ) {
      soundCues.playClueSubmitted();
    }
    prevClueCountRef.current = publicState.clues.length;

    if (
      publicState.phase === "CLUE_ROUND" &&
      publicState.current_speaker_id &&
      publicState.current_speaker_id !== prevSpeakerIdRef.current &&
      publicState.current_speaker_id === credentials?.player_id
    ) {
      soundCues.playYourTurn();
    }
    prevSpeakerIdRef.current = publicState.current_speaker_id;
  }, [
    credentials?.player_id,
    publicState?.clues.length,
    publicState?.current_speaker_id,
    publicState?.phase,
    publicState?.players,
  ]);

  const wsRef = useRef<WebSocket | null>(null);

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
      setErrorBanner("Reconnecting to room... Try again in a moment.");
    }
  };

  const handleJoinOrCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    soundCues.playTap();
    setErrorBanner(null);
    const trimmedName = nicknameInput.trim();
    if (!trimmedName) {
      setErrorBanner("Please enter your name.");
      return;
    }

    const asHost = entryMode === "host";
    const createNewRoom = asHost && (publicState?.players.length ?? 0) === 0;
    setIsSubmittingJoin(true);

    try {
      const resp = await fetch("/api/join", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nickname: trimmedName,
          room_code: asHost
            ? undefined
            : roomCodeInput.trim().toUpperCase() || undefined,
          as_host: asHost,
          create_new_room: createNewRoom,
        }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        setErrorBanner(data.detail || "Could not join the room.");
        return;
      }
      soundCues.playPlayerJoin();
      const creds: StoredCredentials = {
        player_id: data.player_id,
        nickname: data.nickname,
        room_code: data.room_code,
        reconnect_token: data.reconnect_token,
        is_host: data.is_host,
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(creds));
      setCredentials(creds);
      if (window.location.search) {
        window.history.replaceState({}, "", `/?room=${data.room_code}`);
      }
      await fetchNetworkInfo(data.room_code);
    } catch {
      setErrorBanner("Network error while connecting to the server.");
    } finally {
      setIsSubmittingJoin(false);
    }
  };

  const handleGenerateNewRoom = async () => {
    if (!credentials) return;
    soundCues.playTap();
    setErrorBanner(null);
    try {
      const newResp = await fetch("/api/room/new", { method: "POST" });
      if (!newResp.ok) return;
      const netData = (await newResp.json()) as NetworkInfo;
      setNetworkInfo(netData);
      const joinResp = await fetch("/api/join", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nickname: credentials.nickname,
          room_code: netData.room_code,
          as_host: true,
        }),
      });
      if (joinResp.ok) {
        const joinData = await joinResp.json();
        const creds: StoredCredentials = {
          player_id: joinData.player_id,
          nickname: joinData.nickname,
          room_code: joinData.room_code,
          reconnect_token: joinData.reconnect_token,
          is_host: joinData.is_host,
        };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(creds));
        setCredentials(creds);
        window.history.replaceState({}, "", `/?room=${joinData.room_code}`);
      }
    } catch {
      setErrorBanner("Could not create a new room code.");
    }
  };

  const handleLeaveRoom = () => {
    soundCues.playTap();
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

  const handleCopyRoomCode = async () => {
    const code = publicState?.room_code || activeRoomCode;
    const ok = await copyTextReliable(code);
    if (ok) {
      soundCues.playCopy();
      setCopiedCode(true);
      setTimeout(() => setCopiedCode(false), 2000);
    }
  };

  const handleCopyJoinUrl = async () => {
    const urlToCopy =
      networkInfo?.join_url ||
      `${window.location.origin}/?room=${publicState?.room_code || activeRoomCode}`;
    const ok = await copyTextReliable(urlToCopy);
    if (ok) {
      soundCues.playCopy();
      setCopiedUrl(true);
      setTimeout(() => setCopiedUrl(false), 2000);
    }
  };

  const handleTriggerMatrixTest = (state: GhostMatrixState) => {
    sendWsAction({ type: "test_matrix_state", state });
  };

  const isHost = Boolean(privateState?.is_host || credentials?.is_host);
  const currentPhase = publicState?.phase || "LOBBY";
  const players = publicState?.players || [];
  const playerMap = new Map(players.map((p) => [p.player_id, p]));
  const playerIndexMap = new Map(players.map((p, i) => [p.player_id, i]));
  const connectedCount = players.filter((p) => p.connected).length;
  const activeRoomCode =
    publicState?.room_code ||
    networkInfo?.room_code ||
    roomCodeInput ||
    "HAUNT6";

  return (
    <div className="app-root">
      <GhostBackground
        phase={credentials ? currentPhase : "LANDING"}
        winner={publicState?.outcome?.winner ?? null}
        clueRound={publicState?.clue_round_number ?? 1}
      />
      <main className="game-column">
        {/* Top Bar */}
        <header className="room-header">
          <div className="header-brand">
            <span className="status-indicator" data-online={wsConnected} />
            <span className="header-title-text">The Last Clue</span>
          </div>

          <div className="header-actions">
            <button
              type="button"
              className="circle-icon-btn"
              onClick={() => {
                soundCues.playTap();
                setSettingsOpen(true);
              }}
              aria-label="UNO Q Matrix and Settings"
              title="UNO Q Matrix and Settings"
            >
              <GearSix size={18} weight="bold" />
            </button>

            <button
              type="button"
              className="circle-icon-btn"
              onClick={toggleSound}
              aria-label={soundEnabled ? "Mute sound" : "Enable sound"}
              title={soundEnabled ? "Sound on" : "Sound muted"}
            >
              {soundEnabled ? (
                <SpeakerHigh size={18} weight="bold" />
              ) : (
                <SpeakerSlash size={18} weight="bold" />
              )}
            </button>

            <button
              type="button"
              className="circle-icon-btn"
              onClick={() => {
                soundCues.playTap();
                setRulesOpen(true);
              }}
              aria-label="How to Play"
              title="How to Play"
            >
              <BookOpen size={18} weight="bold" />
            </button>

            {credentials && (
              <button
                type="button"
                className="circle-icon-btn"
                onClick={handleLeaveRoom}
                aria-label="Leave room"
                title="Leave room"
              >
                <SignOut size={18} weight="bold" />
              </button>
            )}
          </div>
        </header>

        {errorBanner && (
          <div className="alert-banner" role="alert">
            <WarningCircle size={18} weight="fill" />
            <span>{errorBanner}</span>
            <button
              type="button"
              className="alert-close"
              onClick={() => setErrorBanner(null)}
              aria-label="Dismiss error"
            >
              <X size={16} weight="bold" />
            </button>
          </div>
        )}

        {/* SCREEN 1 & 2: LANDING & CREATE / JOIN ROOM */}
        {!credentials ? (
          <section className="phase-screen">
            <div className="hero-banner">
              <GhostMascot mood="calm" size={72} />
              <h1 className="hero-title">
                <span className="hero-title-sub">Guess the</span>
                <span className="hero-title-main">Imposter</span>
              </h1>
            </div>

            {urlRoomParam ? (
              <div className="scanned-room-notice">
                <span>Joining Room</span>
                <strong>{urlRoomParam}</strong>
              </div>
            ) : (
              <nav className="mode-switch" aria-label="Join or Host">
                <button
                  type="button"
                  className={
                    entryMode === "join" ? "mode-card active" : "mode-card"
                  }
                  onClick={() => {
                    soundCues.playTap();
                    setEntryMode("join");
                  }}
                >
                  <span className="mode-card-top">
                    <Users size={20} weight="bold" />
                    <span className="mode-radio" />
                  </span>
                  <span className="mode-card-name">Join Room</span>
                  <span className="mode-card-when">Enter code or scan QR</span>
                </button>

                <button
                  type="button"
                  className={
                    entryMode === "host" ? "mode-card active" : "mode-card"
                  }
                  onClick={() => {
                    soundCues.playTap();
                    setEntryMode("host");
                  }}
                >
                  <span className="mode-card-top">
                    <WifiHigh size={20} weight="bold" />
                    <span className="mode-radio" />
                  </span>
                  <span className="mode-card-name">Host Game</span>
                  <span className="mode-card-when">Create room on Wi-Fi</span>
                </button>
              </nav>
            )}

            <form className="entry-form" onSubmit={handleJoinOrCreate}>
              <div className="field-block">
                <label htmlFor="nickname-input" className="field-label">
                  Your Name
                </label>
                <input
                  id="nickname-input"
                  type="text"
                  className="text-input"
                  maxLength={18}
                  required
                  autoFocus
                  autoComplete="off"
                  value={nicknameInput}
                  onChange={(e) => setNicknameInput(e.target.value)}
                  placeholder="Enter your nickname"
                />
              </div>

              {entryMode === "join" && (
                <div className="field-block">
                  <label htmlFor="room-code-input" className="field-label">
                    Room Code
                  </label>
                  <input
                    id="room-code-input"
                    type="text"
                    className="text-input code-input"
                    maxLength={8}
                    required
                    autoComplete="off"
                    value={roomCodeInput}
                    onChange={(e) =>
                      setRoomCodeInput(e.target.value.toUpperCase())
                    }
                    placeholder={activeRoomCode}
                  />
                </div>
              )}

              <button
                type="submit"
                className="pill-btn pill-btn-primary"
                disabled={isSubmittingJoin}
              >
                {entryMode === "host" ? "Create & Enter Lobby" : "Join Room"}
              </button>
            </form>
          </section>
        ) : (
          <>
            {/* SCREEN 3 & 11: LOBBY, PLAYER LIST, QR SHARING & HOST CONTROLS */}
            {currentPhase === "LOBBY" && publicState && (
              <section className="phase-screen has-sticky-footer">
                <div className="lobby-invite">
                  <GhostMascot mood="calm" size={64} />
                  <h1 className="lobby-invite-title">Invite Players</h1>

                  {/* Interactive 6-Digit Room Code Tiles (Click to Copy Room Code) */}
                  <button
                    type="button"
                    className="lobby-code-button"
                    onClick={() => void handleCopyRoomCode()}
                    aria-label={`Copy room code ${publicState.room_code}`}
                    title="Tap to copy room code"
                  >
                    <div className="lobby-code-digits">
                      {publicState.room_code.split("").map((char, idx) => (
                        <span key={idx} className="lobby-code-digit">
                          {char}
                        </span>
                      ))}
                    </div>
                    <span className="copy-code-caption">
                      {copiedCode ? (
                        <>
                          <Check size={14} weight="bold" /> Room Code Copied!
                        </>
                      ) : (
                        <>
                          <Copy size={14} weight="bold" /> Tap code to copy
                        </>
                      )}
                    </span>
                  </button>

                  {/* Scannable Backend-Generated QR Code */}
                  {networkInfo && (
                    <div className="qr-share-block">
                      <div className="qr-frame">
                        <img
                          src={`${networkInfo.qr_png_url}&v=${encodeURIComponent(
                            networkInfo.join_url
                          )}`}
                          alt={`QR code for ${networkInfo.join_url}`}
                          className="qr-image"
                          width={184}
                          height={184}
                        />
                      </div>

                      <button
                        type="button"
                        className="lobby-link-pill"
                        onClick={() => void handleCopyJoinUrl()}
                      >
                        <span className="lobby-link-text">
                          {copiedUrl ? "Join Link Copied!" : networkInfo.join_url}
                        </span>
                        {copiedUrl ? (
                          <Check size={16} weight="bold" />
                        ) : (
                          <Copy size={16} weight="bold" />
                        )}
                      </button>

                      {(!networkInfo.network_reachable || editingIp) && (
                        <div className="network-override-box">
                          {networkInfo.network_warning && (
                            <p className="network-warning-text">
                              {networkInfo.network_warning}
                            </p>
                          )}
                          <div className="inline-field-row">
                            <input
                              type="text"
                              className="text-input text-input-sm"
                              value={customHostIp}
                              onChange={(e) => setCustomHostIp(e.target.value)}
                              placeholder="UNO Q Wi-Fi IP (e.g. 192.168.1.50)"
                              aria-label="UNO Q Wi-Fi IP address"
                            />
                            <button
                              type="button"
                              className="pill-btn pill-btn-secondary pill-btn-inline"
                              onClick={() => {
                                soundCues.playTap();
                                void fetchNetworkInfo(
                                  publicState.room_code,
                                  customHostIp
                                );
                                setEditingIp(false);
                              }}
                            >
                              Set IP
                            </button>
                          </div>
                        </div>
                      )}

                      <div className="lobby-share-links">
                        <button
                          type="button"
                          className="underline-btn"
                          onClick={() => {
                            soundCues.playTap();
                            setEditingIp((v) => !v);
                          }}
                        >
                          {editingIp ? "Hide IP setting" : "Change Wi-Fi IP"}
                        </button>
                        {isHost && (
                          <button
                            type="button"
                            className="underline-btn"
                            onClick={() => void handleGenerateNewRoom()}
                          >
                            New Room Code
                          </button>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Host Category Selector inside Lobby Card */}
                  {isHost && (
                    <div className="lobby-config">
                      <div className="lobby-config-divider" />
                      <div className="config-item-stack">
                        <label
                          htmlFor="lobby-category-select"
                          className="config-label"
                        >
                          Category
                        </label>
                        <select
                          id="lobby-category-select"
                          className="select-input"
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
                    </div>
                  )}
                </div>

                {/* Connected Players List */}
                <div className="online-panel">
                  <div className="online-panel-head">
                    <span className="online-panel-label">Players</span>
                    <span
                      className={
                        publicState.host_ready
                          ? "online-panel-count is-ready"
                          : "online-panel-count"
                      }
                    >
                      {connectedCount}/{publicState.max_players}
                    </span>
                  </div>

                  <div className="online-panel-card">
                    <ul className="player-list">
                      {publicState.players.map((p, idx) => (
                        <li
                          key={p.player_id}
                          className={
                            p.connected
                              ? "player-row"
                              : "player-row is-disconnected"
                          }
                        >
                          <span
                            className="player-avatar"
                            style={{ backgroundColor: avatarColor(idx) }}
                          >
                            {p.nickname.charAt(0).toUpperCase()}
                          </span>
                          <div className="player-main">
                            <span className="player-name">{p.nickname}</span>
                            {p.player_id === credentials.player_id && (
                              <span className="badge-pill badge-me">You</span>
                            )}
                            {p.is_host && (
                              <span className="badge-pill badge-host">Host</span>
                            )}
                          </div>
                          <div className="player-right">
                            {p.score > 0 && (
                              <span className="score-label">{p.score} pts</span>
                            )}
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>

                {/* Sticky Stage Footer */}
                <div className="online-stage-footer">
                  {isHost ? (
                    <button
                      type="button"
                      className="stage-btn is-primary"
                      disabled={!publicState.host_ready}
                      onClick={() => sendWsAction({ type: "start_round" })}
                    >
                      {publicState.host_ready
                        ? "Start Game"
                        : `Need ${Math.max(
                            0,
                            publicState.min_players - connectedCount
                          )} more to start (min ${publicState.min_players})`}
                    </button>
                  ) : (
                    <div className="stage-status">
                      <span className="stage-status-dot" />
                      <span>
                        {publicState.host_ready
                          ? "Waiting for host to start..."
                          : `Waiting for players (${connectedCount}/${publicState.min_players})...`}
                      </span>
                    </div>
                  )}
                </div>
              </section>
            )}

            {/* SCREEN 4: SECRET ROLE & WORD REVEAL */}
            {currentPhase === "ROLE_REVEAL" && publicState && privateState && (
              <section className="phase-screen fullscreen-card-stage has-sticky-footer">
                <div className="stage-top-caption">
                  <h1 className="stage-heading">Your Secret Card</h1>
                  <p className="stage-subtext">
                    Tap the card to view your role. Make sure no one else sees it.
                  </p>
                </div>

                <div id="card-area">
                  <button
                    type="button"
                    className={cardRevealed ? "role-card revealed" : "role-card"}
                    onClick={() => {
                      const next = !cardRevealed;
                      soundCues.playCardFlip(next);
                      setCardRevealed(next);
                    }}
                    aria-expanded={cardRevealed}
                  >
                    <div className="role-card-under">
                      <div className="role-card-under-inner">
                        <span
                          className={
                            privateState.role === "IMPOSTER"
                              ? "role-tag role-tag-imposter"
                              : "role-tag role-tag-survivor"
                          }
                        >
                          {privateState.role === "IMPOSTER"
                            ? "IMPOSTER"
                            : "SURVIVOR"}
                        </span>

                        <span className="role-category-caption">
                          {privateState.category || publicState.active_category}
                        </span>

                        {privateState.role === "SURVIVOR" ? (
                          <div className="revealed-secret-word">
                            {privateState.secret_word}
                          </div>
                        ) : (
                          <p className="revealed-imposter-note">
                            You do not know the secret word. Blend in and figure
                            it out.
                          </p>
                        )}
                      </div>
                    </div>

                    <div className="role-card-cover">
                      <GhostMascot mood="curious" size={64} />
                      <span className="role-card-cover-name">
                        {credentials.nickname}
                      </span>
                      <span className="role-card-cover-hint">
                        {cardRevealed ? "Tap to Hide" : "Tap to Reveal"}
                      </span>
                    </div>
                  </button>
                </div>

                <div className="online-stage-footer">
                  {playerMap.get(credentials.player_id)?.ready_in_reveal ? (
                    <div className="stage-status is-ready">
                      <span className="stage-status-dot" />
                      <span>
                        Ready (
                        {
                          publicState.players.filter((p) => p.ready_in_reveal)
                            .length
                        }
                        /{publicState.speaking_order.length})
                      </span>
                    </div>
                  ) : (
                    <button
                      type="button"
                      className="stage-btn is-primary"
                      onClick={() => {
                        setCardRevealed(false);
                        sendWsAction({ type: "acknowledge_role" });
                      }}
                    >
                      Got It, Ready
                    </button>
                  )}

                  {isHost && (
                    <button
                      type="button"
                      className="underline-btn"
                      onClick={() => sendWsAction({ type: "begin_clue_round" })}
                    >
                      Start Clues Now
                    </button>
                  )}
                </div>
              </section>
            )}

            {/* SCREEN 5: CLUE SUBMISSION */}
            {currentPhase === "CLUE_ROUND" && publicState && (
              <section className="phase-screen has-sticky-footer">
                {privateState && (
                  <div
                    className={
                      secretPeekOpen && privateState.role === "IMPOSTER"
                        ? "secret-block is-imposter"
                        : "secret-block"
                    }
                  >
                    <div className="secret-text">
                      <span className="secret-label">
                        {privateState.category || publicState.active_category} ·
                        Clue Round {publicState.clue_round_number}
                      </span>
                      <span className="secret-word">
                        {secretPeekOpen
                          ? privateState.role === "IMPOSTER"
                            ? "You are the Imposter"
                            : privateState.secret_word
                          : "Tap eye to peek your card"}
                      </span>
                    </div>
                    <button
                      type="button"
                      className="circle-icon-btn"
                      onClick={() => {
                        const next = !secretPeekOpen;
                        soundCues.playCardFlip(next);
                        setSecretPeekOpen(next);
                      }}
                      aria-label={
                        secretPeekOpen ? "Hide secret card" : "Peek secret card"
                      }
                    >
                      {secretPeekOpen ? (
                        <EyeSlash size={18} weight="bold" />
                      ) : (
                        <Eye size={18} weight="bold" />
                      )}
                    </button>
                  </div>
                )}

                {publicState.current_speaker_id === credentials.player_id ? (
                  <form
                    className="turn-input-block"
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
                    <label htmlFor="clue-input" className="stage-heading">
                      Your Turn — Give One Clue
                    </label>
                    <input
                      id="clue-input"
                      type="text"
                      className="text-input"
                      maxLength={40}
                      autoFocus
                      required
                      autoComplete="off"
                      value={clueDraft}
                      onChange={(e) => setClueDraft(e.target.value)}
                      placeholder="Enter a one-word or short clue..."
                    />
                    <button type="submit" className="stage-btn is-primary">
                      Submit Clue
                    </button>
                  </form>
                ) : (
                  <div className="turn-waiting-card">
                    <h1 className="stage-heading">
                      {playerMap.get(publicState.current_speaker_id || "")
                        ?.nickname || "Player"}
                      ’s Turn
                    </h1>
                    <p className="stage-subtext">Waiting for their clue...</p>
                  </div>
                )}

                <div className="online-panel">
                  <div className="online-panel-head">
                    <span className="online-panel-label">Clues</span>
                    <span className="online-panel-count">
                      Round {publicState.clue_round_number}
                    </span>
                  </div>

                  <div className="online-panel-card">
                    <ul className="player-list">
                      {publicState.speaking_order.map((pid, orderIdx) => {
                        const p = playerMap.get(pid);
                        const pIdx = playerIndexMap.get(pid) ?? orderIdx;
                        const isCurrent = pid === publicState.current_speaker_id;
                        const playerClues = publicState.clues.filter(
                          (c) => c.player_id === pid
                        );
                        return (
                          <li
                            key={pid}
                            className={[
                              "player-row",
                              isCurrent ? "is-active" : "",
                              playerClues.length > 0 ? "has-clue" : "",
                            ]
                              .filter(Boolean)
                              .join(" ")}
                          >
                            <span
                              className="player-avatar"
                              style={{ backgroundColor: avatarColor(pIdx) }}
                            >
                              {(p?.nickname || "?").charAt(0).toUpperCase()}
                            </span>
                            <div className="player-main">
                              <span className="player-name">
                                {p?.nickname || pid}
                              </span>
                              {isCurrent && (
                                <span className="badge-pill badge-turn">
                                  Speaking
                                </span>
                              )}
                              {playerClues.length > 0 && (
                                <div className="player-clue">
                                  {playerClues.map((c) => c.clue).join(" · ")}
                                </div>
                              )}
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                </div>

                {isHost && (
                  <div className="online-stage-footer">
                    <button
                      type="button"
                      className="stage-btn is-secondary"
                      onClick={() => sendWsAction({ type: "skip_speaker" })}
                    >
                      Skip Inactive Player
                    </button>
                  </div>
                )}
              </section>
            )}

            {/* SCREEN 6: CLUE DISCUSSION & CONTINUATION */}
            {currentPhase === "DISCUSSION" && publicState && (
              <section className="phase-screen has-sticky-footer">
                <div className="stage-top-caption">
                  <h1 className="stage-heading">Discuss the Clues</h1>
                  <p className="stage-subtext">
                    Vote now to expose the Imposter, or play another clue round.
                  </p>
                </div>

                <div className="online-panel">
                  <div className="online-panel-head">
                    <span className="online-panel-label">
                      All Clues ({publicState.active_category})
                    </span>
                    <span className="online-panel-count">
                      {publicState.clue_round_number}{" "}
                      {publicState.clue_round_number === 1 ? "Round" : "Rounds"}
                    </span>
                  </div>

                  <div className="online-panel-card">
                    <ul className="player-list">
                      {publicState.speaking_order.map((pid, orderIdx) => {
                        const p = playerMap.get(pid);
                        const pIdx = playerIndexMap.get(pid) ?? orderIdx;
                        const playerClues = publicState.clues.filter(
                          (c) => c.player_id === pid
                        );
                        return (
                          <li key={pid} className="player-row has-clue">
                            <span
                              className="player-avatar"
                              style={{ backgroundColor: avatarColor(pIdx) }}
                            >
                              {(p?.nickname || "?").charAt(0).toUpperCase()}
                            </span>
                            <div className="player-main">
                              <span className="player-name">
                                {p?.nickname || pid}
                              </span>
                              <div className="player-clue">
                                {playerClues.map((c) => c.clue).join(" · ")}
                              </div>
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                </div>

                <div className="online-stage-footer">
                  {isHost ? (
                    <>
                      <button
                        type="button"
                        className="stage-btn is-primary"
                        onClick={() => sendWsAction({ type: "begin_voting" })}
                      >
                        Start Voting
                      </button>
                      <button
                        type="button"
                        className="stage-btn is-secondary"
                        onClick={() =>
                          sendWsAction({ type: "another_clue_round" })
                        }
                      >
                        <ArrowsClockwise
                          size={18}
                          weight="bold"
                          style={{ verticalAlign: "middle", marginRight: 6 }}
                        />
                        Another Clue Round
                      </button>
                    </>
                  ) : (
                    <div className="stage-status">
                      <span className="stage-status-dot" />
                      <span>
                        Host is choosing: Start Voting or Another Clue Round...
                      </span>
                    </div>
                  )}
                </div>
              </section>
            )}

            {/* SCREEN 7: SECRET VOTING & RUNOFF */}
            {(currentPhase === "VOTING" || currentPhase === "RUNOFF") &&
              publicState && (
                <section className="phase-screen has-sticky-footer">
                  <div className="stage-top-caption">
                    <h1 className="stage-heading">
                      {currentPhase === "RUNOFF"
                        ? "Tie-Breaker Vote"
                        : "Who is the Imposter?"}
                    </h1>
                    <p className="stage-subtext">
                      Tap a player below to cast your secret vote.
                    </p>
                  </div>

                  <div className="online-panel">
                    <div className="online-panel-head">
                      <span className="online-panel-label">Suspects</span>
                      <span className="online-panel-count">
                        {publicState.votes_cast_count}/
                        {publicState.eligible_voters_count} Voted
                      </span>
                    </div>

                    {privateState?.has_voted_for ? (
                      <div className="turn-waiting-card">
                        <strong>
                          You voted for{" "}
                          {playerMap.get(privateState.has_voted_for)?.nickname ||
                            "Suspect"}
                        </strong>
                        <p className="stage-subtext">
                          Waiting for remaining players to vote...
                        </p>
                      </div>
                    ) : (
                      <div className="online-panel-card">
                        <ul className="player-list">
                          {publicState.speaking_order
                            .filter((pid) => pid !== credentials.player_id)
                            .filter(
                              (pid) =>
                                currentPhase !== "RUNOFF" ||
                                publicState.runoff_candidates.includes(pid)
                            )
                            .map((pid) => {
                              const p = playerMap.get(pid);
                              const pIdx = playerIndexMap.get(pid) ?? 0;
                              const playerClues = publicState.clues
                                .filter((c) => c.player_id === pid)
                                .map((c) => c.clue)
                                .join(" · ");
                              const isSelected = selectedVoteTarget === pid;
                              return (
                                <li key={pid}>
                                  <button
                                    type="button"
                                    className={
                                      isSelected
                                        ? "player-row vote-row is-active"
                                        : "player-row vote-row"
                                    }
                                    onClick={() => {
                                      soundCues.playTap();
                                      setSelectedVoteTarget(pid);
                                    }}
                                  >
                                    <span
                                      className="player-avatar"
                                      style={{
                                        backgroundColor: avatarColor(pIdx),
                                      }}
                                    >
                                      {(p?.nickname || "?")
                                        .charAt(0)
                                        .toUpperCase()}
                                    </span>
                                    <div className="player-main">
                                      <span className="player-name">
                                        {p?.nickname || pid}
                                      </span>
                                      {playerClues && (
                                        <div className="player-clue">
                                          {playerClues}
                                        </div>
                                      )}
                                    </div>
                                    <span
                                      className={
                                        isSelected
                                          ? "vote-check is-checked"
                                          : "vote-check"
                                      }
                                    >
                                      {isSelected && (
                                        <Check size={14} weight="bold" />
                                      )}
                                    </span>
                                  </button>
                                </li>
                              );
                            })}
                        </ul>
                      </div>
                    )}
                  </div>

                  <div className="online-stage-footer">
                    {!privateState?.has_voted_for && (
                      <button
                        type="button"
                        className="stage-btn is-primary"
                        disabled={!selectedVoteTarget}
                        onClick={() => {
                          if (!selectedVoteTarget) return;
                          soundCues.playVoteLocked();
                          if (
                            wsRef.current &&
                            wsRef.current.readyState === WebSocket.OPEN
                          ) {
                            wsRef.current.send(
                              JSON.stringify({
                                type: "cast_vote",
                                target_id: selectedVoteTarget,
                              })
                            );
                          }
                        }}
                      >
                        Submit Vote
                      </button>
                    )}

                    {isHost && (
                      <button
                        type="button"
                        className="underline-btn"
                        onClick={() => sendWsAction({ type: "finalize_voting" })}
                      >
                        Close Vote Early
                      </button>
                    )}
                  </div>
                </section>
              )}

            {/* SCREEN 8: IMPOSTER FINAL WORD GUESS */}
            {currentPhase === "FINAL_GUESS" && publicState && (
              <section className="phase-screen has-sticky-footer">
                <div className="ended-banner imposters-win">
                  <GhostMascot mood="alert" size={76} />
                  <h1 className="ended-title">
                    {playerMap.get(publicState.accused_player_id || "")
                      ?.nickname || "The Imposter"}{" "}
                    Was Caught!
                  </h1>
                  <p className="ended-subtitle">
                    One final chance to guess the secret word and steal the win.
                  </p>
                </div>

                {privateState?.can_submit_final_guess ? (
                  <form
                    className="turn-input-block"
                    onSubmit={(e) => {
                      e.preventDefault();
                      if (!finalGuessDraft.trim()) return;
                      sendWsAction({
                        type: "submit_final_guess",
                        guess: finalGuessDraft.trim(),
                      });
                    }}
                  >
                    <label htmlFor="final-guess-input" className="field-label">
                      Secret Word in {publicState.active_category}
                    </label>
                    <input
                      id="final-guess-input"
                      type="text"
                      className="text-input"
                      maxLength={48}
                      autoFocus
                      required
                      autoComplete="off"
                      value={finalGuessDraft}
                      onChange={(e) => setFinalGuessDraft(e.target.value)}
                      placeholder="Type your final guess..."
                    />
                    <button type="submit" className="stage-btn is-primary">
                      Submit Final Guess
                    </button>
                  </form>
                ) : (
                  <div className="turn-waiting-card">
                    <strong>
                      Waiting for{" "}
                      {
                        playerMap.get(publicState.accused_player_id || "")
                          ?.nickname
                      }
                      ’s final guess...
                    </strong>
                  </div>
                )}
              </section>
            )}

            {/* SCREEN 9 & 10: RESULTS, WINNER REVEAL, LEADERBOARD & REPLAY */}
            {currentPhase === "RESULTS" && publicState?.outcome && (
              <section className="phase-screen has-sticky-footer">
                <div
                  className={
                    publicState.outcome.winner === "SURVIVORS"
                      ? "ended-banner civilians-win"
                      : "ended-banner imposters-win"
                  }
                >
                  <GhostMascot
                    mood={
                      publicState.outcome.winner === "SURVIVORS"
                        ? "defeated"
                        : "victory"
                    }
                    size={76}
                  />
                  <h1 className="ended-title">
                    {publicState.outcome.winner === "SURVIVORS"
                      ? "Survivors Win!"
                      : "Imposter Wins!"}
                  </h1>
                  <p className="ended-subtitle">
                    {publicState.outcome.summary_text}
                  </p>
                </div>

                <div className="reveal-pair">
                  <div className="reveal-box">
                    <span className="reveal-box-label">Secret Word</span>
                    <strong className="reveal-box-value">
                      {publicState.outcome.secret_word}
                    </strong>
                    <span className="field-hint">
                      {publicState.outcome.category}
                    </span>
                  </div>

                  <div className="reveal-box">
                    <span className="reveal-box-label">The Imposter</span>
                    <strong className="reveal-box-value is-imposter-name">
                      {publicState.outcome.imposter_nickname}
                    </strong>
                    {publicState.outcome.imposter_final_guess && (
                      <span className="field-hint">
                        Guessed “{publicState.outcome.imposter_final_guess}”
                      </span>
                    )}
                  </div>
                </div>

                <div className="online-panel">
                  <div className="online-panel-head">
                    <span className="online-panel-label">Leaderboard</span>
                    <span className="online-panel-count">
                      Round {publicState.round_number}
                    </span>
                  </div>

                  <div className="online-panel-card">
                    <ul className="player-list">
                      {[...publicState.players]
                        .sort((a, b) => b.score - a.score)
                        .map((p) => {
                          const pIdx = playerIndexMap.get(p.player_id) ?? 0;
                          const isImp =
                            p.player_id === publicState.outcome?.imposter_id;
                          const delta =
                            publicState.outcome?.score_deltas[p.player_id] || 0;
                          const playerClues = publicState.clues
                            .filter((c) => c.player_id === p.player_id)
                            .map((c) => c.clue)
                            .join(" · ");
                          return (
                            <li key={p.player_id} className="player-row">
                              <span
                                className="player-avatar"
                                style={{ backgroundColor: avatarColor(pIdx) }}
                              >
                                {p.nickname.charAt(0).toUpperCase()}
                              </span>
                              <div className="player-main">
                                <span className="player-name">
                                  {p.nickname}
                                </span>
                                {isImp && (
                                  <span className="badge-pill badge-imposter">
                                    Imposter
                                  </span>
                                )}
                                {playerClues && (
                                  <span className="field-hint">
                                    Clues: {playerClues}
                                  </span>
                                )}
                              </div>
                              <div className="player-right">
                                {delta > 0 && (
                                  <span className="delta-badge">+{delta}</span>
                                )}
                                <strong className="score-label">
                                  {p.score} pts
                                </strong>
                              </div>
                            </li>
                          );
                        })}
                    </ul>
                  </div>
                </div>

                <div className="online-stage-footer">
                  {isHost ? (
                    <>
                      <button
                        type="button"
                        className="stage-btn is-primary"
                        onClick={() => sendWsAction({ type: "play_again" })}
                      >
                        Play Again
                      </button>
                      <div className="footer-split-row">
                        <button
                          type="button"
                          className="stage-btn is-secondary"
                          onClick={() =>
                            sendWsAction({ type: "return_to_lobby" })
                          }
                        >
                          Back to Lobby
                        </button>
                        <button
                          type="button"
                          className="stage-btn is-secondary"
                          onClick={() => sendWsAction({ type: "reset_scores" })}
                        >
                          Reset Scores
                        </button>
                      </div>
                    </>
                  ) : (
                    <div className="stage-status">
                      <span className="stage-status-dot" />
                      <span>Waiting for host to start next round...</span>
                    </div>
                  )}
                </div>
              </section>
            )}
          </>
        )}
      </main>

      {/* UNO Q 8x13 LED Matrix & Host Settings Modal */}
      {settingsOpen && (
        <div
          className="modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-labelledby="settings-modal-title"
          onClick={() => setSettingsOpen(false)}
        >
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head-row">
              <h2 id="settings-modal-title" className="modal-title">
                UNO Q Matrix &amp; Settings
              </h2>
              <button
                type="button"
                className="circle-icon-btn"
                onClick={() => setSettingsOpen(false)}
                aria-label="Close settings"
              >
                <X size={18} weight="bold" />
              </button>
            </div>

            {publicState?.matrix && (
              <MatrixVisualizer
                matrix={publicState.matrix}
                canTestHardware={isHost}
                onTriggerTestState={handleTriggerMatrixTest}
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
