"use client";

import {
  createContext,
  useContext,
  useRef,
  useState,
  type ReactNode,
} from "react";
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
  abortAnalyze: () => void;
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
  const abortRef = useRef(false);

  async function startAnalyze(tickers: string[], base: string) {
    setAnalyzing(true);
    abortRef.current = false;

    const initialStatus: Record<string, AnalysisStatus> = {};
    for (const t of tickers) initialStatus[t] = "idle";
    setAnalysisStatus(initialStatus);

    for (const ticker of tickers) {
      if (abortRef.current) break;

      setAnalysisStatus((prev) => ({ ...prev, [ticker]: "loading" }));

      try {
        const metaRes = await fetch(
          `${base}/api/investments/metadata/${ticker}`,
          {
            method: "POST",
          },
        );

        if (metaRes.ok) {
          const meta: SymbolMetadata = await metaRes.json();
          setSymbolMetadata((prev) => ({ ...prev, [ticker]: meta }));
          setAnalyzedTickers((prev) => new Set([...prev, ticker]));
        }

        setAnalysisStatus((prev) => ({ ...prev, [ticker]: "done" }));
      } catch {
        setAnalysisStatus((prev) => ({ ...prev, [ticker]: "error" }));
      }
    }

    setAnalyzing(false);
  }

  function abortAnalyze() {
    abortRef.current = true;
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
        abortAnalyze,
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
