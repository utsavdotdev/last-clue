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
          <div>
            <span className="mono-tag">PARANORMAL FIELD MANUAL</span>
            <h2 id="rules-title" className="section-title">How to Play The Last Clue</h2>
          </div>
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
            <span className="mono-step">01 / SECRET ROLES</span>
            <p>
              4 to 10 players join on the same Wi-Fi network. Every <strong>Survivor</strong> receives
              the exact same secret horror word. Exactly one player is the <strong>Imposter</strong>,
              who sees only the category name and must blend in.
            </p>
          </div>

          <div className="rule-item">
            <span className="mono-step">02 / ONE CLUE EACH</span>
            <p>
              Players speak in a randomized turn order. Submit one short clue (up to 40 characters)
              proving you know the secret word without giving it away to the Imposter.
            </p>
          </div>

          <div className="rule-item">
            <span className="mono-step">03 / DISCUSSION &amp; SECRET VOTE</span>
            <p>
              Debate the clues before the timer runs out, then cast one secret ballot. You cannot
              vote for yourself. If the top suspects tie, a single runoff vote is held between the
              tied players. If the runoff ties again, no one is caught and the Imposter escapes.
            </p>
          </div>

          <div className="rule-item">
            <span className="mono-step">04 / THE LAST CLUE &amp; SCORING</span>
            <p>
              If the group catches the Imposter, the Imposter gets <strong>one final guess</strong> at
              the secret word. If they guess right (or escape the vote), the Imposter wins and earns{" "}
              <strong>+2 points</strong>. If their final guess is wrong, Survivors win and every
              Survivor who voted for the Imposter earns <strong>+1 point</strong>.
            </p>
          </div>
        </div>

        <div className="modal-footer">
          <button type="button" className="btn btn-primary" onClick={onClose}>
            Understood
          </button>
        </div>
      </div>
    </div>
  );
};
