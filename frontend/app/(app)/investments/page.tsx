"use client";

import { useAuth } from "@clerk/nextjs";
import { useCallback, useEffect, useState } from "react";
import CsvDropzone from "@/components/investments/CsvDropzone";
import PositionsTable, {
  type Position,
} from "@/components/investments/PositionsTable";
import TransactionsTable, {
  type Transaction,
} from "@/components/investments/TransactionsTable";

type View = "positions" | "transactions";

export default function InvestmentsPage() {
  const { userId } = useAuth();

  const [positions, setPositions] = useState<Position[] | null>(null);
  const [transactions, setTransactions] = useState<Transaction[] | null>(null);
  const [view, setView] = useState<View>("positions");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasData, setHasData] = useState(false);

  const load = useCallback(async () => {
    if (!userId) return;

    setLoading(true);
    setError(null);

    try {
      const headers = { "X-User-Id": userId };
      const base = process.env.NEXT_PUBLIC_BACKEND_URL;

      const [posRes, txnRes] = await Promise.all([
        fetch(`${base}/api/investments/positions`, { headers }),
        fetch(`${base}/api/investments/transactions`, { headers }),
      ]);

      if (!posRes.ok || !txnRes.ok) {
        throw new Error("Failed to load investments data");
      }

      const posData: Position[] = await posRes.json();
      const txnData: Transaction[] = await txnRes.json();

      setPositions(posData);
      setTransactions(txnData);
      setHasData(txnData.length > 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    load();
  }, [load]);

  function handleUpload() {
    load();
  }

  return (
    <div className="flex flex-col gap-8 max-w-6xl mx-auto">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-white mb-1">
            Investments
          </h1>
          <p className="text-sm text-neutral-500">
            Upload your Wealthsimple activities export to track your portfolio
          </p>
        </div>
        {hasData && userId && (
          <CsvDropzone userId={userId} onUpload={handleUpload} />
        )}
      </div>

      {loading && (
        <div className="flex justify-center py-16">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-neutral-700 border-t-blue-400" />
        </div>
      )}

      {error && !loading && (
        <p className="text-center text-sm text-red-400">{error}</p>
      )}

      {!loading && !hasData && userId && (
        <CsvDropzone userId={userId} onUpload={handleUpload} />
      )}

      {!loading && hasData && positions !== null && transactions !== null && (
        <>
          <div className="flex gap-2">
            <button
              onClick={() => setView("positions")}
              className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
                view === "positions"
                  ? "bg-neutral-700 text-white"
                  : "text-neutral-400 hover:text-neutral-200"
              }`}
            >
              Positions
            </button>
            <button
              onClick={() => setView("transactions")}
              className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
                view === "transactions"
                  ? "bg-neutral-700 text-white"
                  : "text-neutral-400 hover:text-neutral-200"
              }`}
            >
              All Transactions
            </button>
          </div>

          {view === "positions" && <PositionsTable positions={positions} />}
          {view === "transactions" && (
            <TransactionsTable transactions={transactions} />
          )}
        </>
      )}
    </div>
  );
}
