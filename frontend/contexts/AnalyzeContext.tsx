"use client";

import { createContext, useContext, useState, type ReactNode } from "react";
import type { SymbolMetadata } from "@/components/investments/ChartsSection";
import type { AnalysisStatus } from "@/components/investments/PositionsTable";

interface AnalyzeContextValue {
  symbolMetadata: Record<string, SymbolMetadata>;
  setSymbolMetadata: React.Dispatch<
    React.SetStateAction<Record<string, SymbolMetadata>>
  >;
  analysisStatus: Record<string, AnalysisStatus>;
  analyzedTickers: Set<string>;
  setAnalyzedTickers: React.Dispatch<React.SetStateAction<Set<string>>>;
  analyzing: boolean;
  startAnalyze: (tickers: string[], base: string) => void;
}

const AnalyzeContext = createContext<AnalyzeContextValue | null>(null);

export function AnalyzeProvider({ children }: { children: ReactNode }) {
  const [symbolMetadata, setSymbolMetadata] = useState<
    Record<string, SymbolMetadata>
  >({});
  const [analysisStatus, setAnalysisStatus] = useState<
    Record<string, AnalysisStatus>
  >({});
  const [analyzedTickers, setAnalyzedTickers] = useState<Set<string>>(
    new Set(),
  );
  const [analyzing, setAnalyzing] = useState(false);

  async function startAnalyze(tickers: string[], base: string) {
    setAnalyzing(true);

    const initialStatus: Record<string, AnalysisStatus> = {};
    for (const ticker of tickers) initialStatus[ticker] = "idle";
    setAnalysisStatus(initialStatus);

    for (const ticker of tickers) {
      setAnalysisStatus((prev) => ({ ...prev, [ticker]: "loading" }));

      try {
        const res = await fetch(`${base}/api/v1/analysis/${ticker}/data`, {
          method: "POST",
        });

        if (res.ok) {
          const data = await res.json();
          const meta: SymbolMetadata = {
            ticker: data.ticker,
            asset_type: (data.template_key ?? "").startsWith("etf")
              ? "ETF"
              : "Stock",
            sector: data.sector ?? null,
            industry: data.industry ?? null,
            country: null,
            sector_weights: null,
            country_weights: null,
            has_analysis: true,
            fetched_at: data.generated_at,
          };
          setSymbolMetadata((prev) => ({ ...prev, [ticker]: meta }));
        }

        setAnalysisStatus((prev) => ({ ...prev, [ticker]: "done" }));
      } catch {
        setAnalysisStatus((prev) => ({ ...prev, [ticker]: "error" }));
      } finally {
        setAnalyzedTickers((prev) => new Set([...prev, ticker]));
      }
    }

    setAnalyzing(false);
  }

  return (
    <AnalyzeContext.Provider
      value={{
        symbolMetadata,
        setSymbolMetadata,
        analysisStatus,
        analyzedTickers,
        setAnalyzedTickers,
        analyzing,
        startAnalyze,
      }}
    >
      {children}
    </AnalyzeContext.Provider>
  );
}

export function useAnalyze(): AnalyzeContextValue {
  const ctx = useContext(AnalyzeContext);
  if (!ctx) throw new Error("useAnalyze must be used within AnalyzeProvider");
  return ctx;
}
