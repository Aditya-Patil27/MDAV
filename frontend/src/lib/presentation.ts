import type { BranchBelief, BranchInfo, BranchStatus, Decision } from "@/types";

export const SCORE_FORMULA_LABEL =
  "BetP(A) = authentic belief + 0.5 x uncertainty";

export function scoreFormulaLabel(formula: string | null | undefined): string {
  if (!formula || formula === "pignistic_authenticity_v1") return SCORE_FORMULA_LABEL;
  return humanizeEnum(formula);
}

export function clamp01(value: number | null | undefined): number | null {
  if (value == null || !Number.isFinite(value)) return null;
  return Math.max(0, Math.min(1, value));
}

export function formatPercent(
  value: number | null | undefined,
  digits = 1,
): string {
  const normalized = clamp01(value);
  return normalized == null ? "N/A" : `${(normalized * 100).toFixed(digits)}%`;
}

export function formatDecisionScore(value: number | null | undefined): string {
  const normalized = clamp01(value);
  return normalized == null ? "N/A" : `${(normalized * 100).toFixed(1)} / 100`;
}

export function humanizeEnum(value: string | null | undefined): string {
  if (!value) return "Unknown";
  return value
    .toLowerCase()
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function decisionLabel(decision: Decision | string | null | undefined): string {
  if (decision === "REVIEW_REQUIRED") return "Review required";
  return humanizeEnum(decision);
}

export function formatDocumentType(value: string | null | undefined): string {
  if (!value || value === "other" || value === "unknown") return "Unknown";
  if (value === "pan") return "PAN";
  return humanizeEnum(value);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "Not recorded";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not recorded";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function normalizeBranchStatus(status: BranchStatus | string): Exclude<
  BranchStatus,
  "inactive" | "mock" | "pending"
> {
  if (status === "mock" || status === "pending") return "unavailable";
  if (status === "inactive") return "inconclusive";
  if (
    status === "active" ||
    status === "unavailable" ||
    status === "not_applicable" ||
    status === "error" ||
    status === "inconclusive"
  ) {
    return status;
  }
  return "inconclusive";
}

export function displayedMass(branch: BranchInfo): BranchBelief | null {
  return branch.mass ?? branch.belief ?? branch.raw_mass ?? null;
}

export function isVacuous(mass: BranchBelief | null | undefined): boolean {
  return Boolean(
    mass &&
      Math.abs(mass.authentic) < 0.0001 &&
      Math.abs(mass.forged) < 0.0001 &&
      mass.uncertain > 0.999,
  );
}

export function maskSensitiveText(value: string): string {
  return value
    .replace(/\b(\d{4})\s?(\d{4})\s?(\d{4})\b/g, "XXXX XXXX $3")
    .replace(/\b([A-Z]{2})[A-Z]{3}\d{4}([A-Z])\b/g, "$1*** ****$2")
    .replace(/\b\d{9,}\b/g, (match) => `${"X".repeat(match.length - 4)}${match.slice(-4)}`);
}

export function safeDetailLabel(key: string): string {
  const aliases: Record<string, string> = {
    threshold_area: "Localized area",
    max_prob: "Maximum pixel probability",
    high_quantile: "99.5th percentile probability",
    model_type: "Model type",
    fields_detected: "Fields detected",
    qr_found: "QR found",
    signature_status: "Signature status",
    validation_result: "Validation result",
    consistency_score: "Consistency score",
  };
  return aliases[key] ?? humanizeEnum(key);
}

export function detailValue(value: unknown): string | null {
  if (value == null || value === "") return null;
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) return value.length ? value.join(", ") : null;
  if (typeof value === "number") {
    if (value >= 0 && value <= 1) return formatPercent(value);
    return String(value);
  }
  if (typeof value === "object") return null;
  const text = String(value);
  if (text === "aiforge_segmentation") return "AIForge segmentation";
  return /^[a-z0-9_]+$/i.test(text) ? humanizeEnum(text) : maskSensitiveText(text);
}
