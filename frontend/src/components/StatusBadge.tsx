import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  CircleHelp,
  CircleOff,
  Info,
  XCircle,
} from "lucide-react";
import { decisionLabel, humanizeEnum, normalizeBranchStatus } from "@/lib/presentation";
import type { BranchStatus, Decision } from "@/types";

const DECISIONS = {
  APPROVED: { classes: "bg-green-50 text-green-800 ring-green-600/20", Icon: CheckCircle2 },
  REVIEW_REQUIRED: { classes: "bg-amber-50 text-amber-800 ring-amber-600/20", Icon: AlertTriangle },
  FLAGGED: { classes: "bg-red-50 text-red-800 ring-red-600/20", Icon: XCircle },
};

const BRANCHES = {
  active: { label: "Active", classes: "bg-blue-50 text-blue-800 ring-blue-600/20", Icon: Info },
  unavailable: { label: "Unavailable", classes: "bg-gray-100 text-gray-700 ring-gray-500/20", Icon: CircleOff },
  not_applicable: { label: "Not applicable", classes: "bg-gray-100 text-gray-700 ring-gray-500/20", Icon: CircleOff },
  error: { label: "Error", classes: "bg-red-50 text-red-800 ring-red-600/20", Icon: AlertCircle },
  inconclusive: { label: "Inconclusive", classes: "bg-amber-50 text-amber-800 ring-amber-600/20", Icon: CircleHelp },
};

export default function StatusBadge({
  decision,
  status,
  size = "md",
}: {
  decision?: Decision | string | null;
  status?: BranchStatus | string | null;
  size?: "sm" | "md";
}) {
  const branchStatus = status ? normalizeBranchStatus(status) : null;
  const config = decision
    ? DECISIONS[decision as keyof typeof DECISIONS]
    : branchStatus
      ? BRANCHES[branchStatus]
      : null;
  const Icon = config?.Icon ?? CircleHelp;
  const label = decision
    ? decisionLabel(decision)
    : branchStatus
      ? BRANCHES[branchStatus].label
      : humanizeEnum(status);
  const classes = config?.classes ?? "bg-gray-100 text-gray-700 ring-gray-500/20";
  const sizing = size === "sm" ? "gap-1 px-2 py-1 text-xs" : "gap-1.5 px-2.5 py-1.5 text-sm";

  return (
    <span className={`inline-flex items-center rounded-full font-medium ring-1 ring-inset ${classes} ${sizing}`}>
      <Icon size={size === "sm" ? 13 : 15} aria-hidden="true" />
      {label}
    </span>
  );
}
