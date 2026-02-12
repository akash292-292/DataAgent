import React, { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

export default function Preview() {
  const location = useLocation();
  const searchParams = new URLSearchParams(location.search);

  const storedEmail = localStorage.getItem("user_email");
  const email = storedEmail;
  const filename = searchParams.get("filename");
  // const [email,setEmail] = useState(null);
  // const [token , setToken] = useState(null);
  const localPath = searchParams.get("local_path");
 //const [isLoading, setIsLoading] = useState(true);
  const [loading, setLoading] = useState(false);
  const [encodedPath, setEncodedPath] = useState("");
  const [cardVisible, setCardVisible] = useState(false);

  

  useEffect(() => {
    if (localPath) {
      const encoded = btoa(unescape(encodeURIComponent(localPath)));
      setEncodedPath(encoded);
    }

    setTimeout(() => setCardVisible(true), 100);
  }, [localPath]);

  const handleSubmit = (e) => {
    e.preventDefault();
    setLoading(true);

    setTimeout(() => {
      e.target.submit();
    }, 800);
  };

 const handleLogout = async () => {
    // 1. Clear Local Storage (Crucial)
    localStorage.removeItem("user_email");
    
    // 3. Redirect to Landing Page
    window.location.href = `${process.env.REACT_APP_BASE_FRONTEND_URL}?action=logout`;
  };

  return (
    <>
      {/* FIXED TOP-RIGHT BUTTONS */}
      <div
        style={{
          position: "fixed",
          top: "50px",
          right: "50px",
          display: "flex",
          gap: "12px",
          zIndex: 9999,
        }}
      >
        {/* Back
        <button
          onClick={() => (window.location.href = `/profiling/options`)}
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
          onMouseEnter={(e) => {
            e.target.style.transform = "translateY(-2px)";
            e.target.style.boxShadow = "0 6px 16px rgba(20, 83, 198, 0.3)";
          }}
          onMouseLeave={(e) => {
            e.target.style.transform = "translateY(0)";
            e.target.style.boxShadow = "0 4px 12px rgba(20, 83, 198, 0.2)";
          }}
        >
          <i className="fas fa-arrow-left"></i> Back
        </button> */}

        {/* Logout */}
        <button
          onClick={() => {
            if (window.confirm('Are you sure you want to logout?')) {
               handleLogout();
            }}}
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
          onMouseEnter={(e) => {
            e.target.style.background = "#bb2d3b";
            e.target.style.transform = "translateY(-2px)";
            e.target.style.boxShadow = "0 6px 16px rgba(220, 53, 69, 0.3)";
          }}
          onMouseLeave={(e) => {
            e.target.style.background = "#dc3545";
            e.target.style.transform = "translateY(0)";
            e.target.style.boxShadow = "0 4px 12px rgba(220, 53, 69, 0.2)";
          }}
        >
          <i className="fas fa-sign-out-alt"></i> Logout
        </button>
      </div>
      {/* Full Screen Container */}
      <div
        style={{
          background: "linear-gradient(135deg, #f3f6fb 0%, #e8edf7 100%)",
          color: "#1a2b50",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          height: "100vh", // ⬅ scrolling remove
          padding: "10px",
          overflow: "hidden",
          fontFamily: "'Segoe UI', system-ui, -apple-system, sans-serif",
        }}
      >
        <link
          rel="stylesheet"
          href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"
        />

        {/* Main Card (reduced size) */}
        <div
          style={{
            background: "#fff",
            padding: "35px 28px", // ⬅ reduced padding
            borderRadius: "20px",
            boxShadow: "0 10px 30px rgba(20, 83, 198, 0.12)",
            textAlign: "center",
            width: "100%",
            maxWidth: "420px", // ⬅ smaller container
            position: "relative",
            overflow: "hidden",
            opacity: cardVisible ? 1 : 0,
            transform: cardVisible ? "translateY(0)" : "translateY(20px)",
            transition: "opacity 0.5s ease, transform 0.5s ease",
          }}
        >
          {/* Top Accent */}
          <div
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              right: 0,
              height: "4px",
              background:
                "linear-gradient(90deg, #1453c6, #2a6ce8, #4d8eff)",
            }}
          />

          {/* File Icon */}
          <div
            style={{
              width: "80px",
              height: "80px",
              background:
                "linear-gradient(135deg, #eaf0ff 0%, #d5e1ff 100%)",
              borderRadius: "20px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 20px",
              fontSize: "32px",
              color: "#1453c6",
              boxShadow: "0 10px 20px rgba(20, 83, 198, 0.15)",
              animation: "pulse 2s infinite",
            }}
          >
            <i className="far fa-file-alt"></i>
          </div>

          <style>{`
            @keyframes pulse {
              0% { transform: scale(1); }
              50% { transform: scale(1.05); }
              100% { transform: scale(1); }
            }
            @keyframes spin {
              0% { transform: rotate(0deg); }
              100% { transform: rotate(360deg); }
            }
          `}</style>

          {/* Title */}
          <p
            style={{
              color: "#5a6c8d",
              fontSize: "1.25rem",
              marginBottom: "22px",
            }}
          >
            Please confirm the selected file
          </p>

          {/* Filename */}
          <div
            style={{
              background: "#f8faff",
              borderRadius: "14px",
              padding: "16px",
              marginBottom: "20px",
              border: "1px solid #e6eeff",
            }}
          >
            <span
              style={{
                display: "block",
                fontSize: "0.85rem",
                color: "#5a6c8d",
                marginBottom: "6px",
              }}
            >
              File Name
            </span>

            <div
              style={{
                fontWeight: "700",
                color: "#1453c6",
                fontSize: "1.1rem",
                wordBreak: "break-word",
              }}
            >
              {filename}
            </div>
          </div>

          {/* Info Row */}
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              gap: "20px",
              marginBottom: "25px",
              flexWrap: "wrap",
            }}
          >
            <div
              style={{ display: "flex", alignItems: "center", gap: "6px", color: "#5a6c8d" }}
            >
              <i className="far fa-calendar-alt" style={{ color: "#1453c6" }}></i>
              <span>Uploaded: Today</span>
            </div>

            <div
              style={{ display: "flex", alignItems: "center", gap: "6px", color: "#5a6c8d" }}
            >
              <i className="far fa-file-excel" style={{ color: "#1453c6" }}></i>
              <span>Format: CSV</span>
            </div>
          </div>

          {/* Form */}
          <form method="get" action="/profiling/rules" onSubmit={handleSubmit}>
            <input type="hidden" name="filename" value={filename} />
            <input type="hidden" name="local_path" value={encodedPath} />

            <button
              type="submit"
              disabled={loading}
              style={{
                background: loading
                  ? "#ccc"
                  : "linear-gradient(135deg, #1453c6, #2a6ce8)",
                color: "#fff",
                padding: "14px 26px",
                border: "none",
                borderRadius: "12px",
                fontSize: "1rem",
                fontWeight: "600",
                cursor: loading ? "not-allowed" : "pointer",
                transition: "all 0.3s ease",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "10px",
                width: "100%",
              }}
            >
              {loading ? (
                <>
                  <i className="fas fa-spinner fa-spin"></i> Processing...
                </>
              ) : (
                <>
                  <i className="fas fa-check-circle"></i>
                  Confirm & Continue
                </>
              )}
            </button>
          </form>

          {/* Loader */}
          {loading && (
            <div
              style={{
                marginTop: "20px",
                color: "#5a6c8d",
                fontSize: "0.95rem",
                padding: "14px",
                background: "#f8faff",
                borderRadius: "12px",
                border: "1px solid #e6eeff",
                display: "flex",
                gap: "10px",
                justifyContent: "center",
                alignItems: "center",
              }}
            >
              <div
                style={{
                  border: "3px solid rgba(20, 83, 198, 0.2)",
                  borderTop: "3px solid #1453c6",
                  borderRadius: "50%",
                  width: "22px",
                  height: "22px",
                  animation: "spin 1s linear infinite",
                }}
              />
              <span>Processing your file... Please wait</span>
            </div>
          )}

          <div
            style={{
              marginTop: "24px",
              fontSize: "0.8rem",
              color: "#8a9bb8",
            }}
          >
            Your data is processed securely and never stored.
          </div>
        </div>

        {/* Back link */}
        <div
          style={{
            marginTop: "20px",
            color: "#5a6c8d",
            fontSize: "0.9rem",
          }}
        >
          <a
            href={`/profiling/options`}
            style={{
              color: "#1453c6",
              textDecoration: "none",
              display: "inline-flex",
              gap: "5px",
              alignItems: "center",
            }}
          >
            <i className="fas fa-arrow-left"></i> Back to file selection
          </a>
        </div>
      </div>
    </>
  );
}
