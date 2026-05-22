"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface PricePoint {
  date: string;
  close: number;
}

type Range = "1W" | "1M" | "3M" | "6M" | "1Y" | "2Y" | "5Y" | "MAX";

const RANGES: Range[] = ["1W", "1M", "3M", "6M", "1Y", "2Y", "5Y", "MAX"];
const HOURLY_RANGES = new Set<Range>(["1W", "1M", "3M", "6M", "1Y"]);

interface DataState {
  hourly: PricePoint[];
  daily: PricePoint[];
  price: number | null;
  currency: string | null;
  error: string | null;
  loading: boolean;
}

interface Props {
  ticker: string;
  companyName?: string;
  exchange?: string | null;
  sector?: string | null;
  industry?: string | null;
  analysisCurrency?: string;
  logoUrl?: string | null;
}

function cutoffDate(range: Range): Date {
  const now = new Date();
  switch (range) {
    case "1W": {
      const d = new Date(now);
      d.setDate(d.getDate() - 7);
      return d;
    }
    case "1M": {
      const d = new Date(now);
      d.setMonth(d.getMonth() - 1);
      return d;
    }
    case "3M": {
      const d = new Date(now);
      d.setMonth(d.getMonth() - 3);
      return d;
    }
    case "6M": {
      const d = new Date(now);
      d.setMonth(d.getMonth() - 6);
      return d;
    }
    case "1Y": {
      const d = new Date(now);
      d.setFullYear(d.getFullYear() - 1);
      return d;
    }
    case "2Y": {
      const d = new Date(now);
      d.setFullYear(d.getFullYear() - 2);
      return d;
    }
    case "5Y": {
      const d = new Date(now);
      d.setFullYear(d.getFullYear() - 5);
      return d;
    }
    case "MAX":
      return new Date(0);
  }
}

function parseDateStr(dateStr: string): Date {
  return new Date(dateStr.length > 10 ? dateStr.replace(" ", "T") : dateStr);
}

function formatXAxis(dateStr: string, range: Range): string {
  const d = parseDateStr(dateStr);
  if (range === "2Y" || range === "5Y" || range === "MAX") {
    return d.toLocaleDateString("en-US", { month: "short", year: "2-digit" });
  }
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function formatTooltipLabel(dateStr: string): string {
  const d = parseDateStr(dateStr);
  const isHourly = dateStr.length > 10;
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    ...(isHourly && { hour: "2-digit", minute: "2-digit" }),
  });
}

export default function PriceSection({ ticker, companyName, exchange, sector, industry, analysisCurrency, logoUrl }: Props) {
  const [data, setData] = useState<DataState>({
    hourly: [],
    daily: [],
    price: null,
    currency: null,
    error: null,
    loading: true,
  });
  const [range, setRange] = useState<Range>("1Y");

  useEffect(() => {
    let cancelled = false;
    const base = process.env.NEXT_PUBLIC_BACKEND_URL;

    Promise.all([
      fetch(`${base}/api/v1/price/${ticker}`).then((r) => r.json()),
      fetch(
        `${base}/api/v1/price/${ticker}/history?days=729&interval=1h`,
      ).then((r) => r.json()),
      fetch(
        `${base}/api/v1/price/${ticker}/history?days=7300&interval=1day`,
      ).then((r) => r.json()),
    ])
      .then(([priceData, hourlyData, dailyData]) => {
        if (cancelled) return;
        if (priceData.price === undefined) {
          setData((s) => ({
            ...s,
            error: priceData.detail ?? "Failed to load price",
            loading: false,
          }));
        } else {
          setData({
            price: priceData.price,
            currency: priceData.currency ?? null,
            hourly: hourlyData.history ?? [],
            daily: dailyData.history ?? [],
            error: null,
            loading: false,
          });
        }
      })
      .catch(() => {
        if (!cancelled) {
          setData((s) => ({
            ...s,
            error: "Failed to load price data",
            loading: false,
          }));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [ticker]);

  const chartData = useMemo(() => {
    const source = HOURLY_RANGES.has(range) ? data.hourly : data.daily;
    if (range === "MAX") return source;
    const cutoff = cutoffDate(range);
    return source.filter((p) => parseDateStr(p.date) >= cutoff);
  }, [data.hourly, data.daily, range]);

  if (data.loading) {
    return (
      <div className="mb-8">
        <div className="flex items-start gap-4 mb-6">
          <div className="w-[72px] h-[72px] flex-shrink-0 rounded-lg bg-neutral-800 animate-pulse" />
          <div className="flex-1">
            <div className="h-9 w-56 bg-neutral-800 rounded animate-pulse" />
            <div className="h-4 w-64 bg-neutral-800 rounded animate-pulse mt-2" />
          </div>
        </div>
        <div className="h-64 bg-neutral-800 rounded animate-pulse" />
      </div>
    );
  }

  if (data.error) {
    return <div className="mb-8 text-center text-red-400">{data.error}</div>;
  }

  const hasData = data.hourly.length > 0 || data.daily.length > 0;
  const tickInterval =
    chartData.length > 12 ? Math.floor(chartData.length / 6) : 0;

  return (
    <div className="mb-8">
      <div className="flex items-start gap-4 mb-6">
        <div className="w-[72px] h-[72px] flex-shrink-0 rounded-lg bg-white overflow-hidden">
          {logoUrl && (
            <img
              src={logoUrl}
              alt=""
              className="w-full h-full object-contain p-1"
            />
          )}
        </div>
        <div className="min-w-0">
          <h1 className="text-3xl font-bold text-white min-h-[2.25rem]">
            {companyName && companyName !== ticker
              ? `${companyName} (${ticker})`
              : ticker}
          </h1>
          <p className="text-sm text-neutral-500 mt-2">
            {[
              exchange ? `Exchange: ${exchange}` : null,
              sector ? `Sector: ${sector}` : null,
              industry ? `Industry: ${industry}` : null,
              analysisCurrency ? `Currency: ${analysisCurrency}` : null,
            ].filter(Boolean).join(" · ")}
          </p>
        </div>
      </div>
      {hasData && (
        <>
          <div className="flex justify-between items-center mb-4">
            <div className="flex gap-1">
              {RANGES.map((r) => (
                <button
                  key={r}
                  onClick={() => setRange(r)}
                  className={`px-2 py-1 text-xs rounded transition-colors ${
                    range === r
                      ? "bg-neutral-700 text-white"
                      : "text-neutral-500 hover:text-neutral-300"
                  }`}
                >
                  {r}
                </button>
              ))}
            </div>
            {data.price !== null && (
              <p className="text-lg font-semibold text-neutral-300">
                ${data.price.toFixed(2)}{" "}
                <span className="text-xs text-neutral-500">{data.currency ?? "USD"}</span>
              </p>
            )}
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
              <XAxis
                dataKey="date"
                tick={{ fill: "#737373", fontSize: 11 }}
                tickFormatter={(v: string) => formatXAxis(v, range)}
                interval={tickInterval}
              />
              <YAxis
                tick={{ fill: "#737373", fontSize: 11 }}
                domain={["auto", "auto"]}
                tickFormatter={(v: number) => `$${v}`}
                width={56}
              />
              <Tooltip
                contentStyle={{
                  background: "#171717",
                  border: "1px solid #404040",
                  borderRadius: 6,
                }}
                labelStyle={{ color: "#a3a3a3", fontSize: 12 }}
                itemStyle={{ color: "#e5e5e5" }}
                labelFormatter={(label) =>
                  formatTooltipLabel(String(label))
                }
                formatter={(v) => [`$${Number(v).toFixed(2)}`, "Close"]}
              />
              <Line
                type="monotone"
                dataKey="close"
                stroke="#d4af37"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </>
      )}
      {!hasData && data.price !== null && (
        <p className="text-lg font-semibold text-neutral-300">
          ${data.price.toFixed(2)}{" "}
          <span className="text-xs text-neutral-500">{data.currency ?? "USD"}</span>
        </p>
      )}
    </div>
  );
}
