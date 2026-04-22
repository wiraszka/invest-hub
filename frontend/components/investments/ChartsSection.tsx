"use client";

import DonutChart from "./DonutChart";
import type { Position } from "./PositionsTable";

export interface SymbolMetadata {
  ticker: string;
  fmp_ticker: string;
  asset_type: string;
  sector: string | null;
  country: string | null;
  sector_weights: { sector: string; weight: number }[] | null;
  country_weights: { country: string; weight: number }[] | null;
  has_analysis: boolean;
  fetched_at: string;
}

interface Props {
  positions: Position[];
  symbolMetadata: Record<string, SymbolMetadata>;
  metadataReady: boolean;
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
) {
  const buckets: Record<string, number> = {};
  for (const p of positions) {
    if (p.account === "Crypto") {
      accumulate(buckets, "Crypto", p.cost_basis);
      continue;
    }
    const meta = metadata[p.symbol];
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

function computeGeography(
  positions: Position[],
  metadata: Record<string, SymbolMetadata>,
) {
  const buckets: Record<string, number> = {};
  for (const p of positions) {
    if (p.account === "Crypto") {
      accumulate(buckets, "Crypto", p.cost_basis);
      continue;
    }
    const meta = metadata[p.symbol];
    if (!meta) continue;

    if (meta.country_weights) {
      for (const cw of meta.country_weights) {
        accumulate(buckets, cw.country, p.cost_basis * (cw.weight / 100));
      }
    } else if (meta.country) {
      accumulate(buckets, meta.country, p.cost_basis);
    } else {
      accumulate(buckets, "Other", p.cost_basis);
    }
  }
  return toSlices(buckets);
}

export default function ChartsSection({
  positions,
  symbolMetadata,
  metadataReady,
}: Props) {
  const assetTypeData = computeAssetType(positions);
  const sectorData = computeSector(positions, symbolMetadata);
  const geoData = computeGeography(positions, symbolMetadata);

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
        ready={metadataReady && sectorData.length > 0}
        placeholderText="Click Analyze below to see sector breakdown"
      />
      <DonutChart
        title="Geography"
        data={geoData}
        ready={metadataReady && geoData.length > 0}
        placeholderText="Click Analyze below to see geographic breakdown"
      />
    </div>
  );
}
