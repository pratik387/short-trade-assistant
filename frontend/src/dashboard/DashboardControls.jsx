export default function DashboardControls({
  fetchStocks,
  navigate,
  kiteLoggedIn,
  kiteLoginUrl,
  autoEmail,
  toggleAutoEmail,
  indexFilter,
  handleIndexChange,
}) {
  return (
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
  );
}
