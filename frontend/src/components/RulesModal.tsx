import React from "react";
import { X } from "@phosphor-icons/react";

interface RulesModalProps {
  open: boolean;
  onClose: () => void;
}

export const RulesModal: React.FC<RulesModalProps> = ({ open, onClose }) => {
  if (!open) return null;

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="rules-title"
      onClick={onClose}
    >
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head-row">
          <h2 id="rules-title" className="modal-title">How to Play</h2>
          <button
            type="button"
            className="circle-icon-btn"
            onClick={onClose}
            aria-label="Close rules"
          >
            <X size={18} weight="bold" />
          </button>
        </div>

        <ol className="rules-ordered-list">
          <li>
            <strong>Draw Cards</strong>
            <span>
              Everyone receives the same secret horror word except one player: the
              Imposter, who only sees the category.
            </span>
          </li>
          <li>
            <strong>Give Clues</strong>
            <span>
              Take turns giving one short clue related to the secret word. Be subtle
              so the Imposter cannot guess it.
            </span>
          </li>
          <li>
            <strong>Vote or Continue</strong>
            <span>
              After each clue round, choose to <strong>Start Voting</strong> or play{" "}
              <strong>Another Clue Round</strong> at your own pace.
            </span>
          </li>
          <li>
            <strong>The Last Clue</strong>
            <span>
              If caught, the Imposter gets one final guess at the secret word to win
              (+2 pts). Otherwise Survivors win (+1 pt per correct vote).
            </span>
          </li>
        </ol>

        <button type="button" className="pill-btn pill-btn-primary" onClick={onClose}>
          Got It
        </button>
      </div>
    </div>
  );
};
