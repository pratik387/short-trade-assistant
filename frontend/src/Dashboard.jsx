import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";

const KITE_API_KEY = process.env.REACT_APP_KITE_API_KEY;
const kiteLoginUrl = `https://kite.zerodha.com/connect/login?api_key=${KITE_API_KEY}&v=3`;

export default function Dashboard() {
  const [stocks, setStocks] = useState([]);
  const [portfolio, setPortfolio] = useState(() => {
    const saved = localStorage.getItem("portfolio");
    return saved ? JSON.parse(saved) : [];
  });
  const [autoEmail, setAutoEmail] = useState(() => {
    return JSON.parse(localStorage.getItem("autoEmail") || "true");
  });
  const [tokenExpired, setTokenExpired] = useState(false);
  const [indexFilter, setIndexFilter] = useState("all");
  const navigate = useNavigate();

  const fetchStocks = async () => {
    try {
      const res = await axios.get(
        `http://localhost:8000/api/short-term-suggestions?interval=day&index=${indexFilter}`
      );
      setStocks(res.data);
      setTokenExpired(false);
    } catch (err) {
      console.error("Failed to fetch stock suggestions", err);
      if (err.response?.status === 401 || err.response?.data?.reason?.includes("token")) {
        setTokenExpired(true);
      }
    }
  };

  useEffect(() => {
    localStorage.setItem("autoEmail", JSON.stringify(autoEmail));
  }, [autoEmail]);

  useEffect(() => {
    localStorage.setItem("portfolio", JSON.stringify(portfolio));
  }, [portfolio]);

  const handleTrack = async (stock) => {
    if (!portfolio.find((item) => item.symbol === stock.symbol)) {
      const updated = [...portfolio, stock];
      setPortfolio(updated);
      try {
        await axios.post("http://localhost:8000/api/portfolio", stock);
      } catch (error) {
        console.error("Failed to track stock in backend", error);
      }
    }
  };

  const groupedStocks = stocks.reduce((acc, stock) => {
    if (!acc[stock.category]) acc[stock.category] = [];
    acc[stock.category].push(stock);
    return acc;
  }, {});

  return (
    <div className="p-4 space-y-6">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <h1 className="text-3xl font-bold">📊 Stock Dashboard</h1>
        <div className="flex flex-wrap gap-2">
          <button
            className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-4 rounded"
            onClick={() => window.location.href = kiteLoginUrl}
          >
            🔐 Login to Zerodha
          </button>
          <button
            className="border border-gray-400 hover:bg-gray-100 text-gray-800 font-medium py-2 px-4 rounded"
            onClick={() => navigate("/portfolio")}
          >
            📁 Go to Portfolio
          </button>
          <button
            className="bg-gray-200 hover:bg-gray-300 text-gray-800 font-medium py-2 px-4 rounded"
            onClick={fetchStocks}
          >
            🔄 Refresh Suggestions
          </button>
          <label className="flex items-center text-sm">
            <input
              type="checkbox"
              checked={autoEmail}
              onChange={() => setAutoEmail(!autoEmail)}
              className="mr-2"
            />
            Auto Email Alerts
          </label>
          <select
            value={indexFilter}
            onChange={(e) => setIndexFilter(e.target.value)}
            className="p-2 border rounded"
          >
            <option value="all">All</option>
            <option value="nifty_50">Nifty 50</option>
            <option value="nifty_100">Nifty 100</option>
            <option value="nifty_200">Nifty 200</option>
            <option value="nifty_500">Nifty 500</option>
          </select>
        </div>
      </div>

      {tokenExpired && (
        <div className="bg-red-100 text-red-800 border border-red-400 p-3 rounded shadow">
          Your session has expired. Please <strong>login to Zerodha</strong> again.
        </div>
      )}

      {Object.keys(groupedStocks).map((category) => (
        <div key={category} className="bg-white rounded-xl shadow p-4">
          <h2 className="text-xl font-semibold mb-4 capitalize">📌 {category} Picks</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full border text-sm">
              <thead className="bg-gray-100">
                <tr>
                  <th className="p-2 border">Symbol</th>
                  <th className="p-2 border">RSI</th>
                  <th className="p-2 border">MACD</th>
                  <th className="p-2 border">%B</th>
                  <th className="p-2 border">ADX</th>
                  <th className="p-2 border">Close</th>
                  <th className="p-2 border">Stop Loss</th>
                  <th className="p-2 border">Action</th>
                </tr>
              </thead>
              <tbody>
                {groupedStocks[category].map((stock) => (
                  <tr key={stock.symbol} className="text-center hover:bg-gray-50">
                    <td className="p-2 border font-medium">{stock.symbol}</td>
                    <td className="p-2 border">{stock.rsi}</td>
                    <td className="p-2 border">{stock.macd}</td>
                    <td className="p-2 border">{stock.bb}</td>
                    <td className="p-2 border">{stock.adx}</td>
                    <td className="p-2 border">{stock.close}</td>
                    <td className="p-2 border">{stock.stop_loss}</td>
                    <td className="p-2 border">
                      <button className="text-indigo-600 hover:underline font-medium" onClick={() => handleTrack(stock)}>
                        ➕ Track
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}
