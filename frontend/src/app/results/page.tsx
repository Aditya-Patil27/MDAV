"use client";

import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  CircleOff,
  FileQuestion,
  Info,
  MinusCircle,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import AuditTrail from "@/components/AuditTrail";
import BranchCard from "@/components/BranchCard";
import DocumentPreview from "@/components/DocumentPreview";
import EmptyState from "@/components/EmptyState";
import EvidenceMassBar from "@/components/EvidenceMassBar";
import PrivacyReveal from "@/components/PrivacyReveal";
import StatusBadge from "@/components/StatusBadge";
import { getDocumentResults } from "@/lib/api";
import {
  formatDateTime,
  decisionLabel,
  formatDecisionScore,
  formatDocumentType,
  formatPercent,
  humanizeEnum,
  scoreFormulaLabel,
} from "@/lib/presentation";
import type { BranchBelief, SemanticResult, VerificationResult } from "@/types";

type RuleStatus = "valid" | "invalid" | "not_evaluated" | "not_applicable";

function semanticRules(semantic: SemanticResult) {
  const statuses = (semantic.validation_details?.rule_statuses ?? {}) as Record<string, RuleStatus>;
  const fallback = (value: boolean | null, applicable = true): RuleStatus => {
    if (!applicable) return "not_applicable";
    if (value == null) return "not_evaluated";
    return value ? "valid" : "invalid";
  };
  return [
    { key: "aadhaar", label: "Aadhaar checksum", status: statuses.aadhaar ?? fallback(semantic.aadhaar_valid, semantic.aadhaar_valid != null) },
    { key: "pan", label: "PAN format", status: statuses.pan ?? fallback(semantic.pan_valid, semantic.pan_valid != null) },
    { key: "dates", label: "Date consistency", status: statuses.dates ?? fallback(semantic.dates_valid) },
    { key: "field_presence", label: "Context-required fields", status: statuses.field_presence ?? fallback(semantic.field_presence_valid) },
  ];
}

const RULE_STYLE: Record<RuleStatus, { label: string; classes: string; Icon: typeof Info }> = {
  valid: { label: "Valid", classes: "text-green-700", Icon: CheckCircle2 },
  invalid: { label: "Invalid", classes: "text-red-700", Icon: XCircle },
  not_evaluated: { label: "Not evaluated", classes: "text-amber-700", Icon: MinusCircle },
  not_applicable: { label: "Not applicable", classes: "text-gray-500", Icon: CircleOff },
};

function ResultsContent() {
  const id = useSearchParams().get("id");
  const [result, setResult] = useState<VerificationResult | null>(null);
  const [loading, setLoading] = useState(Boolean(id));
  const [error, setError] = useState(id ? "" : "No document ID was supplied.");

  useEffect(() => {
    if (!id) return;
    let active = true;
    getDocumentResults(id)
      .then((response) => {
        if (active) setResult(response);
      })
      .catch((requestError: Error) => {
        if (active) setError(requestError.message || "Verification results could not be loaded.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [id]);

  const fusedMass = useMemo<BranchBelief | null>(() => {
    if (!result?.fused || result.fused.authentic_mass == null || result.fused.forged_mass == null || result.fused.uncertainty_mass == null) return null;
    return { authentic: result.fused.authentic_mass, forged: result.fused.forged_mass, uncertain: result.fused.uncertainty_mass };
  }, [result]);

  if (loading) return <main className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8"><p className="text-sm text-gray-600" role="status">Loading verification results...</p></main>;
  if (error || !result) return <main className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8"><EmptyState Icon={FileQuestion} title="Results unavailable" description={error || "No verification record was returned."} action={<Link href="/history" className="rounded-md bg-gray-950 px-4 py-2.5 text-sm font-semibold text-white">Return to history</Link>} /></main>;

  const fused = result.fused;
  const branches = Object.entries(fused?.branches ?? {});
  const rules = result.semantic ? semanticRules(result.semantic) : [];
  const typeProvenance = result.doc_type_source && result.doc_type_source !== "unknown"
    ? `${formatDocumentType(result.doc_type)} inferred from ${humanizeEnum(result.doc_type_source).toLowerCase()}`
    : "Document type was not established confidently";

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <Link href="/history" className="inline-flex items-center gap-1.5 rounded text-sm font-semibold text-blue-700 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600"><ArrowLeft size={16} aria-hidden="true" /> Back to history</Link>

      <header className="mt-5 flex flex-wrap items-start justify-between gap-5 border-b border-gray-200 pb-6">
        <div className="min-w-0">
          <p className="text-sm font-medium text-blue-700">Verification record</p>
          <h1 className="mt-1 max-w-3xl break-words text-2xl font-semibold text-gray-950 sm:text-3xl">{result.filename}</h1>
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm text-gray-600">
            <span>{formatDocumentType(result.doc_type)}{result.doc_side && result.doc_side !== "unknown" ? ` · ${humanizeEnum(result.doc_side)}` : ""}</span>
            <span>{formatDateTime(result.verified_at || result.created_at)}</span>
            <span title={typeProvenance}>{typeProvenance}</span>
          </div>
          {result.possible_doc_type && result.doc_type === "unknown" && <p className="mt-2 text-xs text-gray-500">Possible type: {formatDocumentType(result.possible_doc_type)} ({formatPercent(result.doc_type_confidence)} confidence)</p>}
        </div>
        {fused && <StatusBadge decision={fused.decision} />}
      </header>

      {!fused ? (
        <div className="mt-7"><EmptyState Icon={AlertTriangle} title="Fusion result unavailable" description="The verification record exists, but no fused decision was stored." /></div>
      ) : (
        <>
          <section aria-labelledby="decision-summary-heading" className="mt-7 grid gap-6 lg:grid-cols-[minmax(0,1.25fr)_minmax(18rem,0.75fr)]">
            <article className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm sm:p-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase text-gray-500">Fused decision</p>
                  <h2 id="decision-summary-heading" className="mt-2 text-xl font-semibold text-gray-950">{decisionLabel(fused.decision)}</h2>
                </div>
                <div className="text-right"><p className="text-xs text-gray-500">Decision score</p><p className="mt-1 text-2xl font-semibold text-gray-950">{formatDecisionScore(fused.decision_score ?? fused.final_score)}</p><p className="mt-1 text-xs text-gray-500">{scoreFormulaLabel(fused.score_formula)}</p></div>
              </div>
              <p className="mt-5 border-t border-gray-100 pt-5 text-sm leading-6 text-gray-700">{fused.reason_summary || "No decision explanation was recorded."}</p>
              <div className="mt-5 rounded-md bg-blue-50 p-4 text-sm leading-6 text-blue-950"><strong>Interpretation:</strong> the decision score is a Dempster-Shafer pignistic score derived from fused belief. It is not a calibrated probability that the document is authentic.</div>
            </article>

            <article className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm sm:p-6">
              <h2 className="text-lg font-semibold text-gray-950">Combined belief</h2>
              <p className="mt-1 text-sm text-gray-600">Evidence after source reliability discounting and fusion.</p>
              {fusedMass ? <div className="mt-5"><EvidenceMassBar mass={fusedMass} label="Fused A / F / U mass" /></div> : <p className="mt-5 text-sm text-gray-500">Fused mass details were not stored for this legacy record.</p>}
              <dl className="mt-5 grid grid-cols-2 gap-4 border-t border-gray-100 pt-4 text-sm">
                <div><dt className="text-xs text-gray-500">Inter-source conflict</dt><dd className="mt-1 font-semibold text-gray-950">{formatPercent(fused.conflict)}</dd></div>
                <div><dt className="text-xs text-gray-500">Active branches</dt><dd className="mt-1 font-semibold text-gray-950">{branches.filter(([, branch]) => branch.status === "active").length} / {branches.length || "N/A"}</dd></div>
              </dl>
            </article>
          </section>

          <section className="mt-7 grid gap-6 xl:grid-cols-[minmax(22rem,0.9fr)_minmax(0,1.1fr)]">
            <DocumentPreview previewUrl={result.preview_url} filename={result.filename} heatmapPath={result.vision?.heatmap_path} />

            <div className="space-y-6">
              <article className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm sm:p-6">
                <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-lg font-semibold text-gray-950">Semantic validation</h2><p className="mt-1 text-sm text-gray-600">Rules run only when the required document context is available.</p></div><span className="text-sm font-semibold text-gray-800">Consistency {formatPercent(result.semantic?.consistency_score)}</span></div>
                {rules.length ? (
                  <ul className="mt-5 divide-y divide-gray-100 border-y border-gray-100">
                    {rules.map((rule) => { const style = RULE_STYLE[rule.status]; const Icon = style.Icon; return <li key={rule.key} className="flex items-center justify-between gap-4 py-3 text-sm"><span className="text-gray-700">{rule.label}</span><span className={`inline-flex items-center gap-1.5 font-semibold ${style.classes}`}><Icon size={15} aria-hidden="true" /> {style.label}</span></li>; })}
                  </ul>
                ) : <p className="mt-5 text-sm text-gray-500">Semantic validation was not available.</p>}
                <p className="mt-4 text-xs leading-5 text-gray-500">“Not evaluated” means evidence was insufficient to run the rule safely; it is not a failed validation.</p>
              </article>

              <article className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm sm:p-6">
                <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-lg font-semibold text-gray-950">OCR extraction</h2><p className="mt-1 text-sm text-gray-600">Machine-readable text used by semantic checks.</p></div><span className="text-sm font-semibold text-gray-800">Confidence {formatPercent(result.ocr?.confidence)}</span></div>
                {result.ocr?.raw_text ? <div className="mt-5"><PrivacyReveal text={result.ocr.raw_text} /></div> : <p className="mt-5 text-sm text-gray-500">No OCR text was extracted.</p>}
              </article>
            </div>
          </section>

          <section aria-labelledby="branch-evidence-heading" className="mt-9">
            <div className="flex flex-wrap items-end justify-between gap-3"><div><h2 id="branch-evidence-heading" className="text-xl font-semibold text-gray-950">Branch evidence</h2><p className="mt-1 text-sm leading-6 text-gray-600">Raw model output, confidence, reliability, and discounted belief are shown separately.</p></div><p className="inline-flex items-center gap-1.5 text-xs text-gray-500"><ShieldCheck size={14} aria-hidden="true" /> Unavailable branches contribute vacuous belief</p></div>
            {branches.length ? <div className="mt-5 grid gap-5 md:grid-cols-2 xl:grid-cols-3">{branches.map(([source, branch]) => <BranchCard key={source} source={source} branch={branch} />)}</div> : <p className="mt-5 rounded-md bg-gray-50 p-5 text-sm text-gray-600">Per-branch evidence was not stored for this legacy record.</p>}
          </section>

          <div className="mt-9"><AuditTrail documentId={result.document_id} /></div>

          <aside className="mt-6 flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950"><AlertTriangle size={18} className="mt-0.5 shrink-0" aria-hidden="true" /><p><strong>Privacy and review notice:</strong> document previews and OCR text may contain personal information. Reveal them only when authorized. Automated evidence supports, but does not replace, a qualified human decision.</p></aside>
        </>
      )}
    </main>
  );
}

export default function ResultsPage() {
  return <Suspense fallback={<main className="mx-auto max-w-7xl px-4 py-12 text-sm text-gray-600">Loading verification results...</main>}><ResultsContent /></Suspense>;
}
