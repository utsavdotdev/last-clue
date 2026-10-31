import React from "react";

export type GhostMood =
  | "wander"
  | "sleep"
  | "curious"
  | "watch"
  | "suspicious"
  | "dramatic"
  | "defeated"
  | "mischievous"
  | "peaceful";

interface GhostFigureProps {
  mood?: GhostMood;
  size?: number;
  opacity?: number;
}

export const GhostFigure: React.FC<GhostFigureProps> = ({
  mood = "wander",
  size = 72,
  opacity = 1,
}) => {
  const intense = mood === "suspicious" || mood === "dramatic";
  const stroke = "#00142f";

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 72 72"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      className={`ghost-figure mood-${mood}`}
      style={{ opacity }}
    >
      <path
        d="M16 34C16 21.85 24.95 12 36 12C47.05 12 56 21.85 56 34V57C56 58.6 54.1 59.5 52.8 58.4L48.5 54.8C47.4 53.9 45.8 53.9 44.7 54.8L40.3 58.5C37.8 60.5 34.2 60.5 31.7 58.5L27.3 54.8C26.2 53.9 24.6 53.9 23.5 54.8L19.2 58.4C17.9 59.5 16 58.6 16 57V34Z"
        fill="#ffffff"
        fillOpacity="0.9"
        stroke={stroke}
        strokeWidth="3.2"
        strokeLinejoin="round"
      />

      {mood === "defeated" ? (
        <>
          <path d="M26 31L31 36M31 31L26 36" stroke={stroke} strokeWidth="2.8" strokeLinecap="round" />
          <path d="M41 31L46 36M46 31L41 36" stroke={stroke} strokeWidth="2.8" strokeLinecap="round" />
        </>
      ) : mood === "sleep" ? (
        <>
          <path d="M25.5 34c2.2-2 6.2-2 8.2 0" stroke={stroke} strokeWidth="2.6" strokeLinecap="round" />
          <path d="M38.3 34c2.2-2 6.2-2 8.2 0" stroke={stroke} strokeWidth="2.6" strokeLinecap="round" />
        </>
      ) : (
        <g className="ghost-eyes">
          <circle cx="28.5" cy={mood === "curious" ? 31.8 : 33} r={intense ? 4.1 : 3.5} fill={intense ? "#e11d38" : stroke} />
          <circle cx="43.5" cy={mood === "curious" ? 31.8 : 33} r={intense ? 4.1 : 3.5} fill={intense ? "#e11d38" : stroke} />
          {intense && (
            <>
              <path d="M24 26.5L32 30" stroke="#e11d38" strokeWidth="2.6" strokeLinecap="round" />
              <path d="M48 26.5L40 30" stroke="#e11d38" strokeWidth="2.6" strokeLinecap="round" />
            </>
          )}
        </g>
      )}

      {mood === "mischievous" ? (
        <path d="M29 42C31 46.5 41 46.5 43 42" stroke="#e11d38" strokeWidth="2.8" strokeLinecap="round" />
      ) : mood === "dramatic" ? (
        <rect x="32" y="40" width="8" height="7" rx="3.5" fill="#e11d38" />
      ) : mood === "sleep" || mood === "peaceful" ? (
        <path d="M33 43.5h6" stroke={stroke} strokeWidth="2.4" strokeLinecap="round" />
      ) : mood === "defeated" ? (
        <ellipse cx="36" cy="44" rx="3" ry="2.2" fill={stroke} />
      ) : (
        <ellipse cx="36" cy="42.8" rx="3.1" ry={mood === "curious" ? 3.2 : 3.8} fill={stroke} />
      )}
    </svg>
  );
};
