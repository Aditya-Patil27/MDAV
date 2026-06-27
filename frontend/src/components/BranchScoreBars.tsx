// Per-branch score breakdown for the fused authenticity decision.
// Weights mirror backend fusion logic: visual 0.40, semantic 0.35, signature 0.25.
// When no signature is present the backend reweights to visual 0.60 / semantic 0.40.

interface FusedScores {
  visual_score: number | null;
  semantic_score: number | null;
  signature_score: number | null;
}

const BARS = [
  { key: "visual_score", label: "Visual Forensics", weight: 0.4, color: "bg-blue-500" },
  { key: "semantic_score", label: "OCR & Semantic", weight: 0.35, color: "bg-teal-500" },
  { key: "signature_score", label: "Digital Signature", weight: 0.25, color: "bg-purple-500" },
] as const;

export default function BranchScoreBars({
  fused,
  signaturePresent,
}: {
  fused: FusedScores;
  signaturePresent: boolean;
}) {
  // Reflect the reweighted split the backend applies when no signature exists.
  const weights = signaturePresent
    ? { visual_score: 0.4, semantic_score: 0.35, signature_score: 0.25 }
    : { visual_score: 0.6, semantic_score: 0.4, signature_score: 0 };

  return (
    <div className="space-y-4">
      {BARS.map(({ key, label, color }) => {
        const score = fused[key];
        const weight = weights[key];
        const isInactive = key === "signature_score" && !signaturePresent;
        const pct = score != null ? Math.max(0, Math.min(1, score)) * 100 : 0;

        return (
          <div key={key} className={isInactive ? "opacity-50" : ""}>
            <div className="mb-1 flex items-center justify-between text-sm">
              <span className="text-gray-700">
                {label}
                <span className="ml-2 text-xs text-gray-400">
                  weight {(weight * 100).toFixed(0)}%
                </span>
              </span>
              <span className="font-medium text-gray-900">
                {isInactive ? "n/a" : score != null ? `${pct.toFixed(0)}%` : "—"}
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-gray-100">
              <div
                className={`h-full rounded-full ${color}`}
                style={{ width: `${pct}%`, transition: "width 0.6s ease" }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
