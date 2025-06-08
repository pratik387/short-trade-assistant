export default function SingleStockModal({ result, onClose, onTrack }) {
  if (!result || result.error) return null;

  const { symbol, score, suggestion, close, volume } = result;
  const suggestionColor = suggestion === "buy" ? "text-green-600" : "text-red-600";

  const handleTrackAndClose = () => {
    onTrack(result);
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50">
      <div className="bg-white p-6 rounded-lg shadow-lg w-full max-w-sm space-y-4">
        <h2 className="text-xl font-bold text-gray-800">{symbol}</h2>
        <p>Score: <strong>{score}</strong></p>
        <p className={suggestionColor}>Suggestion: {suggestion.toUpperCase()}</p>
        <p>Close Price: ₹{close}</p>
        <p>Volume: {volume.toLocaleString()}</p>

        <div className="flex justify-end space-x-2 pt-2">
          {suggestion === "buy" && (
            <button
              className="bg-green-500 text-white px-3 py-1 rounded hover:bg-green-600"
              onClick={handleTrackAndClose}
            >
              Track
            </button>
          )}
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
