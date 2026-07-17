"use client";

import { ChevronLeft, ChevronRight, FileClock, Search, SlidersHorizontal } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import EmptyState from "@/components/EmptyState";
import StatusBadge from "@/components/StatusBadge";
import { getHistory } from "@/lib/api";
import { formatDateTime, formatDecisionScore, formatDocumentType, formatPercent, humanizeEnum } from "@/lib/presentation";
import type { HistoryPage as HistoryPageData } from "@/types";

const PAGE_SIZE = 15;

export default function HistoryPage() {
  const router = useRouter();
  const [data, setData] = useState<HistoryPageData | null>(null);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [decision, setDecision] = useState("");
  const [docType, setDocType] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [sort, setSort] = useState<"date_desc" | "date_asc" | "score_desc" | "score_asc">("date_desc");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedSearch(search.trim());
      setPage(1);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    getHistory({ search: debouncedSearch, decision, doc_type: docType, date_from: dateFrom, date_to: dateTo, sort, page, page_size: PAGE_SIZE })
      .then((response) => {
        if (active) setData(response);
      })
      .catch((requestError: Error) => {
        if (active) setError(requestError.message || "History could not be loaded.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [debouncedSearch, decision, docType, dateFrom, dateTo, sort, page]);

  const updateFilter = (setter: (value: string) => void, value: string) => {
    setter(value);
    setPage(1);
  };
  const openResult = (documentId: string) => router.push(`/results?id=${encodeURIComponent(documentId)}`);

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <header>
        <p className="text-sm font-medium text-blue-700">Document records</p>
        <h1 className="mt-1 text-2xl font-semibold text-gray-950 sm:text-3xl">Verification history</h1>
        <p className="mt-2 text-sm leading-6 text-gray-600">Search and review fused decisions without exposing extracted document content.</p>
      </header>

      <section aria-label="History filters" className="mt-7 rounded-lg border border-gray-200 bg-white p-4 shadow-sm sm:p-5">
        <div className="flex items-center gap-2 text-sm font-semibold text-gray-900"><SlidersHorizontal size={16} aria-hidden="true" /> Filter records</div>
        <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-[minmax(15rem,1.4fr)_repeat(5,minmax(8rem,1fr))]">
          <label className="relative block">
            <span className="mb-1.5 block text-xs font-medium text-gray-600">Filename or ID</span>
            <Search size={16} aria-hidden="true" className="absolute bottom-2.5 left-3 text-gray-400" />
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search records" className="h-10 w-full rounded-md border border-gray-300 bg-white pl-9 pr-3 text-sm text-gray-900 placeholder:text-gray-400 focus:border-blue-600 focus:outline-none focus:ring-1 focus:ring-blue-600" />
          </label>
          <FilterSelect label="Decision" value={decision} onChange={(value) => updateFilter(setDecision, value)} options={[['', 'All decisions'], ['APPROVED', 'Approved'], ['REVIEW_REQUIRED', 'Review required'], ['FLAGGED', 'Flagged']]} />
          <FilterSelect label="Document type" value={docType} onChange={(value) => updateFilter(setDocType, value)} options={[['', 'All types'], ['aadhaar', 'Aadhaar'], ['pan', 'PAN'], ['passport', 'Passport'], ['driving_licence', 'Driving licence'], ['unknown', 'Unknown']]} />
          <label><span className="mb-1.5 block text-xs font-medium text-gray-600">From</span><input type="date" value={dateFrom} onChange={(event) => updateFilter(setDateFrom, event.target.value)} className="h-10 w-full rounded-md border border-gray-300 px-3 text-sm focus:border-blue-600 focus:outline-none focus:ring-1 focus:ring-blue-600" /></label>
          <label><span className="mb-1.5 block text-xs font-medium text-gray-600">To</span><input type="date" value={dateTo} onChange={(event) => updateFilter(setDateTo, event.target.value)} className="h-10 w-full rounded-md border border-gray-300 px-3 text-sm focus:border-blue-600 focus:outline-none focus:ring-1 focus:ring-blue-600" /></label>
          <FilterSelect label="Sort" value={sort} onChange={(value) => { setSort(value as typeof sort); setPage(1); }} options={[['date_desc', 'Newest first'], ['date_asc', 'Oldest first'], ['score_desc', 'Highest score'], ['score_asc', 'Lowest score']]} />
        </div>
      </section>

      <div className="mt-5 flex items-center justify-between gap-4">
        <p className="text-sm text-gray-600" aria-live="polite">{loading ? "Loading records..." : `${data?.total ?? 0} record${data?.total === 1 ? "" : "s"}`}</p>
        {(search || decision || docType || dateFrom || dateTo) && <button type="button" onClick={() => { setSearch(""); setDebouncedSearch(""); setDecision(""); setDocType(""); setDateFrom(""); setDateTo(""); setPage(1); }} className="text-sm font-semibold text-blue-700 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600">Clear filters</button>}
      </div>

      {error ? (
        <div className="mt-4"><EmptyState Icon={FileClock} title="History unavailable" description={error} /></div>
      ) : !loading && data?.items.length === 0 ? (
        <div className="mt-4"><EmptyState Icon={FileClock} title="No matching records" description="Try changing the filters, or verify a document to create a new record." action={<Link href="/upload" className="rounded-md bg-gray-950 px-4 py-2.5 text-sm font-semibold text-white">Verify a document</Link>} /></div>
      ) : (
        <>
          <div className="mt-4 hidden overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm md:block">
            <table className="w-full table-fixed text-left">
              <caption className="sr-only">Document verification records</caption>
              <thead className="border-b border-gray-200 bg-gray-50 text-xs font-semibold uppercase text-gray-600">
                <tr><th className="w-[31%] px-5 py-3">Document</th><th className="w-[14%] px-4 py-3">Type</th><th className="w-[16%] px-4 py-3">Decision</th><th className="w-[14%] px-4 py-3">Decision score</th><th className="w-[11%] px-4 py-3">Evidence</th><th className="w-[14%] px-4 py-3">Date</th></tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {(data?.items ?? []).map((item) => (
                  <tr key={item.document_id} tabIndex={0} role="link" aria-label={`Open results for ${item.filename}`} onClick={() => openResult(item.document_id)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openResult(item.document_id); } }} className="cursor-pointer text-sm hover:bg-gray-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-600">
                    <td className="px-5 py-4"><p className="truncate font-semibold text-gray-950" title={item.filename}>{item.filename}</p><p className="mt-1 truncate font-mono text-xs text-gray-500" title={item.document_id}>{item.document_id}</p></td>
                    <td className="px-4 py-4 text-gray-700"><p>{formatDocumentType(item.doc_type)}</p>{item.doc_side && item.doc_side !== "unknown" && <p className="mt-1 text-xs text-gray-500">{humanizeEnum(item.doc_side)}</p>}</td>
                    <td className="px-4 py-4"><StatusBadge decision={item.decision} size="sm" /></td>
                    <td className="px-4 py-4 font-semibold text-gray-950">{formatDecisionScore(item.final_score)}</td>
                    <td className="px-4 py-4 text-gray-700"><p>{item.active_branches ?? 0}/{item.total_branches ?? 0} active</p><p className="mt-1 text-xs text-gray-500">U {formatPercent(item.uncertainty, 0)} · K {formatPercent(item.conflict, 0)}</p></td>
                    <td className="px-4 py-4 text-gray-600">{formatDateTime(item.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <ul className="mt-4 space-y-3 md:hidden">
            {(data?.items ?? []).map((item) => (
              <li key={item.document_id}><Link href={`/results?id=${encodeURIComponent(item.document_id)}`} className="block rounded-lg border border-gray-200 bg-white p-4 shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="truncate font-semibold text-gray-950" title={item.filename}>{item.filename}</p><p className="mt-1 text-xs text-gray-500">{formatDocumentType(item.doc_type)} · {formatDateTime(item.created_at)}</p></div><StatusBadge decision={item.decision} size="sm" /></div><div className="mt-4 grid grid-cols-3 gap-3 border-t border-gray-100 pt-3 text-xs"><div><p className="text-gray-500">Decision score</p><p className="mt-1 font-semibold text-gray-900">{formatDecisionScore(item.final_score)}</p></div><div><p className="text-gray-500">Uncertainty / conflict</p><p className="mt-1 font-semibold text-gray-900">{formatPercent(item.uncertainty)} / {formatPercent(item.conflict)}</p></div><div><p className="text-gray-500">Branches</p><p className="mt-1 font-semibold text-gray-900">{item.active_branches ?? 0}/{item.total_branches ?? 0}</p></div></div></Link></li>
            ))}
          </ul>
        </>
      )}

      {(data?.total_pages ?? 0) > 1 && (
        <nav className="mt-6 flex items-center justify-between border-t border-gray-200 pt-4" aria-label="History pagination">
          <button type="button" disabled={page <= 1 || loading} onClick={() => setPage((value) => Math.max(1, value - 1))} className="inline-flex items-center gap-1 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600"><ChevronLeft size={16} aria-hidden="true" /> Previous</button>
          <p className="text-sm text-gray-600">Page <span className="font-semibold text-gray-900">{data?.page ?? page}</span> of {data?.total_pages ?? 1}</p>
          <button type="button" disabled={page >= (data?.total_pages ?? 1) || loading} onClick={() => setPage((value) => value + 1)} className="inline-flex items-center gap-1 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600">Next <ChevronRight size={16} aria-hidden="true" /></button>
        </nav>
      )}
    </main>
  );
}

function FilterSelect({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: [string, string][] }) {
  return <label><span className="mb-1.5 block text-xs font-medium text-gray-600">{label}</span><select value={value} onChange={(event) => onChange(event.target.value)} className="h-10 w-full rounded-md border border-gray-300 bg-white px-3 text-sm text-gray-900 focus:border-blue-600 focus:outline-none focus:ring-1 focus:ring-blue-600">{options.map(([optionValue, optionLabel]) => <option key={optionValue} value={optionValue}>{optionLabel}</option>)}</select></label>;
}
