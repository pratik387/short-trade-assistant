export default function SuggestionTable({ stocks, portfolio, handleTrack }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full border-collapse border border-gray-300">
        <thead>
          <tr className="bg-gray-100">
            <th className="border px-2 py-1">Symbol</th>
            <th className="border px-2 py-1">ADX</th>
            <th className="border px-2 py-1">DMP</th>
            <th className="border px-2 py-1">DMN</th>
            <th className="border px-2 py-1">RSI</th>
            <th className="border px-2 py-1">MACD</th>
            <th className="border px-2 py-1">MACD Signal</th>
            <th className="border px-2 py-1">%B</th>
            <th className="border px-2 py-1">Volume</th>
            <th className="border px-2 py-1">Close</th>
            <th className="border px-2 py-1">Score</th>
            <th className="border px-2 py-1">Action</th>
          </tr>
        </thead>
        <tbody>
          {stocks.length === 0 ? (
            <tr>
              <td colSpan={12} className="text-center py-4 text-gray-500">
                No suggestions available. Click "🔄 Refresh Suggestions" to load.
              </td>
            </tr>
          ) : (
            stocks.map((stock) => (
              <tr key={stock.symbol} className="hover:bg-gray-50">
                <td className="border px-2 py-1">{stock.symbol}</td>
                <td className="border px-2 py-1">{stock.adx}</td>
                <td className="border px-2 py-1">{stock.dmp}</td>
                <td className="border px-2 py-1">{stock.dmn}</td>
                <td className="border px-2 py-1">{stock.rsi}</td>
                <td className="border px-2 py-1">{stock.macd}</td>
                <td className="border px-2 py-1">{stock.macd_signal}</td>
                <td className="border px-2 py-1">{stock.bb}</td>
                <td className="border px-2 py-1">{stock.volume}</td>
                <td className="border px-2 py-1">{stock.close}</td>
                <td className="border px-2 py-1">{stock.score}</td>
                <td className="border px-2 py-1">
                  <button
                    className={`font-medium py-1 px-2 rounded ${
                      portfolio.includes(stock.symbol)
                        ? "bg-gray-200 text-gray-500 cursor-not-allowed"
                        : "bg-green-200 hover:bg-green-300 text-green-800"
                    }`}
                    onClick={() => handleTrack(stock)}
                    disabled={portfolio.includes(stock.symbol)}
                  >
                    {portfolio.includes(stock.symbol) ? "Tracked" : "Track"}
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
