import React from "react";
import { GhostFigure } from "./GhostFigure";

export const GhostParticles: React.FC = () => {
  return (
    <>
      <div className="ghost-mist ghost-mist-a" />
      <div className="ghost-mist ghost-mist-b" />
      <div className="ghost-particle" />
      <div className="ghost-particle" />
      <div className="ghost-particle" />
      <div className="ghost-particle" />
      <div className="ghost-particle" />
      <div className="ghost-distant ghost-distant-a">
        <GhostFigure mood="peaceful" size={40} />
      </div>
      <div className="ghost-distant ghost-distant-b">
        <GhostFigure mood="wander" size={32} />
      </div>
    </>
  );
};
