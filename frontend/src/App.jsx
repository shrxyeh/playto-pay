import { useState } from "react";
import Dashboard from "./components/Dashboard";

export default function App() {
  const [merchantIdInput, setMerchantIdInput] = useState("");
  const [activeMerchantId, setActiveMerchantId] = useState(null);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b px-6 py-4 flex items-center gap-4">
        <h1 className="text-xl font-bold text-gray-800">Payout Engine</h1>
        <div className="flex items-center gap-2 ml-auto">
          <input
            value={merchantIdInput}
            onChange={(e) => setMerchantIdInput(e.target.value)}
            placeholder="Merchant UUID"
            className="border rounded-lg px-3 py-1.5 text-sm w-72 focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
          <button
            onClick={() => setActiveMerchantId(merchantIdInput.trim())}
            className="bg-blue-600 text-white text-sm rounded-lg px-3 py-1.5 hover:bg-blue-700"
          >
            Load
          </button>
        </div>
      </header>

      <main>
        <Dashboard merchantId={activeMerchantId} />
      </main>
    </div>
  );
}
