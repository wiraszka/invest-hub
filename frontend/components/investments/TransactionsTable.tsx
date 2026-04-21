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

export default function TransactionsTable({ transactions }: Props) {
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
            <th className="px-4 py-3">Date</th>
            <th className="px-4 py-3">Account</th>
            <th className="px-4 py-3">Type</th>
            <th className="px-4 py-3">Symbol</th>
            <th className="px-4 py-3">Name</th>
            <th className="px-4 py-3 text-right">Qty</th>
            <th className="px-4 py-3 text-right">Price</th>
            <th className="px-4 py-3 text-right">Amount</th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((t, i) => (
            <tr
              key={i}
              className="border-b border-neutral-800/50 last:border-0 hover:bg-neutral-800/30"
            >
              <td className="px-4 py-3 tabular-nums text-neutral-400">
                {t.transaction_date}
              </td>
              <td className="px-4 py-3 text-neutral-400">{t.account_type}</td>
              <td className={`px-4 py-3 ${typeBadgeClass(t)}`}>
                {typeLabel(t)}
              </td>
              <td className="px-4 py-3 font-semibold text-neutral-100">
                {t.symbol ?? "—"}
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
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
