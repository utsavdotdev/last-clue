import React from "react";
import { X } from "@phosphor-icons/react";

interface RulesModalProps {
  open: boolean;
  onClose: () => void;
}

export const RulesModal: React.FC<RulesModalProps> = ({ open, onClose }) => {
  if (!open) return null;

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="rules-title">
      <div className="modal-sheet">
        <div className="modal-header">
          <h2 id="rules-title" className="section-title">How to Play</h2>
          <button
            type="button"
            className="icon-btn"
            onClick={onClose}
            aria-label="Close rules"
          >
            <X size={20} weight="regular" />
          </button>
        </div>

        <div className="rules-grid">
          <div className="rule-item">
            <span className="mono-step">1. DRAW CARDS</span>
            <p>
              Everyone gets the same secret horror word except one player: the{" "}
              <strong>Imposter</strong>, who only sees the category.
            </p>
          </div>

          <div className="rule-item">
            <span className="mono-step">2. GIVE CLUES</span>
            <p>
              Take turns giving one short clue related to the secret word. Be subtle so the
              Imposter cannot guess it.
            </p>
          </div>

          <div className="rule-item">
            <span className="mono-step">3. VOTE OR PLAY ANOTHER ROUND</span>
            <p>
              After everyone gives a clue, choose <strong>Start Voting</strong> or{" "}
              <strong>Another Clue Round</strong> until you are ready to accuse.
            </p>
          </div>

          <div className="rule-item">
            <span className="mono-step">4. THE LAST CLUE</span>
            <p>
              If caught, the Imposter gets one final guess at the secret word to steal the win
              (+2 pts). Otherwise Survivors win (+1 pt per correct vote).
            </p>
          </div>
        </div>

        <div className="modal-footer">
          <button type="button" className="btn btn-primary full-width" onClick={onClose}>
            Got It
          </button>
        </div>
      </div>
    </div>
  );
};
