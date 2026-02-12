import React, { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';

const AuthContext = createContext();

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check for existing session on app load
    const savedSession = localStorage.getItem('sessionId');
    const savedUser = localStorage.getItem('user');
    
    if (savedSession && savedUser) {
      setSessionId(savedSession);
      setUser(JSON.parse(savedUser));
    }
    
    setLoading(false);
  }, []);

  const login = async (email = 'demo@example.com', name = 'Demo User') => {
    try {
      // For now, keep demo login for testing
      // TODO: Implement real Google OAuth
      const demoUser = {
        id: 1,
        email: email,
        name: name,
        google_id: `demo_${Math.random().toString(36).substr(2, 9)}`
      };
      
      const demoSessionId = `demo_session_${Date.now()}`;
      
      // Clear any existing workspace selection on login
      localStorage.removeItem('selectedWorkspace');
      
      setSessionId(demoSessionId);
      setUser(demoUser);
      
      // Save to localStorage
      localStorage.setItem('sessionId', demoSessionId);
      localStorage.setItem('user', JSON.stringify(demoUser));
      
      return { success: true };
    } catch (error) {
      console.error('Login error:', error);
      return { success: false, message: 'Login failed. Please try again.' };
    }
  };

  const loginWithGoogle = async () => {
    try {
      // Get Google OAuth URL from backend
      const response = await axios.get(`${process.env.REACT_APP_API_URL}/api/auth/google/url`);
      const { auth_url, error } = response.data;
      
      if (error || !auth_url) {
        console.error('Google OAuth configuration error:', error);
        return { 
          success: false, 
          message: error || 'Google OAuth not configured. Please contact your administrator.' 
        };
      }
      
      // Redirect to Google OAuth
      window.location.href = auth_url;
    } catch (error) {
      console.error('Google OAuth error:', error);
      return { success: false, message: 'Google OAuth failed. Please try again.' };
    }
  };

  const logout = async () => {
    try {
      // Demo: Skip API call and just clear local state
      console.log('Demo logout - skipping API call');
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      // Clear session regardless of API response
      setUser(null);
      setSessionId(null);
      localStorage.removeItem('sessionId');
      localStorage.removeItem('user');
      // Clear sessionStorage to reset chatbot fullscreen flags
      sessionStorage.removeItem('hasShownFullscreenChat');
      sessionStorage.removeItem('lastShownFullscreenChatUserId');
    }
  };

  const value = {
    user,
    sessionId,
    loading,
    login,
    loginWithGoogle,
    logout,
    setUser,
    setSessionId,
    isAuthenticated: !!user && !!sessionId
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}; 