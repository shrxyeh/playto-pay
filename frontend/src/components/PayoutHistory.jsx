import { useEffect, useState } from "react";
import { fetchPayouts } from "../api/client";

const STATUS_STYLES = {
  pending: "bg-yellow-100 text-yellow-800",
  processing: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

function paise(p) {
  return `₹${(p / 100).toFixed(2)}`;
}

export default function PayoutHistory({ merchantId, refreshKey }) {
  const [payouts, setPayouts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!merchantId) return;
    setLoading(true);
    fetchPayouts(merchantId)
      .then(setPayouts)
      .finally(() => setLoading(false));
  }, [merchantId, refreshKey]);

  if (loading) return <p className="text-gray-400 text-sm">Loading history...</p>;
  if (!payouts.length)
    return <p className="text-gray-400 text-sm">No payouts yet.</p>;

  return (
    <div>
      <h2 className="text-lg font-semibold mb-3">Payout History</h2>
      <div className="space-y-2">
        {payouts.map((p) => (
          <div
            key={p.id}
            className="bg-white border rounded-lg px-4 py-3 flex items-center justify-between text-sm shadow-sm"
          >
            <div>
              <p className="font-mono text-xs text-gray-400">{p.id}</p>
              <p className="text-gray-700 mt-0.5">
                {paise(p.amount_paise)} → {p.bank_account_id}
              </p>
              <p className="text-gray-400 text-xs mt-0.5">
                {new Date(p.created_at).toLocaleString()}
              </p>
            </div>
            <span
              className={`px-2 py-1 rounded-full text-xs font-medium ${
                STATUS_STYLES[p.status] || "bg-gray-100 text-gray-600"
              }`}
            >
              {p.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
