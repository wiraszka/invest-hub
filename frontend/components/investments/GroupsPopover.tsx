"use client";

import { useEffect, useRef, useState } from "react";

interface Props {
  groupingLabels: string[];
  onAdd: (name: string) => void;
  onRemove: (name: string) => void;
}

export default function GroupsPopover({
  groupingLabels,
  onAdd,
  onRemove,
}: Props) {
  const [open, setOpen] = useState(false);
  const [inputValue, setInputValue] = useState("");
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

  function handleAdd() {
    const name = inputValue.trim();
    if (!name || groupingLabels.includes(name)) return;
    onAdd(name);
    setInputValue("");
  }

  const buttonLabel =
    groupingLabels.length > 0 ? `Groups · ${groupingLabels.length}` : "Groups";

  return (
    <div ref={containerRef} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className={`rounded-md px-3 py-2 text-sm font-medium transition-colors ${
          open
            ? "bg-neutral-700 text-white"
            : "text-neutral-400 hover:text-neutral-200"
        }`}
      >
        {buttonLabel}
      </button>

      {open && (
        <div className="absolute right-0 top-full z-10 mt-1 w-56 rounded-lg border border-neutral-700 bg-neutral-900 shadow-lg">
          {groupingLabels.length > 0 && (
            <ul className="border-b border-neutral-800 py-1">
              {groupingLabels.map((g) => (
                <li
                  key={g}
                  className="flex items-center justify-between px-3 py-2 text-sm text-neutral-300"
                >
                  <span>{g}</span>
                  <button
                    onClick={() => onRemove(g)}
                    className="text-neutral-600 transition-colors hover:text-neutral-300"
                    aria-label={`Remove ${g}`}
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}

          <div className="flex gap-2 p-2">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAdd()}
              placeholder="New group…"
              className="min-w-0 flex-1 rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1.5 text-sm text-neutral-200 outline-none placeholder:text-neutral-600 focus:border-neutral-500"
            />
            <button
              onClick={handleAdd}
              disabled={
                !inputValue.trim() || groupingLabels.includes(inputValue.trim())
              }
              className="rounded-md bg-neutral-700 px-2 py-1.5 text-sm font-medium text-neutral-200 transition-colors hover:bg-neutral-600 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Add
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
