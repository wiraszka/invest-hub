"use client";

import { useEffect, useState } from "react";

interface AnalysisDoc {
  ticker: string;
  company_type: string;
  snapshot: string;
  data_integrity: {
    filing_type: string;
    filing_date: string;
    data_source: string;
    llm_model: string;
    analysis_timestamp: string;
  };
  updated_at: string;
}

interface Props {
  ticker: string;
}

export default function ResearchPanel({ ticker }: Props) {
  const [analysis, setAnalysis] = useState<AnalysisDoc | null>(null);
  const [loading, setLoading] = useState(true);

  const base = process.env.NEXT_PUBLIC_BACKEND_URL;

  useEffect(() => {
    setLoading(true);
    fetch(`${base}/api/analysis/${ticker}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data: AnalysisDoc | null) => setAnalysis(data))
      .catch(() => setAnalysis(null))
      .finally(() => setLoading(false));
  }, [ticker, base]);

  if (loading) {
    return (
      <div className="flex justify-center py-8">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-neutral-700 border-t-blue-400" />
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="border-t border-neutral-800 pt-8">
        <p className="text-sm text-neutral-500 text-center">
          No analysis found — run Analyze from the Investments page
        </p>
      </div>
    );
  }

  const bullets = analysis.snapshot
    .split("\n")
    .filter((line) => line.trim().startsWith("- "))
    .map((line) => line.replace(/^- /, "").trim());

  const date = new Date(analysis.updated_at).toLocaleDateString("en-CA", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  return (
    <div className="border-t border-neutral-800 pt-8 flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-neutral-200">
          Company Snapshot
        </h2>
        <span className="text-xs text-neutral-600">{date}</span>
      </div>

      <ul className="flex flex-col gap-3">
        {bullets.map((b, i) => (
          <li key={i} className="flex gap-3 text-sm text-neutral-300">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-400" />
            {b}
          </li>
        ))}
      </ul>

      <p className="text-xs text-neutral-600">
        {analysis.data_integrity.data_source} ·{" "}
        {analysis.data_integrity.filing_type !== "none"
          ? `${analysis.data_integrity.filing_type} (${analysis.data_integrity.filing_date})`
          : "No SEC filing"}{" "}
        · {analysis.data_integrity.llm_model}
      </p>
    </div>
  );
}
