import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";

import DashboardControls from "./DashboardControls";
import LoadingOverlay from "./LoadingOverlay";
import SingleStockChecker from "./SingleStockChecker";
import SuggestionTable from "./SuggestionTable";
import SingleStockModal from "./components/SingleStockModal";

// Set the base URL for all axios requests
axios.defaults.baseURL = "http://129.154.252.182:8000";

export default function Dashboard() {
  const [stocks, setStocks] = useState([]);
  const [portfolio, setPortfolio] = useState([]);
  const [autoEmail, setAutoEmail] = useState(() => {
    const saved = localStorage.getItem("autoEmail");
    return saved !== null ? JSON.parse(saved) : true;
  });
  const [kiteLoggedIn, setKiteLoggedIn] = useState(() => {
    const saved = localStorage.getItem("kiteLoggedIn");
    return saved === "true";
  });
  const [kiteLoginUrl, setKiteLoginUrl] = useState("");
  const [indexFilter, setIndexFilter] = useState("nifty_50");
  const [tokenExpired, setTokenExpired] = useState(false);
  const [loading, setLoading] = useState(false);
  const [checkSymbol, setCheckSymbol] = useState("");
  const [checkResult, setCheckResult] = useState(null);
  const [showModal, setShowModal] = useState(false);

  const navigate = useNavigate();

  useEffect(() => {
    localStorage.setItem("kiteLoggedIn", kiteLoggedIn ? "true" : "false");
  }, [kiteLoggedIn]);

  useEffect(() => {
    localStorage.setItem("autoEmail", JSON.stringify(autoEmail));
  }, [autoEmail]);

  useEffect(() => {
    localStorage.setItem("stocks", JSON.stringify(stocks));
  }, [stocks]);

  useEffect(() => {
    localStorage.setItem("portfolio", JSON.stringify(portfolio));
  }, [portfolio]);

  // Fetch the Kite login URL from the backend
  useEffect(() => {
    axios
      .get("/api/kite/login-url")
      .then((res) => setKiteLoginUrl(res.data.url))
      .catch(console.error);
  }, []);

  // Check Kite session status
  useEffect(() => {
    async function checkSession() {
      try {
        const res = await axios.get("/api/kite/session-status");
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
        `/api/short-term-suggestions?interval=day&index=${indexFilter}`
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
      const res = await axios.get("/api/portfolio");
      const symbols = res.data.map((item) => item.symbol);
      setPortfolio(symbols);
    } catch (err) {
      console.error("Failed to fetch portfolio", err);
    }
  };

  useEffect(() => {
    if (stocks.length === 0) {
      fetchStocks();
    }
    fetchPortfolio();
  }, []);

  const handleTrack = async (stock) => {
    const payload = {
      symbol: stock.symbol,
      close: Number(stock.close),
      quantity: 100,
    };
    try {
      await axios.post("/api/portfolio", payload);
      setPortfolio((prev) => [...prev, stock.symbol]);
    } catch (err) {
      console.error("Failed to add to portfolio", err);
      alert("Unable to add to portfolio. Please check console for details.");
    }
  };

  const handleCheckScore = async () => {
    try {
      const res = await axios.get(`/api/stock-score/${checkSymbol}`);
      setCheckResult(res.data);
      setShowModal(true);
    } catch (err) {
      setCheckResult({ error: "Could not fetch score." });
      setShowModal(true);
    }
  };

  if (loading) return <LoadingOverlay />;

  return (
    <div className="p-4 space-y-4">
      {kiteLoggedIn && (
        <div className="bg-green-100 text-green-800 border border-green-400 p-2 rounded">
          Logged in to Kite successfully! You can now refresh suggestions.
        </div>
      )}

      {tokenExpired && (
        <div className="bg-red-100 text-red-800 border border-red-400 p-3 rounded shadow">
          Your session has expired. Please <strong>login to Kite</strong> again.
        </div>
      )}

      <DashboardControls
        fetchStocks={fetchStocks}
        navigate={navigate}
        kiteLoggedIn={kiteLoggedIn}
        kiteLoginUrl={kiteLoginUrl}
        autoEmail={autoEmail}
        toggleAutoEmail={() => setAutoEmail((prev) => !prev)}
        indexFilter={indexFilter}
        handleIndexChange={(e) => setIndexFilter(e.target.value)}
      />

      <SingleStockChecker
        checkSymbol={checkSymbol}
        setCheckSymbol={setCheckSymbol}
        checkResult={checkResult}
        handleCheckScore={handleCheckScore}
      />

      {showModal && (
        <SingleStockModal
          result={checkResult}
          onClose={() => setShowModal(false)}
          onTrack={handleTrack}
        />
      )}

      <SuggestionTable
        stocks={stocks}
        portfolio={portfolio}
        handleTrack={handleTrack}
      />
    </div>
  );
}
