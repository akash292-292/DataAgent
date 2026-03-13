import React from "react";
import { useNavigate } from "react-router-dom";

const QALandingPage = () => {
  const navigate = useNavigate();

  return (
    <div style={{
      height: "100vh",
      display: "flex",
      flexDirection: "column",
      background: "#f3f6fb"
    }}>

      {/* =========================
          TOP BAR
      ========================= */}
      <div style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "20px 30px",
        background: "#ffffff",
        borderBottom: "1px solid #ddd"
      }}>
        <h2 style={{ margin: 0 }}>🧪 QA Agent</h2>

        <button
          onClick={() => navigate("/")}
          style={{
            padding: "8px 16px",
            borderRadius: 8,
            border: "none",
            background: "#1453c6",
            color: "white",
            cursor: "pointer"
          }}
        >
          ← Back
        </button>
      </div>

      {/* =========================
          CONTENT
      ========================= */}
      <div style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center"
      }}>
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, 300px)",
          gap: 30
        }}>
          
          {/* Requirement Analysis — disabled */}
          <div style={disabledBubbleStyle}>
            <div style={comingSoonBadge}>Coming Soon</div>
            <div style={{ fontSize: 40 }}>📄</div>
            <h3>Requirement Analysis</h3>
            <p>Extract functional & non-functional requirements</p>
          </div>

          {/* Test Case Generation */}
          <div
            onClick={() => navigate("/qa/testcases")}
            style={bubbleStyle}
          >
            <div style={{ fontSize: 40 }}>🧪</div>
            <h3>Test Case Generation</h3>
            <p>Generate Given / When / Then scenarios</p>
          </div>

        </div>
      </div>
    </div>
  );
};

const bubbleStyle = {
  background: "white",
  borderRadius: 16,
  padding: 30,
  cursor: "pointer",
  textAlign: "center",
  boxShadow: "0 6px 16px rgba(0,0,0,0.12)",
  transition: "transform 0.2s",
};

const disabledBubbleStyle = {
  ...bubbleStyle,
  opacity: 0.6,
  cursor: "not-allowed",
  position: "relative",
};

const comingSoonBadge = {
  position: "absolute",
  top: 10,
  right: 10,
  background: "rgba(0,0,0,0.08)",
  color: "#5a6c8d",
  padding: "4px 8px",
  borderRadius: 12,
  fontSize: "0.7rem",
  fontWeight: 600,
};

export default QALandingPage;
