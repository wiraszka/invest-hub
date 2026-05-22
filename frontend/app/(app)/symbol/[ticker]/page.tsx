"use client";

import Link from "next/link";
import { useState } from "react";
import { useParams } from "next/navigation";
import PriceSection from "@/components/symbol/PriceSection";
import SymbolOverview from "@/components/symbol/SymbolOverview";

interface SymbolMeta {
  exchange: string | null;
  sector: string | null;
  industry: string | null;
  currency: string;
  logoUrl: string | null;
}

export default function SymbolPage() {
  const { ticker } = useParams<{ ticker: string }>();
  const [companyName, setCompanyName] = useState<string | undefined>();
  const [meta, setMeta] = useState<SymbolMeta | undefined>();

  return (
    <div className="max-w-5xl mx-auto flex flex-col gap-8">
      <Link
        href="/investments"
        className="inline-flex items-center gap-1 text-sm text-neutral-400 hover:text-neutral-200 transition-colors w-fit"
      >
        ← Investments
      </Link>

      <PriceSection
        key={`price-${ticker}`}
        ticker={ticker}
        companyName={companyName}
        exchange={meta?.exchange}
        sector={meta?.sector}
        industry={meta?.industry}
        analysisCurrency={meta?.currency}
        logoUrl={meta?.logoUrl}
      />
      <SymbolOverview
        key={`overview-${ticker}`}
        ticker={ticker}
        onCompanyName={setCompanyName}
        onMetadata={setMeta}
      />
    </div>
  );
}
