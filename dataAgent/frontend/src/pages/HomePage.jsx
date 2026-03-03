import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

const HomePage = () => {
  const navigate = useNavigate();
  const [isSignedIn, setIsSignedIn] = useState(false);
  const [hoveredCard, setHoveredCard] = useState(null);
  const [showLogout, setShowLogout] = useState(false);
  const [email, setEmail] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const queryParams = new URLSearchParams(window.location.search);
    const urlEmail = queryParams.get("email");
    const action = queryParams.get("action");

    if (action === "logout") {
      localStorage.removeItem("user_email");
      setIsSignedIn(false);
      setEmail(null);
      setLoading(false);
      window.history.replaceState({}, document.title, window.location.pathname);
      return;
    }

    if (urlEmail) {
      localStorage.setItem("user_email", urlEmail);
      setEmail(urlEmail);
      setIsSignedIn(true);
      setLoading(false);
      window.history.replaceState({}, document.title, window.location.pathname);
      return;
    }

    verifySession();
  }, []);

  const verifySession = async () => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 8000);

    try {
      setLoading(true);

      const response = await fetch(
        `${process.env.REACT_APP_BASE_BACKEND_URL}/api/verify-session`,
        {
          credentials: "include",
          signal: controller.signal,
        }
      );

      if (response.ok) {
        const data = await response.json();
        setEmail(data.email);
        setIsSignedIn(true);
      } else {
        const storedEmail = localStorage.getItem("user_email");
        if (storedEmail) {
          setEmail(storedEmail);
          setIsSignedIn(true);
        } else {
          setIsSignedIn(false);
          setEmail(null);
        }
      }
    } catch (error) {
      console.error("Session verification error:", error);
      const storedEmail = localStorage.getItem("user_email");
      if (storedEmail) {
        setEmail(storedEmail);
        setIsSignedIn(true);
      } else {
        setIsSignedIn(false);
        setEmail(null);
      }
    } finally {
      clearTimeout(timeoutId);
      setLoading(false);
    }
  };

  const handleSignIn = () => {
    window.location.href = `${process.env.REACT_APP_BASE_BACKEND_URL}/login`;
  };

  const handleLogout = async () => {
    const csrfToken = document.cookie
      .split("; ")
      .find((row) => row.startsWith("csrf_token="))
      ?.split("=")[1];
    try {
      await fetch(`${process.env.REACT_APP_BASE_BACKEND_URL}/api/logout`, {
        method: "POST",
        credentials: "include",
        headers: csrfToken ? { "X-CSRF-Token": decodeURIComponent(csrfToken) } : {},
      });
    } catch (error) {
      console.error("Logout error:", error);
    } finally {
      localStorage.removeItem("user_email");
      setIsSignedIn(false);
      setEmail(null);
    }
  };

  const handleCardClick = (cardIndex) => {
    if (!isSignedIn) return;

    switch (cardIndex) {
      case 0:
        navigate("/dashboard");
        break;
      case 1:
        navigate("/qa");
        break;
      case 2:
        break;
      case 3:
        navigate("/pm");
        break;
      default:
        break;
    }
  };

  const getFirstName = (inputEmail) => {
    if (!inputEmail) return "User";
    const localPart = inputEmail.split("@")[0];
    const parts = localPart.split(/[._-]/);
    const firstName = parts[0];
    if (firstName) {
      return firstName.charAt(0).toUpperCase() + firstName.slice(1);
    }
    return "User";
  };

  const cards = [
    {
      icon: "🤖",
      title: "Data Agent",
      desc: "Intelligent data profiling, validation, and quality analysis",
      hoverDesc:
        "Automate data profiling with AI-powered validation rules. Detect anomalies, ensure integrity, and generate comprehensive quality reports instantly.",
    },
    {
      icon: "🧪",
      title: "QA Agent",
      desc: "Automated testing and quality assurance workflows",
      hoverDesc:
        "Generate test cases automatically, identify bugs intelligently, and execute comprehensive testing workflows with minimal manual intervention.",
    },
    {
      icon: "💻",
      title: "Coding Agent",
      desc: "AI-powered code generation and optimization",
      hoverDesc:
        "Generate production-ready code, optimize performance, refactor legacy systems, and receive intelligent code reviews with best practice recommendations.",
    },
    {
      icon: "📋",
      title: "PM Agent",
      desc: "Project management and workflow automation",
      hoverDesc:
        "Automate sprint planning, track deliverables intelligently, generate status reports, and optimize resource allocation with AI-driven insights.",
    },
  ];

  if (loading) {
    return (
      <div
        style={{
          height: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(135deg, #f3f6fb 0%, #e8edf7 100%)",
        }}
      >
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "3rem", marginBottom: "20px" }}>⏳</div>
          <div style={{ fontSize: "1.2rem", color: "#1453c6" }}>Loading...</div>
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        height: "100vh",
        overflow: "hidden",
        background: "linear-gradient(135deg, #f3f6fb 0%, #e8edf7 100%)",
        fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <nav
        style={{
          height: "85px",
          background: "white",
          borderBottom: "1px solid #e0e0e0",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 50px",
          boxShadow: "0 2px 8px rgba(0,0,0,0.05)",
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "20px" }}>
          <img
            src="https://www.forsysinc.com/assets/img/logo.png"
            alt="Forsys Logo"
            style={{
              width: "70px",
              height: "70px",
              objectFit: "contain",
            }}
          />

          <div
            style={{
              fontSize: "28px",
              fontWeight: "700",
              letterSpacing: "-0.5px",
              display: "flex",
              gap: "2px",
            }}
          >
            <span style={{ color: "#1761c2" }}>For</span>
            <span style={{ color: "#c3c614" }}>sys</span>
            <span style={{ color: "#0d77e2", marginLeft: "8px" }}>Agents</span>
          </div>
        </div>

        {!isSignedIn ? (
          <button
            onClick={handleSignIn}
            style={{
              padding: "12px 28px",
              background: "#1453c6",
              color: "white",
              border: "none",
              borderRadius: "8px",
              fontSize: "16px",
              fontWeight: "600",
              cursor: "pointer",
              transition: "all 0.3s ease",
              boxShadow: "0 2px 8px rgba(20, 83, 198, 0.3)",
            }}
            onMouseEnter={(e) => {
              e.target.style.background = "#0d3d9a";
              e.target.style.transform = "translateY(-2px)";
            }}
            onMouseLeave={(e) => {
              e.target.style.background = "#1453c6";
              e.target.style.transform = "translateY(0)";
            }}
          >
            Sign In
          </button>
        ) : (
          <div
            style={{ position: "relative" }}
            onMouseEnter={() => setShowLogout(true)}
            onMouseLeave={() => setShowLogout(false)}
          >
            <div
              style={{
                padding: "10px 20px",
                background: "#eaf0ff",
                borderRadius: "8px",
                color: "#1453c6",
                fontSize: "15px",
                fontWeight: "600",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "10px",
              }}
            >
              <span style={{ fontSize: "18px" }}>👤</span>
              <span>Hi, {getFirstName(email)}</span>
            </div>

            {showLogout && (
              <div
                onClick={handleLogout}
                style={{
                  position: "absolute",
                  top: "100%",
                  right: 0,
                  padding: "10px 20px",
                  background: "white",
                  borderRadius: "8px",
                  boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
                  fontSize: "14px",
                  fontWeight: "600",
                  color: "#e74c3c",
                  cursor: "pointer",
                  width: "max-content",
                  zIndex: 10,
                }}
              >
                Logout
              </div>
            )}
          </div>
        )}
      </nav>

      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          padding: "30px 50px",
          overflow: "hidden",
        }}
      >
        <h2
          style={{
            textAlign: "center",
            fontSize: "2rem",
            color: "#0941b9",
            marginBottom: "40px",
            fontWeight: "700",
            letterSpacing: "-0.5px",
          }}
        >
          Forsys Agentic Workforce
        </h2>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: "24px",
            width: "100%",
            maxWidth: "1300px",
          }}
        >
          {cards.map((card, idx) => {
            const isHovered = hoveredCard === idx;
            const isDisabledComingSoon = idx === 2;
            const isClickable = isSignedIn && !isDisabledComingSoon;

            return (
              <div
                key={idx}
                onClick={() => handleCardClick(idx)}
                onMouseEnter={() => setHoveredCard(idx)}
                onMouseLeave={() => setHoveredCard(null)}
                style={{
                  background: "white",
                  borderRadius: "16px",
                  padding: "28px 20px",
                  boxShadow: isHovered && isClickable
                    ? "0 8px 24px rgba(20, 83, 198, 0.25)"
                    : "0 4px 12px rgba(0,0,0,0.08)",
                  cursor: isClickable ? "pointer" : "not-allowed",
                  opacity: isClickable ? 1 : 0.5,
                  transition: "all 0.3s ease",
                  position: "relative",
                  border: isHovered && isClickable ? "2px solid #1453c6" : "2px solid transparent",
                  transform: isHovered && isClickable ? "translateY(-8px)" : "translateY(0)",
                  display: "flex",
                  flexDirection: "column",
                  height: "260px",
                }}
              >
                {isDisabledComingSoon ? (
                  <div
                    style={{
                      position: "absolute",
                      top: "12px",
                      right: "12px",
                      background: "rgba(255, 193, 7, 0.2)",
                      padding: "4px 12px",
                      borderRadius: "20px",
                      fontSize: "11px",
                      fontWeight: "600",
                      color: "#b8860b",
                      border: "1px solid rgba(255, 193, 7, 0.4)",
                    }}
                  >
                    Coming Soon
                  </div>
                ) : !isSignedIn ? (
                  <div
                    style={{
                      position: "absolute",
                      top: "12px",
                      right: "12px",
                      background: "rgba(255,255,255,0.95)",
                      padding: "4px 12px",
                      borderRadius: "20px",
                      fontSize: "11px",
                      fontWeight: "600",
                      color: "#5a6c8d",
                      border: "1px solid #e0e0e0",
                    }}
                  >
                    Sign in required
                  </div>
                ) : (
                  <div
                    style={{
                      position: "absolute",
                      top: "12px",
                      right: "12px",
                      background: "rgba(76, 175, 80, 0.1)",
                      padding: "4px 12px",
                      borderRadius: "20px",
                      fontSize: "11px",
                      fontWeight: "600",
                      color: "#2e7d32",
                      border: "1px solid rgba(76, 175, 80, 0.3)",
                    }}
                  >
                    Available
                  </div>
                )}

                <div
                  style={{
                    width: "65px",
                    height: "65px",
                    background: isClickable && isHovered ? "#1453c6" : "#eaf0ff",
                    borderRadius: "50%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "34px",
                    marginBottom: "18px",
                    transition: "all 0.3s ease",
                  }}
                >
                  {card.icon}
                </div>

                <h3
                  style={{
                    fontSize: "1.3rem",
                    fontWeight: "700",
                    color: isClickable && isHovered ? "#1453c6" : "#1a2b50",
                    marginBottom: "10px",
                    transition: "color 0.3s ease",
                  }}
                >
                  {card.title}
                </h3>

                <p
                  style={{
                    fontSize: "0.9rem",
                    color: "#5a6c8d",
                    lineHeight: "1.5",
                    flex: 1,
                    transition: "all 0.3s ease",
                  }}
                >
                  {isHovered && isClickable ? card.hoverDesc : card.desc}
                </p>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default HomePage;
