"use client";

import { useEffect, useRef, useState } from "react";

interface SearchResult {
  ticker: string;
  name: string;
  cik: string;
}

interface Props {
  onSelect: (ticker: string) => void;
}

export default function ResearchSearchBar({ onSelect }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length === 0) {
      setResults([]);
      setOpen(false);
      return;
    }

    const timeout = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_BACKEND_URL}/api/search?q=${encodeURIComponent(trimmed)}`,
        );
        if (res.ok) {
          const data: SearchResult[] = await res.json();
          setResults(data);
          setOpen(data.length > 0);
        }
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 250);

    return () => clearTimeout(timeout);
  }, [query]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function handleSelect(result: SearchResult) {
    setQuery("");
    setResults([]);
    setOpen(false);
    onSelect(result.ticker);
  }

  return (
    <div ref={containerRef} className="relative w-full">
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search ticker or company name..."
          className="flex-1 rounded-md bg-neutral-800 px-4 py-3 text-sm text-neutral-100 placeholder-neutral-500 outline-none focus:ring-1 focus:ring-neutral-600"
        />
        {loading && (
          <span className="text-xs text-neutral-500 shrink-0">
            Searching...
          </span>
        )}
      </div>
      {open && results.length > 0 && (
        <ul
          role="listbox"
          className="absolute z-50 mt-1 w-full overflow-y-auto rounded-md border border-neutral-700 bg-neutral-900 shadow-lg"
          style={{ maxHeight: "calc(5 * 44px)" }}
        >
          {results.map((result) => (
            <li key={result.cik}>
              <button
                onClick={() => handleSelect(result)}
                className="flex w-full items-baseline gap-2 px-4 py-2.5 text-left text-sm hover:bg-neutral-800"
              >
                <span className="font-semibold text-neutral-100">
                  {result.ticker}
                </span>
                <span className="truncate text-neutral-400">{result.name}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
