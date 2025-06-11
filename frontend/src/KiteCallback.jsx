import { useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import axios from "axios";

export default function KiteCallback() {
  const navigate = useNavigate();
  const { search } = useLocation();

  useEffect(() => {
    const params = new URLSearchParams(search);
    const requestToken = params.get("request_token");
    const status = params.get("status");

    if (!requestToken || status !== "success") {
      localStorage.removeItem("kiteLoggedIn");
      navigate("/"); // 🔁 clean redirect
      return;
    }

    axios
      .get(`/kite-callback?request_token=${requestToken}&status=success`)
      .then(() => {
        localStorage.setItem("kiteLoggedIn", "true");
        navigate("/"); // ✅ CLEAN REDIRECT
      })
      .catch((err) => {
        console.error("Kite callback error", err);
        localStorage.removeItem("kiteLoggedIn");
        navigate("/"); // ❌ also goes to clean route
      });
  }, [search, navigate]);

  return <div>Logging in to Kite...</div>;
}
