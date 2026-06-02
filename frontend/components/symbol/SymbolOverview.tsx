"use client";

import { useEffect, useState } from "react";

interface IncomeStatement {
  period: string;
  fiscal_year: number | null;
  revenue: number | null;
  gross_profit: number | null;
  operating_income: number | null;
  net_income: number | null;
  ebitda: number | null;
}

interface BalanceSheet {
  period: string;
  cash: number | null;
  total_debt: number | null;
  net_debt: number | null;
  total_equity: number | null;
  total_assets: number | null;
}

interface CashFlow {
  period: string;
  operating_cash_flow: number | null;
  capex: number | null;
  free_cash_flow: number | null;
}

interface KeyMetrics {
  period: string;
  market_cap: number | null;
  enterprise_value: number | null;
  pe_ratio: number | null;
  ev_ebitda: number | null;
  price_to_book: number | null;
  roe: number | null;
  eps: number | null;
  forward_eps: number | null;
  dividend_yield: number | null;
  beta: number | null;
  debt_to_equity: number | null;
}

interface FinancialData {
  currency: string;
  income: IncomeStatement[];
  balance_sheet: BalanceSheet | null;
  cash_flow: CashFlow[];
  metrics: KeyMetrics | null;
}

interface Profile {
  name: string;
  exchange: string | null;
  description: string | null;
  sector: string | null;
  industry: string | null;
  employees: number | null;
  country: string | null;
}

interface AnalysisData {
  ticker: string;
  company_name: string;
  exchange: string | null;
  currency: string;
  sector: string | null;
  industry: string | null;
  snapshot: {
    financials: FinancialData | null;
    profile: Profile | null;
    metrics_block: string;
    filing_excerpt: string;
  };
  template_key: string;
  generated_at: string;
}

interface SymbolMeta {
  exchange: string | null;
  sector: string | null;
  industry: string | null;
  currency: string;
  logoUrl: string | null;
}

interface Props {
  ticker: string;
  onCompanyName?: (name: string) => void;
  onMetadata?: (meta: SymbolMeta) => void;
}

type Status = "loading" | "generating" | "done" | "error";

// --- Formatting helpers ---

function fmt(value: number | null, prefix = "$"): string {
  if (value === null || value === undefined) return "—";
  const absVal = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (absVal >= 1_000_000_000)
    return `${sign}${prefix}${(absVal / 1_000_000_000).toFixed(2)}B`;
  if (absVal >= 1_000_000)
    return `${sign}${prefix}${(absVal / 1_000_000).toFixed(1)}M`;
  return `${sign}${prefix}${absVal.toLocaleString()}`;
}

function pct(num: number | null, denom: number | null): string {
  if (num === null || !denom) return "—";
  return `${((num / denom) * 100).toFixed(1)}%`;
}

function yoy(curr: number | null, prior: number | null): string {
  if (curr === null || prior === null || prior === 0) return "";
  const chg = ((curr - prior) / Math.abs(prior)) * 100;
  const sign = chg >= 0 ? "+" : "";
  return `${sign}${chg.toFixed(1)}%`;
}

function fmtMultiple(v: number | null, suffix = "x"): string {
  if (v === null || v === undefined) return "—";
  return `${v.toFixed(1)}${suffix}`;
}

function fmtPct(v: number | null): string {
  if (v === null || v === undefined) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

// --- Sub-components ---

function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-xs font-semibold uppercase tracking-widest text-neutral-500 mb-4">
      {children}
    </h3>
  );
}

function StatPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1 bg-neutral-900 rounded-md px-4 py-3 border border-neutral-800">
      <span className="text-xs text-neutral-500">{label}</span>
      <span className="text-sm font-mono font-semibold text-neutral-100">
        {value}
      </span>
    </div>
  );
}

function MetricRow({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="flex justify-between items-baseline gap-4 py-2 border-b border-neutral-800 last:border-0">
      <span className="text-sm text-neutral-400">{label}</span>
      <div className="text-right">
        <span className="text-sm font-mono text-neutral-100">{value}</span>
        {sub && <span className="text-xs text-neutral-500 ml-2">{sub}</span>}
      </div>
    </div>
  );
}

export default function SymbolOverview({
  ticker,
  onCompanyName,
  onMetadata,
}: Props) {
  const [data, setData] = useState<AnalysisData | null>(null);
  const [status, setStatus] = useState<Status>("loading");

  const base = process.env.NEXT_PUBLIC_BACKEND_URL;

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const cached = await fetch(`${base}/api/v1/analysis/${ticker}/data`);
        if (!cancelled && cached.ok) {
          const parsed = await cached.json();
          setData(parsed);
          onCompanyName?.(parsed.company_name);
          onMetadata?.({
            exchange: parsed.exchange,
            sector: parsed.sector,
            industry: parsed.industry,
            currency: parsed.currency,
            logoUrl: parsed.logo_url ?? null,
          });
          setStatus("done");
          return;
        }

        if (!cancelled) setStatus("generating");
        const generated = await fetch(
          `${base}/api/v1/analysis/${ticker}/data`,
          { method: "POST" },
        );
        if (cancelled) return;
        if (!generated.ok) {
          setStatus("error");
          return;
        }
        const parsed = await generated.json();
        setData(parsed);
        onCompanyName?.(parsed.company_name);
        onMetadata?.({
          exchange: parsed.exchange,
          sector: parsed.sector,
          industry: parsed.industry,
          currency: parsed.currency,
          logoUrl: parsed.logo_url ?? null,
        });
        setStatus("done");
      } catch {
        if (!cancelled) setStatus("error");
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [ticker, base]);

  if (status === "loading" || status === "generating") {
    return (
      <div className="border-t border-neutral-800 pt-8 flex flex-col gap-4">
        <div className="flex items-center gap-3 text-sm text-neutral-400">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-neutral-700 border-t-neutral-300" />
          {status === "generating" ? "Fetching company data…" : "Loading…"}
        </div>
        <div className="h-4 w-48 bg-neutral-800 rounded animate-pulse" />
        <div className="h-4 w-64 bg-neutral-800 rounded animate-pulse" />
        <div className="h-24 bg-neutral-800 rounded animate-pulse mt-2" />
      </div>
    );
  }

  if (status === "error" || !data) {
    return (
      <div className="border-t border-neutral-800 pt-8">
        <p className="text-sm text-neutral-500 text-center">
          Unable to load company data
        </p>
      </div>
    );
  }

  const fin = data.snapshot.financials;
  const profile = data.snapshot.profile;
  const description = profile?.description ?? null;
  const metrics = fin?.metrics ?? null;

  const income = [...(fin?.income ?? [])]
    .sort((a, b) => (a.fiscal_year ?? 0) - (b.fiscal_year ?? 0))
    .filter(
      (p) =>
        p.revenue !== null ||
        p.gross_profit !== null ||
        p.operating_income !== null ||
        p.net_income !== null ||
        p.ebitda !== null,
    );
  const cashFlow = [...(fin?.cash_flow ?? [])].sort((a, b) =>
    a.period < b.period ? -1 : 1,
  );
  const bs = fin?.balance_sheet ?? null;

  const updatedAt = new Date(data.generated_at).toLocaleDateString("en-CA", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  return (
    <div className="border-t border-neutral-800 pt-8 flex flex-col gap-12">
      {/* Company Snapshot */}
      {description && (
        <div>
          <SectionHeader>Company Snapshot</SectionHeader>
          <p className="text-sm text-neutral-300 leading-relaxed">
            {description}
          </p>
        </div>
      )}

      {/* Valuation */}
      {metrics && (
        <div>
          <SectionHeader>Valuation</SectionHeader>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
            <StatPill label="Market Cap" value={fmt(metrics.market_cap)} />
            <StatPill
              label="Enterprise Value"
              value={fmt(metrics.enterprise_value)}
            />
            <StatPill label="P/E Ratio" value={fmtMultiple(metrics.pe_ratio)} />
            <StatPill
              label="EV / EBITDA"
              value={fmtMultiple(metrics.ev_ebitda)}
            />
            <StatPill
              label="Price / Book"
              value={fmtMultiple(metrics.price_to_book)}
            />
            <StatPill label="ROE" value={fmtPct(metrics.roe)} />
            {metrics.beta !== null && (
              <StatPill label="Beta" value={fmtMultiple(metrics.beta, "")} />
            )}
            {metrics.dividend_yield !== null && metrics.dividend_yield > 0 && (
              <StatPill
                label="Dividend Yield"
                value={`${metrics.dividend_yield.toFixed(2)}%`}
              />
            )}
            {metrics.eps !== null && (
              <StatPill label="EPS (TTM)" value={fmt(metrics.eps, "")} />
            )}
            {metrics.forward_eps !== null && (
              <StatPill
                label="Forward EPS"
                value={fmt(metrics.forward_eps, "")}
              />
            )}
          </div>
        </div>
      )}

      {/* Income Statement */}
      {income.length > 0 && (
        <div>
          <SectionHeader>Income Statement</SectionHeader>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr>
                  <th className="text-left text-xs text-neutral-500 font-medium pb-3 pr-4 w-40">
                    {fin?.currency ?? data.currency}
                  </th>
                  {income.map((p) => (
                    <th
                      key={p.period}
                      className="text-right text-xs text-neutral-400 font-semibold pb-3 px-2"
                    >
                      {p.fiscal_year ? `FY${p.fiscal_year}` : p.period}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-800">
                <tr>
                  <td className="py-2 pr-4 text-neutral-400">Revenue</td>
                  {income.map((p, i) => {
                    const prior = income[i - 1] ?? null;
                    // yfinance returns 0.0 as a data-gap sentinel for no-revenue periods
                    const rev = p.revenue || null;
                    const prevRev = prior?.revenue || null;
                    const change = yoy(rev, prevRev);
                    return (
                      <td key={p.period} className="py-2 px-2 text-right">
                        <span className="font-mono text-neutral-100">
                          {fmt(rev)}
                        </span>
                        {change && (
                          <span
                            className={`block text-xs ${change.startsWith("+") ? "text-emerald-500" : "text-red-400"}`}
                          >
                            {change}
                          </span>
                        )}
                      </td>
                    );
                  })}
                </tr>
                <tr>
                  <td className="py-2 pr-4 text-neutral-400">Gross Profit</td>
                  {income.map((p) => {
                    const rev = p.revenue || null;
                    // treat gross_profit=0 as missing only when revenue is also absent
                    const gp =
                      p.gross_profit === 0 && !rev ? null : p.gross_profit;
                    return (
                      <td key={p.period} className="py-2 px-2 text-right">
                        <span className="font-mono text-neutral-100">
                          {fmt(gp)}
                        </span>
                        <span className="block text-xs text-neutral-500">
                          {pct(gp, rev)}
                        </span>
                      </td>
                    );
                  })}
                </tr>
                <tr>
                  <td className="py-2 pr-4 text-neutral-400">
                    Operating Income
                  </td>
                  {income.map((p) => (
                    <td key={p.period} className="py-2 px-2 text-right">
                      <span className="font-mono text-neutral-100">
                        {fmt(p.operating_income)}
                      </span>
                      <span className="block text-xs text-neutral-500">
                        {pct(p.operating_income, p.revenue)}
                      </span>
                    </td>
                  ))}
                </tr>
                <tr>
                  <td className="py-2 pr-4 text-neutral-400">EBITDA</td>
                  {income.map((p) => (
                    <td key={p.period} className="py-2 px-2 text-right">
                      <span className="font-mono text-neutral-100">
                        {fmt(p.ebitda)}
                      </span>
                      <span className="block text-xs text-neutral-500">
                        {pct(p.ebitda, p.revenue)}
                      </span>
                    </td>
                  ))}
                </tr>
                <tr>
                  <td className="py-2 pr-4 text-neutral-400">Net Income</td>
                  {income.map((p) => (
                    <td key={p.period} className="py-2 px-2 text-right">
                      <span className="font-mono text-neutral-100">
                        {fmt(p.net_income)}
                      </span>
                      <span className="block text-xs text-neutral-500">
                        {pct(p.net_income, p.revenue)}
                      </span>
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Balance Sheet + Cash Flow */}
      {(bs || cashFlow.length > 0) && (
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-2">
          {bs && (
            <div>
              <SectionHeader>Balance Sheet</SectionHeader>
              <MetricRow label="Cash" value={fmt(bs.cash)} />
              <MetricRow label="Total Debt" value={fmt(bs.total_debt)} />
              <MetricRow
                label={
                  bs.net_debt !== null && bs.net_debt < 0
                    ? "Net Cash"
                    : "Net Debt"
                }
                value={fmt(bs.net_debt)}
              />
              <MetricRow label="Total Equity" value={fmt(bs.total_equity)} />
              <MetricRow label="Total Assets" value={fmt(bs.total_assets)} />
            </div>
          )}

          {cashFlow.length > 0 && (
            <div>
              {(() => {
                const cf = cashFlow[cashFlow.length - 1];
                const latestIncome =
                  income.length > 0 ? income[income.length - 1] : null;
                const fcfConv =
                  cf.free_cash_flow && latestIncome?.net_income
                    ? cf.free_cash_flow / latestIncome.net_income
                    : null;
                return (
                  <>
                    <SectionHeader>
                      Cash Flow{" "}
                      <span className="normal-case tracking-normal font-normal text-neutral-600">
                        ({cf.period})
                      </span>
                    </SectionHeader>
                    <MetricRow
                      label="Operating CF"
                      value={fmt(cf.operating_cash_flow)}
                    />
                    <MetricRow label="CapEx" value={fmt(cf.capex)} />
                    <MetricRow
                      label="Free Cash Flow"
                      value={fmt(cf.free_cash_flow)}
                    />
                    {fcfConv !== null && (
                      <MetricRow
                        label="FCF Conversion"
                        value={`${fcfConv.toFixed(2)}x`}
                        sub="FCF / Net Income"
                      />
                    )}
                  </>
                );
              })()}
            </div>
          )}
        </div>
      )}

      <p className="text-xs text-neutral-700">Last updated {updatedAt}</p>
    </div>
  );
}
