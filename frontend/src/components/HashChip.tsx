"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";

export default function HashChip({ value, label }: { value: string | null | undefined; label?: string }) {
  const [copied, setCopied] = useState(false);

  if (!value) return <span className="text-sm text-gray-400">N/A</span>;
  const truncated = value.length > 20 ? `${value.slice(0, 10)}...${value.slice(-8)}` : value;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <span className="inline-flex max-w-full items-center gap-2">
      {label && <span className="text-xs text-gray-500">{label}</span>}
      <code title={value} className="min-w-0 truncate rounded-md bg-gray-100 px-2 py-1 font-mono text-xs text-gray-700">{truncated}</code>
      <button type="button" onClick={copy} aria-label={copied ? "Hash copied" : "Copy full hash"} className="rounded p-1 text-gray-500 hover:bg-gray-200 hover:text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600">
        {copied ? <Check size={14} className="text-green-700" aria-hidden="true" /> : <Copy size={14} aria-hidden="true" />}
      </button>
    </span>
  );
}
