"use client";

import { Eye, EyeOff, FileText, Image as ImageIcon, Layers3 } from "lucide-react";
import { useMemo, useState } from "react";

type Mode = "original" | "heatmap" | "overlay";

function artifactUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  const filename = path.split(/[\\/]/).pop();
  return filename ? `/files/heatmaps/${filename}` : null;
}

export default function DocumentPreview({
  previewUrl,
  filename,
  heatmapPath,
  sensitive = true,
}: {
  previewUrl: string | null | undefined;
  filename: string;
  heatmapPath?: string | null;
  sensitive?: boolean;
}) {
  const [revealed, setRevealed] = useState(false);
  const [mode, setMode] = useState<Mode>("original");
  const heatmapUrl = useMemo(() => artifactUrl(heatmapPath), [heatmapPath]);
  const isPdf = filename.toLowerCase().endsWith(".pdf");
  const modes: { key: Mode; label: string; Icon: typeof ImageIcon; disabled?: boolean }[] = [
    { key: "original", label: "Original", Icon: ImageIcon },
    { key: "heatmap", label: "Heatmap", Icon: Layers3, disabled: !heatmapUrl },
    { key: "overlay", label: "Overlay", Icon: Layers3, disabled: !heatmapUrl },
  ];

  return (
    <section aria-labelledby="document-preview-heading">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="document-preview-heading" className="text-lg font-semibold text-gray-950">Document preview</h2>
          <p className="mt-1 text-sm text-gray-600">Localization overlays are model evidence, not definitive proof.</p>
        </div>
        {sensitive && !isPdf && (
          <button
            type="button"
            onClick={() => setRevealed((value) => !value)}
            className="inline-flex items-center gap-2 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-800 hover:bg-gray-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600"
          >
            {revealed ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
            {revealed ? "Protect preview" : "Reveal preview"}
          </button>
        )}
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-3 shadow-sm">
        {!isPdf && (
          <div className="mb-3 flex flex-wrap gap-1" role="group" aria-label="Preview mode">
            {modes.map(({ key, label, Icon, disabled }) => (
              <button
                key={key}
                type="button"
                disabled={disabled}
                onClick={() => setMode(key)}
                className={`inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 disabled:cursor-not-allowed disabled:opacity-40 ${mode === key ? "bg-gray-900 text-white" : "text-gray-700 hover:bg-gray-100"}`}
                aria-pressed={mode === key}
              >
                <Icon size={15} aria-hidden="true" /> {label}
              </button>
            ))}
          </div>
        )}

        <div className="relative flex min-h-72 items-center justify-center overflow-hidden rounded-md bg-gray-100">
          {!previewUrl ? (
            <p className="text-sm text-gray-500">Preview is unavailable.</p>
          ) : isPdf ? (
            <a href={previewUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 text-sm font-medium text-blue-700 hover:underline">
              <FileText size={18} aria-hidden="true" /> Open the submitted PDF in a new tab
            </a>
          ) : (
            <>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={mode === "heatmap" && heatmapUrl ? heatmapUrl : previewUrl}
                alt={mode === "original" ? `Protected preview of ${filename}` : `${mode} evidence for ${filename}`}
                className={`max-h-[36rem] w-auto max-w-full object-contain transition-[filter] ${sensitive && !revealed && mode === "original" ? "blur-md" : ""}`}
              />
              {mode === "overlay" && heatmapUrl && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={heatmapUrl} alt="" aria-hidden="true" className="absolute inset-0 h-full w-full object-contain opacity-45 mix-blend-multiply" />
              )}
              {sensitive && !revealed && mode === "original" && (
                <p className="absolute rounded-md bg-gray-950/85 px-3 py-2 text-sm font-medium text-white">Preview protected</p>
              )}
            </>
          )}
        </div>
      </div>
    </section>
  );
}
