"use client";

import { Cell, Pie, PieChart, Tooltip } from "recharts";

const COLORS = [
  "#60a5fa", // blue-400
  "#34d399", // emerald-400
  "#fbbf24", // amber-400
  "#a78bfa", // violet-400
  "#f87171", // red-400
  "#22d3ee", // cyan-400
  "#fb923c", // orange-400
  "#a3e635", // lime-400
  "#f472b6", // pink-400
  "#818cf8", // indigo-400
  "#2dd4bf", // teal-400
  "#e879f9", // fuchsia-400
];

interface Slice {
  name: string;
  value: number;
}

interface Props {
  title: string;
  data: Slice[];
  ready: boolean;
  placeholderText?: string;
}

function fmt(n: number): string {
  return n.toLocaleString("en-CA", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
}

interface TooltipPayloadItem {
  name: string;
  value: number;
  payload: Slice & { percent: number };
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadItem[];
}

function CustomTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  const item = payload[0];
  return (
    <div className="rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-xs shadow-lg">
      <p className="font-medium text-neutral-200">{item.name}</p>
      <p className="text-neutral-400">{fmt(item.payload.percent * 100)}%</p>
    </div>
  );
}

export default function DonutChart({
  title,
  data,
  ready,
  placeholderText = "Run Analyze to see breakdown",
}: Props) {
  return (
    <div className="flex flex-1 flex-col items-center gap-4 rounded-lg border border-neutral-800 p-6">
      <p className="text-xs font-semibold uppercase tracking-wider text-neutral-500">
        {title}
      </p>

      {ready && data.length > 0 ? (
        <>
          <PieChart width={160} height={160}>
            <Pie
              data={data}
              cx={75}
              cy={75}
              innerRadius={48}
              outerRadius={75}
              dataKey="value"
              strokeWidth={0}
            >
              {data.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
          </PieChart>

          <ul className="w-full space-y-1">
            {data.map((slice, i) => (
              <li key={slice.name} className="flex items-center gap-2 text-xs">
                <span
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ backgroundColor: COLORS[i % COLORS.length] }}
                />
                <span className="min-w-0 truncate text-neutral-400">
                  {slice.name}
                </span>
                <span className="ml-auto shrink-0 text-neutral-300">
                  {fmt(
                    (slice.value / data.reduce((s, d) => s + d.value, 0)) * 100,
                  )}
                  %
                </span>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <div className="flex flex-1 items-center justify-center">
          <p className="text-center text-xs text-neutral-600">
            {placeholderText}
          </p>
        </div>
      )}
    </div>
  );
}
