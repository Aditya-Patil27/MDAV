// Circular authenticity-score gauge, colored by decision thresholds
// APPROVED >= 0.8 (green), FLAGGED >= 0.5 (amber), else red — mirrors fusion logic.

function colorFor(score: number): string {
  if (score >= 0.8) return "#16a34a"; // green-600
  if (score >= 0.5) return "#d97706"; // amber-600
  return "#dc2626"; // red-600
}

export default function ScoreRing({
  score,
  size = 140,
  stroke = 12,
}: {
  score: number; // 0..1
  size?: number;
  stroke?: number;
}) {
  const clamped = Math.max(0, Math.min(1, score));
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - clamped);
  const color = colorFor(clamped);

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#e5e7eb"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 0.6s ease" }}
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-3xl font-bold" style={{ color }}>
          {(clamped * 100).toFixed(0)}
        </span>
        <span className="text-xs text-gray-500">/ 100</span>
      </div>
    </div>
  );
}
