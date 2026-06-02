"use client";

import Link from "next/link";
import React, { useState } from "react";
import { canonicalTicker } from "./ChartsSection";
import type { SymbolMetadata } from "./ChartsSection";

export interface Position {
  account: string;
  symbol: string;
  raw_symbol?: string;
  name: string;
  asset_type: string;
  currency: string;
  shares_held: number;
  avg_cost_per_share: number;
  cost_basis: number;
  realized_pl: number;
  dividends: number;
  is_option?: boolean;
  option_details?: string;
  // from holdings
  exchange?: string;
  market_price?: number;
  market_price_currency?: string;
  market_value_cad?: number;
  unrealized_pl_cad?: number;
  implied_fx?: number;
}

export type AnalysisStatus = "idle" | "loading" | "done" | "error";

export interface ColumnDef {
  key: string;
  label: string;
}

export const ALL_COLUMN_DEFS: ColumnDef[] = [
  { key: "account", label: "Account" },
  { key: "name", label: "Name" },
  { key: "symbol", label: "Symbol" },
  { key: "asset_type", label: "Type" },
  { key: "exchange", label: "Exchange" },
  { key: "sector", label: "Sector" },
  { key: "industry", label: "Industry" },
  { key: "grouping", label: "Grouping" },
  { key: "shares_held", label: "Shares" },
  { key: "avg_cost_per_share", label: "Avg Cost" },
  { key: "cost_basis", label: "Cost Basis" },
  { key: "market_price", label: "Mkt Price" },
  { key: "market_value_cad", label: "Mkt Value (CAD)" },
  { key: "unrealized_pl", label: "Unreal. P/L (CAD)" },
  { key: "unrealized_pct", label: "Unreal. %" },
  { key: "realized_pl", label: "Realized P/L" },
  { key: "dividends", label: "Dividends" },
  { key: "total_return", label: "Total Return (CAD)" },
  { key: "total_return_pct", label: "Total %" },
  { key: "portfolio_weight", label: "Weight %" },
];

export const DEFAULT_VISIBLE_COLUMNS: string[] = [
  "account",
  "name",
  "symbol",
  "asset_type",
  "sector",
  "industry",
  "grouping",
  "shares_held",
  "avg_cost_per_share",
  "cost_basis",
  "market_price",
  "market_value_cad",
  "unrealized_pl",
  "unrealized_pct",
  "realized_pl",
  "total_return",
  "total_return_pct",
  "portfolio_weight",
];

type SortKey =
  | "account"
  | "name"
  | "symbol"
  | "asset_type"
  | "exchange"
  | "shares_held"
  | "avg_cost_per_share"
  | "cost_basis"
  | "market_price"
  | "market_value_cad"
  | "unrealized_pl"
  | "unrealized_pct"
  | "realized_pl"
  | "dividends"
  | "total_return"
  | "total_return_pct"
  | "portfolio_weight";
type SortDir = "asc" | "desc";

const NUMERIC_SORT_KEYS = new Set<SortKey>([
  "shares_held",
  "avg_cost_per_share",
  "cost_basis",
  "market_price",
  "market_value_cad",
  "unrealized_pl",
  "unrealized_pct",
  "realized_pl",
  "dividends",
  "total_return",
  "total_return_pct",
  "portfolio_weight",
]);

interface RowData {
  pos: Position;
  cticker: string;
  posKey: string;
  isLink: boolean;
  status: AnalysisStatus;
  unrealPct: number | null;
  totalReturn: number;
  totalReturnPct: number | null;
  portfolioWeight: number | null;
}

function getSortValue(row: RowData, key: SortKey): string | number | null {
  const p = row.pos;
  switch (key) {
    case "account":
      return p.account;
    case "name":
      return p.name || p.symbol;
    case "symbol":
      return p.symbol;
    case "asset_type":
      return p.asset_type;
    case "exchange":
      return p.exchange ?? null;
    case "shares_held":
      return p.shares_held;
    case "avg_cost_per_share":
      return p.avg_cost_per_share;
    case "cost_basis":
      return p.cost_basis;
    case "market_price":
      return p.market_price ?? null;
    case "market_value_cad":
      return p.market_value_cad ?? null;
    case "unrealized_pl":
      return p.unrealized_pl_cad ?? null;
    case "unrealized_pct":
      return row.unrealPct;
    case "realized_pl":
      return p.realized_pl;
    case "dividends":
      return p.dividends;
    case "total_return":
      return row.totalReturn;
    case "total_return_pct":
      return row.totalReturnPct;
    case "portfolio_weight":
      return row.portfolioWeight;
  }
}

interface Props {
  positions: Position[];
  analysisStatus?: Record<string, AnalysisStatus>;
  analyzedTickers?: Set<string>;
  symbolMetadata?: Record<string, SymbolMetadata>;
  resolvedCanonicals?: Record<string, string>;
  groupingLabels?: string[];
  groupingAssignments?: Record<string, string>;
  sectorOverrides?: Record<string, string>;
  industryOverrides?: Record<string, string>;
  visibleColumns?: string[];
  onGroupingChange?: (key: string, group: string) => void;
  onSectorChange?: (key: string, sector: string) => void;
  onIndustryChange?: (key: string, industry: string) => void;
}

function fmt(value: number, decimals = 2): string {
  return value.toLocaleString("en-CA", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function fmtPct(value: number): string {
  return value.toLocaleString("en-CA", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
}

function plClass(value: number): string {
  return value > 0
    ? "text-green-400"
    : value < 0
      ? "text-red-400"
      : "text-neutral-500";
}

function plPrefix(value: number): string {
  return value >= 0 ? "+" : "";
}

function StatusCell({ status }: { status: AnalysisStatus }) {
  if (status === "loading") {
    return (
      <div className="h-4 w-4 animate-spin rounded-full border-2 border-neutral-700 border-t-blue-400" />
    );
  }
  if (status === "done") {
    return <span className="text-sm text-emerald-400">✓</span>;
  }
  if (status === "error") {
    return <span className="text-sm text-neutral-600">✗</span>;
  }
  return null;
}

function effectiveSector(
  meta: SymbolMetadata | undefined,
  override: string | undefined,
): string {
  if (override !== undefined) return override;
  if (!meta) return "";
  if (meta.asset_type === "ETF") return "ETF";
  return meta.sector ?? "";
}

function effectiveIndustry(
  meta: SymbolMetadata | undefined,
  override: string | undefined,
): string {
  if (override !== undefined) return override;
  if (!meta) return "";
  return meta.industry ?? "";
}

export default function PositionsTable({
  positions,
  analysisStatus = {},
  analyzedTickers = new Set(),
  symbolMetadata = {},
  resolvedCanonicals = {},
  groupingLabels = [],
  groupingAssignments = {},
  sectorOverrides = {},
  industryOverrides = {},
  visibleColumns,
  onGroupingChange,
  onSectorChange,
  onIndustryChange,
}: Props) {
  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [sortClicks, setSortClicks] = useState(0);

  const visSet = new Set(visibleColumns ?? DEFAULT_VISIBLE_COLUMNS);
  const isVisible = (col: string) => visSet.has(col);

  function handleSort(key: SortKey) {
    if (sortKey !== key) {
      setSortKey(key);
      setSortDir(NUMERIC_SORT_KEYS.has(key) ? "desc" : "asc");
      setSortClicks(1);
    } else {
      const next = sortClicks + 1;
      setSortClicks(next);
      if (next % 3 === 0) {
        setSortKey(null);
      } else {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      }
    }
  }

  const totalMarketValue = positions.reduce(
    (sum, p) => sum + (p.market_value_cad ?? 0),
    0,
  );

  const rows: RowData[] = positions.map((p) => {
    const cticker =
      resolvedCanonicals[p.symbol] ??
      canonicalTicker(p.symbol, p.exchange) ??
      p.symbol;
    const posKey = `${p.account}::${p.symbol}`;
    const fx = p.implied_fx ?? 1;
    const unrealPct =
      p.unrealized_pl_cad != null && p.cost_basis > 0
        ? (p.unrealized_pl_cad / (p.cost_basis * fx)) * 100
        : null;
    const totalReturn =
      (p.unrealized_pl_cad ?? 0) + p.realized_pl * fx + p.dividends * fx;
    const totalReturnPct =
      p.market_price != null && p.avg_cost_per_share > 0
        ? ((p.market_price - p.avg_cost_per_share) / p.avg_cost_per_share) * 100
        : null;
    const portfolioWeight =
      totalMarketValue > 0 && p.market_value_cad != null
        ? (p.market_value_cad / totalMarketValue) * 100
        : null;
    return {
      pos: p,
      cticker,
      posKey,
      isLink: analyzedTickers.has(cticker),
      status: analysisStatus[cticker] ?? "idle",
      unrealPct,
      totalReturn,
      totalReturnPct,
      portfolioWeight,
    };
  });

  const sortedRows = [...rows].sort((a, b) => {
    if (!sortKey) return 0;
    const av = getSortValue(a, sortKey);
    const bv = getSortValue(b, sortKey);
    if (av === null && bv === null) return 0;
    if (av === null) return 1;
    if (bv === null) return -1;
    const cmp =
      typeof av === "string"
        ? av.localeCompare(bv as string)
        : (av as number) - (bv as number);
    return sortDir === "asc" ? cmp : -cmp;
  });

  function SortTh({
    col,
    label,
    className,
  }: {
    col: SortKey;
    label: React.ReactNode;
    className?: string;
  }) {
    const numeric = NUMERIC_SORT_KEYS.has(col);
    return (
      <th
        className={`px-4 py-3 ${numeric ? "text-right" : ""} ${className ?? ""}`}
      >
        <button
          onClick={() => handleSort(col)}
          className={`inline-flex items-center gap-0.5 hover:text-neutral-300 ${
            sortKey === col ? "text-neutral-300" : ""
          } ${numeric ? "ml-auto" : ""}`}
        >
          {label}
          {sortKey === col && (
            <span className="ml-1 opacity-60">
              {sortDir === "asc" ? "↑" : "↓"}
            </span>
          )}
        </button>
      </th>
    );
  }

  const showStatusColumn = Object.keys(analysisStatus).length > 0;

  if (positions.length === 0) {
    return (
      <p className="text-center text-sm text-neutral-500">No positions found</p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-neutral-800">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-neutral-800 text-left text-xs text-neutral-500">
            {isVisible("account") && (
              <SortTh col="account" label="Account" className="w-24" />
            )}
            {isVisible("name") && (
              <SortTh col="name" label="Name" className="w-48" />
            )}
            {isVisible("symbol") && (
              <SortTh col="symbol" label="Symbol" className="w-20" />
            )}
            {isVisible("asset_type") && (
              <SortTh col="asset_type" label="Type" className="w-24" />
            )}
            {isVisible("exchange") && (
              <SortTh col="exchange" label="Exchange" className="w-24" />
            )}
            {isVisible("sector") && (
              <th className="w-32 px-4 py-3 text-neutral-500">Sector</th>
            )}
            {isVisible("industry") && (
              <th className="w-32 px-4 py-3 text-neutral-500">Industry</th>
            )}
            {isVisible("grouping") && (
              <th className="w-32 px-4 py-3 text-neutral-500">Grouping</th>
            )}
            {isVisible("shares_held") && (
              <SortTh col="shares_held" label="Shares" />
            )}
            {isVisible("avg_cost_per_share") && (
              <SortTh col="avg_cost_per_share" label="Avg Cost" />
            )}
            {isVisible("cost_basis") && (
              <SortTh col="cost_basis" label="Cost Basis" />
            )}
            {isVisible("realized_pl") && (
              <SortTh col="realized_pl" label="Realized P/L" />
            )}
            {isVisible("market_price") && (
              <SortTh col="market_price" label="Mkt Price" />
            )}
            {isVisible("market_value_cad") && (
              <SortTh
                col="market_value_cad"
                label={
                  <>
                    Mkt Value
                    <br />
                    <span className="text-neutral-600">(CAD)</span>
                  </>
                }
              />
            )}
            {isVisible("unrealized_pl") && (
              <SortTh
                col="unrealized_pl"
                label={
                  <>
                    Unreal. P/L
                    <br />
                    <span className="text-neutral-600">(CAD)</span>
                  </>
                }
              />
            )}
            {isVisible("unrealized_pct") && (
              <SortTh col="unrealized_pct" label="Unreal. %" />
            )}
            {isVisible("dividends") && (
              <SortTh col="dividends" label="Dividends" />
            )}
            {isVisible("total_return") && (
              <SortTh
                col="total_return"
                label={
                  <>
                    Total Return
                    <br />
                    <span className="text-neutral-600">(CAD)</span>
                  </>
                }
              />
            )}
            {isVisible("total_return_pct") && (
              <SortTh col="total_return_pct" label="Total %" />
            )}
            {isVisible("portfolio_weight") && (
              <SortTh col="portfolio_weight" label="Weight %" />
            )}
            {showStatusColumn && <th className="w-8 px-4 py-3" />}
          </tr>
        </thead>
        <tbody>
          {sortedRows.map((row, i) => {
            const {
              pos: p,
              cticker,
              posKey,
              isLink,
              status,
              unrealPct,
              totalReturn,
              totalReturnPct,
              portfolioWeight,
            } = row;

            return (
              <tr
                key={`${p.account}-${p.symbol}-${i}`}
                className="border-b border-neutral-800/50 last:border-0 hover:bg-neutral-800/30"
              >
                {isVisible("account") && (
                  <td className="w-24 px-4 py-3 text-neutral-400">
                    {p.account}
                  </td>
                )}
                {isVisible("name") && (
                  <td className="w-48 max-w-48 px-4 py-3 text-neutral-400">
                    {isLink ? (
                      <Link
                        href={`/symbol/${cticker}`}
                        className="truncate text-blue-400 hover:text-blue-300 hover:underline"
                      >
                        {p.name || p.symbol}
                      </Link>
                    ) : (
                      <span className="block truncate">
                        {p.name || p.symbol}
                      </span>
                    )}
                    {p.option_details && (
                      <span className="block truncate text-xs text-neutral-600">
                        {p.option_details}
                      </span>
                    )}
                  </td>
                )}
                {isVisible("symbol") && (
                  <td className="w-20 px-4 py-3 font-semibold text-neutral-100">
                    {p.symbol}
                  </td>
                )}
                {isVisible("asset_type") && (
                  <td className="w-24 px-4 py-3 text-neutral-500">
                    {p.asset_type}
                  </td>
                )}
                {isVisible("exchange") && (
                  <td className="w-24 px-4 py-3 text-neutral-500">
                    {p.exchange ?? "—"}
                  </td>
                )}
                {isVisible("sector") && (
                  <td className="w-32 px-4 py-2">
                    <input
                      type="text"
                      value={effectiveSector(
                        symbolMetadata[cticker],
                        sectorOverrides[posKey],
                      )}
                      onChange={(e) => onSectorChange?.(posKey, e.target.value)}
                      placeholder="—"
                      className="w-full bg-transparent text-sm text-neutral-500 outline-none placeholder:text-neutral-700 focus:text-neutral-200"
                    />
                  </td>
                )}
                {isVisible("industry") && (
                  <td className="w-32 px-4 py-2">
                    <input
                      type="text"
                      value={effectiveIndustry(
                        symbolMetadata[cticker],
                        industryOverrides[posKey],
                      )}
                      onChange={(e) =>
                        onIndustryChange?.(posKey, e.target.value)
                      }
                      placeholder="—"
                      className="w-full bg-transparent text-sm text-neutral-500 outline-none placeholder:text-neutral-700 focus:text-neutral-200"
                    />
                  </td>
                )}
                {isVisible("grouping") && (
                  <td className="w-32 px-4 py-2">
                    <select
                      value={groupingAssignments[posKey] ?? ""}
                      onChange={(e) =>
                        onGroupingChange?.(posKey, e.target.value)
                      }
                      className="w-full cursor-pointer bg-transparent text-sm text-neutral-500 outline-none"
                    >
                      <option value="" className="bg-neutral-900">
                        —
                      </option>
                      {groupingLabels.map((g) => (
                        <option key={g} value={g} className="bg-neutral-900">
                          {g}
                        </option>
                      ))}
                    </select>
                  </td>
                )}
                {isVisible("shares_held") && (
                  <td className="px-4 py-3 text-right text-neutral-200">
                    {fmt(p.shares_held, p.shares_held % 1 === 0 ? 0 : 4)}
                  </td>
                )}
                {isVisible("avg_cost_per_share") && (
                  <td className="px-4 py-3 text-right text-neutral-200">
                    ${fmt(p.avg_cost_per_share, 4)}{" "}
                    <span className="text-xs text-neutral-500">
                      {p.currency}
                    </span>
                  </td>
                )}
                {isVisible("cost_basis") && (
                  <td className="px-4 py-3 text-right text-neutral-200">
                    ${fmt(p.cost_basis)}{" "}
                    <span className="text-xs text-neutral-500">
                      {p.currency}
                    </span>
                  </td>
                )}
                {isVisible("realized_pl") && (
                  <td
                    className={`px-4 py-3 text-right ${plClass(p.realized_pl)}`}
                  >
                    {plPrefix(p.realized_pl)}${fmt(p.realized_pl)}{" "}
                    <span className="text-xs text-neutral-500">
                      {p.currency}
                    </span>
                  </td>
                )}
                {isVisible("market_price") && (
                  <td className="px-4 py-3 text-right text-neutral-200">
                    {p.market_price != null ? (
                      <>
                        ${fmt(p.market_price, 2)}{" "}
                        <span className="text-xs text-neutral-500">
                          {p.market_price_currency ?? p.currency}
                        </span>
                      </>
                    ) : (
                      "—"
                    )}
                  </td>
                )}
                {isVisible("market_value_cad") && (
                  <td className="px-4 py-3 text-right text-neutral-200">
                    {p.market_value_cad != null
                      ? `$${fmt(p.market_value_cad)}`
                      : "—"}
                  </td>
                )}
                {isVisible("unrealized_pl") && (
                  <td
                    className={`px-4 py-3 text-right ${p.unrealized_pl_cad != null ? plClass(p.unrealized_pl_cad) : "text-neutral-600"}`}
                  >
                    {p.unrealized_pl_cad != null
                      ? `${plPrefix(p.unrealized_pl_cad)}$${fmt(p.unrealized_pl_cad)}`
                      : "—"}
                  </td>
                )}
                {isVisible("unrealized_pct") && (
                  <td
                    className={`px-4 py-3 text-right ${unrealPct != null ? plClass(unrealPct) : "text-neutral-600"}`}
                  >
                    {unrealPct != null
                      ? `${plPrefix(unrealPct)}${fmtPct(unrealPct)}%`
                      : "—"}
                  </td>
                )}
                {isVisible("dividends") && (
                  <td className="px-4 py-3 text-right text-neutral-200">
                    ${fmt(p.dividends)}{" "}
                    <span className="text-xs text-neutral-500">
                      {p.currency}
                    </span>
                  </td>
                )}
                {isVisible("total_return") && (
                  <td
                    className={`px-4 py-3 text-right ${plClass(totalReturn)}`}
                  >
                    {plPrefix(totalReturn)}${fmt(totalReturn)}
                  </td>
                )}
                {isVisible("total_return_pct") && (
                  <td
                    className={`px-4 py-3 text-right ${totalReturnPct != null ? plClass(totalReturnPct) : "text-neutral-600"}`}
                  >
                    {totalReturnPct != null
                      ? `${plPrefix(totalReturnPct)}${fmtPct(totalReturnPct)}%`
                      : "—"}
                  </td>
                )}
                {isVisible("portfolio_weight") && (
                  <td className="px-4 py-3 text-right text-neutral-400">
                    {portfolioWeight != null
                      ? `${fmtPct(portfolioWeight)}%`
                      : "—"}
                  </td>
                )}
                {showStatusColumn && (
                  <td className="w-8 px-4 py-3 text-center">
                    <StatusCell status={status} />
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
