"use client";

import DonutChart from "./DonutChart";
import type { Position } from "./PositionsTable";

export interface SymbolMetadata {
  ticker: string;
  fmp_ticker?: string;
  asset_type: string;
  sector: string | null;
  country: string | null;
  sector_weights: { sector: string; weight: number }[] | null;
  country_weights: { country: string; weight: number }[] | null;
  has_analysis: boolean;
  fetched_at: string;
}

export function canonicalTicker(symbol: string, currency: string): string {
  return currency === "CAD" ? `${symbol}.TO` : symbol;
}

interface Props {
  positions: Position[];
  symbolMetadata: Record<string, SymbolMetadata>;
  metadataReady: boolean;
  groupingAssignments: Record<string, string>;
  sectorOverrides: Record<string, string>;
  industryOverrides: Record<string, string>;
  middleChartColumn: "sector" | "industry";
  onMiddleChartColumnChange: (col: "sector" | "industry") => void;
  chartValueMode: "cost_basis" | "market_value";
}

function accumulate(
  buckets: Record<string, number>,
  key: string,
  value: number,
) {
  buckets[key] = (buckets[key] ?? 0) + value;
}

function toSlices(buckets: Record<string, number>) {
  return Object.entries(buckets)
    .map(([name, value]) => ({ name, value }))
    .filter((s) => s.value > 0)
    .sort((a, b) => b.value - a.value);
}

function posValue(p: Position, mode: "cost_basis" | "market_value"): number {
  return mode === "market_value"
    ? (p.market_value_cad ?? p.cost_basis)
    : p.cost_basis;
}

function computeAssetType(
  positions: Position[],
  mode: "cost_basis" | "market_value",
) {
  const buckets: Record<string, number> = {};
  for (const p of positions) {
    const label = p.account === "Crypto" ? "Crypto" : p.asset_type;
    accumulate(buckets, label, posValue(p, mode));
  }
  return toSlices(buckets);
}

function computeSector(
  positions: Position[],
  metadata: Record<string, SymbolMetadata>,
  sectorOverrides: Record<string, string>,
  mode: "cost_basis" | "market_value",
) {
  const buckets: Record<string, number> = {};
  for (const p of positions) {
    const val = posValue(p, mode);
    if (p.account === "Crypto") {
      accumulate(buckets, "Crypto", val);
      continue;
    }
    const key = `${p.account}::${p.symbol}`;
    const override = sectorOverrides[key]?.trim();
    if (override) {
      accumulate(buckets, override, val);
      continue;
    }
    const meta = metadata[canonicalTicker(p.symbol, p.currency)];
    if (!meta) continue;
    if (meta.sector_weights) {
      for (const sw of meta.sector_weights) {
        accumulate(buckets, sw.sector, val * (sw.weight / 100));
      }
    } else if (meta.sector) {
      accumulate(buckets, meta.sector, val);
    } else {
      accumulate(buckets, "Other", val);
    }
  }
  return toSlices(buckets);
}

function computeIndustry(
  positions: Position[],
  industryOverrides: Record<string, string>,
  mode: "cost_basis" | "market_value",
) {
  const buckets: Record<string, number> = {};
  for (const p of positions) {
    const key = `${p.account}::${p.symbol}`;
    const override = industryOverrides[key]?.trim();
    if (override) {
      accumulate(buckets, override, posValue(p, mode));
    }
  }
  return toSlices(buckets);
}

function computeGroupings(
  positions: Position[],
  assignments: Record<string, string>,
  mode: "cost_basis" | "market_value",
) {
  const buckets: Record<string, number> = {};
  for (const p of positions) {
    const key = `${p.account}::${p.symbol}`;
    const group = assignments[key];
    if (!group) continue;
    accumulate(buckets, group, posValue(p, mode));
  }
  return toSlices(buckets);
}

const MIDDLE_OPTIONS = ["Sector", "Industry"];

export default function ChartsSection({
  positions,
  symbolMetadata,
  groupingAssignments,
  sectorOverrides,
  industryOverrides,
  middleChartColumn,
  onMiddleChartColumnChange,
  chartValueMode,
}: Props) {
  const assetTypeData = computeAssetType(positions, chartValueMode);
  const sectorData = computeSector(
    positions,
    symbolMetadata,
    sectorOverrides,
    chartValueMode,
  );
  const industryData = computeIndustry(
    positions,
    industryOverrides,
    chartValueMode,
  );
  const groupingsData = computeGroupings(
    positions,
    groupingAssignments,
    chartValueMode,
  );

  const middleData = middleChartColumn === "sector" ? sectorData : industryData;
  const middleTitle = middleChartColumn === "sector" ? "Sector" : "Industry";
  const middlePlaceholder =
    middleChartColumn === "sector"
      ? "Run Analyze or enter sectors in the table"
      : "Enter industries in the table below";

  return (
    <div className="flex gap-8">
      <DonutChart
        title="Asset Type"
        data={assetTypeData}
        ready={assetTypeData.length > 0}
        placeholderText="No positions to display"
      />
      <DonutChart
        title={middleTitle}
        data={middleData}
        ready={middleData.length > 0}
        placeholderText={middlePlaceholder}
        titleOptions={MIDDLE_OPTIONS}
        selectedOption={middleTitle}
        onOptionChange={(opt) =>
          onMiddleChartColumnChange(opt.toLowerCase() as "sector" | "industry")
        }
      />
      <DonutChart
        title="Groupings"
        data={groupingsData}
        ready={groupingsData.length > 0}
        placeholderText="Assign groupings in the table below"
      />
    </div>
  );
}
