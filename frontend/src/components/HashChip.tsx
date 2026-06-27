"use client";

import { useState } from "react";
import { Copy, Check } from "lucide-react";

export default function HashChip({
  value,
  label,
}: {
  value: string | null | undefined;
  label?: string;
}) {
  const [copied, setCopied] = useState(false);

  if (!value) {
    return <span className="text-sm text-gray-400">—</span>;
  }

  const truncated =
    value.length > 20 ? `${value.slice(0, 10)}…${value.slice(-8)}` : value;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <span className="inline-flex items-center gap-2">
      {label && <span className="text-xs text-gray-500">{label}</span>}
      <code
        title={value}
        className="rounded-md bg-gray-100 px-2 py-1 font-mono text-xs text-gray-700"
      >
        {truncated}
      </code>
      <button
        onClick={copy}
        aria-label="Copy hash"
        className="text-gray-400 transition-colors hover:text-gray-700"
      >
        {copied ? <Check size={14} className="text-green-600" /> : <Copy size={14} />}
      </button>
    </span>
  );
}
