"use client";

import { useParams } from "next/navigation";
import PriceSection from "@/components/company/PriceSection";
import MoreInfoSection from "@/components/company/MoreInfoSection";

export default function CompanyPage() {
  const { ticker } = useParams<{ ticker: string }>();

  return (
    <div className="max-w-5xl mx-auto">
      <PriceSection key={ticker} ticker={ticker} />
      <MoreInfoSection key={ticker} ticker={ticker} />
    </div>
  );
}
