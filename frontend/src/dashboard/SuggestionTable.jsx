import React, { useState } from "react";

export default function SuggestionTable({ stocks }) {
  const suggestions = stocks || [];
  const [expandedRow, setExpandedRow] = useState(null);

  if (!suggestions.length) return null;

  const toggleDetails = (idx) => {
    setExpandedRow(expandedRow === idx ? null : idx);
  };

  return (
    <div className="overflow-x-auto">
      <table className="table-auto border-collapse border border-gray-400 text-sm w-full">
        <thead className="bg-gray-200 sticky top-0 z-10">
          <tr>
            <th className="border border-gray-400 px-3 py-2">Symbol</th>
            <th className="border border-gray-400 px-3 py-2">Entry</th>
            <th className="border border-gray-400 px-3 py-2">Stop</th>
            <th className="border border-gray-400 px-3 py-2">Targets</th>
            <th className="border border-gray-400 px-3 py-2">RR</th>
            <th className="border border-gray-400 px-3 py-2">Note</th>
            <th className="border border-gray-400 px-3 py-2">Details</th>
          </tr>
        </thead>
        <tbody>
          {suggestions.map((s, idx) => (
            <React.Fragment key={idx}>
              <tr className="hover:bg-gray-100">
                <td className="border border-gray-400 px-3 py-2 font-semibold">{s.symbol}</td>
                <td className="border border-gray-400 px-3 py-2">
                  {s.plan?.entry_zone?.[0]} - {s.plan?.entry_zone?.[1]}
                </td>
                <td className="border border-gray-400 px-3 py-2">{s.plan?.stop}</td>
                <td className="border border-gray-400 px-3 py-2">
                  {s.plan?.targets?.[0]} / {s.plan?.targets?.[1]}
                </td>
                <td className="border border-gray-400 px-3 py-2">{s.plan?.rr_first}</td>
                <td className="border border-gray-400 px-3 py-2">{s.plan?.entry_note}</td>
                <td
                  className="border border-gray-400 px-3 py-2 text-blue-600 cursor-pointer text-center"
                  onClick={() => toggleDetails(idx)}
                >
                  {expandedRow === idx ? "Hide" : "Show"}
                </td>
              </tr>
              {expandedRow === idx && (
                <tr>
                  <td colSpan="7" className="border border-gray-400 px-3 py-2 bg-gray-50">
                    <pre className="text-xs whitespace-pre-wrap break-words">
                      {JSON.stringify(s.breakdown, null, 2)}
                    </pre>
                  </td>
                </tr>
              )}
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
