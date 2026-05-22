"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { UserButton } from "@clerk/nextjs";

const NAV_ITEMS = [
  { label: "HOME", href: "/" },
  { label: "RESEARCH", href: "/research" },
  { label: "INVESTMENTS", href: "/investments" },
  { label: "SHORTLIST", href: "/shortlist" },
  { label: "COMMODITIES SENTIMENT", href: "/commodities-sentiment" },
];

interface SearchResult {
  ticker: string;
  name: string;
}

function SymbolSearch() {
  const router = useRouter();
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
          `${process.env.NEXT_PUBLIC_BACKEND_URL}/api/v1/search?q=${encodeURIComponent(trimmed)}`,
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
    router.push(`/symbol/${result.ticker}`);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && results.length > 0) {
      handleSelect(results[0]);
    }
  }

  return (
    <div ref={containerRef} className="relative w-full mb-6">
      <div className="flex items-center gap-2 rounded-md bg-neutral-900 border border-neutral-800 px-3 py-2">
        <svg
          className="h-3.5 w-3.5 shrink-0 text-neutral-600"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          viewBox="0 0 24 24"
        >
          <circle cx={11} cy={11} r={8} />
          <path d="m21 21-4.35-4.35" />
        </svg>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Search symbol…"
          className="min-w-0 flex-1 bg-transparent text-xs text-neutral-200 placeholder-neutral-600 outline-none"
        />
        {loading && (
          <div className="h-3 w-3 animate-spin rounded-full border border-neutral-700 border-t-neutral-400 shrink-0" />
        )}
      </div>
      {open && results.length > 0 && (
        <ul
          role="listbox"
          className="absolute left-0 right-0 z-50 mt-1 overflow-y-auto rounded-md border border-neutral-700 bg-neutral-900 shadow-lg"
          style={{ maxHeight: "calc(5 * 40px)" }}
        >
          {results.map((result) => (
            <li key={result.ticker}>
              <button
                onClick={() => handleSelect(result)}
                className="flex w-full items-baseline gap-2 px-3 py-2 text-left text-xs hover:bg-neutral-800"
              >
                <span className="font-semibold text-neutral-100">
                  {result.ticker}
                </span>
                <span className="truncate text-neutral-500">{result.name}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex flex-col w-64 min-h-screen bg-neutral-950 border-r border-neutral-800 px-6 py-8 shrink-0 relative z-10">
      <div className="text-2xl font-extrabold tracking-wide text-white mb-8">
        InvestHub
      </div>

      <SymbolSearch />

      <nav className="flex flex-col gap-1 flex-1">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`px-3 py-2 rounded-md text-sm font-semibold tracking-wide transition-colors ${
                isActive
                  ? "bg-neutral-800 text-white"
                  : "text-neutral-400 hover:text-white hover:bg-neutral-900"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="pt-4 border-t border-neutral-800">
        <UserButton
          appearance={{
            elements: {
              userButtonAvatarBox: "w-8 h-8",
            },
          }}
        />
      </div>
    </aside>
  );
}
