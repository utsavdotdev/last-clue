import React from "react";
import type { GhostMatrixState, MatrixPreviewView } from "../types/game";

const ALL_STATES: GhostMatrixState[] = [
  "BOOT",
  "LOBBY",
  "ROLES_ASSIGNED",
  "CLUE_PHASE",
  "VOTING_PHASE",
  "RUNOFF",
  "IMPOSTER_DISCOVERED",
  "SURVIVORS_WIN",
  "IMPOSTER_WINS",
  "IDLE",
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
    <section className="panel matrix-panel" aria-label="Arduino UNO Q 8x13 LED Matrix">
      <div className="matrix-header">
        <div>
          <span className="mono-tag">
            {matrix.hardware_connected
              ? "HARDWARE BRIDGE: UNO Q 8x13 LED MATRIX"
              : "SIMULATED 8x13 MATRIX (MACOS / WEB)"}
          </span>
          <h3 className="panel-subtitle">{matrix.label}</h3>
        </div>
        <span className="mono-badge" title="Active state code and generation">
          STATE #{matrix.state_code} / GEN {matrix.generation}
        </span>
      </div>

      <div
        className="led-grid-frame"
        role="img"
        aria-label={`8 by 13 LED Matrix showing ${matrix.state}`}
      >
        <div className="led-grid">
          {pixels.map((lit, index) => (
            <span
              key={index}
              className={lit ? "led-cell led-on" : "led-cell led-off"}
            />
          ))}
        </div>
      </div>

      {canTestHardware && onTriggerTestState && (
        <div className="matrix-test-bar">
          <p className="helper-label">
            Hardware Diagnostic: Test all 10 ghost states on UNO Q 8x13 matrix
          </p>
          <div className="matrix-state-pills">
            {ALL_STATES.map((st) => (
              <button
                key={st}
                type="button"
                className={
                  matrix.state === st
                    ? "chip-btn chip-btn-active"
                    : "chip-btn"
                }
                onClick={() => onTriggerTestState(st)}
              >
                {st.replace(/_/g, " ")}
              </button>
            ))}
          </div>
        </div>
      )}
    </section>
  );
};
