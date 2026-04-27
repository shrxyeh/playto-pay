import { useState } from "react";
import { createPayout } from "../api/client";

export default function PayoutForm({ merchantId, onSuccess }) {
  const [amountRupees, setAmountRupees] = useState("");
  const [bankAccountId, setBankAccountId] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setMessage(null);

    const amountPaise = Math.round(parseFloat(amountRupees) * 100);
    if (!amountPaise || amountPaise <= 0) {
      setMessage({ type: "error", text: "Enter a valid amount." });
      return;
    }

    setLoading(true);
    try {
      const result = await createPayout(merchantId, amountPaise, bankAccountId);
      setMessage({ type: "success", text: `Payout queued: ${result.id}` });
      setAmountRupees("");
      setBankAccountId("");
      onSuccess();
    } catch (err) {
      const detail = err?.data?.detail || err?.data?.error || err.message;
      setMessage({ type: "error", text: detail });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-white border rounded-xl p-5 shadow-sm">
      <h2 className="text-lg font-semibold mb-4">Request Payout</h2>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label className="block text-sm text-gray-600 mb-1">Amount (₹)</label>
          <input
            type="number"
            min="0.01"
            step="0.01"
            value={amountRupees}
            onChange={(e) => setAmountRupees(e.target.value)}
            className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            placeholder="e.g. 500.00"
            required
          />
        </div>
        <div>
          <label className="block text-sm text-gray-600 mb-1">Bank Account ID</label>
          <input
            type="text"
            value={bankAccountId}
            onChange={(e) => setBankAccountId(e.target.value)}
            className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            placeholder="e.g. HDFC-0001"
            required
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 text-white rounded-lg py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Processing..." : "Request Payout"}
        </button>
        {message && (
          <p
            className={`text-sm mt-1 ${
              message.type === "error" ? "text-red-500" : "text-green-600"
            }`}
          >
            {message.text}
          </p>
        )}
      </form>
    </div>
  );
}
