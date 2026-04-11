"use client";

interface Props {
  ticker: string;
}

export default function MoreInfoSection({ ticker }: Props) {
  return (
    <div className="mt-8 border-t border-neutral-800 pt-8">
      <h2 className="text-xl font-semibold text-neutral-300 mb-4">More Info</h2>
      <p className="text-neutral-500 text-sm">
        Analysis for {ticker} will appear here.
      </p>
    </div>
  );
}
