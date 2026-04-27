import { useEffect, useState } from "react";
import { fetchLedger } from "../api/client";

const TYPE_LABEL = {
  credit: { label: "Credit", color: "text-green-600" },
  payout_hold: { label: "Hold", color: "text-yellow-600" },
  payout_debit: { label: "Debit", color: "text-red-600" },
  payout_refund: { label: "Refund", color: "text-blue-600" },
};

function paise(p) {
  const sign = p >= 0 ? "+" : "";
  return `${sign}₹${(Math.abs(p) / 100).toFixed(2)}`;
}

export default function LedgerHistory({ merchantId, refreshKey }) {
  const [entries, setEntries] = useState([]);

  useEffect(() => {
    if (!merchantId) return;
    fetchLedger(merchantId).then(setEntries).catch(() => {});
  }, [merchantId, refreshKey]);

  if (!entries.length)
    return <p className="text-gray-400 text-sm">No ledger activity yet.</p>;

  return (
    <div>
      <h2 className="text-lg font-semibold mb-3">Recent Activity</h2>
      <div className="space-y-1.5">
        {entries.map((e) => {
          const meta = TYPE_LABEL[e.entry_type] || { label: e.entry_type, color: "text-gray-600" };
          return (
            <div
              key={e.id}
              className="bg-white border rounded-lg px-4 py-2.5 flex items-center justify-between text-sm shadow-sm"
            >
              <div>
                <span className={`font-medium ${meta.color}`}>{meta.label}</span>
                {e.reference_id && (
                  <span className="ml-2 font-mono text-xs text-gray-400">
                    ref: {e.reference_id.slice(0, 8)}…
                  </span>
                )}
                <p className="text-gray-400 text-xs mt-0.5">
                  {new Date(e.created_at).toLocaleString()}
                </p>
              </div>
              <span className={`font-semibold ${e.amount >= 0 ? "text-green-600" : "text-red-500"}`}>
                {paise(e.amount)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
