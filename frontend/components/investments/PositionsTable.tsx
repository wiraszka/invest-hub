"use client";

import Link from "next/link";
import { useState } from "react";
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
  { key: "market_value_cad", label: "Mkt Value" },
  { key: "unrealized_pl", label: "Unreal. P/L" },
  { key: "unrealized_pct", label: "Unreal. %" },
  { key: "realized_pl", label: "Realized P/L" },
  { key: "dividends", label: "Dividends" },
  { key: "total_return", label: "Total Return" },
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

type SortKey = keyof Pick<
  Position,
  | "account"
  | "name"
  | "symbol"
  | "asset_type"
  | "shares_held"
  | "avg_cost_per_share"
  | "cost_basis"
  | "realized_pl"
>;
type SortDir = "asc" | "desc";

interface SortableColDef {
  key: SortKey;
  label: string;
  numeric: boolean;
  className?: string;
}

const COLS_LEFT: SortableColDef[] = [
  { key: "account", label: "Account", numeric: false, className: "w-24" },
  { key: "name", label: "Name", numeric: false, className: "w-48" },
  { key: "symbol", label: "Symbol", numeric: false, className: "w-20" },
  { key: "asset_type", label: "Type", numeric: false, className: "w-24" },
];

const COLS_RIGHT: SortableColDef[] = [
  { key: "shares_held", label: "Shares", numeric: true },
  { key: "avg_cost_per_share", label: "Avg Cost", numeric: true },
  { key: "cost_basis", label: "Cost Basis", numeric: true },
  { key: "realized_pl", label: "Realized P/L", numeric: true },
];

interface Props {
  positions: Position[];
  analysisStatus?: Record<string, AnalysisStatus>;
  analyzedTickers?: Set<string>;
  symbolMetadata?: Record<string, SymbolMetadata>;
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

export default function PositionsTable({
  positions,
  analysisStatus = {},
  analyzedTickers = new Set(),
  symbolMetadata = {},
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

  function handleSort(key: SortKey, numeric: boolean) {
    if (sortKey !== key) {
      setSortKey(key);
      setSortDir(numeric ? "desc" : "asc");
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

  const sorted = [...positions].sort((a, b) => {
    if (!sortKey) return 0;
    const av = a[sortKey];
    const bv = b[sortKey];
    const cmp =
      typeof av === "string"
        ? av.localeCompare(bv as string)
        : (av as number) - (bv as number);
    return sortDir === "asc" ? cmp : -cmp;
  });

  function indicator(key: SortKey) {
    if (sortKey !== key) return null;
    return (
      <span className="ml-1 opacity-60">{sortDir === "asc" ? "↑" : "↓"}</span>
    );
  }

  const totalMarketValue = positions.reduce(
    (sum, p) => sum + (p.market_value_cad ?? 0),
    0,
  );
  const showStatusColumn = Object.keys(analysisStatus).length > 0;
  const visibleLeft = COLS_LEFT.filter((c) => isVisible(c.key));
  const visibleRight = COLS_RIGHT.filter((c) => isVisible(c.key));

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
            {visibleLeft.map(({ key, label, numeric, className }) => (
              <th
                key={key}
                className={`px-4 py-3 ${numeric ? "text-right" : ""} ${className ?? ""}`}
              >
                <button
                  onClick={() => handleSort(key, numeric)}
                  className={`inline-flex items-center gap-0.5 hover:text-neutral-300 ${
                    sortKey === key ? "text-neutral-300" : ""
                  } ${numeric ? "ml-auto" : ""}`}
                >
                  {label}
                  {indicator(key)}
                </button>
              </th>
            ))}
            {isVisible("exchange") && (
              <th className="w-24 px-4 py-3 text-neutral-500">Exchange</th>
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
            {visibleRight.map(({ key, label, numeric, className }) => (
              <th
                key={key}
                className={`px-4 py-3 ${numeric ? "text-right" : ""} ${className ?? ""}`}
              >
                <button
                  onClick={() => handleSort(key, numeric)}
                  className={`inline-flex items-center gap-0.5 hover:text-neutral-300 ${
                    sortKey === key ? "text-neutral-300" : ""
                  } ${numeric ? "ml-auto" : ""}`}
                >
                  {label}
                  {indicator(key)}
                </button>
              </th>
            ))}
            {isVisible("market_price") && (
              <th className="px-4 py-3 text-right text-neutral-500">
                Mkt Price
              </th>
            )}
            {isVisible("market_value_cad") && (
              <th className="px-4 py-3 text-right text-neutral-500">
                Mkt Value
              </th>
            )}
            {isVisible("unrealized_pl") && (
              <th className="px-4 py-3 text-right text-neutral-500">
                Unreal. P/L
              </th>
            )}
            {isVisible("unrealized_pct") && (
              <th className="px-4 py-3 text-right text-neutral-500">
                Unreal. %
              </th>
            )}
            {isVisible("dividends") && (
              <th className="px-4 py-3 text-right text-neutral-500">
                Dividends
              </th>
            )}
            {isVisible("total_return") && (
              <th className="px-4 py-3 text-right text-neutral-500">
                Total Return
              </th>
            )}
            {isVisible("total_return_pct") && (
              <th className="px-4 py-3 text-right text-neutral-500">Total %</th>
            )}
            {isVisible("portfolio_weight") && (
              <th className="px-4 py-3 text-right text-neutral-500">
                Weight %
              </th>
            )}
            {showStatusColumn && <th className="w-8 px-4 py-3" />}
          </tr>
        </thead>
        <tbody>
          {sorted.map((p, i) => {
            const cticker = canonicalTicker(p.symbol, p.currency);
            const posKey = `${p.account}::${p.symbol}`;
            const isLink = analyzedTickers.has(cticker);
            const status = analysisStatus[cticker] ?? "idle";

            const unrealPct =
              p.unrealized_pl_cad != null && p.cost_basis > 0
                ? (p.unrealized_pl_cad / p.cost_basis) * 100
                : null;
            const totalReturn =
              (p.unrealized_pl_cad ?? 0) + p.realized_pl + p.dividends;
            const totalReturnPct =
              p.cost_basis > 0 ? (totalReturn / p.cost_basis) * 100 : null;
            const portfolioWeight =
              totalMarketValue > 0 && p.market_value_cad != null
                ? (p.market_value_cad / totalMarketValue) * 100
                : null;

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
                        href={`/company/${cticker}`}
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
                      value={industryOverrides[posKey] ?? ""}
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
                    ${fmt(p.avg_cost_per_share, 4)}
                  </td>
                )}
                {isVisible("cost_basis") && (
                  <td className="px-4 py-3 text-right text-neutral-200">
                    ${fmt(p.cost_basis)}
                  </td>
                )}
                {isVisible("realized_pl") && (
                  <td
                    className={`px-4 py-3 text-right ${plClass(p.realized_pl)}`}
                  >
                    {plPrefix(p.realized_pl)}${fmt(p.realized_pl)}
                  </td>
                )}
                {isVisible("market_price") && (
                  <td className="px-4 py-3 text-right text-neutral-200">
                    {p.market_price != null
                      ? `$${fmt(p.market_price, 2)}${p.market_price_currency === "USD" ? " USD" : ""}`
                      : "—"}
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
                    ${fmt(p.dividends)}
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
