"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import PriceSection from "@/components/symbol/PriceSection";
import ResearchPanel from "@/components/symbol/ResearchPanel";

export default function SymbolPage() {
  const { ticker } = useParams<{ ticker: string }>();

  return (
    <div className="max-w-5xl mx-auto flex flex-col gap-8">
      <Link
        href="/investments"
        className="inline-flex items-center gap-1 text-sm text-neutral-400 hover:text-neutral-200 transition-colors w-fit"
      >
        ← Investments
      </Link>

      <PriceSection key={ticker} ticker={ticker} />
      <ResearchPanel key={ticker} ticker={ticker} />
    </div>
  );
}
