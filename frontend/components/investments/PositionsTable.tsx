"use client";

import { useState } from "react";

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

type SortKey = keyof Pick<
  Position,
  | "symbol"
  | "account"
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
}

const COLUMNS: ColDef[] = [
  { key: "account", label: "Account", numeric: false },
  { key: "symbol", label: "Symbol", numeric: false },
  { key: "shares_held", label: "Shares", numeric: true },
  { key: "avg_cost_per_share", label: "Avg Cost", numeric: true },
  { key: "cost_basis", label: "Cost Basis", numeric: true },
  { key: "realized_pl", label: "Realized P/L", numeric: true },
];

interface Props {
  positions: Position[];
}

function fmt(n: number, decimals = 2): string {
  return n.toLocaleString("en-CA", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export default function PositionsTable({ positions }: Props) {
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
            {COLUMNS.map(({ key, label, numeric }) => (
              <th
                key={key}
                className={`px-4 py-3 ${numeric ? "text-right" : ""}`}
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
            <th className="px-4 py-3">Name</th>
            <th className="px-4 py-3">Type</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((p, i) => (
            <tr
              key={`${p.account}-${p.symbol}-${i}`}
              className="border-b border-neutral-800/50 last:border-0 hover:bg-neutral-800/30"
            >
              <td className="px-4 py-3 text-neutral-400">{p.account}</td>
              <td className="px-4 py-3 font-semibold text-neutral-100">
                {p.symbol}
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
              <td className="max-w-48 truncate px-4 py-3 text-neutral-400">
                {p.name}
              </td>
              <td className="px-4 py-3 text-neutral-500">{p.asset_type}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
