import { useEffect, useState } from "react";
import axios from "axios";

export default function App() {
  const [stocks, setStocks] = useState([]);
  const [portfolio, setPortfolio] = useState(() => {
    const saved = localStorage.getItem("portfolio");
    return saved ? JSON.parse(saved) : [];
  });
  const [exitAlerts, setExitAlerts] = useState([]);
  const [dismissedAlerts, setDismissedAlerts] = useState(() => {
    const saved = localStorage.getItem("dismissedAlerts");
    return saved ? JSON.parse(saved) : [];
  });
  const [autoAlert, setAutoAlert] = useState(() => {
    const saved = localStorage.getItem("autoAlert");
    return saved ? JSON.parse(saved) : true;
  });
  const [refreshInterval, setRefreshInterval] = useState(() => {
    const saved = localStorage.getItem("refreshInterval");
    return saved ? parseInt(saved, 10) : 60000;
  });
  const [error, setError] = useState(null);

  useEffect(() => {
    localStorage.setItem("portfolio", JSON.stringify(portfolio));
    checkExitAlerts();
  }, [portfolio]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await axios.get("http://localhost:8000/api/short-term-suggestions");
        setStocks(res.data);
        if (autoAlert) checkExitAlerts();
      } catch (err) {
        console.error("API fetch error:", err);
        setError("Unable to fetch short-term stock suggestions. Make sure the FastAPI server is running.");
      }
    };

    fetchData();
    const interval = setInterval(fetchData, refreshInterval);
    return () => clearInterval(interval);
  }, [refreshInterval, autoAlert]);

  const handleTrack = (stock) => {
    if (!portfolio.find(item => item.symbol === stock.symbol)) {
      setPortfolio([...portfolio, stock]);
    }
  };

  const handleRemove = (symbol) => {
    const updated = portfolio.filter(item => item.symbol !== symbol);
    setPortfolio(updated);
    localStorage.setItem("portfolio", JSON.stringify(updated));
  };

  const handleDismiss = (symbol) => {
    const updatedDismissed = [...dismissedAlerts, symbol];
    setDismissedAlerts(updatedDismissed);
    localStorage.setItem("dismissedAlerts", JSON.stringify(updatedDismissed));
  };

  const checkExitAlerts = () => {
    const alerts = portfolio.filter(item => {
      const shouldAlert =
        item.macd < 0 ||
        item.rsi < 40 ||
        item.rsi > 75 ||
        item.bb < 0.1 ||
        item.bb > 0.9 ||
        item.adx < 20 ||
        item.close <= item.stop_loss;

      if (shouldAlert && !dismissedAlerts.includes(item.symbol)) {
        axios.post("http://localhost:8000/api/send-exit-email", { symbol: item.symbol })
          .then(() => console.log(`Exit email sent for ${item.symbol}`))
          .catch(err => console.error(`Email error for ${item.symbol}`, err));
      }

      return shouldAlert && !dismissedAlerts.includes(item.symbol);
    });
    setExitAlerts(alerts);
  };

  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold mb-4">Short-Term Transaction Suggestions</h1>
      <div className="mb-4">
        <label className="mr-2 font-semibold">Auto Email Alerts:</label>
        <input type="checkbox" checked={autoAlert} onChange={() => {
          const updatedAlert = !autoAlert;
          setAutoAlert(updatedAlert);
          localStorage.setItem("autoAlert", JSON.stringify(updatedAlert));
        }} className="mr-4" />
        <label className="mr-2 font-semibold">Refresh Interval (seconds):</label>
        <input type="number" value={refreshInterval / 1000} min="15" step="15" onChange={(e) => {
          const interval = Number(e.target.value) * 1000;
          setRefreshInterval(interval);
          localStorage.setItem("refreshInterval", interval.toString());
        }} className="border p-1 w-16" />
      </div>
      {error ? (
        <div className="text-red-500 mb-4">{error}</div>
      ) : (
        <>
          <table className="table-auto w-full border mb-8">
            <thead>
              <tr className="bg-gray-200">
                <th className="p-2 border">Symbol</th>
                <th className="p-2 border">ADX</th>
                <th className="p-2 border">RSI</th>
                <th className="p-2 border">MACD</th>
                <th className="p-2 border">BB %B</th>
                <th className="p-2 border">Volume</th>
                <th className="p-2 border">Close</th>
                <th className="p-2 border">Stop Loss</th>
                <th className="p-2 border">Action</th>
              </tr>
            </thead>
            <tbody>
              {stocks.map(stock => (
                <tr key={stock.symbol} className="text-center">
                  <td className="p-2 border">{stock.symbol}</td>
                  <td className="p-2 border">{stock.adx}</td>
                  <td className="p-2 border">{stock.rsi}</td>
                  <td className="p-2 border">{stock.macd}</td>
                  <td className="p-2 border">{stock.bb}</td>
                  <td className="p-2 border">{stock.volume}</td>
                  <td className="p-2 border">{stock.close}</td>
                  <td className="p-2 border">{stock.stop_loss}</td>
                  <td className="p-2 border">
                    <button onClick={() => handleTrack(stock)} className="bg-blue-500 text-white px-2 py-1 rounded">
                      Track
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {portfolio.length > 0 && (
            <div>
              <h2 className="text-xl font-semibold mb-2">My Portfolio (Active Trades)</h2>
              <table className="table-auto w-full border mb-4">
                <thead>
                  <tr className="bg-gray-200">
                    <th className="p-2 border">Symbol</th>
                    <th className="p-2 border">Entry</th>
                    <th className="p-2 border">Stop Loss</th>
                    <th className="p-2 border">Remove</th>
                  </tr>
                </thead>
                <tbody>
                  {portfolio.map(item => (
                    <tr key={item.symbol} className="text-center">
                      <td className="p-2 border">{item.symbol}</td>
                      <td className="p-2 border">{item.close}</td>
                      <td className="p-2 border">{item.stop_loss}</td>
                      <td className="p-2 border">
                        <button onClick={() => handleRemove(item.symbol)} className="bg-red-500 text-white px-2 py-1 rounded">
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {exitAlerts.length > 0 && (
            <div className="bg-yellow-100 border-l-4 border-yellow-500 text-yellow-700 p-4">
              <h3 className="font-bold mb-2">Exit Alerts</h3>
              <ul className="list-disc list-inside">
                {exitAlerts.map(stock => (
                  <li key={stock.symbol} className="mb-2 flex items-center justify-between">
                    <span>
                      {stock.symbol}: Consider exiting based on exit rules (RSI/MACD/BB%/ADX/Stop Loss).
                    </span>
                    <button onClick={() => handleDismiss(stock.symbol)} className="ml-4 bg-green-500 text-white px-2 py-1 rounded">
                      Mark as Exited
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );
}
