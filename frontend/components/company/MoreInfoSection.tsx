"use client";

interface Props {
  ticker: string;
  ready: boolean;
  onReady: () => void;
}

export default function MoreInfoSection({ ticker, ready }: Props) {
  if (!ready) {
    return (
      <div className="mt-8 border-t border-neutral-800 pt-8">
        <h2 className="text-xl font-semibold text-neutral-300 mb-4">More Info</h2>
        <div className="flex items-center gap-3 text-neutral-500">
          <div className="h-4 w-4 rounded-full border-2 border-neutral-600 border-t-neutral-300 animate-spin" />
          <span className="text-sm">Fetching filings and running analysis…</span>
        </div>
      </div>
    );
  }

  return (
    <div className="mt-8 border-t border-neutral-800 pt-8">
      <h2 className="text-xl font-semibold text-neutral-300 mb-4">More Info</h2>
      <p className="text-neutral-500 text-sm">
        Analysis for {ticker} will appear here.
      </p>
    </div>
  );
}
