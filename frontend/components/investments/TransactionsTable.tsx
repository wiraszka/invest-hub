"use client";

import { useState } from "react";

export interface Transaction {
  transaction_date: string;
  account_type: string;
  activity_type: string;
  activity_sub_type: string;
  symbol: string | null;
  name: string | null;
  currency: string;
  quantity: number | null;
  unit_price: number | null;
  commission: number;
  net_cash_amount: number | null;
}

type SortKey =
  | "transaction_date"
  | "account_type"
  | "symbol"
  | "net_cash_amount";
type SortDir = "asc" | "desc";

interface ColDef {
  key: SortKey;
  label: string;
  numeric: boolean;
}

const COLUMNS: ColDef[] = [
  { key: "transaction_date", label: "Date", numeric: false },
  { key: "account_type", label: "Account", numeric: false },
  { key: "symbol", label: "Symbol", numeric: false },
  { key: "net_cash_amount", label: "Amount", numeric: true },
];

interface Props {
  transactions: Transaction[];
}

function typeLabel(t: Transaction): string {
  if (t.activity_type === "Trade") {
    if (t.activity_sub_type === "BUY") return "Buy";
    if (t.activity_sub_type === "SELL") return "Sell";
  }
  if (t.activity_type === "Dividend") return "Dividend";
  if (t.activity_type === "CorporateAction")
    return t.activity_sub_type || "Corporate Action";
  return t.activity_type;
}

function typeBadgeClass(t: Transaction): string {
  if (t.activity_sub_type === "BUY") return "text-blue-400";
  if (t.activity_sub_type === "SELL") return "text-orange-400";
  if (t.activity_type === "Dividend") return "text-green-400";
  return "text-neutral-400";
}

function fmt(n: number): string {
  return n.toLocaleString("en-CA", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function getSortValue(t: Transaction, key: SortKey): string | number {
  if (key === "transaction_date") return t.transaction_date;
  if (key === "account_type") return t.account_type;
  if (key === "symbol") return t.symbol ?? "";
  if (key === "net_cash_amount") return t.net_cash_amount ?? 0;
  return "";
}

export default function TransactionsTable({ transactions }: Props) {
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

  const sorted = [...transactions].sort((a, b) => {
    if (!sortKey) return 0;
    const av = getSortValue(a, sortKey);
    const bv = getSortValue(b, sortKey);
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

  if (transactions.length === 0) {
    return (
      <p className="text-center text-sm text-neutral-500">
        No transactions found
      </p>
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
            <th className="px-4 py-3">Type</th>
            <th className="px-4 py-3">Name</th>
            <th className="px-4 py-3 text-right">Qty</th>
            <th className="px-4 py-3 text-right">Price</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((t, i) => (
            <tr
              key={i}
              className="border-b border-neutral-800/50 last:border-0 hover:bg-neutral-800/30"
            >
              <td className="px-4 py-3 tabular-nums text-neutral-400">
                {t.transaction_date}
              </td>
              <td className="px-4 py-3 text-neutral-400">{t.account_type}</td>
              <td className="px-4 py-3 font-semibold text-neutral-100">
                {t.symbol ?? "—"}
              </td>
              <td
                className={`px-4 py-3 text-right tabular-nums ${
                  (t.net_cash_amount ?? 0) >= 0
                    ? "text-green-400"
                    : "text-red-400"
                }`}
              >
                {t.net_cash_amount != null
                  ? `${t.net_cash_amount >= 0 ? "+" : ""}$${fmt(t.net_cash_amount)}`
                  : "—"}
              </td>
              <td className={`px-4 py-3 ${typeBadgeClass(t)}`}>
                {typeLabel(t)}
              </td>
              <td className="max-w-40 truncate px-4 py-3 text-neutral-400">
                {t.name ?? "—"}
              </td>
              <td className="px-4 py-3 text-right tabular-nums text-neutral-300">
                {t.quantity != null ? t.quantity : "—"}
              </td>
              <td className="px-4 py-3 text-right tabular-nums text-neutral-300">
                {t.unit_price != null ? `$${fmt(t.unit_price)}` : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
