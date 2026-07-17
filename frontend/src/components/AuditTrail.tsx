"use client";

import { Clock3, Link2, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { getAuditTrail } from "@/lib/api";
import { formatDecisionScore, scoreFormulaLabel } from "@/lib/presentation";
import type { AuditTrailData } from "@/types";
import HashChip from "./HashChip";
import StatusBadge from "./StatusBadge";

export default function AuditTrail({ documentId }: { documentId: string }) {
  const [audit, setAudit] = useState<AuditTrailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    getAuditTrail(documentId)
      .then((data) => {
        if (active) setAudit(data);
      })
      .catch(() => {
        if (active) setError("No audit record is available for this document.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [documentId]);

  return (
    <section aria-labelledby="audit-heading" className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm sm:p-6">
      <header className="flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-emerald-50 text-emerald-700">
          <ShieldCheck size={18} aria-hidden="true" />
        </span>
        <div>
          <h2 id="audit-heading" className="text-lg font-semibold text-gray-950">Hash-chained audit record</h2>
          <p className="mt-1 text-sm leading-6 text-gray-600">
            Each record contains SHA-256 hashes and a link to the preceding local record. This is an integrity log, not a decentralized blockchain.
          </p>
        </div>
      </header>

      {loading && <p className="py-8 text-center text-sm text-gray-500" role="status">Loading audit record...</p>}
      {!loading && error && <p className="mt-5 rounded-md bg-gray-50 p-4 text-sm text-gray-600">{error}</p>}

      {!loading && audit && (
        <div className="mt-6 border-l-2 border-emerald-100 pl-5">
          {audit.previous_hash && (
            <div className="relative mb-5">
              <span className="absolute -left-[1.7rem] top-1.5 h-3 w-3 rounded-full border-2 border-emerald-200 bg-white" aria-hidden="true" />
              <p className="text-xs font-semibold uppercase text-gray-500">Previous record hash</p>
              <div className="mt-1"><HashChip value={audit.previous_hash} /></div>
            </div>
          )}

          <div className="relative rounded-lg border border-emerald-200 bg-emerald-50/40 p-4">
            <span className="absolute -left-[1.9rem] top-5 flex h-5 w-5 items-center justify-center rounded-full bg-emerald-700 text-white">
              <Link2 size={11} aria-hidden="true" />
            </span>
            <p className="text-xs font-semibold uppercase text-emerald-800">Current verification record</p>
            <dl className="mt-4 grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2">
              <div>
                <dt className="text-xs text-gray-500">Record hash</dt>
                <dd className="mt-1"><HashChip value={audit.block_hash} /></dd>
              </div>
              <div>
                <dt className="text-xs text-gray-500">Document hash (SHA-256)</dt>
                <dd className="mt-1"><HashChip value={audit.document_hash} /></dd>
              </div>
              <div>
                <dt className="text-xs text-gray-500">Recorded decision</dt>
                <dd className="mt-1"><StatusBadge decision={audit.verification_status} size="sm" /></dd>
              </div>
              <div>
                <dt className="text-xs text-gray-500">Decision score</dt>
                <dd className="mt-1 text-sm font-semibold text-gray-950">{formatDecisionScore(audit.authenticity_score)}</dd>
                <p className="mt-1 text-xs text-gray-500">{scoreFormulaLabel(audit.score_formula)}</p>
              </div>
              <div className="sm:col-span-2">
                <dt className="flex items-center gap-1.5 text-xs text-gray-500"><Clock3 size={13} aria-hidden="true" /> Recorded at</dt>
                <dd className="mt-1 text-sm text-gray-800">{new Date(audit.verification_timestamp).toLocaleString()}</dd>
              </div>
            </dl>
          </div>
        </div>
      )}
    </section>
  );
}
