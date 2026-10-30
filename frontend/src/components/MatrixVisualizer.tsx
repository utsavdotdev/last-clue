import React from "react";
import type { GhostMatrixState, MatrixPreviewView } from "../types/game";

const ALL_STATES: { id: GhostMatrixState; label: string }[] = [
  { id: "BOOT", label: "Boot" },
  { id: "LOBBY", label: "Lobby" },
  { id: "ROLES_ASSIGNED", label: "Roles" },
  { id: "CLUE_PHASE", label: "Clues" },
  { id: "VOTING_PHASE", label: "Voting" },
  { id: "RUNOFF", label: "Runoff" },
  { id: "IMPOSTER_DISCOVERED", label: "Caught" },
  { id: "SURVIVORS_WIN", label: "Survivors Win" },
  { id: "IMPOSTER_WINS", label: "Imposter Wins" },
  { id: "IDLE", label: "Idle" },
];

interface MatrixVisualizerProps {
  matrix: MatrixPreviewView;
  canTestHardware?: boolean;
  onTriggerTestState?: (state: GhostMatrixState) => void;
}

export const MatrixVisualizer: React.FC<MatrixVisualizerProps> = ({
  matrix,
  canTestHardware = false,
  onTriggerTestState,
}) => {
  const pixels =
    matrix.pixels && matrix.pixels.length === 104
      ? matrix.pixels
      : Array<number>(104).fill(0);

  return (
    <div className="matrix-section" data-ui="true">
      <div className="row-between">
        <strong className="block-title">
          {matrix.hardware_connected
            ? "Arduino UNO Q 8x13 LED Matrix"
            : "8x13 LED Matrix Simulator"}
        </strong>
        <span className="pill-tag">{matrix.label.split(":").pop()?.trim() || matrix.state}</span>
      </div>

      <div
        className="led-board"
        role="img"
        aria-label={`8 by 13 LED Matrix showing ${matrix.state}`}
      >
        <div className="led-grid">
          {pixels.map((lit, index) => (
            <span
              key={index}
              className={lit ? "led-dot led-dot-on" : "led-dot led-dot-off"}
            />
          ))}
        </div>
      </div>

      {canTestHardware && onTriggerTestState && (
        <div className="matrix-controls">
          <span className="field-hint">Tap to test state on UNO Q matrix:</span>
          <div className="matrix-chip-row">
            {ALL_STATES.map((st) => (
              <button
                key={st.id}
                type="button"
                className={
                  matrix.state === st.id
                    ? "state-chip state-chip-active"
                    : "state-chip"
                }
                onClick={() => onTriggerTestState(st.id)}
              >
                {st.label}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
