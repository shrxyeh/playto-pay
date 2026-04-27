import { useEffect, useState, useCallback } from "react";
import { fetchBalance, addCredit } from "../api/client";
import PayoutForm from "./PayoutForm";
import PayoutHistory from "./PayoutHistory";
import LedgerHistory from "./LedgerHistory";

const POLL_INTERVAL_MS = 5000; // live refresh every 5 s

function paise(p) {
  return `₹${(p / 100).toFixed(2)}`;
}

export default function Dashboard({ merchantId }) {
  const [balance, setBalance] = useState(null);
  const [error, setError] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);

  // Fetch balance on mount and every poll interval
  useEffect(() => {
    if (!merchantId) return;

    function load() {
      fetchBalance(merchantId)
        .then(setBalance)
        .catch((e) => setError(e.message));
    }

    load();
    const timer = setInterval(load, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [merchantId, refreshKey]);

  // Also poll payout list so status updates appear without manual refresh
  useEffect(() => {
    if (!merchantId) return;
    const timer = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [merchantId, refresh]);

  async function handleAddCredit() {
    const amount = prompt("Enter credit amount in paise (e.g. 100000 for ₹1000):");
    if (!amount || isNaN(+amount)) return;
    await addCredit(merchantId, parseInt(amount));
    refresh();
  }

  if (!merchantId)
    return <p className="text-gray-500 mt-8 text-center">Enter a merchant ID to begin.</p>;
  if (error)
    return <p className="text-red-500 mt-8 text-center">{error}</p>;
  if (!balance)
    return <p className="text-gray-400 mt-8 text-center">Loading...</p>;

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-8">
      {/* Balance cards */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white border rounded-xl p-5 shadow-sm">
          <p className="text-sm text-gray-500">Available Balance</p>
          <p className="text-3xl font-bold text-green-600 mt-1">
            {paise(balance.available_paise)}
          </p>
        </div>
        <div className="bg-white border rounded-xl p-5 shadow-sm">
          <p className="text-sm text-gray-500">Held (Pending Payouts)</p>
          <p className="text-3xl font-bold text-yellow-500 mt-1">
            {paise(balance.held_paise)}
          </p>
        </div>
      </div>

      <button onClick={handleAddCredit} className="text-sm text-blue-600 underline">
        + Add test credit
      </button>

      <PayoutForm merchantId={merchantId} onSuccess={refresh} />
      <PayoutHistory merchantId={merchantId} refreshKey={refreshKey} />
      <LedgerHistory merchantId={merchantId} refreshKey={refreshKey} />
    </div>
  );
}
