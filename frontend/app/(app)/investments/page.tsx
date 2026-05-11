"use client";

import { useAuth } from "@clerk/nextjs";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  canonicalTicker,
  type SymbolMetadata,
} from "@/components/investments/ChartsSection";
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

  const [groupingLabels, setGroupingLabels] = useState<string[]>([]);
  const [groupingAssignments, setGroupingAssignments] = useState<
    Record<string, string>
  >({});
  const [sectorOverrides, setSectorOverrides] = useState<
    Record<string, string>
  >({});
  const [newGroupName, setNewGroupName] = useState("");

  const saveTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  const base = process.env.NEXT_PUBLIC_BACKEND_URL;

  const load = useCallback(async () => {
    if (!userId) return;

    setLoading(true);
    setError(null);

    try {
      const headers = { "X-User-Id": userId };

      const [posRes, txnRes, prefRes] = await Promise.all([
        fetch(`${base}/api/investments/positions`, { headers }),
        fetch(`${base}/api/investments/transactions`, { headers }),
        fetch(`${base}/api/investments/preferences`, { headers }),
      ]);

      if (!posRes.ok || !txnRes.ok) {
        throw new Error("Failed to load investments data");
      }

      const posData: Position[] = await posRes.json();
      const txnData: Transaction[] = await txnRes.json();

      setPositions(posData);
      setTransactions(txnData);
      setHasData(txnData.length > 0);

      if (prefRes.ok) {
        const prefs = await prefRes.json();
        setGroupingLabels(prefs.grouping_labels ?? []);
        setGroupingAssignments(prefs.grouping_assignments ?? {});
        setSectorOverrides(prefs.sector_overrides ?? {});
      }

      const nonCryptoTickers = [
        ...new Set(
          posData
            .filter((p) => p.account !== "Crypto")
            .map((p) => canonicalTicker(p.symbol, p.currency)),
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

  function savePreferences(
    labels: string[],
    assignments: Record<string, string>,
    overrides: Record<string, string>,
  ) {
    if (!userId || !base) return;
    if (saveTimeout.current) clearTimeout(saveTimeout.current);
    saveTimeout.current = setTimeout(() => {
      fetch(`${base}/api/investments/preferences`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", "X-User-Id": userId },
        body: JSON.stringify({
          grouping_labels: labels,
          grouping_assignments: assignments,
          sector_overrides: overrides,
        }),
      });
    }, 300);
  }

  function handleAddGroup() {
    const name = newGroupName.trim();
    if (!name || groupingLabels.includes(name)) return;
    const next = [...groupingLabels, name];
    setGroupingLabels(next);
    setNewGroupName("");
    savePreferences(next, groupingAssignments, sectorOverrides);
  }

  function handleGroupingChange(posKey: string, group: string) {
    const next = { ...groupingAssignments, [posKey]: group };
    setGroupingAssignments(next);
    savePreferences(groupingLabels, next, sectorOverrides);
  }

  function handleSectorChange(posKey: string, sector: string) {
    const next = { ...sectorOverrides, [posKey]: sector };
    setSectorOverrides(next);
    savePreferences(groupingLabels, groupingAssignments, next);
  }

  useEffect(() => {
    load();
  }, [load]);

  function handleAnalyze() {
    if (!positions || !base) return;
    const tickers = [
      ...new Set(
        positions
          .filter((p) => p.account !== "Crypto")
          .map((p) => canonicalTicker(p.symbol, p.currency)),
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
            groupingAssignments={groupingAssignments}
            sectorOverrides={sectorOverrides}
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

            <div className="ml-auto flex items-center gap-2">
              <input
                type="text"
                value={newGroupName}
                onChange={(e) => setNewGroupName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAddGroup()}
                placeholder="New group…"
                className="rounded-md border border-neutral-700 bg-neutral-800 px-3 py-2 text-sm text-neutral-200 outline-none placeholder:text-neutral-600 focus:border-neutral-500"
              />
              <button
                onClick={handleAddGroup}
                disabled={
                  !newGroupName.trim() ||
                  groupingLabels.includes(newGroupName.trim())
                }
                className="rounded-md bg-neutral-700 px-3 py-2 text-sm font-medium text-neutral-200 transition-colors hover:bg-neutral-600 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Add group
              </button>
            </div>
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
                      groupingLabels={groupingLabels}
                      groupingAssignments={groupingAssignments}
                      sectorOverrides={sectorOverrides}
                      onGroupingChange={handleGroupingChange}
                      onSectorChange={handleSectorChange}
                    />
                  </section>
                  <section className="flex flex-col gap-4">
                    <h2 className="text-sm font-semibold uppercase tracking-wider text-neutral-500">
                      Crypto
                    </h2>
                    <PositionsTable
                      positions={cryptoPositions}
                      groupingLabels={groupingLabels}
                      groupingAssignments={groupingAssignments}
                      sectorOverrides={sectorOverrides}
                      onGroupingChange={handleGroupingChange}
                      onSectorChange={handleSectorChange}
                    />
                  </section>
                </>
              ) : (
                <PositionsTable
                  positions={equityPositions}
                  analysisStatus={analysisStatus}
                  analyzedTickers={analyzedTickers}
                  symbolMetadata={symbolMetadata}
                  groupingLabels={groupingLabels}
                  groupingAssignments={groupingAssignments}
                  sectorOverrides={sectorOverrides}
                  onGroupingChange={handleGroupingChange}
                  onSectorChange={handleSectorChange}
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
