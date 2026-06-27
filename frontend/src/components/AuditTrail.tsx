"use client";

import { useEffect, useState } from "react";
import { Link2, ShieldCheck, Clock } from "lucide-react";
import HashChip from "./HashChip";
import type { AuditTrail as AuditTrailData } from "@/lib/api";

export default function AuditTrail({ documentId }: { documentId: string }) {
  const [audit, setAudit] = useState<AuditTrailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    fetch(`/api/documents/${documentId}/audit`)
      .then((res) => {
        if (!res.ok) throw new Error("Audit record not available");
        return res.json();
      })
      .then((data) => {
        if (active) {
          setAudit(data);
          setLoading(false);
        }
      })
      .catch(() => {
        if (active) {
          setError("No audit record found for this document.");
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [documentId]);

  return (
    <div className="rounded-xl border border-purple-100 bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center gap-2">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-purple-100">
          <ShieldCheck size={18} className="text-purple-600" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Blockchain Audit Trail</h3>
          <p className="text-xs text-gray-500">Immutable, hash-chained verification record</p>
        </div>
      </div>

      {loading && (
        <div className="py-6 text-center text-sm text-gray-500">Loading audit record…</div>
      )}

      {!loading && error && (
        <div className="rounded-lg bg-gray-50 py-6 text-center text-sm text-gray-500">{error}</div>
      )}

      {!loading && audit && (
        <div className="relative pl-6">
          {/* chain connector */}
          <span className="absolute left-2 top-2 bottom-2 w-px bg-purple-200" aria-hidden />

          {audit.previous_hash && (
            <div className="relative mb-4">
              <span className="absolute -left-[1.15rem] top-1.5 h-3 w-3 rounded-full border-2 border-purple-200 bg-white" />
              <p className="text-xs font-medium uppercase tracking-wide text-gray-400">
                Previous Block
              </p>
              <HashChip value={audit.previous_hash} />
            </div>
          )}

          <div className="relative rounded-lg border border-purple-200 bg-purple-50/50 p-4">
            <span className="absolute -left-[1.4rem] top-5 flex h-4 w-4 items-center justify-center rounded-full bg-purple-600">
              <Link2 size={10} className="text-white" />
            </span>

            <p className="mb-3 text-xs font-medium uppercase tracking-wide text-purple-700">
              Current Block
            </p>

            <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <dt className="text-xs text-gray-500">Block Hash</dt>
                <dd className="mt-0.5">
                  <HashChip value={audit.block_hash} />
                </dd>
              </div>
              <div>
                <dt className="text-xs text-gray-500">Document Hash (SHA-256)</dt>
                <dd className="mt-0.5">
                  <HashChip value={audit.document_hash} />
                </dd>
              </div>
              <div>
                <dt className="text-xs text-gray-500">Verification Status</dt>
                <dd className="mt-0.5 text-sm font-medium text-gray-900">
                  {audit.verification_status}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-gray-500">Authenticity Score</dt>
                <dd className="mt-0.5 text-sm font-medium text-gray-900">
                  {audit.authenticity_score != null
                    ? `${(audit.authenticity_score * 100).toFixed(1)}%`
                    : "—"}
                </dd>
              </div>
              <div className="sm:col-span-2">
                <dt className="flex items-center gap-1 text-xs text-gray-500">
                  <Clock size={12} /> Logged At
                </dt>
                <dd className="mt-0.5 text-sm text-gray-700">
                  {new Date(audit.verification_timestamp).toLocaleString()}
                </dd>
              </div>
            </dl>
          </div>
        </div>
      )}
    </div>
  );
}
