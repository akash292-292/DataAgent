import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import './GoogleCallback.css';

const EmailLoginCallback = () => {
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const { setUser, setSessionId, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const handleEmailLogin = async () => {
      try {
        // If user is already authenticated, redirect to home
        if (isAuthenticated) {
          navigate('/home');
          return;
        }

        const urlParams = new URLSearchParams(location.search);
        const email = urlParams.get('email');
        const name = urlParams.get('name');

        if (!email) {
          setError('Email parameter is required. Usage: /email-login?email=user@example.com');
          setLoading(false);
          return;
        }

        // First, check if we already have a valid session cookie (from backend redirect)
        try {
          const sessionCheck = await axios.get(
            `${process.env.REACT_APP_API_URL}/api/auth/session`,
            { withCredentials: true }
          );
          
          if (sessionCheck.data?.success && sessionCheck.data?.session_id && sessionCheck.data?.user) {
            // Session already exists from backend redirect, use it
            setUser(sessionCheck.data.user);
            setSessionId(sessionCheck.data.session_id);
            localStorage.setItem('user', JSON.stringify(sessionCheck.data.user));
            localStorage.setItem('sessionId', sessionCheck.data.session_id);
            
            // Clear any existing workspace selection
            localStorage.removeItem('selectedWorkspace');
            // Clear chatbot session flags to ensure it shows on new login
            sessionStorage.removeItem('hasShownFullscreenChat');
            sessionStorage.removeItem('lastShownFullscreenChatUserId');
            
            // Clear the URL parameters to prevent back button issues
            window.history.replaceState({}, document.title, '/email-login');
            navigate('/home');
            return;
          }
        } catch (sessionError) {
          // Session check failed, continue with email login
          console.log('No existing session, proceeding with email login...');
        }

        // No valid session, call the email login endpoint with format=json to get JSON response
        const response = await axios.get(`${process.env.REACT_APP_API_URL}/api/auth/login-by-email`, {
          params: { email, name, format: 'json' }, // Force JSON response
          withCredentials: true // Important for cookies
        });

        if (response.data.success) {
          // Clear any existing workspace selection
          localStorage.removeItem('selectedWorkspace');
          // Clear chatbot session flags to ensure it shows on new login
          sessionStorage.removeItem('hasShownFullscreenChat');
          sessionStorage.removeItem('lastShownFullscreenChatUserId');
          
          setUser(response.data.user);
          setSessionId(response.data.session_id);
          localStorage.setItem('user', JSON.stringify(response.data.user));
          localStorage.setItem('sessionId', response.data.session_id);
          
          // Clear the URL parameters to prevent back button issues
          window.history.replaceState({}, document.title, '/email-login');
          navigate('/home');
        } else {
          setError(response.data.message || 'Email login failed.');
          setLoading(false);
        }
      } catch (error) {
        console.error('Email login error:', error);
        setError(error.response?.data?.message || error.message || 'Email login failed. Please try again.');
        setLoading(false);
      }
    };

    handleEmailLogin();
  }, [location, navigate, setUser, setSessionId, isAuthenticated]);

  if (loading && !error) {
    return (
      <div className="pm-scope callback-page">
        <div className="container">
          <div className="card">
            <div className="text-center">
              <div className="loading-spinner" style={{
                border: '4px solid #f3f3f3',
                borderTop: '4px solid #007bff',
                borderRadius: '50%',
                width: '50px',
                height: '50px',
                animation: 'spin 1s linear infinite',
                margin: '0 auto 20px'
              }}></div>
              <h2>Logging in...</h2>
              <p>Please wait while we authenticate you.</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="pm-scope callback-page">
        <div className="container">
          <div className="card">
            <div className="text-center">
              <div className="error-icon">❌</div>
              <h2>Authentication Failed</h2>
              <p className="error-message">{error}</p>
              <button className="btn" onClick={() => navigate('/')}>
                Back to Login
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return null;
};

export default EmailLoginCallback;

