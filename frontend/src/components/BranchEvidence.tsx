// Generic evidence cards for branches that don't have a bespoke panel
// (QR, Layout, and the AIForge diffusion branch). Each card shows the branch's
// status, its Dempster-Shafer belief masses, and a few branch-specific details.
// New branches render automatically — no code change needed here.

import type { BranchInfo, BranchStatus } from "@/types";

const STATUS_STYLE: Record<BranchStatus, { text: string; cls: string }> = {
  active: { text: "active", cls: "bg-green-50 text-green-700" },
  inactive: { text: "not present", cls: "bg-gray-100 text-gray-500" },
  mock: { text: "model offline", cls: "bg-amber-50 text-amber-700" },
  pending: { text: "awaiting model", cls: "bg-blue-50 text-blue-700" },
  error: { text: "error", cls: "bg-red-50 text-red-700" },
};

function MassBar({ belief }: { belief: BranchInfo["belief"] }) {
  if (!belief) return null;
  const seg = [
    { v: belief.authentic, cls: "bg-green-500", label: "authentic" },
    { v: belief.forged, cls: "bg-red-500", label: "forged" },
    { v: belief.uncertain, cls: "bg-gray-300", label: "uncertain" },
  ];
  return (
    <div>
      <div className="flex h-2 w-full overflow-hidden rounded-full">
        {seg.map((s) => (
          <div key={s.label} className={s.cls} style={{ width: `${(s.v ?? 0) * 100}%` }} />
        ))}
      </div>
      <div className="mt-1 flex justify-between text-[11px] text-gray-400">
        <span>A {(belief.authentic * 100).toFixed(0)}%</span>
        <span>F {(belief.forged * 100).toFixed(0)}%</span>
        <span>U {(belief.uncertain * 100).toFixed(0)}%</span>
      </div>
    </div>
  );
}

function detailLines(detail: Record<string, unknown>): string[] {
  const out: string[] = [];
  for (const [k, v] of Object.entries(detail ?? {})) {
    if (v == null || (Array.isArray(v) && v.length === 0)) continue;
    const val = Array.isArray(v) ? v.join(", ") : String(v);
    out.push(`${k.replace(/_/g, " ")}: ${val}`);
  }
  return out;
}

export default function BranchEvidence({
  branches,
  only,
}: {
  branches: Record<string, BranchInfo>;
  only?: string[];
}) {
  const keys = (only ?? Object.keys(branches)).filter((k) => branches[k]);
  if (keys.length === 0) return null;

  return (
    <div className="grid gap-6 md:grid-cols-2">
      {keys.map((key) => {
        const b = branches[key];
        const status = STATUS_STYLE[b.status] ?? STATUS_STYLE.inactive;
        const lines = detailLines(b.detail);
        return (
          <div key={key} className="rounded-xl border border-gray-100 bg-white p-6 shadow-sm">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">{b.label}</h3>
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${status.cls}`}>
                {status.text}
              </span>
            </div>
            <MassBar belief={b.belief} />
            {lines.length > 0 && (
              <ul className="mt-3 space-y-1 text-sm text-gray-600">
                {lines.map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
            )}
          </div>
        );
      })}
    </div>
  );
}
