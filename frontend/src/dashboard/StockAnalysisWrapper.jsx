import { useState } from "react";
import axios from "axios";
import UnifiedStockModal from "./components/UnifiedStockModal";

export default function UnifiedStockChecker() {
  const [symbol, setSymbol] = useState("");
  const [entryResult, setEntryResult] = useState(null);
  const [exitResult, setExitResult] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [entryPrice, setEntryPrice] = useState("");
  const [entryTime, setEntryTime] = useState("");
  const [mode, setMode] = useState("entry");
  const [loading, setLoading] = useState(false);

  const handleAnalyze = async () => {
    if (!symbol || (mode === "exit" && (!entryPrice || !entryTime))) return;
    setLoading(true);
    try {
      let entryRes = null;
      let exitRes = null;

      if (mode === "entry") {
        entryRes = await axios.get(`/api/stock-score/${symbol}`);
      } else {
        [entryRes, exitRes] = await Promise.all([
          axios.get(`/api/stock-score/${symbol}`),
          axios.post("/api/check-exit", {
            symbol,
            entry_price: parseFloat(entryPrice),
            entry_time: new Date(entryTime).toISOString()
          })
        ]);
      }

      setEntryResult(entryRes?.data || null);
      setExitResult(exitRes?.data || null);
      setShowModal(true);
    } catch (err) {
      console.error("Error fetching stock data", err);
      alert("Failed to fetch data for the symbol");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white border p-4 rounded shadow space-y-3">
      <h2 className="text-lg font-semibold">Stock Analysis</h2>
      <div className="flex space-x-2 pb-2">
        <button
          className={`px-3 py-1 rounded ${mode === "entry" ? "bg-blue-500 text-white" : "bg-gray-200"}`}
          onClick={() => setMode("entry")}
        >
          Entry Check
        </button>
        <button
          className={`px-3 py-1 rounded ${mode === "exit" ? "bg-blue-500 text-white" : "bg-gray-200"}`}
          onClick={() => setMode("exit")}
        >
          Exit Check
        </button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        <input
          type="text"
          placeholder="Stock symbol (e.g. INFY.NS)"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          className="border p-2 rounded"
        />
        {mode === "exit" && (
          <>
            <input
              type="number"
              placeholder="Entry Price"
              value={entryPrice}
              onChange={(e) => setEntryPrice(e.target.value)}
              className="border p-2 rounded"
            />
            <input
              type="datetime-local"
              value={entryTime}
              onChange={(e) => setEntryTime(e.target.value)}
              className="border p-2 rounded col-span-2"
            />
          </>
        )}
      </div>
      <button
        className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
        onClick={handleAnalyze}
        disabled={loading}
      >
        {loading ? "Analyzing..." : "Analyze Stock"}
      </button>

      {showModal && entryResult && (
        <UnifiedStockModal
          entryResult={entryResult}
          exitResult={exitResult}
          mode={mode}
          onClose={() => setShowModal(false)}
        />
      )}
    </div>
  );
}
