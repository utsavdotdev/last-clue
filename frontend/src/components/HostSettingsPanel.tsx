import React, { useState } from "react";
import { Cpu, Sliders, Sparkle } from "@phosphor-icons/react";
import type { PublicGameState } from "../types/game";

interface HostSettingsPanelProps {
  game: PublicGameState;
  playerId: string;
  token: string;
  onUpdateSettings: (payload: {
    selected_category?: string;
    discussion_seconds?: number;
    voting_seconds?: number;
    ai_enabled?: boolean;
  }) => void;
}

export const HostSettingsPanel: React.FC<HostSettingsPanelProps> = ({
  game,
  playerId,
  token,
  onUpdateSettings,
}) => {
  const [aiCategory, setAiCategory] = useState("Haunted Relics");
  const [summoning, setSummoning] = useState(false);
  const [aiFeedback, setAiFeedback] = useState<string | null>(null);

  const handleSummonWords = async () => {
    setSummoning(true);
    setAiFeedback(null);
    try {
      const resp = await fetch(
        `/api/host/ai/generate-words?category=${encodeURIComponent(
          aiCategory
        )}&player_id=${encodeURIComponent(playerId)}&token=${encodeURIComponent(
          token
        )}`,
        { method: "POST" }
      );
      const data = await resp.json();
      if (!resp.ok) {
        setAiFeedback(data.detail || "Local AI unavailable; using built-in word packs.");
      } else {
        const words = (data.generated || []).map((w: { word: string }) => w.word).join(", ");
        setAiFeedback(`Added AI words: ${words}`);
      }
    } catch {
      setAiFeedback("Local AI request failed; built-in word packs remain active.");
    } finally {
      setSummoning(false);
    }
  };

  return (
    <section className="panel host-settings-panel" aria-label="Host Controls and Local AI Status">
      <div className="panel-header-row">
        <div className="row-center gap-2">
          <Sliders size={18} />
          <h3 className="panel-subtitle">Host Ritual Configuration</h3>
        </div>
        <span
          className={
            game.ai_status.status === "READY"
              ? "status-pill status-ready"
              : game.ai_status.status === "GENERATING"
              ? "status-pill status-generating"
              : "status-pill status-fallback"
          }
        >
          <Cpu size={14} />
          {game.ai_status.status === "READY"
            ? `AI READY (${game.ai_status.model})`
            : game.ai_status.status === "GENERATING"
            ? "AI GENERATING..."
            : "AI UNAVAILABLE - USING BUILT-IN CONTENT"}
        </span>
      </div>

      <p className="helper-label">{game.ai_status.detail}</p>

      <div className="settings-form-grid">
        <div className="form-field">
          <label htmlFor="category-select">Horror Theme Category</label>
          <select
            id="category-select"
            className="input-control"
            value={game.selected_category || "random"}
            onChange={(e) =>
              onUpdateSettings({ selected_category: e.target.value })
            }
          >
            <option value="random">Random Category Each Round</option>
            {game.available_categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </div>

        <div className="form-field">
          <label htmlFor="discussion-timer">Discussion Timer (Seconds)</label>
          <select
            id="discussion-timer"
            className="input-control"
            value={game.discussion_seconds}
            onChange={(e) =>
              onUpdateSettings({ discussion_seconds: Number(e.target.value) })
            }
          >
            <option value={30}>30s (Fast Round)</option>
            <option value={60}>60s (Standard)</option>
            <option value={90}>90s (Extended)</option>
            <option value={120}>120s (Deep Investigation)</option>
          </select>
        </div>

        <div className="form-field">
          <label htmlFor="voting-timer">Voting Timer (Seconds)</label>
          <select
            id="voting-timer"
            className="input-control"
            value={game.voting_seconds}
            onChange={(e) =>
              onUpdateSettings({ voting_seconds: Number(e.target.value) })
            }
          >
            <option value={30}>30s</option>
            <option value={45}>45s (Standard)</option>
            <option value={60}>60s</option>
          </select>
        </div>

        <div className="form-field">
          <label htmlFor="ai-toggle">On-Board Local AI Flavor</label>
          <select
            id="ai-toggle"
            className="input-control"
            value={game.ai_status.status === "DISABLED" ? "off" : "on"}
            onChange={(e) =>
              onUpdateSettings({ ai_enabled: e.target.value === "on" })
            }
          >
            <option value="on">Enabled (Local UNO Q Model + Fallback)</option>
            <option value="off">Disabled (Bundled Word Packs Only)</option>
          </select>
        </div>
      </div>

      <div className="ai-wordpack-box">
        <div className="form-field">
          <label htmlFor="ai-custom-cat">
            Optional Local AI Candidate Word Pack ({game.ai_status.custom_words_count} cached)
          </label>
          <div className="inline-input-row">
            <input
              id="ai-custom-cat"
              type="text"
              className="input-control"
              maxLength={32}
              value={aiCategory}
              onChange={(e) => setAiCategory(e.target.value)}
              placeholder="Category name"
            />
            <button
              type="button"
              className="btn btn-secondary"
              disabled={summoning || game.ai_status.status === "DISABLED"}
              onClick={handleSummonWords}
            >
              <Sparkle size={16} />
              {summoning ? "Summoning..." : "Summon AI Words"}
            </button>
          </div>
          {aiFeedback && <p className="helper-label">{aiFeedback}</p>}
        </div>
      </div>
    </section>
  );
};
