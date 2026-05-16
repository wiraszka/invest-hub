"use client";

import { useEffect, useRef, useState } from "react";

interface SourceSummary {
  source: string | null;
  count: number;
  min_date: string;
  max_date: string;
}

interface Props {
  userId: string;
  onUpload: () => void;
}

const SOURCE_LABELS: Record<string, string> = {
  wealthsimple: "Wealthsimple",
  questrade: "Questrade",
};

function fmtMonth(dateStr: string): string {
  const [year, month] = dateStr.split("-");
  return new Date(parseInt(year), parseInt(month) - 1).toLocaleDateString(
    "en-CA",
    { month: "short", year: "numeric" },
  );
}

function fmtRange(min: string, max: string): string {
  const minFmt = fmtMonth(min);
  const maxFmt = fmtMonth(max);
  return minFmt === maxFmt ? minFmt : `${minFmt} – ${maxFmt}`;
}

export default function UploadManager({ userId, onUpload }: Props) {
  const [sources, setSources] = useState<SourceSummary[]>([]);
  const [sourcesLoading, setSourcesLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const addInputRef = useRef<HTMLInputElement>(null);
  const reUploadRefs = useRef<Record<string, HTMLInputElement | null>>({});

  const base = process.env.NEXT_PUBLIC_BACKEND_URL;

  async function fetchSources() {
    try {
      const res = await fetch(`${base}/api/investments/sources`, {
        headers: { "X-User-Id": userId },
      });
      if (res.ok) setSources(await res.json());
    } catch {
      // non-fatal — sources list just won't show
    } finally {
      setSourcesLoading(false);
    }
  }

  useEffect(() => {
    fetchSources();
  }, []);

  async function handleFile(file: File) {
    setError(null);
    setUploading(true);

    const form = new FormData();
    form.append("file", file);

    try {
      const res = await fetch(`${base}/api/investments/upload`, {
        method: "POST",
        headers: { "X-User-Id": userId },
        body: form,
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? "Upload failed — please try again");
      }

      await fetchSources();
      onUpload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setUploading(false);
    }
  }

  async function handleClear(source: string | null) {
    const sourceKey = source ?? "legacy";
    try {
      await fetch(`${base}/api/investments/sources/${sourceKey}`, {
        method: "DELETE",
        headers: { "X-User-Id": userId },
      });
      await fetchSources();
      onUpload();
    } catch {
      // non-fatal — page reload will reflect actual state
    }
  }

  function makeFileInput(
    refSetter: (el: HTMLInputElement | null) => void,
  ): React.ReactElement {
    return (
      <input
        ref={refSetter}
        type="file"
        accept=".csv,.xlsx"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFile(file);
          e.target.value = "";
        }}
      />
    );
  }

  if (sourcesLoading) {
    return (
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-neutral-700 border-t-blue-400" />
    );
  }

  const addLabel = uploading
    ? "Uploading…"
    : sources.length === 0
      ? "↑ Upload activities"
      : "+ Add source";

  return (
    <div className="flex flex-col gap-1">
      {sources.map((s) => {
        const sourceKey = s.source ?? "legacy";
        const label = s.source
          ? (SOURCE_LABELS[s.source] ?? s.source)
          : "Legacy";

        return (
          <div
            key={sourceKey}
            className="flex items-center gap-2 rounded-lg border border-neutral-700 px-3 py-1.5 text-xs"
          >
            <span className="w-24 font-medium text-neutral-300">{label}</span>
            <span className="text-neutral-500">
              {s.count} txn{s.count !== 1 ? "s" : ""}
            </span>
            <span className="text-neutral-700">·</span>
            <span className="text-neutral-500">
              {fmtRange(s.min_date, s.max_date)}
            </span>

            {makeFileInput((el) => {
              reUploadRefs.current[sourceKey] = el;
            })}

            <button
              onClick={() => reUploadRefs.current[sourceKey]?.click()}
              disabled={uploading}
              title="Re-upload"
              className="ml-auto text-neutral-500 transition-colors hover:text-neutral-300 disabled:opacity-50"
            >
              ↑
            </button>
            <button
              onClick={() => handleClear(s.source)}
              disabled={uploading}
              title="Clear"
              className="text-neutral-600 transition-colors hover:text-red-400 disabled:opacity-50"
            >
              ×
            </button>
          </div>
        );
      })}

      {makeFileInput((el) => {
        addInputRef.current = el;
      })}

      <button
        onClick={() => addInputRef.current?.click()}
        disabled={uploading}
        className="flex items-center gap-1 rounded-lg border border-dashed border-neutral-700 px-3 py-1.5 text-xs text-neutral-500 transition-colors hover:border-neutral-500 hover:text-neutral-400 disabled:opacity-50"
      >
        {addLabel}
      </button>

      {error && (
        <p className="mt-1 text-center text-xs text-red-400">{error}</p>
      )}
    </div>
  );
}
