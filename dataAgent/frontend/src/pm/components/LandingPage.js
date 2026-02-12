import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import './LandingPage.css';

const LandingPage = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [checkingSession, setCheckingSession] = useState(true);
  const { loginWithGoogle, setUser, setSessionId, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const baseBackend = process.env.REACT_APP_BASE_BACKEND_URL || 'http://localhost:8000';
  const apiCandidates = useMemo(() => {
    const rawApiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';
    return rawApiBase.endsWith('/pm')
      ? [rawApiBase, rawApiBase.replace(/\/pm$/, '')]
      : [rawApiBase, `${rawApiBase}/pm`];
  }, []);

  // Check for existing PM session cookie, then bootstrap from DataAgent session cookie.
  useEffect(() => {
    const checkSessionCookie = async () => {
      const applySession = (sessionData) => {
        setUser(sessionData.user);
        setSessionId(sessionData.session_id);
        localStorage.setItem('user', JSON.stringify(sessionData.user));
        localStorage.setItem('sessionId', sessionData.session_id);
        localStorage.removeItem('selectedWorkspace');
        sessionStorage.removeItem('hasShownFullscreenChat');
        sessionStorage.removeItem('lastShownFullscreenChatUserId');
      };

      try {
        // If user is already authenticated (from localStorage), redirect to home
        if (isAuthenticated) {
          navigate('/home');
          setCheckingSession(false);
          return;
        }

        // Step 1: Check if we have a valid PM session cookie.
        for (const base of apiCandidates) {
          try {
            const sessionCheck = await axios.get(
              `${base}/api/auth/session`,
              { withCredentials: true }
            );

            if (sessionCheck.data?.success && sessionCheck.data?.session_id && sessionCheck.data?.user) {
              applySession(sessionCheck.data);
              navigate('/home');
              setCheckingSession(false);
              return;
            }
          } catch (sessionError) {
            // try next candidate
          }
        }

        // Step 2: Bootstrap PM session from DataAgent session cookie (no URL email needed).
        for (const base of apiCandidates) {
          try {
            const bootstrap = await axios.post(
              `${base}/api/auth/login-by-session-email`,
              {},
              { withCredentials: true }
            );

            if (bootstrap.data?.success && bootstrap.data?.session_id && bootstrap.data?.user) {
              applySession(bootstrap.data);
              navigate('/home');
              setCheckingSession(false);
              return;
            }
          } catch (bootstrapError) {
            // try next candidate
          }
        }

        // Step 3: Fallback bootstrap using known signed-in email.
        let fallbackEmail = localStorage.getItem('user_email');
        if (!fallbackEmail) {
          try {
            const verify = await axios.get(
              `${baseBackend}/api/verify-session`,
              { withCredentials: true }
            );
            if (verify.data?.authenticated && verify.data?.email) {
              fallbackEmail = verify.data.email;
              localStorage.setItem('user_email', fallbackEmail);
            }
          } catch (_verifyErr) {
            // Ignore; fallback email may still come from localStorage.
          }
        }

        if (fallbackEmail) {
          for (const base of apiCandidates) {
            try {
              const emailLogin = await axios.get(
                `${base}/api/auth/login-by-email`,
                {
                  params: { email: fallbackEmail, format: 'json' },
                  withCredentials: true
                }
              );
              if (emailLogin.data?.success && emailLogin.data?.session_id && emailLogin.data?.user) {
                applySession(emailLogin.data);
                navigate('/home');
                setCheckingSession(false);
                return;
              }
            } catch (_emailLoginError) {
              // try next candidate
            }
          }
        }
      } catch (error) {
        console.error('Error checking session:', error);
      } finally {
        setCheckingSession(false);
      }
    };

    checkSessionCookie();
  }, [isAuthenticated, navigate, setUser, setSessionId, location, apiCandidates, baseBackend]);

  const handleGoogleLogin = async () => {
    setLoading(true);
    setError('');

    try {
      const result = await loginWithGoogle();
      if (result && result.success === false) {
        setError(result.message || 'Google OAuth failed. Please try again.');
        setLoading(false);
      }
      // If successful, loginWithGoogle will redirect to Google OAuth
      // Don't set loading to false here as we're redirecting
    } catch (error) {
      setError('An unexpected error occurred. Please try again.');
      setLoading(false);
    }
  };

  // Show loading state while checking for session cookie
  if (checkingSession) {
    return (
      <div className="pm-scope landing-page">
        <div className="main-content" style={{ textAlign: 'center' }}>
          <p>Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="pm-scope landing-page">
      <header className="top-bar">
        <img src="/forsys-logo.png" alt="Forsys Logo" className="forsys-logo" />
      </header>

      <div className="main-content">
        <h1 className="main-heading">Welcome to PM Portal</h1>
        <p className="sub-text">
          Engage, plan, and collaborate effectively with your team using the PM portal built for Forsys employees.
        </p>

        <button
          className="google-login-btn"
          onClick={handleGoogleLogin}
          disabled={loading}
        >
          <img
            src="https://developers.google.com/identity/images/g-logo.png"
            alt="Google"
            className="google-icon-img"
          />
          {loading ? 'Logging in...' : 'Login with Google'}
        </button>

        {error && <div className="error-message">{error}</div>}
      </div>
    </div>
  );
};

export default LandingPage;
