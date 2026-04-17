"use client";

import {
  Bar,
  BarChart,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export interface DataIntegrity {
  filing_type: string;
  filing_date: string;
  filing_recency: "fresh" | "stale";
  reporting_currency: string;
  xbrl_quality: "full" | "partial" | "none";
  sections_extracted: boolean;
  company_independence:
    | "independent"
    | "possibly_acquired"
    | "confirmed_inactive";
  llm_model: string;
  llm_knowledge_cutoff: string;
  analysis_timestamp: string;
}

export interface AnalysisData {
  ticker: string;
  company_type: string;
  snapshot: string;
  chart_data: {
    capital_structure: {
      market_cap_usd: number | null;
      net_debt_usd: number | null;
    } | null;
    revenue_by_segment: Record<string, number> | null;
    cash_burn: { annual_burn_usd: number } | null;
  };
  xbrl_data: {
    cash: number | null;
    total_debt: number | null;
    revenue: number | null;
    net_income: number | null;
    operating_cash_flow: number | null;
    shares_outstanding: number | null;
    net_debt: number | null;
  };
  market_cap_usd: number | null;
  data_integrity: DataIntegrity;
  updated_at: string;
}

interface Props {
  data: AnalysisData;
}

function fmt(value: number | null): string {
  if (value === null) return "—";
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1e12) return `${sign}$${(abs / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(2)}M`;
  return `${sign}$${abs.toLocaleString()}`;
}

function fmtShort(value: number): string {
  if (value >= 1e12) return `$${(value / 1e12).toFixed(1)}T`;
  if (value >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
  if (value >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  return `$${value.toLocaleString()}`;
}

const CHART_COLORS = ["#60a5fa", "#f87171", "#34d399", "#fbbf24", "#a78bfa"];

function fmtValue(
  value: number | string | readonly (string | number)[] | null | undefined,
): string {
  if (value === null || value === undefined || typeof value !== "number")
    return "—";
  return fmt(value);
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-xs font-semibold uppercase tracking-widest text-neutral-500 mb-4">
      {children}
    </h3>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-neutral-800 px-4 py-3">
      <div className="text-xs text-neutral-500 mb-1">{label}</div>
      <div className="text-sm font-semibold text-neutral-100">{value}</div>
    </div>
  );
}

function IntegrityRow({
  label,
  value,
  status,
}: {
  label: string;
  value: string;
  status: "green" | "yellow" | "red" | "neutral";
}) {
  const icon =
    status === "green"
      ? "✓"
      : status === "yellow"
        ? "⚠"
        : status === "red"
          ? "✗"
          : "·";
  const iconClass =
    status === "green"
      ? "text-green-500"
      : status === "yellow"
        ? "text-yellow-400"
        : status === "red"
          ? "text-red-500"
          : "text-neutral-500";
  return (
    <tr className="border-t border-neutral-800">
      <td className={`py-2 pr-4 text-xs font-mono w-4 ${iconClass}`}>{icon}</td>
      <td className="py-2 pr-8 text-xs text-neutral-400">{label}</td>
      <td className="py-2 text-xs text-neutral-300">{value}</td>
    </tr>
  );
}

function DataIntegrityTable({ di }: { di: DataIntegrity }) {
  const independenceStatus =
    di.company_independence === "independent"
      ? "green"
      : di.company_independence === "possibly_acquired"
        ? "yellow"
        : "red";

  const independenceLabel =
    di.company_independence === "independent"
      ? "Independent"
      : di.company_independence === "possibly_acquired"
        ? "Possibly acquired"
        : "Confirmed inactive";

  return (
    <div>
      <SectionTitle>Data Integrity</SectionTitle>
      <table className="w-full">
        <tbody>
          <IntegrityRow
            label="Filing type"
            value={di.filing_type || "None"}
            status={di.filing_type ? "green" : "red"}
          />
          <IntegrityRow
            label="Filing date"
            value={di.filing_date || "Unknown"}
            status={di.filing_date ? "neutral" : "red"}
          />
          <IntegrityRow
            label="Filing recency"
            value={
              di.filing_recency === "fresh" ? "Fresh" : "Stale (>18 months)"
            }
            status={di.filing_recency === "fresh" ? "green" : "yellow"}
          />
          <IntegrityRow
            label="Reporting currency"
            value={di.reporting_currency || "Unknown"}
            status={di.reporting_currency === "USD" ? "green" : "yellow"}
          />
          <IntegrityRow
            label="XBRL data"
            value={
              di.xbrl_quality === "full"
                ? "Full"
                : di.xbrl_quality === "partial"
                  ? "Partial"
                  : "None"
            }
            status={
              di.xbrl_quality === "full"
                ? "green"
                : di.xbrl_quality === "partial"
                  ? "yellow"
                  : "red"
            }
          />
          <IntegrityRow
            label="Filing text extracted"
            value={
              di.sections_extracted ? "Yes" : "No (LLM used own knowledge)"
            }
            status={di.sections_extracted ? "green" : "yellow"}
          />
          <IntegrityRow
            label="Company status"
            value={independenceLabel}
            status={independenceStatus}
          />
          <IntegrityRow
            label="LLM model"
            value={di.llm_model || "Unknown"}
            status="neutral"
          />
          <IntegrityRow
            label="LLM knowledge cutoff"
            value={di.llm_knowledge_cutoff || "Unknown"}
            status="neutral"
          />
          <IntegrityRow
            label="Analysis generated"
            value={
              di.analysis_timestamp
                ? new Date(di.analysis_timestamp).toLocaleString()
                : "Unknown"
            }
            status="neutral"
          />
        </tbody>
      </table>
    </div>
  );
}

export default function ResearchPanel({ data }: Props) {
  const { ticker, company_type, snapshot, chart_data, xbrl_data } = data;

  const snapshotLines = snapshot
    .split("\n")
    .map((line) => line.replace(/^-\s*/, "").trim())
    .filter(Boolean);

  const capitalStructureData = (() => {
    const cs = chart_data.capital_structure;
    if (!cs) return null;
    const entries = [
      { name: "Market Cap", value: cs.market_cap_usd },
      { name: "Net Debt", value: cs.net_debt_usd },
    ].filter((e): e is { name: string; value: number } => e.value !== null);
    return entries.length > 0 ? entries : null;
  })();

  const revenueSegmentData = (() => {
    if (!chart_data.revenue_by_segment) return null;
    return Object.entries(chart_data.revenue_by_segment).map(
      ([name, value]) => ({ name, value }),
    );
  })();

  return (
    <div className="flex flex-col gap-8">
      {/* Header */}
      <div className="flex items-baseline gap-3">
        <h2 className="text-2xl font-extrabold text-white">{ticker}</h2>
        <span className="rounded-full bg-neutral-800 px-3 py-1 text-xs text-neutral-400">
          {company_type}
        </span>
      </div>

      {/* Snapshot */}
      <div>
        <SectionTitle>Company Snapshot</SectionTitle>
        <ul className="flex flex-col gap-2">
          {snapshotLines.map((line, i) => (
            <li key={i} className="flex gap-2 text-sm text-neutral-300">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-400" />
              {line}
            </li>
          ))}
        </ul>
      </div>

      {/* Key Metrics */}
      <div>
        <SectionTitle>Key Metrics</SectionTitle>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <MetricCard label="Market Cap" value={fmt(data.market_cap_usd)} />
          <MetricCard label="Revenue" value={fmt(xbrl_data.revenue)} />
          <MetricCard label="Net Income" value={fmt(xbrl_data.net_income)} />
          <MetricCard label="Cash" value={fmt(xbrl_data.cash)} />
        </div>
      </div>

      {/* Capital Structure */}
      {capitalStructureData && (
        <div>
          <SectionTitle>Capital Structure</SectionTitle>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={capitalStructureData} layout="vertical">
              <XAxis
                type="number"
                tickFormatter={fmtShort}
                tick={{ fill: "#737373", fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                type="category"
                dataKey="name"
                tick={{ fill: "#a3a3a3", fontSize: 12 }}
                axisLine={false}
                tickLine={false}
                width={80}
              />
              <Tooltip
                formatter={(v) => fmtValue(v)}
                contentStyle={{
                  background: "#171717",
                  border: "1px solid #404040",
                  borderRadius: 6,
                }}
                labelStyle={{ color: "#e5e5e5" }}
                itemStyle={{ color: "#a3a3a3" }}
              />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {capitalStructureData.map((_, i) => (
                  <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Cash Burn (pre-revenue only) */}
      {company_type === "pre-revenue" && chart_data.cash_burn && (
        <div>
          <SectionTitle>Cash Burn</SectionTitle>
          <div className="flex items-center gap-4">
            <MetricCard
              label="Annual Burn"
              value={fmt(chart_data.cash_burn.annual_burn_usd)}
            />
            {xbrl_data.cash !== null &&
              chart_data.cash_burn.annual_burn_usd > 0 && (
                <MetricCard
                  label="Runway"
                  value={`${(xbrl_data.cash / chart_data.cash_burn.annual_burn_usd).toFixed(1)} yrs`}
                />
              )}
          </div>
        </div>
      )}

      {/* Revenue by Segment */}
      {revenueSegmentData && (
        <div>
          <SectionTitle>Revenue by Segment</SectionTitle>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={revenueSegmentData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={80}
                label={({ name, percent }) =>
                  `${name} ${percent ? (percent * 100).toFixed(0) : 0}%`
                }
                labelLine={false}
              >
                {revenueSegmentData.map((_, i) => (
                  <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                formatter={(v) => fmtValue(v)}
                contentStyle={{
                  background: "#171717",
                  border: "1px solid #404040",
                  borderRadius: 6,
                }}
                labelStyle={{ color: "#e5e5e5" }}
                itemStyle={{ color: "#a3a3a3" }}
              />
              <Legend
                formatter={(value) => (
                  <span style={{ color: "#a3a3a3", fontSize: 12 }}>
                    {value}
                  </span>
                )}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Data Integrity */}
      {data.data_integrity && <DataIntegrityTable di={data.data_integrity} />}
    </div>
  );
}
