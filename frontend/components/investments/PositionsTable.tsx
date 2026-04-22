"use client";

import Link from "next/link";
import { useState } from "react";
import type { SymbolMetadata } from "./ChartsSection";

export interface Position {
  account: string;
  symbol: string;
  name: string;
  asset_type: string;
  currency: string;
  shares_held: number;
  avg_cost_per_share: number;
  cost_basis: number;
  realized_pl: number;
  dividends: number;
}

export type AnalysisStatus = "idle" | "loading" | "done" | "error";

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

interface ColDef {
  key: SortKey;
  label: string;
  numeric: boolean;
  className?: string;
}

const COLS_LEFT: ColDef[] = [
  { key: "account", label: "Account", numeric: false, className: "w-24" },
  { key: "name", label: "Name", numeric: false, className: "w-48" },
  { key: "symbol", label: "Symbol", numeric: false, className: "w-20" },
  { key: "asset_type", label: "Type", numeric: false, className: "w-24" },
];

const COLS_RIGHT: ColDef[] = [
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
}

function fmt(n: number, decimals = 2): string {
  return n.toLocaleString("en-CA", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
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

function sectorLabel(meta: SymbolMetadata | undefined): string {
  if (!meta) return "";
  if (meta.asset_type === "ETF") return "ETF";
  if (meta.sector) return meta.sector;
  return "—";
}

export default function PositionsTable({
  positions,
  analysisStatus = {},
  analyzedTickers = new Set(),
  symbolMetadata = {},
}: Props) {
  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [sortClicks, setSortClicks] = useState(0);

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
            {COLS_LEFT.map(({ key, label, numeric, className }) => (
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
            <th className="w-28 px-4 py-3 text-neutral-500">Sector</th>
            {COLS_RIGHT.map(({ key, label, numeric, className }) => (
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
            {showStatusColumn && <th className="w-8 px-4 py-3" />}
          </tr>
        </thead>
        <tbody>
          {sorted.map((p, i) => {
            const isLink = analyzedTickers.has(p.symbol);
            const status = analysisStatus[p.symbol] ?? "idle";

            return (
              <tr
                key={`${p.account}-${p.symbol}-${i}`}
                className="border-b border-neutral-800/50 last:border-0 hover:bg-neutral-800/30"
              >
                <td className="w-24 px-4 py-3 text-neutral-400">{p.account}</td>
                <td className="w-48 max-w-48 truncate px-4 py-3 text-neutral-400">
                  {isLink ? (
                    <Link
                      href={`/company/${p.symbol}`}
                      className="text-blue-400 hover:text-blue-300 hover:underline"
                    >
                      {p.name}
                    </Link>
                  ) : (
                    p.name
                  )}
                </td>
                <td className="w-20 px-4 py-3 font-semibold text-neutral-100">
                  {p.symbol}
                </td>
                <td className="w-24 px-4 py-3 text-neutral-500">
                  {p.asset_type}
                </td>
                <td className="w-28 px-4 py-3 text-neutral-500">
                  {sectorLabel(symbolMetadata[p.symbol])}
                </td>
                <td className="px-4 py-3 text-right text-neutral-200">
                  {fmt(p.shares_held, p.shares_held % 1 === 0 ? 0 : 4)}
                </td>
                <td className="px-4 py-3 text-right text-neutral-200">
                  ${fmt(p.avg_cost_per_share, 4)}
                </td>
                <td className="px-4 py-3 text-right text-neutral-200">
                  ${fmt(p.cost_basis)}
                </td>
                <td
                  className={`px-4 py-3 text-right ${
                    p.realized_pl > 0
                      ? "text-green-400"
                      : p.realized_pl < 0
                        ? "text-red-400"
                        : "text-neutral-500"
                  }`}
                >
                  {p.realized_pl >= 0 ? "+" : ""}${fmt(p.realized_pl)}
                </td>
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
