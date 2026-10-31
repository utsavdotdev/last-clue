import React, { useEffect, useRef, useState } from "react";
import type { GamePhase, WinnerSide } from "../../types/game";
import { FloatingGhost } from "./FloatingGhost";
import { GhostParticles } from "./GhostParticles";
import { type GhostMood } from "./GhostFigure";
import "./GhostEffects.css";

export type AtmospherePhase = GamePhase | "LANDING";

interface GhostBackgroundProps {
  phase: AtmospherePhase;
  winner?: WinnerSide | null;
  clueRound?: number;
}

function moodForPhase(
  phase: AtmospherePhase,
  winner: WinnerSide | null | undefined,
  clueRound: number,
): GhostMood {
  if (phase === "LANDING") return "wander";
  if (phase === "LOBBY") return "sleep";
  if (phase === "ROLE_REVEAL") return "curious";
  if (phase === "CLUE_ROUND") return clueRound > 1 ? "curious" : "watch";
  if (phase === "DISCUSSION") return "curious";
  if (phase === "VOTING" || phase === "RUNOFF") return "suspicious";
  if (phase === "FINAL_GUESS") return "dramatic";
  if (phase === "RESULTS") {
    if (winner === "SURVIVORS") return "defeated";
    if (winner === "IMPOSTER") return "mischievous";
    return "peaceful";
  }
  return "wander";
}

export const GhostBackground: React.FC<GhostBackgroundProps> = React.memo(
  ({ phase, winner = null, clueRound = 1 }) => {
    const [hidden, setHidden] = useState(false);
    const [moment, setMoment] = useState<"none" | "reveal" | "vanish">("none");
    const prevPhaseRef = useRef<AtmospherePhase>(phase);
    const mood = moodForPhase(phase, winner, clueRound);

    useEffect(() => {
      const onVisibility = () => setHidden(document.hidden);
      onVisibility();
      document.addEventListener("visibilitychange", onVisibility);
      return () => document.removeEventListener("visibilitychange", onVisibility);
    }, []);

    useEffect(() => {
      const previous = prevPhaseRef.current;
      prevPhaseRef.current = phase;
      if (previous === phase) return;

      if (phase === "FINAL_GUESS") {
        setMoment("reveal");
      } else if (phase === "RESULTS" && winner === "SURVIVORS") {
        setMoment("vanish");
      } else {
        setMoment("none");
        return;
      }

      const timer = window.setTimeout(() => setMoment("none"), 3200);
      return () => window.clearTimeout(timer);
    }, [phase, winner]);

    return (
      <div
        className="ghost-atmosphere"
        data-mood={mood}
        data-phase={phase}
        data-moment={moment}
        data-hidden={hidden}
        aria-hidden="true"
      >
        <GhostParticles />
        <FloatingGhost mood={mood} />
      </div>
    );
  },
);

GhostBackground.displayName = "GhostBackground";
