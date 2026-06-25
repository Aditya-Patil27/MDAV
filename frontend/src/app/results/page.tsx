"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

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
    final_score: number;
    decision: string;
    reason_summary: string;
  } | null;
  created_at: string;
}

export default function ResultsPage() {
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
      <div className="max-w-4xl mx-auto px-4 py-12">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading verification results...</p>
        </div>
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-12">
        <div className="text-center text-red-600">{error || "No results found"}</div>
      </div>
    );
  }

  const getDecisionColor = (decision: string) => {
    switch (decision) {
      case "APPROVED":
        return "bg-green-100 text-green-800";
      case "FLAGGED":
        return "bg-yellow-100 text-yellow-800";
      case "REVIEW_REQUIRED":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-12">
      <h1 className="text-2xl font-bold text-gray-900 mb-8">Verification Results</h1>

      <div className="bg-white rounded-lg shadow-md p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">{result.filename}</h2>
            <p className="text-gray-500 text-sm">Document Type: {result.doc_type || "Unknown"}</p>
          </div>
          {result.fused && (
            <span className={`px-4 py-2 rounded-full text-sm font-medium ${getDecisionColor(result.fused.decision)}`}>
              {result.fused.decision}
            </span>
          )}
        </div>

        {result.fused && (
          <div className="mt-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600">Authenticity Score</span>
              <span className="text-sm font-medium text-gray-900">
                {(result.fused.final_score * 100).toFixed(1)}%
              </span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full"
                style={{ width: `${result.fused.final_score * 100}%` }}
              ></div>
            </div>
          </div>
        )}
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow-md p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Visual Analysis</h3>
          {result.vision ? (
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-600">Tamper Probability</span>
                <span className="font-medium">{(result.vision.tamper_probability * 100).toFixed(1)}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Confidence</span>
                <span className="font-medium">{(result.vision.confidence * 100).toFixed(1)}%</span>
              </div>
              <p className="text-sm text-gray-600 mt-3">{result.vision.explanation}</p>
            </div>
          ) : (
            <p className="text-gray-500">No visual analysis available</p>
          )}
        </div>

        <div className="bg-white rounded-lg shadow-md p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Semantic Validation</h3>
          {result.semantic ? (
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-600">Aadhaar Valid</span>
                <span className={`font-medium ${result.semantic.aadhaar_valid ? "text-green-600" : "text-red-600"}`}>
                  {result.semantic.aadhaar_valid !== null ? (result.semantic.aadhaar_valid ? "Yes" : "No") : "N/A"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">PAN Valid</span>
                <span className={`font-medium ${result.semantic.pan_valid ? "text-green-600" : "text-red-600"}`}>
                  {result.semantic.pan_valid !== null ? (result.semantic.pan_valid ? "Yes" : "No") : "N/A"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Consistency Score</span>
                <span className="font-medium">{(result.semantic.consistency_score * 100).toFixed(1)}%</span>
              </div>
            </div>
          ) : (
            <p className="text-gray-500">No semantic validation available</p>
          )}
        </div>

        <div className="bg-white rounded-lg shadow-md p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Digital Signature</h3>
          {result.signature ? (
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-600">Signature Detected</span>
                <span className={`font-medium ${result.signature.signature_detected ? "text-green-600" : "text-yellow-600"}`}>
                  {result.signature.signature_detected ? "Yes" : "No"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Validation</span>
                <span className="font-medium">{result.signature.validation_result}</span>
              </div>
            </div>
          ) : (
            <p className="text-gray-500">No signature information available</p>
          )}
        </div>

        <div className="bg-white rounded-lg shadow-md p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">OCR Extraction</h3>
          {result.ocr ? (
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-600">Confidence</span>
                <span className="font-medium">{(result.ocr.confidence * 100).toFixed(1)}%</span>
              </div>
              <div className="text-sm text-gray-600 max-h-32 overflow-y-auto">
                <pre className="whitespace-pre-wrap">{result.ocr.raw_text?.substring(0, 500)}</pre>
              </div>
            </div>
          ) : (
            <p className="text-gray-500">No OCR data available</p>
          )}
        </div>
      </div>

      {result.fused && (
        <div className="bg-white rounded-lg shadow-md p-6 mt-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Reason Summary</h3>
          <p className="text-gray-600">{result.fused.reason_summary}</p>
        </div>
      )}
    </div>
  );
}
