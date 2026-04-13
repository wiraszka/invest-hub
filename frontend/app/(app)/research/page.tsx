"use client";

import { useState, useCallback } from "react";
import ResearchSearchBar from "@/components/research/ResearchSearchBar";
import RecentChips from "@/components/research/RecentChips";
import ResearchPanel from "@/components/research/ResearchPanel";
import type { AnalysisData } from "@/components/research/ResearchPanel";

const CACHE_KEY = "research_cache";
const RECENT_KEY = "research_recent";

function readCache(): Record<string, AnalysisData> {
  try {
    return JSON.parse(sessionStorage.getItem(CACHE_KEY) ?? "{}");
  } catch {
    return {};
  }
}

function writeCache(cache: Record<string, AnalysisData>): void {
  sessionStorage.setItem(CACHE_KEY, JSON.stringify(cache));
}

function readRecent(): string[] {
  try {
    return JSON.parse(sessionStorage.getItem(RECENT_KEY) ?? "[]");
  } catch {
    return [];
  }
}

function writeRecent(tickers: string[]): void {
  sessionStorage.setItem(RECENT_KEY, JSON.stringify(tickers));
}

function addToRecent(ticker: string): string[] {
  const current = readRecent().filter((t) => t !== ticker);
  const updated = [ticker, ...current];
  writeRecent(updated);
  return updated;
}

export default function ResearchPage() {
  const [activeTicker, setActiveTicker] = useState<string | null>(null);
  const [panelData, setPanelData] = useState<AnalysisData | null>(null);
  const [recentTickers, setRecentTickers] = useState<string[]>(() =>
    readRecent(),
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runAnalysis = useCallback(async (ticker: string) => {
    setError(null);
    setActiveTicker(ticker);

    const cached = readCache()[ticker];
    if (cached) {
      setPanelData(cached);
      setRecentTickers(addToRecent(ticker));
      return;
    }

    setLoading(true);
    setPanelData(null);

    try {
      const postRes = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_URL}/api/analysis/${ticker}`,
        { method: "POST" },
      );

      if (!postRes.ok) {
        const body = await postRes.json().catch(() => ({}));
        throw new Error(body.detail ?? "Analysis failed — please try again");
      }

      const getRes = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_URL}/api/analysis/${ticker}`,
      );

      if (!getRes.ok) {
        throw new Error("Failed to load results — please try again");
      }

      const data: AnalysisData = await getRes.json();

      const cache = readCache();
      cache[ticker] = data;
      writeCache(cache);

      setPanelData(data);
      setRecentTickers(addToRecent(ticker));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }, []);

  function handleSelect(ticker: string) {
    runAnalysis(ticker);
  }

  return (
    <div className="flex flex-col gap-8 max-w-4xl mx-auto">
      <div>
        <h1 className="text-2xl font-extrabold text-white mb-1">Research</h1>
        <p className="text-sm text-neutral-500">
          Search a company to run an AI-powered analysis
        </p>
      </div>

      <ResearchSearchBar onSelect={(ticker) => runAnalysis(ticker)} />

      {recentTickers.length > 0 && (
        <RecentChips tickers={recentTickers} onSelect={handleSelect} />
      )}

      {loading && (
        <div className="flex flex-col items-center gap-4 py-16 text-neutral-500">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-neutral-700 border-t-blue-400" />
          <p className="text-sm">
            Running analysis for{" "}
            <span className="font-semibold text-neutral-300">
              {activeTicker}
            </span>
            …
          </p>
          <p className="text-xs text-neutral-600">
            This may take up to a minute
          </p>
        </div>
      )}

      {error && !loading && (
        <p className="text-sm text-red-400 text-center">{error}</p>
      )}

      {panelData && !loading && <ResearchPanel data={panelData} />}
    </div>
  );
}
