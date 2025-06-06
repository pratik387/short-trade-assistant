import { useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";

export default function KiteCallback() {
  const navigate = useNavigate();
  const { search } = useLocation();

  useEffect(() => {
    const params = new URLSearchParams(search);
    const loginStatus = params.get("kite_login"); // “success” or “failed”

    if (loginStatus === "success") {
      // Mark as logged in
      localStorage.setItem("kiteLoggedIn", "true");
    } else {
      // Clear any previous flag
      localStorage.removeItem("kiteLoggedIn");
    }

    // Redirect to Dashboard after a brief pause
    setTimeout(() => {
      navigate("/");
    }, 100);
  }, [search, navigate]);

  return null;
}
