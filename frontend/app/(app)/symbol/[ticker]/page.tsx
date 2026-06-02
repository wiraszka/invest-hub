"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
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
  const router = useRouter();
  const [companyName, setCompanyName] = useState<string | undefined>();
  const [meta, setMeta] = useState<SymbolMeta | undefined>();

  return (
    <div>
      <button
        onClick={() => router.back()}
        aria-label="Go back"
        className="mb-6 text-neutral-500 hover:text-neutral-200 transition-colors"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="28"
          height="28"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M15 18l-6-6 6-6" />
        </svg>
      </button>

      <div className="max-w-5xl mx-auto flex flex-col gap-8">
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
    </div>
  );
}
