import { CheckCircle2, AlertTriangle, XCircle, HelpCircle } from "lucide-react";

const CONFIG: Record<
  string,
  { label: string; classes: string; Icon: typeof CheckCircle2 }
> = {
  APPROVED: {
    label: "Approved",
    classes: "bg-green-100 text-green-800 ring-green-600/20",
    Icon: CheckCircle2,
  },
  FLAGGED: {
    label: "Flagged",
    classes: "bg-amber-100 text-amber-800 ring-amber-600/20",
    Icon: AlertTriangle,
  },
  REVIEW_REQUIRED: {
    label: "Review Required",
    classes: "bg-red-100 text-red-800 ring-red-600/20",
    Icon: XCircle,
  },
};

const FALLBACK = {
  label: "Unknown",
  classes: "bg-gray-100 text-gray-700 ring-gray-500/20",
  Icon: HelpCircle,
};

export default function DecisionBadge({
  decision,
  size = "md",
}: {
  decision: string | null | undefined;
  size?: "sm" | "md";
}) {
  const { label, classes, Icon } = CONFIG[decision ?? ""] ?? FALLBACK;
  const sizing = size === "sm" ? "px-2 py-1 text-xs gap-1" : "px-3 py-1.5 text-sm gap-1.5";
  const iconSize = size === "sm" ? 14 : 16;

  return (
    <span
      className={`inline-flex items-center rounded-full font-medium ring-1 ring-inset ${classes} ${sizing}`}
    >
      <Icon size={iconSize} />
      {label}
    </span>
  );
}
