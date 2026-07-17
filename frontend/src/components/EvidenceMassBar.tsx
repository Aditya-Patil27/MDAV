import { formatPercent } from "@/lib/presentation";
import type { BranchBelief } from "@/types";

export default function EvidenceMassBar({
  mass,
  label = "Discounted evidence mass",
}: {
  mass: BranchBelief;
  label?: string;
}) {
  const segments = [
    { key: "Authentic", value: mass.authentic, color: "bg-green-500" },
    { key: "Forged", value: mass.forged, color: "bg-red-500" },
    { key: "Uncertainty", value: mass.uncertain, color: "bg-gray-300" },
  ];
  const description = segments.map((segment) => `${segment.key} ${formatPercent(segment.value)}`).join(", ");
  return (
    <div>
      <p className="mb-2 text-xs font-medium text-gray-600">{label}</p>
      <div
        className="flex h-3 w-full overflow-hidden rounded-sm bg-gray-100"
        role="img"
        aria-label={`${label}: ${description}`}
      >
        {segments.map((segment) => (
          <span
            key={segment.key}
            className={segment.color}
            style={{ width: `${Math.max(0, segment.value) * 100}%` }}
            aria-hidden="true"
          />
        ))}
      </div>
      <div className="mt-2 grid grid-cols-3 gap-2 text-xs">
        {segments.map((segment) => (
          <div key={segment.key}>
            <span className="block text-gray-500">{segment.key}</span>
            <span className="font-semibold text-gray-900">{formatPercent(segment.value)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
