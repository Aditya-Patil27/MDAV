import type { LucideIcon } from "lucide-react";

export default function MetricCard({
  label,
  value,
  detail,
  Icon,
  tone = "neutral",
}: {
  label: string;
  value: string | number;
  detail?: string;
  Icon: LucideIcon;
  tone?: "neutral" | "green" | "amber" | "red" | "blue" | "violet";
}) {
  const tones = {
    neutral: "bg-gray-100 text-gray-700",
    green: "bg-green-50 text-green-700",
    amber: "bg-amber-50 text-amber-700",
    red: "bg-red-50 text-red-700",
    blue: "bg-blue-50 text-blue-700",
    violet: "bg-violet-50 text-violet-700",
  };
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-gray-600">{label}</p>
          <p className="mt-2 text-2xl font-semibold text-gray-950">{value}</p>
          {detail && <p className="mt-1 text-xs leading-5 text-gray-500">{detail}</p>}
        </div>
        <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-md ${tones[tone]}`}>
          <Icon size={18} aria-hidden="true" />
        </span>
      </div>
    </div>
  );
}
