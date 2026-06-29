"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Check, X, Minus } from "lucide-react";
import DecisionBadge from "@/components/DecisionBadge";
import ScoreRing from "@/components/ScoreRing";
import BranchScoreBars from "@/components/BranchScoreBars";
import AuditTrail from "@/components/AuditTrail";
import BranchEvidence from "@/components/BranchEvidence";
import type { BranchInfo } from "@/types";

interface VerificationResult {
  document_id: string;
  filename: string;
  doc_type: string;
  status: string;
  ocr: {
    raw_text: string;
    extracted_fields: Record<string, unknown>;
    confidence: number;
  } | null;
  semantic: {
    aadhaar_valid: boolean | null;
    pan_valid: boolean | null;
    dates_valid: boolean | null;
    field_presence_valid: boolean | null;
    consistency_score: number;
    validation_details: Record<string, unknown>;
  } | null;
  vision: {
    tamper_probability: number;
    confidence: number;
    heatmap_path: string | null;
    explanation: string;
  } | null;
  signature: {
    signature_detected: boolean;
    certificate_valid: boolean | null;
    hash_valid: boolean | null;
    validation_result: string;
    details: Record<string, unknown>;
  } | null;
  fused: {
    visual_score: number;
    semantic_score: number;
    signature_score: number;
    layout_score?: number | null;
    qr_score?: number | null;
    diffusion_score?: number | null;
    final_score: number;
    conflict?: number | null;
    decision: string;
    reason_summary: string;
    branches?: Record<string, BranchInfo> | null;
  } | null;
  created_at: string;
}

function ValidityChip({ valid }: { valid: boolean | null }) {
  if (valid === null) {
    return (
      <span className="inline-flex items-center gap-1 text-sm text-gray-400">
        <Minus size={14} /> N/A
      </span>
    );
  }
  return valid ? (
    <span className="inline-flex items-center gap-1 text-sm font-medium text-green-600">
      <Check size={14} /> Valid
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-sm font-medium text-red-600">
      <X size={14} /> Invalid
    </span>
  );
}

function ResultsContent() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id");
  const [result, setResult] = useState<VerificationResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;

    fetch(`/api/documents/${id}`)
      .then((res) => res.json())
      .then((data) => {
        setResult(data);
        setLoading(false);
      })
      .catch(() => {
        setError("Failed to load results");
        setLoading(false);
      });
  }, [id]);

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-12">
        <div className="text-center">
          <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-b-2 border-blue-600"></div>
          <p className="text-gray-600">Loading verification results...</p>
        </div>
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-12">
        <div className="text-center text-red-600">{error || "No results found"}</div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <h1 className="mb-1 text-2xl font-bold text-gray-900">Verification Results</h1>
      <p className="mb-8 text-sm text-gray-500">
        {result.filename} · {result.doc_type || "Unknown type"}
      </p>

      <div className="grid gap-6 lg:grid-cols-[320px,1fr]">
        {/* Verdict panel */}
        <div className="space-y-6">
          <div className="rounded-xl border border-gray-100 bg-white p-6 text-center shadow-sm">
            <p className="mb-4 text-sm font-medium text-gray-500">Authenticity Score</p>
            {result.fused ? (
              <>
                <div className="flex justify-center">
                  <ScoreRing score={result.fused.final_score} />
                </div>
                <div className="mt-4 flex justify-center">
                  <DecisionBadge decision={result.fused.decision} />
                </div>
              </>
            ) : (
              <p className="text-gray-400">Fusion result unavailable</p>
            )}
          </div>

          {result.fused && (
            <div className="rounded-xl border border-gray-100 bg-white p-6 shadow-sm">
              <h3 className="mb-1 text-sm font-semibold text-gray-900">Branch Breakdown</h3>
              <p className="mb-4 text-xs text-gray-400">
                Dempster-Shafer fusion · P(authentic) per branch
              </p>
              <BranchScoreBars fused={result.fused} />
              {result.fused.conflict != null && result.fused.conflict >= 0.05 && (
                <p className="mt-4 border-t border-gray-100 pt-3 text-xs text-amber-600">
                  Inter-branch conflict K = {(result.fused.conflict * 100).toFixed(0)}% — sources
                  partly disagree.
                </p>
              )}
            </div>
          )}

          {result.fused?.reason_summary && (
            <div className="rounded-xl border border-gray-100 bg-white p-6 shadow-sm">
              <h3 className="mb-2 text-sm font-semibold text-gray-900">Why this decision</h3>
              <p className="text-sm text-gray-600">{result.fused.reason_summary}</p>
            </div>
          )}
        </div>

        {/* Evidence panels */}
        <div className="space-y-6">
          <div className="grid gap-6 md:grid-cols-2">
            {/* Visual */}
            <div className="rounded-xl border border-gray-100 bg-white p-6 shadow-sm">
              <h3 className="mb-4 text-lg font-semibold text-gray-900">Visual Forensics</h3>
              {result.vision ? (
                <div className="space-y-3">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600">Tamper Probability</span>
                    <span className="font-medium">
                      {(result.vision.tamper_probability * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600">Confidence</span>
                    <span className="font-medium">
                      {(result.vision.confidence * 100).toFixed(1)}%
                    </span>
                  </div>
                  <p className="mt-3 text-sm text-gray-600">{result.vision.explanation}</p>
                  {result.vision.heatmap_path && (
                    <div className="mt-3">
                      <p className="mb-1 text-xs font-medium text-gray-500">Tamper heatmap</p>
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={`/files/heatmaps/${result.vision.heatmap_path
                          .split(/[\\/]/)
                          .pop()}`}
                        alt="Tamper localization heatmap"
                        className="w-full rounded-lg border border-gray-100"
                      />
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-sm text-gray-500">No visual analysis available</p>
              )}
            </div>

            {/* Semantic */}
            <div className="rounded-xl border border-gray-100 bg-white p-6 shadow-sm">
              <h3 className="mb-4 text-lg font-semibold text-gray-900">OCR &amp; Semantic</h3>
              {result.semantic ? (
                <div className="space-y-3 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-600">Aadhaar (Verhoeff)</span>
                    <ValidityChip valid={result.semantic.aadhaar_valid} />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-600">PAN (format)</span>
                    <ValidityChip valid={result.semantic.pan_valid} />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-600">Dates</span>
                    <ValidityChip valid={result.semantic.dates_valid} />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-600">Required fields</span>
                    <ValidityChip valid={result.semantic.field_presence_valid} />
                  </div>
                  <div className="flex items-center justify-between border-t border-gray-100 pt-3">
                    <span className="text-gray-600">Consistency Score</span>
                    <span className="font-medium">
                      {(result.semantic.consistency_score * 100).toFixed(1)}%
                    </span>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-gray-500">No semantic validation available</p>
              )}
            </div>

            {/* Signature */}
            <div className="rounded-xl border border-gray-100 bg-white p-6 shadow-sm">
              <h3 className="mb-4 text-lg font-semibold text-gray-900">Digital Signature</h3>
              {result.signature ? (
                <div className="space-y-3 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-600">Signature Detected</span>
                    <ValidityChip valid={result.signature.signature_detected} />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-600">Certificate Valid</span>
                    <ValidityChip valid={result.signature.certificate_valid} />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-600">Hash Match</span>
                    <ValidityChip valid={result.signature.hash_valid} />
                  </div>
                  <div className="flex items-center justify-between border-t border-gray-100 pt-3">
                    <span className="text-gray-600">Result</span>
                    <span className="font-medium">{result.signature.validation_result}</span>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-gray-500">
                  No signature present — fusion reweighted to visual &amp; semantic only.
                </p>
              )}
            </div>

            {/* OCR text */}
            <div className="rounded-xl border border-gray-100 bg-white p-6 shadow-sm">
              <h3 className="mb-4 text-lg font-semibold text-gray-900">OCR Extraction</h3>
              {result.ocr ? (
                <div className="space-y-3">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600">Confidence</span>
                    <span className="font-medium">
                      {(result.ocr.confidence * 100).toFixed(1)}%
                    </span>
                  </div>
                  <pre className="max-h-32 overflow-y-auto whitespace-pre-wrap rounded-lg bg-gray-50 p-3 text-xs text-gray-600">
                    {result.ocr.raw_text?.substring(0, 500) || "No text extracted"}
                  </pre>
                </div>
              ) : (
                <p className="text-sm text-gray-500">No OCR data available</p>
              )}
            </div>
          </div>

          {result.fused?.branches && (
            <BranchEvidence
              branches={result.fused.branches}
              only={["qr", "layout", "diffusion"]}
            />
          )}

          {id && <AuditTrail documentId={id} />}
        </div>
      </div>
    </div>
  );
}

export default function ResultsPage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-5xl px-4 py-12 text-center text-gray-600">
          Loading verification results...
        </div>
      }
    >
      <ResultsContent />
    </Suspense>
  );
}
