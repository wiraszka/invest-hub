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
            <th className="px-4 py-3">Account</th>
            <th className="px-4 py-3">Symbol</th>
            <th className="px-4 py-3">Name</th>
            <th className="px-4 py-3">Type</th>
            <th className="px-4 py-3 text-right">Shares</th>
            <th className="px-4 py-3 text-right">Avg Cost</th>
            <th className="px-4 py-3 text-right">Cost Basis</th>
            <th className="px-4 py-3 text-right">Realized P/L</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((p, i) => (
            <tr
              key={`${p.account}-${p.symbol}-${i}`}
              className="border-b border-neutral-800/50 last:border-0 hover:bg-neutral-800/30"
            >
              <td className="px-4 py-3 text-neutral-400">{p.account}</td>
              <td className="px-4 py-3 font-semibold text-neutral-100">
                {p.symbol}
              </td>
              <td className="max-w-48 truncate px-4 py-3 text-neutral-400">
                {p.name}
              </td>
              <td className="px-4 py-3 text-neutral-500">{p.asset_type}</td>
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
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
