"use client";

import { useEffect, useRef, useState } from "react";
import type { ColumnDef } from "./PositionsTable";

interface Props {
  columns: ColumnDef[];
  visibleColumns: string[];
  onChange: (visibleColumns: string[]) => void;
}

export default function ColumnsPopover({
  columns,
  visibleColumns,
  onChange,
}: Props) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  const visSet = new Set(visibleColumns);
  const hiddenCount = columns.length - visibleColumns.length;

  function toggle(key: string) {
    const next = visSet.has(key)
      ? visibleColumns.filter((k) => k !== key)
      : [...visibleColumns, key];
    onChange(next);
  }

  const buttonLabel =
    hiddenCount > 0 ? `Columns · ${hiddenCount} hidden` : "Columns";

  return (
    <div ref={containerRef} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className={`rounded-md border border-neutral-700 px-3 py-2 text-sm font-medium transition-colors ${
          open
            ? "bg-neutral-700 text-white"
            : "text-neutral-400 hover:text-neutral-200"
        }`}
      >
        {buttonLabel}
      </button>

      {open && (
        <div className="absolute right-0 top-full z-10 mt-1 w-48 rounded-lg border border-neutral-700 bg-neutral-900 py-1 shadow-lg">
          {columns.map(({ key, label }) => (
            <label
              key={key}
              className="flex cursor-pointer items-center gap-2 px-3 py-2 text-sm text-neutral-300 hover:bg-neutral-800"
            >
              <input
                type="checkbox"
                checked={visSet.has(key)}
                onChange={() => toggle(key)}
                className="accent-blue-400"
              />
              {label}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
