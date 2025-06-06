import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";

const KITE_API_KEY = process.env.REACT_APP_KITE_API_KEY;
const kiteLoginUrl = `https://kite.zerodha.com/connect/login?api_key=${KITE_API_KEY}&v=3`;

export default function Dashboard() {
  const [stocks, setStocks] = useState(() => {
    const saved = localStorage.getItem("stocks");
    return saved ? JSON.parse(saved) : [];
  });

  const [portfolio, setPortfolio] = useState(() => {
    const saved = localStorage.getItem("portfolio");
    return saved ? JSON.parse(saved) : [];
  });

  const [autoEmail, setAutoEmail] = useState(() => {
    return JSON.parse(localStorage.getItem("autoEmail") || "true");
  });

  const [tokenExpired, setTokenExpired] = useState(false);
  const [kiteLoggedIn, setKiteLoggedIn] = useState(() => {
    return localStorage.getItem("kiteLoggedIn") === "true";
  });

  const [indexFilter, setIndexFilter] = useState("nifty_50");
  const [loading, setLoading] = useState(false);

  const navigate = useNavigate();

  useEffect(() => {
    localStorage.setItem("kiteLoggedIn", kiteLoggedIn ? "true" : "false");
  }, [kiteLoggedIn]);

  useEffect(() => {
    localStorage.setItem("portfolio", JSON.stringify(portfolio));
  }, [portfolio]);

  useEffect(() => {
    localStorage.setItem("autoEmail", JSON.stringify(autoEmail));
  }, [autoEmail]);

  useEffect(() => {
    localStorage.setItem("stocks", JSON.stringify(stocks));
  }, [stocks]);

  useEffect(() => {
    async function checkSession() {
      try {
        const res = await axios.get("http://localhost:8000/api/kite/session-status");
        setKiteLoggedIn(res.data.logged_in);
      } catch (err) {
        console.error("Error checking Kite session:", err);
        setKiteLoggedIn(false);
      }
    }
    checkSession();
  }, []);

  const fetchStocks = async () => {
    setLoading(true);
    try {
      const res = await axios.get(
        `http://localhost:8000/api/short-term-suggestions?interval=day&index=${indexFilter}`
      );
      setStocks(Array.isArray(res.data) ? res.data : []);
      setTokenExpired(false);
    } catch (err) {
      console.error("Failed to fetch stock suggestions", err);
      if (
        err.response?.status === 401 ||
        err.response?.data?.reason?.includes("token")
      ) {
        setTokenExpired(true);
        setKiteLoggedIn(false);
      }
    } finally {
      setLoading(false);
    }
  };

  const fetchPortfolio = async () => {
    try {
      const res = await axios.get("http://localhost:8000/api/portfolio");
      const symbols = res.data.map((item) => item.symbol);
      setPortfolio(symbols);
      setTokenExpired(false);
    } catch (err) {
      console.error("Failed to fetch portfolio", err);
    }
  };

  useEffect(() => {
    if (stocks.length === 0) {
      fetchStocks();
    }
    fetchPortfolio();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleTrack = async (stock) => {
    const payload = {
      symbol: stock.symbol,
      close: Number(stock.close),
      quantity: 100, // hybrid strategy compatible
    };
    console.log("Adding to portfolio with payload:", payload);

    try {
      const res = await axios.post("http://localhost:8000/api/portfolio", payload);
      console.log("Add to portfolio response:", res.data);
      setPortfolio((prev) => [...prev, stock.symbol]);
    } catch (err) {
      console.error("Failed to add to portfolio", err, err.response?.data);
      alert(
        "Unable to add to portfolio. Please check console for details or ensure all fields are correct."
      );
    }
  };

  const toggleAutoEmail = () => {
    setAutoEmail((prev) => !prev);
  };

  const handleIndexChange = (e) => {
    setIndexFilter(e.target.value);
  };

  // ── LOADING OVERLAY ────────────────────────────────────────
  if (loading) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-white bg-opacity-70 z-50">
        <div className="flex flex-col items-center space-y-4">
          <div className="w-12 h-12 border-4 border-blue-400 border-dashed rounded-full animate-spin"></div>
          <div className="text-blue-700 font-medium">Processing suggestions...</div>
        </div>
      </div>
    );
  }

  // ── MAIN DASHBOARD ─────────────────────────────────────────
  return (
    <div className="p-4 space-y-4">
      {kiteLoggedIn && (
        <div className="bg-green-100 text-green-800 border border-green-400 p-2 rounded">
          Logged in to Kite successfully! You can now refresh suggestions.
        </div>
      )}

      {tokenExpired && (
        <div className="bg-red-100 text-red-800 border border-red-400 p-3 rounded shadow">
          Your session has expired. Please <strong>login to Zerodha</strong> again.
        </div>
      )}

      <div className="flex items-center space-x-2">
        <button
          className="bg-gray-200 hover:bg-gray-300 text-gray-800 font-medium py-2 px-4 rounded"
          onClick={fetchStocks}
        >
          🔄 Refresh Suggestions
        </button>
        <button
          className="border border-gray-400 hover:bg-gray-100 text-gray-800 font-medium py-2 px-4 rounded"
          onClick={() => navigate("/portfolio")}
        >
          📁 Go to Portfolio
        </button>
        {!kiteLoggedIn && (
          <button
            className="border border-gray-400 hover:bg-gray-100 text-gray-800 font-medium py-2 px-4 rounded"
            onClick={() => (window.location.href = kiteLoginUrl)}
          >
            🔑 Login to Kite
          </button>
        )}
        <label className="flex items-center space-x-1">
          <input
            type="checkbox"
            checked={autoEmail}
            onChange={toggleAutoEmail}
            className="form-checkbox h-5 w-5"
          />
          <span>Email Alerts</span>
        </label>
        <select
          value={indexFilter}
          onChange={handleIndexChange}
          className="border border-gray-400 rounded py-2 px-3"
        >
          <option value="nifty_50">Nifty 50</option>
          <option value="nifty_100">Nifty 100</option>
          <option value="nifty_200">Nifty 200</option>
          <option value="nifty_500">Nifty 500</option>
          <option value="all">All</option>
        </select>
      </div>

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
    </div>
  );
}
