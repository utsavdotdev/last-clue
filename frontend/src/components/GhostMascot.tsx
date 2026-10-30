import React from "react";

interface GhostMascotProps {
  mood?: "calm" | "curious" | "alert" | "victory" | "defeated";
  size?: number;
}

export const GhostMascot: React.FC<GhostMascotProps> = ({
  mood = "calm",
  size = 68,
}) => {
  const isAlert = mood === "alert" || mood === "victory";
  const bodyFill = isAlert ? "#ffffff" : "#ffffff";
  const strokeColor = "#00142f";

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 72 72"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      className="ghost-mascot-svg"
    >
      {/* Classic sheet ghost silhouette with scalloped hem */}
      <path
        d="M16 34C16 21.8497 24.9543 12 36 12C47.0457 12 56 21.8497 56 34V57C56 58.6 54.1 59.5 52.8 58.4L48.5 54.8C47.4 53.9 45.8 53.9 44.7 54.8L40.3 58.5C37.8 60.5 34.2 60.5 31.7 58.5L27.3 54.8C26.2 53.9 24.6 53.9 23.5 54.8L19.2 58.4C17.9 59.5 16 58.6 16 57V34Z"
        fill={bodyFill}
        stroke={strokeColor}
        strokeWidth="3.5"
        strokeLinejoin="round"
      />
      {/* Eyes */}
      {mood === "defeated" ? (
        <>
          <path
            d="M26 31L31 36M31 31L26 36"
            stroke={strokeColor}
            strokeWidth="3"
            strokeLinecap="round"
          />
          <path
            d="M41 31L46 36M46 31L41 36"
            stroke={strokeColor}
            strokeWidth="3"
            strokeLinecap="round"
          />
        </>
      ) : (
        <>
          <circle cx="28.5" cy="33" r="3.6" fill={strokeColor} />
          <circle cx="43.5" cy="33" r="3.6" fill={strokeColor} />
          {isAlert && (
            <path
              d="M24 27L32 30M48 27L40 30"
              stroke="#e11d38"
              strokeWidth="3"
              strokeLinecap="round"
            />
          )}
        </>
      )}
      {/* Mouth */}
      {mood === "victory" ? (
        <path
          d="M29 42C31 46 41 46 43 42"
          stroke="#e11d38"
          strokeWidth="3"
          strokeLinecap="round"
        />
      ) : mood === "alert" ? (
        <rect
          x="32"
          y="40"
          width="8"
          height="7"
          rx="3.5"
          fill="#e11d38"
        />
      ) : (
        <ellipse cx="36" cy="42.5" rx="3.5" ry="4.2" fill={strokeColor} />
      )}
    </svg>
  );
};
