"use client";

import { useAuth } from "@clerk/nextjs";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  canonicalTicker,
  type SymbolMetadata,
} from "@/components/investments/ChartsSection";
import ChartsSection from "@/components/investments/ChartsSection";
import ColumnsPopover from "@/components/investments/ColumnsPopover";
import CsvDropzone from "@/components/investments/CsvDropzone";
import GroupsPopover from "@/components/investments/GroupsPopover";
import UploadManager from "@/components/investments/UploadManager";
import PositionsTable, {
  ALL_COLUMN_DEFS,
  DEFAULT_VISIBLE_COLUMNS,
  type Position,
} from "@/components/investments/PositionsTable";
import TransactionsTable, {
  type Transaction,
} from "@/components/investments/TransactionsTable";
import { useAnalyze } from "@/contexts/AnalyzeContext";

type View = "positions" | "transactions";
type ChartValueMode = "cost_basis" | "market_value";

interface HoldingRecord {
  account: string;
  raw_symbol: string;
  symbol: string;
  exchange?: string;
  market_price?: number;
  market_price_currency?: string;
  market_value_cad?: number;
  unrealized_pl_cad?: number;
  is_option?: boolean;
  option_details?: string;
}

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
  const [holdings, setHoldings] = useState<HoldingRecord[]>([]);
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
  const [industryOverrides, setIndustryOverrides] = useState<
    Record<string, string>
  >({});
  const [visibleColumns, setVisibleColumns] = useState<string[]>(
    DEFAULT_VISIBLE_COLUMNS,
  );
  const [middleChartColumn, setMiddleChartColumn] = useState<
    "sector" | "industry"
  >("sector");
  const [chartValueMode, setChartValueMode] =
    useState<ChartValueMode>("cost_basis");

  const saveTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  const base = process.env.NEXT_PUBLIC_BACKEND_URL;

  const load = useCallback(async () => {
    if (!userId) return;

    setLoading(true);
    setError(null);

    try {
      const headers = { "X-User-Id": userId };

      const [posRes, txnRes, prefRes, holdingsRes] = await Promise.all([
        fetch(`${base}/api/investments/positions`, { headers }),
        fetch(`${base}/api/investments/transactions`, { headers }),
        fetch(`${base}/api/investments/preferences`, { headers }),
        fetch(`${base}/api/investments/holdings`, { headers }),
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
        setIndustryOverrides(prefs.industry_overrides ?? {});
        if (prefs.visible_columns?.length) {
          setVisibleColumns(prefs.visible_columns);
        }
        if (prefs.middle_chart_column) {
          setMiddleChartColumn(prefs.middle_chart_column);
        }
        if (prefs.chart_value_mode) {
          setChartValueMode(prefs.chart_value_mode);
        }
      }

      if (holdingsRes.ok) {
        const holdingsData: HoldingRecord[] = await holdingsRes.json();
        setHoldings(holdingsData);
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

  function savePreferences(prefs: {
    groupingLabels: string[];
    groupingAssignments: Record<string, string>;
    sectorOverrides: Record<string, string>;
    industryOverrides: Record<string, string>;
    visibleColumns: string[];
    middleChartColumn: string;
    chartValueMode: string;
  }) {
    if (!userId || !base) return;
    if (saveTimeout.current) clearTimeout(saveTimeout.current);
    saveTimeout.current = setTimeout(() => {
      fetch(`${base}/api/investments/preferences`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", "X-User-Id": userId },
        body: JSON.stringify({
          grouping_labels: prefs.groupingLabels,
          grouping_assignments: prefs.groupingAssignments,
          sector_overrides: prefs.sectorOverrides,
          industry_overrides: prefs.industryOverrides,
          visible_columns: prefs.visibleColumns,
          middle_chart_column: prefs.middleChartColumn,
          chart_value_mode: prefs.chartValueMode,
        }),
      });
    }, 300);
  }

  function currentPrefs(
    overrides?: Partial<Parameters<typeof savePreferences>[0]>,
  ) {
    return {
      groupingLabels,
      groupingAssignments,
      sectorOverrides,
      industryOverrides,
      visibleColumns,
      middleChartColumn,
      chartValueMode,
      ...overrides,
    };
  }

  function handleAddGroup(name: string) {
    const next = [...groupingLabels, name];
    setGroupingLabels(next);
    savePreferences(currentPrefs({ groupingLabels: next }));
  }

  function handleRemoveGroup(name: string) {
    const nextLabels = groupingLabels.filter((g) => g !== name);
    const nextAssignments = Object.fromEntries(
      Object.entries(groupingAssignments).filter(([, v]) => v !== name),
    );
    setGroupingLabels(nextLabels);
    setGroupingAssignments(nextAssignments);
    savePreferences(
      currentPrefs({
        groupingLabels: nextLabels,
        groupingAssignments: nextAssignments,
      }),
    );
  }

  function handleGroupingChange(posKey: string, group: string) {
    const next = { ...groupingAssignments, [posKey]: group };
    setGroupingAssignments(next);
    savePreferences(currentPrefs({ groupingAssignments: next }));
  }

  function handleSectorChange(posKey: string, sector: string) {
    const next = { ...sectorOverrides, [posKey]: sector };
    setSectorOverrides(next);
    savePreferences(currentPrefs({ sectorOverrides: next }));
  }

  function handleIndustryChange(posKey: string, industry: string) {
    const next = { ...industryOverrides, [posKey]: industry };
    setIndustryOverrides(next);
    savePreferences(currentPrefs({ industryOverrides: next }));
  }

  function handleVisibleColumnsChange(cols: string[]) {
    setVisibleColumns(cols);
    savePreferences(currentPrefs({ visibleColumns: cols }));
  }

  function handleMiddleChartColumnChange(col: "sector" | "industry") {
    setMiddleChartColumn(col);
    savePreferences(currentPrefs({ middleChartColumn: col }));
  }

  function handleChartValueModeChange(mode: ChartValueMode) {
    setChartValueMode(mode);
    savePreferences(currentPrefs({ chartValueMode: mode }));
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

  // Merge holdings market data into positions by account + raw_symbol (falling back to symbol)
  const holdingsMap = new Map<string, HoldingRecord>();
  for (const h of holdings) {
    holdingsMap.set(`${h.account}::${h.raw_symbol}`, h);
  }

  function enrichPosition(p: Position): Position {
    const h =
      holdingsMap.get(`${p.account}::${p.raw_symbol}`) ??
      holdingsMap.get(`${p.account}::${p.symbol}`);
    if (!h) return p;
    return {
      ...p,
      exchange: h.exchange,
      market_price: h.market_price,
      market_price_currency: h.market_price_currency,
      market_value_cad: h.market_value_cad ?? undefined,
      unrealized_pl_cad: h.unrealized_pl_cad ?? undefined,
    };
  }

  const hasHoldings = holdings.length > 0;
  const allPositions = positions?.map(enrichPosition) ?? [];
  const equityPositions = allPositions.filter((p) => p.account !== "Crypto");
  const cryptoPositions = allPositions.filter((p) => p.account === "Crypto");
  const hasCrypto = cryptoPositions.length > 0;
  const metadataReady = Object.keys(symbolMetadata).length > 0;

  const tableProps = {
    groupingLabels,
    groupingAssignments,
    sectorOverrides,
    industryOverrides,
    visibleColumns,
    onGroupingChange: handleGroupingChange,
    onSectorChange: handleSectorChange,
    onIndustryChange: handleIndustryChange,
  };

  return (
    <div className="flex flex-col gap-8 max-w-6xl mx-auto">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-white mb-1">
            Investments
          </h1>
          <p className="text-sm text-neutral-500">
            Upload your Wealthsimple activities CSV or Questrade activities XLSX
            to track your portfolio
          </p>
        </div>
        {userId && (
          <div className="flex items-start gap-2">
            <UploadManager userId={userId} onUpload={load} />
            {hasData && (
              <CsvDropzone
                userId={userId}
                onUpload={load}
                label={hasHoldings ? "Holdings ✓" : "↑ Holdings"}
                uploaded={hasHoldings}
              />
            )}
          </div>
        )}
      </div>

      {loading && (
        <div className="flex justify-center py-16">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-neutral-700 border-t-blue-400" />
        </div>
      )}

      {error && !loading && (
        <p className="text-center text-sm text-red-400">{error}</p>
      )}

      {!loading && hasData && positions !== null && transactions !== null && (
        <>
          {hasHoldings && (
            <div className="flex justify-center">
              <div className="inline-flex overflow-hidden rounded-md border border-neutral-700 text-xs">
                <button
                  onClick={() => handleChartValueModeChange("cost_basis")}
                  className={`px-3 py-1.5 transition-colors ${
                    chartValueMode === "cost_basis"
                      ? "bg-neutral-700 text-white"
                      : "text-neutral-400 hover:text-neutral-300"
                  }`}
                >
                  Cost Basis
                </button>
                <button
                  onClick={() => handleChartValueModeChange("market_value")}
                  className={`px-3 py-1.5 transition-colors ${
                    chartValueMode === "market_value"
                      ? "bg-neutral-700 text-white"
                      : "text-neutral-400 hover:text-neutral-300"
                  }`}
                >
                  Market Value
                </button>
              </div>
            </div>
          )}

          <ChartsSection
            positions={allPositions}
            symbolMetadata={symbolMetadata}
            metadataReady={metadataReady}
            groupingAssignments={groupingAssignments}
            sectorOverrides={sectorOverrides}
            industryOverrides={industryOverrides}
            middleChartColumn={middleChartColumn}
            onMiddleChartColumnChange={handleMiddleChartColumnChange}
            chartValueMode={chartValueMode}
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

            <div className="ml-auto flex gap-2">
              <GroupsPopover
                groupingLabels={groupingLabels}
                onAdd={handleAddGroup}
                onRemove={handleRemoveGroup}
              />
              <ColumnsPopover
                columns={ALL_COLUMN_DEFS}
                visibleColumns={visibleColumns}
                onChange={handleVisibleColumnsChange}
              />
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
                      {...tableProps}
                    />
                  </section>
                  <section className="flex flex-col gap-4">
                    <h2 className="text-sm font-semibold uppercase tracking-wider text-neutral-500">
                      Crypto
                    </h2>
                    <PositionsTable
                      positions={cryptoPositions}
                      {...tableProps}
                    />
                  </section>
                </>
              ) : (
                <PositionsTable
                  positions={equityPositions}
                  analysisStatus={analysisStatus}
                  analyzedTickers={analyzedTickers}
                  symbolMetadata={symbolMetadata}
                  {...tableProps}
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
