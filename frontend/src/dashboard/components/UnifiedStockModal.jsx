import { useEffect, useState } from "react";

export default function UnifiedStockModal({ entryResult, exitResult, onClose, mode }) {
  const [activeTab, setActiveTab] = useState("entry");

  useEffect(() => {
    if (mode === "entry" || mode === "exit") {
      setActiveTab(mode);
    }
  }, [mode]);

  if (!entryResult || entryResult.error) return null;

  const suggestionColor = entryResult.suggestion === "buy" ? "text-green-600" : "text-red-600";
  const recommendationColor = exitResult?.recommendation === "EXIT" ? "text-red-600" : "text-green-600";

  return (
    <div className="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50">
      <div className="bg-white p-6 rounded-lg shadow-lg w-full max-w-md space-y-4">
        <h2 className="text-xl font-bold text-gray-800">{entryResult.symbol}</h2>

        {mode === "both" && (
          <div className="flex space-x-4 border-b pb-2">
            <button
              onClick={() => setActiveTab("entry")}
              className={`px-3 py-1 rounded ${activeTab === "entry" ? "bg-blue-500 text-white" : "bg-gray-200"}`}
            >
              Entry Score
            </button>
            <button
              onClick={() => setActiveTab("exit")}
              className={`px-3 py-1 rounded ${activeTab === "exit" ? "bg-blue-500 text-white" : "bg-gray-200"}`}
            >
              Exit Recommendation
            </button>
          </div>
        )}

        {activeTab === "entry" && (
          <div className="space-y-1">
            <p>Score: <strong>{entryResult.score}</strong></p>
            <p className={suggestionColor}>Suggestion: {entryResult.suggestion.toUpperCase()}</p>
            <p>Close Price: ₹{entryResult.close}</p>
            <p>Volume: {typeof entryResult.volume === "number" ? entryResult.volume.toLocaleString() : "N/A"}</p>
          </div>
        )}

        {activeTab === "exit" && (
          <div className="space-y-1">
            {exitResult ? (
              <>
                <p>Entry Price: ₹{exitResult.entry_price}</p>
                <p>Current Price: ₹{exitResult.current_price}</p>
                <p>P&L %: {exitResult.pnl_percent}%</p>
                <p>Days Held: {exitResult.days_held}</p>
                <p className={recommendationColor}>Recommendation: {exitResult.recommendation}</p>
                {exitResult.exit_reasons?.length > 0 && (
                  <div>
                    <p>Reasons:</p>
                    <ul className="list-disc list-inside text-sm">
                      {exitResult.exit_reasons.map((r, i) => (
                        <li key={i}>{r}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            ) : (
              <p className="text-gray-500 italic">No exit result available.</p>
            )}
          </div>
        )}

        <div className="flex justify-end pt-4">
          <button
            className="bg-gray-300 text-gray-800 px-3 py-1 rounded hover:bg-gray-400"
            onClick={onClose}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
