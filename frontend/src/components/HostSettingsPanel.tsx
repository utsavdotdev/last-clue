import React, { useState } from "react";
import type { PublicGameState } from "../types/game";

interface HostSettingsPanelProps {
  game: PublicGameState;
  playerId: string;
  token: string;
  onUpdateSettings: (payload: {
    selected_category?: string;
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
        setAiFeedback(data.detail || "Using built-in word packs.");
      } else {
        const words = (data.generated || [])
          .map((w: { word: string }) => w.word)
          .join(", ");
        setAiFeedback(`Added AI words: ${words}`);
      }
    } catch {
      setAiFeedback("Using built-in word packs.");
    } finally {
      setSummoning(false);
    }
  };

  return (
    <div className="host-settings-group">
      <div className="config-list">
        <div className="config-item">
          <label htmlFor="host-category-select" className="config-label">
            Category
          </label>
          <select
            id="host-category-select"
            className="select-input"
            value={game.selected_category || "random"}
            onChange={(e) =>
              onUpdateSettings({ selected_category: e.target.value })
            }
          >
            <option value="random">Random Theme</option>
            {game.available_categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </div>

        <div className="config-item">
          <div>
            <span className="config-label">Local UNO Q AI</span>
            <span className="field-hint">{game.ai_status.detail}</span>
          </div>
          <label className="switch-toggle">
            <input
              type="checkbox"
              checked={game.ai_status.status !== "DISABLED"}
              onChange={(e) =>
                onUpdateSettings({ ai_enabled: e.target.checked })
              }
              aria-label="Enable Local UNO Q AI"
            />
            <span className="switch-track" />
          </label>
        </div>
      </div>

      {game.ai_status.status !== "DISABLED" && (
        <div className="custom-word-box">
          <label htmlFor="ai-custom-cat" className="block-title">
            Generate AI Words ({game.ai_status.custom_words_count} saved)
          </label>
          <div className="inline-field-row">
            <input
              id="ai-custom-cat"
              type="text"
              className="text-input"
              maxLength={32}
              value={aiCategory}
              onChange={(e) => setAiCategory(e.target.value)}
              placeholder="Theme name"
            />
            <button
              type="button"
              className="pill-btn pill-btn-secondary pill-btn-inline"
              disabled={summoning}
              onClick={handleSummonWords}
            >
              {summoning ? "Adding..." : "Generate"}
            </button>
          </div>
          {aiFeedback && <p className="field-hint">{aiFeedback}</p>}
        </div>
      )}
    </div>
  );
};
