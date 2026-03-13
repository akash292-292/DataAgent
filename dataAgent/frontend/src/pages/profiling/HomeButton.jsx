import React from 'react';
import { useNavigate , useLocation } from 'react-router-dom';

const HomeButton = ({ email, position = 'absolute' }) => {
  const navigate = useNavigate();
  const location = useLocation();


  if (
    location.pathname.startsWith("/mapping/") ||
    location.pathname.startsWith("/profiling/")
  ) {
    return (
      <div 
      style={{
        position : 'fixed',
        top: "50px",               
        left: "50px",
        background: "linear-gradient(135deg, #6f42c1, #8c63d3)",
        color: 'white',
        width: '40px',
        height: '40px',
        borderRadius: '10px',
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        boxShadow: '0 4px 12px rgba(111, 66, 193, 0.3)',
        cursor: 'pointer',
        transition: 'transform 0.2s ease',
        zIndex: 9999
      }}
      onClick={() => navigate(`/dashboard`)}
      onMouseEnter={(e) => e.currentTarget.style.transform = 'scale(1.1)'}
      onMouseLeave={(e) => e.currentTarget.style.transform = 'scale(1)'}
    >
      <i className="fas fa-home"></i>
    </div>
  );
  }
  return null;
};

export default HomeButton;
