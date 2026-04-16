"use client";

import { useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const ALL_COMMODITIES = [
  "Gold",
  "Silver",
  "Platinum",
  "Copper",
  "Uranium",
  "Lithium",
  "Nickel",
  "Phosphate",
  "Graphite",
  "Zinc",
  "Antimony",
];

const DEFAULT_COMMODITIES = ["Gold", "Silver", "Platinum", "Copper", "Uranium"];

const TIMEFRAMES = [
  "Past 1 week",
  "Past 1 month",
  "Past 3 months",
  "Past 6 months",
  "Past 12 months",
  "Past 5 years",
  "2004 to present",
];

const COLOR_MAP: Record<string, string> = {
  Gold: "#D4AF37",
  Silver: "#C0C0C0",
  Platinum: "#9FA7B2",
  Copper: "#B87333",
  Uranium: "#6B8E23",
  Lithium: "#4F86C6",
  Nickel: "#6E7F80",
  Phosphate: "#7EA04D",
  Graphite: "#4A4A4A",
  Zinc: "#7D8CA3",
  Antimony: "#A67C52",
};

interface LatestEntry {
  commodity: string;
  interest: number;
  momentum: number | null;
}

interface TrendsData {
  series: Record<string, string | number>[];
  latest: LatestEntry[];
}

export default function CommoditiesSentimentPage() {
  const [timeframe, setTimeframe] = useState("Past 1 month");
  const [geo, setGeo] = useState("");
  const [selectedCommodities, setSelectedCommodities] =
    useState<string[]>(DEFAULT_COMMODITIES);

  const [data, setData] = useState<TrendsData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggleCommodity(name: string) {
    setSelectedCommodities((prev) =>
      prev.includes(name) ? prev.filter((c) => c !== name) : [...prev, name],
    );
  }

  async function handleRefresh() {
    if (selectedCommodities.length === 0) return;

    setLoading(true);
    setError(null);

    const params = new URLSearchParams();
    selectedCommodities.forEach((c) => params.append("commodities", c));
    params.set("timeframe", timeframe);
    params.set("geo", geo.trim().toUpperCase());

    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_URL}/api/trends?${params}`,
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? "Failed to fetch trends data");
      }
      const json: TrendsData = await res.json();
      setData(json);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-8 max-w-5xl mx-auto">
      <div>
        <h1 className="text-2xl font-extrabold text-white mb-1">
          Commodities Sentiment
        </h1>
        <p className="text-sm text-neutral-500">
          Google Trends retail interest across commodities
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-4">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-neutral-400">Time range</label>
          <select
            value={timeframe}
            onChange={(e) => setTimeframe(e.target.value)}
            className="rounded-md bg-neutral-800 px-3 py-2 text-sm text-neutral-100 outline-none focus:ring-1 focus:ring-neutral-600"
          >
            {TIMEFRAMES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-neutral-400">
            Geo{" "}
            <span className="text-neutral-600">(country code, optional)</span>
          </label>
          <input
            type="text"
            value={geo}
            onChange={(e) => setGeo(e.target.value)}
            placeholder="e.g. US"
            maxLength={2}
            className="w-24 rounded-md bg-neutral-800 px-3 py-2 text-sm text-neutral-100 placeholder-neutral-500 outline-none focus:ring-1 focus:ring-neutral-600"
          />
        </div>

        <button
          onClick={handleRefresh}
          disabled={loading || selectedCommodities.length === 0}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>

      {/* Commodity toggles */}
      <div className="flex flex-wrap gap-2">
        {ALL_COMMODITIES.map((name) => {
          const active = selectedCommodities.includes(name);
          return (
            <button
              key={name}
              onClick={() => toggleCommodity(name)}
              style={active ? { borderColor: COLOR_MAP[name] } : undefined}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                active
                  ? "text-white"
                  : "border-neutral-700 text-neutral-500 hover:border-neutral-500 hover:text-neutral-300"
              }`}
            >
              {name}
            </button>
          );
        })}
      </div>

      {selectedCommodities.length === 0 && (
        <p className="text-sm text-yellow-500 text-center">
          Select at least one commodity, then press Refresh
        </p>
      )}

      {error && <p className="text-sm text-red-400 text-center">{error}</p>}

      {data && !loading && (
        <>
          {/* Interest panel */}
          {data.latest.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-neutral-400 uppercase tracking-wide mb-4">
                Current Interest Levels
              </h2>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
                {data.latest.map(({ commodity, interest, momentum }) => {
                  const deltaClass =
                    momentum === null || momentum === 0
                      ? "text-neutral-500"
                      : momentum > 0
                        ? "text-green-500"
                        : "text-red-500";
                  const deltaText =
                    momentum === null
                      ? "0.0"
                      : momentum >= 0
                        ? `+${momentum.toFixed(1)}`
                        : momentum.toFixed(1);
                  return (
                    <div
                      key={commodity}
                      className="flex flex-col items-center rounded-md bg-neutral-800 px-4 py-4 gap-1"
                    >
                      <span
                        className="text-sm font-semibold text-neutral-300"
                        style={{ color: COLOR_MAP[commodity] }}
                      >
                        {commodity}
                      </span>
                      <div className="flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-white">
                          {interest}
                        </span>
                        <span className={`text-xs font-semibold ${deltaClass}`}>
                          {deltaText}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Line chart */}
          {data.series.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-neutral-400 uppercase tracking-wide mb-4">
                Interest Over Time
              </h2>
              <ResponsiveContainer width="100%" height={360}>
                <LineChart
                  data={data.series}
                  margin={{ top: 4, right: 16, left: 0, bottom: 4 }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="#2a2a2a"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: "#737373", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v: string) => v.slice(0, 7)}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    domain={[0, 100]}
                    tick={{ fill: "#737373", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    width={28}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1a1a1a",
                      border: "1px solid #333",
                      borderRadius: "6px",
                      fontSize: "12px",
                    }}
                    labelStyle={{ color: "#a3a3a3" }}
                  />
                  <Legend
                    wrapperStyle={{ fontSize: "12px", paddingTop: "16px" }}
                  />
                  {selectedCommodities.map((name) => (
                    <Line
                      key={name}
                      type="monotone"
                      dataKey={name}
                      stroke={COLOR_MAP[name]}
                      dot={false}
                      strokeWidth={2}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {data.series.length === 0 && (
            <p className="text-sm text-neutral-500 text-center">
              No trend data returned for the selected settings
            </p>
          )}
        </>
      )}

      <p className="text-xs text-neutral-600">
        Google Trends values are normalized (0–100) relative to the selected
        timeframe and comparison set
      </p>
    </div>
  );
}
