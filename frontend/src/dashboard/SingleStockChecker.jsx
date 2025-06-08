export default function SingleStockChecker({ checkSymbol, setCheckSymbol, handleCheckScore }) {
  return (
    <div className="bg-white border p-4 rounded shadow space-y-2">
      <h2 className="text-lg font-semibold">Check Single Stock Score</h2>
      <div className="flex items-center space-x-2">
        <input
          type="text"
          value={checkSymbol}
          onChange={(e) => setCheckSymbol(e.target.value)}
          placeholder="Enter stock symbol (e.g., IEX)"
          className="border px-2 py-1 rounded"
        />
        <button
          onClick={handleCheckScore}
          className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-1 rounded"
        >
          Check Score
        </button>
      </div>
    </div>
  );
}
