"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import PriceSection from "@/components/company/PriceSection";
import MoreInfoSection from "@/components/company/MoreInfoSection";

export default function CompanyPage() {
  const { ticker } = useParams<{ ticker: string }>();
  const [analysisReady, setAnalysisReady] = useState(false);

  useEffect(() => {
    setAnalysisReady(false);
  }, [ticker]);

  return (
    <div className="max-w-5xl mx-auto">
      <PriceSection ticker={ticker} />
      <MoreInfoSection ticker={ticker} ready={analysisReady} onReady={() => setAnalysisReady(true)} />
    </div>
  );
}
