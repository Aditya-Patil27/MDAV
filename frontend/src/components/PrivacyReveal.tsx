"use client";

import { Eye, EyeOff, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { maskSensitiveText } from "@/lib/presentation";

export default function PrivacyReveal({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const displayed = revealed ? text : maskSensitiveText(text);

  return (
    <div>
      <button
        type="button"
        onClick={() => {
          setExpanded((value) => !value);
          if (expanded) setRevealed(false);
        }}
        className="inline-flex items-center gap-2 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-800 hover:bg-gray-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600"
        aria-expanded={expanded}
      >
        {expanded ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
        {expanded ? "Hide extracted text" : "Show extracted text"}
      </button>

      {expanded && (
        <div className="mt-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <p className="flex items-center gap-2 text-xs text-amber-800">
              <ShieldAlert size={15} aria-hidden="true" />
              Sensitive identifiers are masked by default.
            </p>
            <button
              type="button"
              onClick={() => setRevealed((value) => !value)}
              className="text-sm font-medium text-blue-700 underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600"
            >
              {revealed ? "Mask sensitive text" : "Reveal sensitive text"}
            </button>
          </div>
          {revealed && (
            <p className="mb-2 rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-900">
              Revealed text may contain personal information. Confirm that you are authorized to view it.
            </p>
          )}
          <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-md border border-gray-200 bg-gray-950 p-4 font-mono text-xs leading-6 text-gray-100">
            {displayed || "No text extracted"}
          </pre>
        </div>
      )}
    </div>
  );
}
