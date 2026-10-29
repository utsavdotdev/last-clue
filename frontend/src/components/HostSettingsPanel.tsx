import React, { useState } from "react";
import { Cpu, Sparkle } from "@phosphor-icons/react";
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
        const words = (data.generated || []).map((w: { word: string }) => w.word).join(", ");
        setAiFeedback(`Added: ${words}`);
      }
    } catch {
      setAiFeedback("Using built-in word packs.");
    } finally {
      setSummoning(false);
    }
  };

  return (
    <section className="host-settings-block" aria-label="Host Settings">
      <div className="settings-form-grid">
        <div className="form-field">
          <label htmlFor="category-select">Category</label>
          <select
            id="category-select"
            className="input-control"
            value={game.selected_category || "random"}
            onChange={(e) =>
              onUpdateSettings({ selected_category: e.target.value })
            }
          >
            <option value="random">Random Category</option>
            {game.available_categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </div>

        <div className="form-field">
          <label htmlFor="ai-toggle">Local UNO Q AI</label>
          <select
            id="ai-toggle"
            className="input-control"
            value={game.ai_status.status === "DISABLED" ? "off" : "on"}
            onChange={(e) =>
              onUpdateSettings({ ai_enabled: e.target.value === "on" })
            }
          >
            <option value="on">Enabled (Local AI + Fallback)</option>
            <option value="off">Off (Built-in Packs Only)</option>
          </select>
        </div>
      </div>

      <div className="ai-wordpack-box">
        <div className="row-between">
          <span className="helper-label">
            <Cpu size={14} style={{ verticalAlign: "middle", marginRight: 4 }} />
            {game.ai_status.detail}
          </span>
          <span className="mono-badge">{game.ai_status.custom_words_count} AI words</span>
        </div>

        <div className="inline-input-row" style={{ marginTop: "0.5rem" }}>
          <input
            id="ai-custom-cat"
            type="text"
            className="input-control"
            maxLength={32}
            value={aiCategory}
            onChange={(e) => setAiCategory(e.target.value)}
            placeholder="Custom AI theme..."
          />
          <button
            type="button"
            className="btn btn-secondary"
            disabled={summoning || game.ai_status.status === "DISABLED"}
            onClick={handleSummonWords}
          >
            <Sparkle size={16} />
            {summoning ? "..." : "Add Words"}
          </button>
        </div>
        {aiFeedback && <p className="helper-label">{aiFeedback}</p>}
      </div>
    </section>
  );
};
