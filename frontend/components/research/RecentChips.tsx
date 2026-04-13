"use client";

interface Props {
  tickers: string[];
  onSelect: (ticker: string) => void;
}

export default function RecentChips({ tickers, onSelect }: Props) {
  if (tickers.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs text-neutral-500 uppercase tracking-wide">
        Recent
      </span>
      {tickers.map((ticker) => (
        <button
          key={ticker}
          onClick={() => onSelect(ticker)}
          className="rounded-full border border-neutral-700 bg-neutral-800 px-3 py-1 text-xs font-semibold text-neutral-300 hover:border-neutral-500 hover:text-white transition-colors"
        >
          {ticker}
        </button>
      ))}
    </div>
  );
}
