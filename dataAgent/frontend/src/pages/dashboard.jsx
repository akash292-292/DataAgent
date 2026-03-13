import "./dashboard.css";
import { useNavigate } from "react-router-dom";
import { useState, useEffect } from "react";

const Dashboard = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const bootstrapSession = async () => {
      try {
        const response = await fetch(
          `${process.env.REACT_APP_BASE_BACKEND_URL}/api/verify-session`,
          { credentials: "include" }
        );

        if (response.ok) {
          const data = await response.json();
          setEmail(data.email);
          localStorage.setItem("user_email", data.email);
          setIsLoading(false);
          return;
        }
      } catch (error) {
        console.error("Session verification failed:", error);
      }

      const storedEmail = localStorage.getItem("user_email");
      if (storedEmail && storedEmail !== "undefined") {
        setEmail(storedEmail);
      } else {
        setEmail(null);
      }
      setIsLoading(false);
    };

    bootstrapSession();
  }, []);

  const handleLogout = async () => {
    localStorage.removeItem("user_email");
    window.location.href = "/?action=logout";
  };

  if (isLoading) {
    return (
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          height: "100vh",
          fontSize: "1.5rem",
          color: "#1453c6",
          fontFamily: "'Inter', system-ui, sans-serif",
        }}
      >
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "3rem", marginBottom: "20px" }}>⏳</div>
          <div>Loading Dashboard...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="body">
      <div
        className="header"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "20px 40px",
        }}
      >
        <p className="subtitle">Hi there! What can I do for you today?</p>

        <div
          style={{
            position: "fixed",
            top: "50px",
            right: "50px",
            display: "flex",
            gap: "12px",
            alignItems: "center",
            zIndex: 10,
          }}
        >
          <button
            onClick={() => (window.location.href = "/")}
            style={{
              background: "linear-gradient(135deg, #1453c6, #2a6ce8)",
              color: "white",
              border: "none",
              borderRadius: "10px",
              padding: "10px 20px",
              fontWeight: "600",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              fontSize: "0.95rem",
              transition: "all 0.3s",
              boxShadow: "0 4px 12px rgba(20, 83, 198, 0.2)",
            }}
          >
            <i className="fas fa-arrow-left"></i> Back
          </button>

          <button
            onClick={() => {
              if (window.confirm("Are you sure you want to logout?")) {
                handleLogout();
              }
            }}
            style={{
              background: "#dc3545",
              color: "white",
              border: "none",
              borderRadius: "10px",
              padding: "10px 20px",
              fontWeight: "600",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              fontSize: "0.95rem",
              transition: "all 0.3s",
              boxShadow: "0 4px 12px rgba(220, 53, 69, 0.2)",
            }}
          >
            <i className="fas fa-sign-out-alt"></i> Logout
          </button>
        </div>
      </div>

      <div className="grid">
        <div
          className="bubble primary"
          onClick={() => navigate("/profiling/options")}
        >
          <div className="bubble-icon">📊</div>
          <div className="bubble-title">Data Profiling</div>
          <div className="bubble-desc">Analyze and understand your data structure</div>
        </div>

        <div className="bubble disabled">
          <div className="coming-soon">Coming Soon</div>
          <div className="bubble-icon">🧹</div>
          <div className="bubble-title">Data Cleaning</div>
          <div className="bubble-desc">Remove inconsistencies and errors</div>
        </div>

        <div
          className="bubble primary"
          onClick={() => navigate("/mapping/optionsMapping")}
        >
          <div className="bubble-icon">🗺️</div>
          <div className="bubble-title">Smart Mapping</div>
          <div className="bubble-desc">Transform data between formats</div>
        </div>

        <div
          className="bubble primary"
          onClick={() => navigate("/metadata-comparison")}
        >
          <div className="bubble-icon">✅</div>
          <div className="bubble-title">Data Mapping</div>
          <div className="bubble-desc">Compare metadata of both source and target systems</div>
        </div>

        <div className="bubble disabled">
          <div className="coming-soon">Coming Soon</div>
          <div className="bubble-icon">⚖️</div>
          <div className="bubble-title">Reconciliation</div>
          <div className="bubble-desc">Match and compare data sets</div>
        </div>
      </div>

      <div className="footer">
        <p>AI Agent Dashboard</p>
      </div>
    </div>
  );
};

export default Dashboard;
