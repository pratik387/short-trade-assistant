import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";

function KiteCallback() {
  const [searchParams] = useSearchParams();

  useEffect(() => {
    const token = searchParams.get("request_token");
    if (token) {
      fetch(`http://localhost:3000/kite-callback?request_token=${token}`)
        .then((res) => res.json())
        .then((data) => {
          alert("Kite login successful!");
          console.log("Backend response:", data);
        })
        .catch((err) => {
          console.error("Kite callback error:", err);
        });
    }
  }, [searchParams]);

  return (
    <div style={{ padding: "20px" }}>
      <h2>Login Complete</h2>
      <p>You have been authenticated via Kite. You can now return to the dashboard.</p>
    </div>
  );
}

export default KiteCallback;
