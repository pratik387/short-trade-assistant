export default function SuggestionTable({ stocks, portfolio, handleTrack }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm text-left border">
        <thead className="bg-gray-200 text-xs uppercase font-semibold">
          <tr>
            <th className="px-2 py-1">Symbol</th>
            <th className="px-2 py-1">ADX</th>
            <th className="px-2 py-1">DMP</th>
            <th className="px-2 py-1">DMN</th>
            <th className="px-2 py-1">RSI</th>
            <th className="px-2 py-1">MACD</th>
            <th className="px-2 py-1">Signal</th>
            <th className="px-2 py-1">%B</th>
            <th className="px-2 py-1">OBV</th>
            <th className="px-2 py-1">ATR</th>
            <th className="px-2 py-1">Volume</th>
            <th className="px-2 py-1">Close</th>
            <th className="px-2 py-1">Score</th>
            <th className="px-2 py-1">Action</th>
          </tr>
        </thead>
        <tbody>
          {stocks.map((stock, index) => (
            <tr key={index} className="border-t">
              <td className="px-2 py-1 font-medium">{stock.symbol}</td>
              <td className="px-2 py-1">{stock.adx}</td>
              <td className="px-2 py-1">{stock.dmp}</td>
              <td className="px-2 py-1">{stock.dmn}</td>
              <td className="px-2 py-1">{stock.rsi}</td>
              <td className="px-2 py-1">{stock.macd}</td>
              <td className="px-2 py-1">{stock.macd_signal}</td>
              <td className="px-2 py-1">{stock.bb}</td>
              <td className="px-2 py-1">{stock.obv}</td>
              <td className="px-2 py-1">{stock.atr}</td>
              <td className="px-2 py-1">{stock.volume}</td>
              <td className="px-2 py-1">{stock.close}</td>
              <td className="px-2 py-1">{stock.score}</td>
              <td className="px-2 py-1">
                {!portfolio.includes(stock.symbol) && (
                  <button
                    className="bg-blue-500 hover:bg-blue-600 text-white px-2 py-1 rounded text-xs"
                    onClick={() => handleTrack(stock)}
                  >
                    Track
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
