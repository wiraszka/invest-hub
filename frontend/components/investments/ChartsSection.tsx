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

function computeAssetType(positions: Position[]) {
  const buckets: Record<string, number> = {};
  for (const p of positions) {
    const label = p.account === "Crypto" ? "Crypto" : p.asset_type;
    accumulate(buckets, label, p.cost_basis);
  }
  return toSlices(buckets);
}

function computeSector(
  positions: Position[],
  metadata: Record<string, SymbolMetadata>,
  sectorOverrides: Record<string, string>,
) {
  const buckets: Record<string, number> = {};
  for (const p of positions) {
    if (p.account === "Crypto") {
      accumulate(buckets, "Crypto", p.cost_basis);
      continue;
    }
    const key = `${p.account}::${p.symbol}`;
    const override = sectorOverrides[key]?.trim();
    if (override) {
      accumulate(buckets, override, p.cost_basis);
      continue;
    }
    const meta = metadata[canonicalTicker(p.symbol, p.currency)];
    if (!meta) continue;
    if (meta.sector_weights) {
      for (const sw of meta.sector_weights) {
        accumulate(buckets, sw.sector, p.cost_basis * (sw.weight / 100));
      }
    } else if (meta.sector) {
      accumulate(buckets, meta.sector, p.cost_basis);
    } else {
      accumulate(buckets, "Other", p.cost_basis);
    }
  }
  return toSlices(buckets);
}

function computeGroupings(
  positions: Position[],
  assignments: Record<string, string>,
) {
  const buckets: Record<string, number> = {};
  for (const p of positions) {
    const key = `${p.account}::${p.symbol}`;
    const group = assignments[key];
    if (!group) continue;
    accumulate(buckets, group, p.cost_basis);
  }
  return toSlices(buckets);
}

export default function ChartsSection({
  positions,
  symbolMetadata,
  groupingAssignments,
  sectorOverrides,
}: Props) {
  const assetTypeData = computeAssetType(positions);
  const sectorData = computeSector(positions, symbolMetadata, sectorOverrides);
  const groupingsData = computeGroupings(positions, groupingAssignments);

  return (
    <div className="flex gap-8">
      <DonutChart
        title="Asset Type"
        data={assetTypeData}
        ready={assetTypeData.length > 0}
        placeholderText="No positions to display"
      />
      <DonutChart
        title="Sector"
        data={sectorData}
        ready={sectorData.length > 0}
        placeholderText="Run Analyze or enter sectors in the table"
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
