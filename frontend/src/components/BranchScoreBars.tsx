// Per-branch breakdown for the fused authenticity decision.
//
// The backend fuses branches with Dempster-Shafer, discounting each by a source
// *reliability* (not an additive weight). Each bar shows that branch's pignistic
// P(authentic). Branches that did not contribute (vacuous / pending / inactive)
// are dimmed. Renders generically from `fused.branches`, so new branches (e.g.
// the AIForge diffusion model) appear automatically once the backend emits them.

import type { BranchInfo, BranchStatus } from "@/types";

// Structural subset of FusedResult this component needs -- kept loose so callers
// with a plain `decision: string` (e.g. the results page) type-check cleanly.
interface FusedLike {
  visual_score: number;
  semantic_score: number;
  signature_score: number;
  branches?: Record<string, BranchInfo> | null;
}

// Display order + reliability (mirrors backend RELIABILITY) + bar colour.
const ORDER: { key: string; reliability: number; color: string }[] = [
  { key: "signature", reliability: 0.95, color: "bg-purple-500" },
  { key: "qr", reliability: 0.9, color: "bg-pink-500" },
  { key: "visual", reliability: 0.85, color: "bg-blue-500" },
  { key: "diffusion", reliability: 0.8, color: "bg-amber-500" },
  { key: "semantic", reliability: 0.7, color: "bg-teal-500" },
  { key: "layout", reliability: 0.4, color: "bg-slate-400" },
];

const STATUS_LABEL: Record<BranchStatus, string> = {
  active: "",
  inactive: "not present",
  mock: "model offline",
  pending: "awaiting model",
  error: "error",
};

// Fallback when the backend hasn't sent the rich `branches` payload yet.
function legacyBranches(fused: FusedLike): Record<string, BranchInfo> {
  const mk = (label: string, score: number | null | undefined): BranchInfo => ({
    label,
    score: score ?? 0.5,
    belief: null,
    status: "active",
    detail: {},
  });
  return {
    visual: mk("Visual Forensics", fused.visual_score),
    semantic: mk("OCR & Semantic", fused.semantic_score),
    signature: mk("Digital Signature", fused.signature_score),
  };
}

export default function BranchScoreBars({ fused }: { fused: FusedLike }) {
  const branches = fused.branches ?? legacyBranches(fused);

  return (
    <div className="space-y-4">
      {ORDER.filter(({ key }) => branches[key]).map(({ key, reliability, color }) => {
        const b = branches[key];
        const inactive = b.status !== "active";
        const pct = Math.max(0, Math.min(1, b.score ?? 0.5)) * 100;
        const note = STATUS_LABEL[b.status];

        return (
          <div key={key} className={inactive ? "opacity-50" : ""}>
            <div className="mb-1 flex items-center justify-between text-sm">
              <span className="text-gray-700">
                {b.label}
                <span className="ml-2 text-xs text-gray-400">
                  reliability {(reliability * 100).toFixed(0)}%
                </span>
              </span>
              <span className="font-medium text-gray-900">
                {note ? note : `${pct.toFixed(0)}%`}
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-gray-100">
              <div
                className={`h-full rounded-full ${color}`}
                style={{ width: note ? "0%" : `${pct}%`, transition: "width 0.6s ease" }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
