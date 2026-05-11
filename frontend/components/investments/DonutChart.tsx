"use client";

import { useEffect, useRef, useState } from "react";
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
  titleOptions?: string[];
  selectedOption?: string;
  onOptionChange?: (opt: string) => void;
}

function fmt(value: number): string {
  return value.toLocaleString("en-CA", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
}

interface TooltipPayloadItem {
  name: string;
  value: number;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  total: number;
}

function CustomTooltip({ active, payload, total }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  const item = payload[0];
  return (
    <div className="rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-xs shadow-lg">
      <p className="font-medium text-neutral-200">{item.name}</p>
      <p className="text-neutral-400">{fmt((item.value / total) * 100)}%</p>
    </div>
  );
}

export default function DonutChart({
  title,
  data,
  ready,
  placeholderText = "Run Analyze to see breakdown",
  titleOptions,
  selectedOption,
  onOptionChange,
}: Props) {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node)
      ) {
        setDropdownOpen(false);
      }
    }
    if (dropdownOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [dropdownOpen]);

  const total = data.reduce((sum, slice) => sum + slice.value, 0);

  const hasOptions = titleOptions && titleOptions.length > 1;

  const titleEl = hasOptions ? (
    <div ref={dropdownRef} className="relative flex w-full items-center">
      <p className="flex-1 text-center text-xs font-semibold uppercase tracking-wider text-neutral-500">
        {title}
      </p>
      <button
        onClick={() => setDropdownOpen((o) => !o)}
        className="text-neutral-600 transition-colors hover:text-neutral-400"
        aria-label="Switch chart type"
      >
        <svg
          width="18"
          height="18"
          viewBox="0 0 18 18"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M5 7L9 11L13 7"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
      {dropdownOpen && (
        <div className="absolute right-0 top-full z-10 mt-1 min-w-max rounded-md border border-neutral-700 bg-neutral-900 py-1 shadow-lg">
          {titleOptions!.map((opt) => (
            <button
              key={opt}
              onClick={() => {
                onOptionChange?.(opt);
                setDropdownOpen(false);
              }}
              className={`block w-full px-3 py-1.5 text-left text-xs transition-colors hover:bg-neutral-800 ${
                opt === selectedOption ? "text-neutral-200" : "text-neutral-500"
              }`}
            >
              {opt}
            </button>
          ))}
        </div>
      )}
    </div>
  ) : (
    <p className="text-xs font-semibold uppercase tracking-wider text-neutral-500">
      {title}
    </p>
  );

  return (
    <div className="flex flex-1 flex-col items-center gap-4 rounded-lg border border-neutral-800 p-6">
      {titleEl}

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
            <Tooltip content={<CustomTooltip total={total} />} />
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
                  {fmt((slice.value / total) * 100)}%
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
