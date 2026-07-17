import { CircleGauge, ShieldQuestion } from "lucide-react";
import EvidenceMassBar from "./EvidenceMassBar";
import StatusBadge from "./StatusBadge";
import {
  detailValue,
  displayedMass,
  formatPercent,
  normalizeBranchStatus,
  safeDetailLabel,
} from "@/lib/presentation";
import type { BranchInfo } from "@/types";

const OMITTED_DETAILS = new Set([
  "ai_forgery_prob",
  "tamper_probability",
  "confidence",
  "explanation",
  "reason",
  "document_context",
  "rule_statuses",
  "model_limitation",
  "heatmap_path",
  "mismatches",
]);

export default function BranchCard({ source, branch }: { source: string; branch: BranchInfo }) {
  const status = normalizeBranchStatus(branch.status);
  const mass = displayedMass(branch);
  const active = status === "active";
  const detailRows = Object.entries(branch.detail ?? {})
    .filter(([key]) => !OMITTED_DETAILS.has(key))
    .map(([key, value]) => [safeDetailLabel(key), detailValue(value)] as const)
    .filter((row): row is readonly [string, string] => row[1] !== null);

  return (
    <article className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
      <header className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase text-gray-500">Evidence branch</p>
          <h3 className="mt-1 text-base font-semibold text-gray-950">
            {branch.display_name || branch.label}
          </h3>
        </div>
        <StatusBadge status={status} size="sm" />
      </header>

      <div className="mt-5 grid grid-cols-2 gap-4 border-y border-gray-100 py-4 text-sm">
        <div>
          <p className="text-xs text-gray-500">
            {active && branch.probability_label
              ? `Raw ${branch.probability_label} probability`
              : "Raw model output"}
          </p>
          <p className="mt-1 font-semibold text-gray-950">
            {active ? formatPercent(branch.raw_probability, 2) : "N/A"}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Model confidence</p>
          <p className="mt-1 font-semibold text-gray-950">
            {active ? formatPercent(branch.confidence) : "N/A"}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Source reliability</p>
          <p className="mt-1 font-semibold text-gray-950">{formatPercent(branch.reliability)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Evidence contribution</p>
          <p className="mt-1 inline-flex items-center gap-1.5 font-semibold text-gray-950">
            {active ? <CircleGauge size={15} aria-hidden="true" /> : <ShieldQuestion size={15} aria-hidden="true" />}
            {active ? "Included" : "None"}
          </p>
        </div>
      </div>

      {mass && <div className="mt-5"><EvidenceMassBar mass={mass} /></div>}

      <p className="mt-5 text-sm leading-6 text-gray-600">
        {branch.reason || String(branch.detail?.explanation || "No explanation was supplied.")}
      </p>

      {detailRows.length > 0 && (
        <dl className="mt-4 space-y-2 border-t border-gray-100 pt-4 text-sm">
          {detailRows.map(([label, value]) => (
            <div key={label} className="flex items-start justify-between gap-4">
              <dt className="text-gray-500">{label}</dt>
              <dd className="max-w-[60%] break-words text-right font-medium text-gray-900">{value}</dd>
            </div>
          ))}
        </dl>
      )}

      {source === "diffusion" && (
        <p className="mt-4 rounded-md bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900">
          The AIForge model was validated primarily on receipt/form-derived data. Identity-document results require human review.
        </p>
      )}
    </article>
  );
}
