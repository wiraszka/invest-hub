"use client";

import { useEffect, useState } from "react";
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

interface State {
  price: number | null;
  history: PricePoint[];
  error: string | null;
  loading: boolean;
}

const INITIAL_STATE: State = {
  price: null,
  history: [],
  error: null,
  loading: true,
};

interface Props {
  ticker: string;
}

export default function PriceSection({ ticker }: Props) {
  const [state, setState] = useState<State>(INITIAL_STATE);

  useEffect(() => {
    let cancelled = false;
    const base = process.env.NEXT_PUBLIC_BACKEND_URL;

    Promise.all([
      fetch(`${base}/api/price/${ticker}`).then((r) => r.json()),
      fetch(`${base}/api/price/${ticker}/history`).then((r) => r.json()),
    ])
      .then(([priceData, historyData]) => {
        if (cancelled) return;
        if (priceData.price === undefined) {
          setState((s) => ({
            ...s,
            error: priceData.detail ?? "Failed to load price",
            loading: false,
          }));
        } else {
          setState((s) => ({
            ...s,
            price: priceData.price,
            history: historyData.history ?? [],
            loading: false,
          }));
        }
      })
      .catch(() => {
        if (!cancelled) {
          setState((s) => ({
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

  if (state.loading) {
    return (
      <div className="mb-8">
        <div className="h-8 w-48 bg-neutral-800 rounded animate-pulse mb-2" />
        <div className="h-6 w-24 bg-neutral-800 rounded animate-pulse mb-6" />
        <div className="h-64 bg-neutral-800 rounded animate-pulse" />
      </div>
    );
  }

  if (state.error) {
    return <div className="mb-8 text-center text-red-400">{state.error}</div>;
  }

  return (
    <div className="mb-8">
      <h1 className="text-3xl font-bold text-white mb-1">{ticker}</h1>
      {state.price !== null && (
        <p className="text-2xl font-semibold text-neutral-300 mb-6">
          ${state.price.toFixed(2)}{" "}
          <span className="text-sm text-neutral-500">USD</span>
        </p>
      )}
      {state.history.length > 0 && (
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={state.history}>
            <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
            <XAxis
              dataKey="date"
              tick={{ fill: "#737373", fontSize: 11 }}
              tickFormatter={(v) => v.slice(5)}
              interval={Math.floor(state.history.length / 6)}
            />
            <YAxis
              tick={{ fill: "#737373", fontSize: 11 }}
              domain={["auto", "auto"]}
              tickFormatter={(v) => `$${v}`}
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
      )}
    </div>
  );
}
