import { useEffect, useState } from "react";
import axios from "axios";

export default function Portfolio() {
  const [portfolio, setPortfolio] = useState([]);

  useEffect(() => {
    const fetchPortfolio = async () => {
      try {
        const res = await axios.get("http://localhost:8000/api/portfolio");
        setPortfolio(res.data);
      } catch (error) {
        console.error("Failed to load portfolio", error);
      }
    };
    fetchPortfolio();
  }, []);

  const handleRemove = async (symbol) => {
    try {
      await axios.delete(`http://localhost:8000/api/portfolio/${symbol}`);
      setPortfolio(prev => prev.filter(item => item.symbol !== symbol));
    } catch (error) {
      console.error("Failed to remove stock", error);
    }
  };

  const handleExit = async (symbol) => {
    try {
      await axios.post("http://localhost:8000/api/exit", { symbol });
      alert(`Exit action triggered for ${symbol}`);
    } catch (error) {
      console.error("Failed to trigger exit", error);
    }
  };

  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold mb-4">My Portfolio</h1>

      {portfolio.length === 0 ? (
        <p>No tracked stocks. Go back to the dashboard and track a few.</p>
      ) : (
        <table className="table-auto w-full border">
          <thead>
            <tr className="bg-gray-200">
              <th className="p-2 border">Symbol</th>
              <th className="p-2 border">Entry Price</th>
              <th className="p-2 border">Quantity</th>
              <th className="p-2 border">Sold Targets</th>
              <th className="p-2 border">Highest Price</th>
              <th className="p-2 border">Exit</th>
              <th className="p-2 border">Remove</th>
            </tr>
          </thead>
          <tbody>
            {portfolio.map((stock) => (
              <tr key={stock.symbol} className="text-center">
                <td className="p-2 border">{stock.symbol}</td>
                <td className="p-2 border">{stock.close}</td>
                <td className="p-2 border">{stock.quantity ?? "-"}</td>
                <td className="p-2 border">
                  {(stock.sold_targets && stock.sold_targets.length > 0)
                    ? stock.sold_targets.join(", ")
                    : "None"}
                </td>
                <td className="p-2 border">{stock.highest_price ?? "-"}</td>
                <td className="p-2 border">
                  <button
                    onClick={() => handleExit(stock.symbol)}
                    className="bg-yellow-500 text-white px-2 py-1 rounded"
                  >
                    Exit
                  </button>
                </td>
                <td className="p-2 border">
                  <button
                    onClick={() => handleRemove(stock.symbol)}
                    className="bg-red-500 text-white px-2 py-1 rounded"
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
