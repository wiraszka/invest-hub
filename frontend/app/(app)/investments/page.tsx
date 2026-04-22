"use client";

import { useAuth } from "@clerk/nextjs";
import { useCallback, useEffect, useState } from "react";
import type { SymbolMetadata } from "@/components/investments/ChartsSection";
import ChartsSection from "@/components/investments/ChartsSection";
import CsvDropzone from "@/components/investments/CsvDropzone";
import PositionsTable, {
  type Position,
} from "@/components/investments/PositionsTable";
import TransactionsTable, {
  type Transaction,
} from "@/components/investments/TransactionsTable";
import { useAnalyze } from "@/contexts/AnalyzeContext";

type View = "positions" | "transactions";

export default function InvestmentsPage() {
  const { userId } = useAuth();
  const {
    symbolMetadata,
    setSymbolMetadata,
    analysisStatus,
    analyzedTickers,
    setAnalyzedTickers,
    analyzing,
    startAnalyze,
  } = useAnalyze();

  const [positions, setPositions] = useState<Position[] | null>(null);
  const [transactions, setTransactions] = useState<Transaction[] | null>(null);
  const [view, setView] = useState<View>("positions");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasData, setHasData] = useState(false);

  const base = process.env.NEXT_PUBLIC_BACKEND_URL;

  const load = useCallback(async () => {
    if (!userId) return;

    setLoading(true);
    setError(null);

    try {
      const headers = { "X-User-Id": userId };

      const [posRes, txnRes] = await Promise.all([
        fetch(`${base}/api/investments/positions`, { headers }),
        fetch(`${base}/api/investments/transactions`, { headers }),
      ]);

      if (!posRes.ok || !txnRes.ok) {
        throw new Error("Failed to load investments data");
      }

      const posData: Position[] = await posRes.json();
      const txnData: Transaction[] = await txnRes.json();

      setPositions(posData);
      setTransactions(txnData);
      setHasData(txnData.length > 0);

      const nonCryptoTickers = [
        ...new Set(
          posData.filter((p) => p.account !== "Crypto").map((p) => p.symbol),
        ),
      ];

      if (nonCryptoTickers.length > 0) {
        const metaRes = await fetch(
          `${base}/api/investments/metadata?tickers=${nonCryptoTickers.join(",")}`,
        );
        if (metaRes.ok) {
          const metaData: Record<string, SymbolMetadata> = await metaRes.json();
          setSymbolMetadata(metaData);

          const withAnalysis = new Set(
            Object.values(metaData)
              .filter((m) => m.has_analysis)
              .map((m) => m.ticker),
          );
          setAnalyzedTickers(withAnalysis);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }, [userId, base, setSymbolMetadata, setAnalyzedTickers]);

  useEffect(() => {
    load();
  }, [load]);

  function handleAnalyze() {
    if (!positions || !base) return;
    const tickers = [
      ...new Set(
        positions.filter((p) => p.account !== "Crypto").map((p) => p.symbol),
      ),
    ];
    startAnalyze(tickers, base);
  }

  const equityPositions =
    positions?.filter((p) => p.account !== "Crypto") ?? [];
  const cryptoPositions =
    positions?.filter((p) => p.account === "Crypto") ?? [];
  const hasCrypto = cryptoPositions.length > 0;
  const metadataReady = Object.keys(symbolMetadata).length > 0;

  return (
    <div className="flex flex-col gap-8 max-w-6xl mx-auto">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-white mb-1">
            Investments
          </h1>
          <p className="text-sm text-neutral-500">
            Upload your Wealthsimple activities export to track your portfolio
          </p>
        </div>
        {hasData && userId && <CsvDropzone userId={userId} onUpload={load} />}
      </div>

      {loading && (
        <div className="flex justify-center py-16">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-neutral-700 border-t-blue-400" />
        </div>
      )}

      {error && !loading && (
        <p className="text-center text-sm text-red-400">{error}</p>
      )}

      {!loading && !hasData && userId && (
        <CsvDropzone userId={userId} onUpload={load} />
      )}

      {!loading && hasData && positions !== null && transactions !== null && (
        <>
          <ChartsSection
            positions={positions}
            symbolMetadata={symbolMetadata}
            metadataReady={metadataReady}
          />

          <div className="flex items-center gap-4">
            <div className="flex gap-2">
              <button
                onClick={() => setView("positions")}
                className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
                  view === "positions"
                    ? "bg-neutral-700 text-white"
                    : "text-neutral-400 hover:text-neutral-200"
                }`}
              >
                Positions
              </button>
              <button
                onClick={() => setView("transactions")}
                className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
                  view === "transactions"
                    ? "bg-neutral-700 text-white"
                    : "text-neutral-400 hover:text-neutral-200"
                }`}
              >
                All Transactions
              </button>
            </div>

            <button
              onClick={handleAnalyze}
              disabled={analyzing}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {analyzing ? "Analyzing…" : "Analyze"}
            </button>
          </div>

          {view === "positions" && (
            <div className="flex flex-col gap-8">
              {hasCrypto ? (
                <>
                  <section className="flex flex-col gap-4">
                    <h2 className="text-sm font-semibold uppercase tracking-wider text-neutral-500">
                      Equities &amp; ETFs
                    </h2>
                    <PositionsTable
                      positions={equityPositions}
                      analysisStatus={analysisStatus}
                      analyzedTickers={analyzedTickers}
                      symbolMetadata={symbolMetadata}
                    />
                  </section>
                  <section className="flex flex-col gap-4">
                    <h2 className="text-sm font-semibold uppercase tracking-wider text-neutral-500">
                      Crypto
                    </h2>
                    <PositionsTable positions={cryptoPositions} />
                  </section>
                </>
              ) : (
                <PositionsTable
                  positions={equityPositions}
                  analysisStatus={analysisStatus}
                  analyzedTickers={analyzedTickers}
                  symbolMetadata={symbolMetadata}
                />
              )}
            </div>
          )}

          {view === "transactions" && (
            <TransactionsTable transactions={transactions} />
          )}
        </>
      )}
    </div>
  );
}
