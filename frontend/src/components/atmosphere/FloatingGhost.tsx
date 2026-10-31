import React from "react";
import { GhostFigure, type GhostMood } from "./GhostFigure";

interface FloatingGhostProps {
  mood: GhostMood;
}

export const FloatingGhost: React.FC<FloatingGhostProps> = ({ mood }) => {
  return (
    <div className="ghost-wander">
      <div className="ghost-bob">
        <span className="ghost-aura" />
        <GhostFigure mood={mood} size={78} />
      </div>
    </div>
  );
};
