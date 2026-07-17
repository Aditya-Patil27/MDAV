"use client";

import {
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  FileSearch,
  History as HistoryIcon,
  ShieldAlert,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import EmptyState from "@/components/EmptyState";
import MetricCard from "@/components/MetricCard";
import StatusBadge from "@/components/StatusBadge";
import { getDashboardStats, getHistory } from "@/lib/api";
import { formatDateTime, formatDecisionScore, formatDocumentType, formatPercent } from "@/lib/presentation";
import type { DashboardStats, HistoryItem } from "@/types";

const OUTCOMES = [
  { key: "approved_count", label: "Approved", color: "#15803d" },
  { key: "review_required_count", label: "Review required", color: "#d97706" },
  { key: "flagged_count", label: "Flagged", color: "#b91c1c" },
] as const;

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recent, setRecent] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([getDashboardStats(), getHistory({ page: 1, page_size: 5 })])
      .then(([statsData, historyData]) => {
        if (!active) return;
        setStats(statsData);
        setRecent(historyData.items);
      })
      .catch((requestError: Error) => {
        if (active) setError(requestError.message || "Dashboard data could not be loaded.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const pieData = useMemo(
    () => OUTCOMES.map((item) => ({ ...item, value: stats?.[item.key] ?? 0 })),
    [stats],
  );
  const decisionTotal = pieData.reduce((sum, item) => sum + item.value, 0);

  if (loading) {
    return <main className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8"><p className="text-sm text-gray-600" role="status">Loading dashboard...</p></main>;
  }

  if (!stats || error) {
    return (
      <main className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <EmptyState Icon={AlertTriangle} title="Dashboard unavailable" description={error || "The dashboard service did not return data."} />
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <header className="mb-7 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-blue-700">Verification operations</p>
          <h1 className="mt-1 text-2xl font-semibold text-gray-950 sm:text-3xl">Dashboard</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-gray-600">A decision-level view of processed documents and evidence availability.</p>
        </div>
        <Link href="/upload" className="inline-flex items-center gap-2 rounded-md bg-gray-950 px-4 py-2.5 text-sm font-semibold text-white hover:bg-gray-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2">
          <FileSearch size={17} aria-hidden="true" /> Verify a document
        </Link>
      </header>

      <section aria-label="Verification summary" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <MetricCard label="Documents submitted" value={stats.total_documents} detail="All uploaded document records" Icon={ClipboardList} />
        <MetricCard label="Decisions recorded" value={stats.total_verifications} detail={`${stats.verifications_last_7_days ?? 0} in the last 7 days`} Icon={FileSearch} tone="blue" />
        <MetricCard label="Approved" value={stats.approved_count} detail="Evidence met the approval criteria" Icon={CheckCircle2} tone="green" />
        <MetricCard label="Review required" value={stats.review_required_count} detail="Uncertain or conflicting evidence" Icon={AlertTriangle} tone="amber" />
        <MetricCard label="Flagged" value={stats.flagged_count} detail="Strong forgery evidence" Icon={ShieldAlert} tone="red" />
      </section>

      <section className="mt-7 grid gap-6 lg:grid-cols-[minmax(0,1.45fr)_minmax(19rem,0.75fr)]">
        <article className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-gray-950">Verification activity</h2>
              <p className="mt-1 text-sm text-gray-600">Daily outcomes over the latest 14-day reporting window.</p>
            </div>
            <div className="flex gap-4 text-xs text-gray-600" aria-hidden="true">
              {OUTCOMES.map((item) => <span key={item.key} className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: item.color }} />{item.label}</span>)}
            </div>
          </div>
          {(stats.activity?.length ?? 0) > 0 ? (
            <>
              <p className="sr-only">{stats.activity!.map((item) => `${item.date}: ${item.approved} approved, ${item.review_required} review required, ${item.flagged} flagged`).join(". ")}</p>
              <div className="mt-5 h-72" aria-hidden="true">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={stats.activity} margin={{ top: 8, right: 4, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                    <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#6b7280" }} tickFormatter={(value) => value.slice(5)} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#6b7280" }} />
                    <Tooltip />
                    <Bar dataKey="approved" stackId="outcome" fill="#15803d" name="Approved" isAnimationActive={false} />
                    <Bar dataKey="review_required" stackId="outcome" fill="#d97706" name="Review required" isAnimationActive={false} />
                    <Bar dataKey="flagged" stackId="outcome" fill="#b91c1c" name="Flagged" radius={[3, 3, 0, 0]} isAnimationActive={false} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </>
          ) : <p className="mt-8 rounded-md bg-gray-50 p-5 text-sm text-gray-600">No activity has been recorded in this period.</p>}
        </article>

        <article className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm sm:p-6">
          <h2 className="text-lg font-semibold text-gray-950">Decision distribution</h2>
          <p className="mt-1 text-sm text-gray-600">All recorded fused decisions.</p>
          {decisionTotal > 0 ? (
            <div className="mt-4">
              <div className="mx-auto h-48 max-w-xs" aria-hidden="true">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart><Pie data={pieData} dataKey="value" nameKey="label" innerRadius={52} outerRadius={78} paddingAngle={2} isAnimationActive={false}>{pieData.map((entry) => <Cell key={entry.key} fill={entry.color} />)}</Pie><Tooltip /></PieChart>
                </ResponsiveContainer>
              </div>
              <ul className="space-y-2" aria-label="Decision counts">
                {pieData.map((item) => (
                  <li key={item.key} className="flex items-center justify-between gap-4 text-sm">
                    <span className="inline-flex items-center gap-2 text-gray-700"><span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: item.color }} aria-hidden="true" />{item.label}</span>
                    <span className="font-semibold text-gray-950">{item.value} <span className="font-normal text-gray-500">({formatPercent(item.value / decisionTotal, 0)})</span></span>
                  </li>
                ))}
              </ul>
            </div>
          ) : <p className="mt-8 rounded-md bg-gray-50 p-5 text-sm text-gray-600">No decisions are available yet.</p>}
        </article>
      </section>

      <section className="mt-7 grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(20rem,0.6fr)]">
        <article className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
          <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4 sm:px-6">
            <div><h2 className="text-lg font-semibold text-gray-950">Recent verifications</h2><p className="mt-1 text-sm text-gray-600">Latest completed document decisions.</p></div>
            <Link href="/history" className="text-sm font-semibold text-blue-700 hover:underline">View history</Link>
          </div>
          {recent.length === 0 ? (
            <div className="p-5"><EmptyState Icon={HistoryIcon} title="No verification history" description="Completed checks will appear here." /></div>
          ) : (
            <ul className="divide-y divide-gray-100">
              {recent.map((item) => (
                <li key={item.document_id}>
                  <Link href={`/results?id=${encodeURIComponent(item.document_id)}`} className="grid gap-2 px-5 py-4 hover:bg-gray-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-600 sm:grid-cols-[minmax(0,1fr)_auto_auto] sm:items-center sm:px-6">
                    <div className="min-w-0"><p className="truncate text-sm font-semibold text-gray-950" title={item.filename}>{item.filename}</p><p className="mt-1 text-xs text-gray-500">{formatDocumentType(item.doc_type)} · {formatDateTime(item.created_at)}</p></div>
                    <div className="text-sm text-gray-700 sm:text-right"><p className="font-medium">{formatDecisionScore(item.final_score)}</p><p className="mt-1 text-xs text-gray-500">Uncertainty {formatPercent(item.uncertainty)}</p></div>
                    <StatusBadge decision={item.decision} size="sm" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </article>

        <article className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm sm:p-6">
          <h2 className="text-lg font-semibold text-gray-950">Evidence health</h2>
          <p className="mt-1 text-sm text-gray-600">Branch availability across recorded checks.</p>
          <dl className="mt-5 space-y-4">
            {Object.entries(stats.branch_availability ?? {}).length ? Object.entries(stats.branch_availability ?? {}).map(([name, availability]) => (
              <div key={name}>
                <div className="flex justify-between gap-4 text-sm"><dt className="capitalize text-gray-700">{name.replaceAll("_", " ")}</dt><dd className="font-semibold text-gray-950">{availability.active}/{availability.total}</dd></div>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-gray-100"><div className="h-full bg-blue-700" style={{ width: `${Math.max(0, Math.min(100, availability.rate * 100))}%` }} /></div>
              </div>
            )) : <p className="text-sm text-gray-600">Availability data has not been recorded.</p>}
          </dl>
          <div className="mt-6 grid grid-cols-2 gap-3 border-t border-gray-100 pt-5">
            <div><p className="text-xs text-gray-500">Average uncertainty</p><p className="mt-1 font-semibold text-gray-950">{formatPercent(stats.average_uncertainty)}</p></div>
            <div><p className="text-xs text-gray-500">Average conflict</p><p className="mt-1 font-semibold text-gray-950">{formatPercent(stats.average_conflict)}</p></div>
          </div>
        </article>
      </section>
    </main>
  );
}
