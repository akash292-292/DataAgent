import React, { useState, useEffect, useRef } from 'react';
import { useLocation } from "react-router-dom";
import GoogleDrivePicker from './GoogleDrivePicker'; 


const ProfilingOptions = () => {
  const location = useLocation();
  const [email , setEmail] = useState(null);
  const [activeOption, setActiveOption] = useState('drive'); 
  const [selectedFile, setSelectedFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const fileInputRef = useRef(null);
  const drivePickerRef = useRef();
  const [isPickerReady, setIsPickerReady] = useState(false);
//  const [isLoading, setIsLoading] = useState(true);
  const showLoader = (msg = "Loading...") => setLoading(msg);
  const hideLoader = () => setLoading(false);
 
  // useEffect(() => {
  //   // Verify session with backend using cookie
  //   fetch(`${process.env.REACT_APP_BASE_BACKEND_URL}/api/verify-session`, {
  //     credentials: 'include'  // CRITICAL: Sends cookies
  //   })
  //   .then(res => {
  //     if (!res.ok) {
  //       throw new Error('Not authenticated');
  //     }
  //     return res.json();
  //   })
  //   .then(data => {
  //     console.log('Ã¢Å“â€¦ Authenticated:', data.email);
  //     setEmail(data.email);
  //     setToken(data.access_token);
      
  //     // Store access token and email in localStorage for convenience
  //     if (data.access_token) {
  //     }
  //     localStorage.setItem('user_email', data.email);
      
  //     setIsLoading(false);
  //   })
  //   .catch(error => {
  //     console.error('Ã¢ÂÅ’ Auth error:', error);
  //     // Redirect to landing page if not authenticated
  //     window.location.href = `${process.env.REACT_APP_FRONTEND_URL}`;
  //   });
  // }, []);
  
   useEffect(() => {
    // 1. Get params from URL (Passed from Dashboard)
    const queryParams = new URLSearchParams(window.location.search);
    const urlEmail = queryParams.get("email");

    // 2. Get params from LocalStorage (Refresh / Back Button)
    const storedEmail = localStorage.getItem("user_email");

    if (urlEmail && urlEmail !== "undefined") {
      console.log("Ã°Å¸â€œÂ¥ Receiving Session in Profiling Options...");
      
      // Save valid data to storage
      localStorage.setItem("user_email", urlEmail);

      // Update State
      setEmail(urlEmail);

      // Ã°Å¸Â§Â¹ Clean the URL
      window.history.replaceState({}, document.title, window.location.pathname);
    } 
    else if (storedEmail && storedEmail !== "undefined") {
      console.log("Ã¢â„¢Â»Ã¯Â¸Â Restoring Session from Storage...");
      setEmail(storedEmail);
    } 
    else {
      console.warn("Ã¢â€ºâ€ No session found. Redirecting...");
      // Optional: Redirect to landing page if critical
      // window.location.href = process.env.REACT_APP_BASE_FRONTEND_URL;
    }
  }, []);

const showDrive = () => {
  console.log('showing drive');
  setActiveOption('drive'); 
  if (isPickerReady && drivePickerRef.current) {
    drivePickerRef.current.open(); 
  }  
    else {
    console.log("Picker not ready yet...");
  }
  
};
  const showLocal = () => {
    setActiveOption('local');
    // Automatically open file picker when local upload is clicked
    setTimeout(() => {
      if (fileInputRef.current) {
        fileInputRef.current.click();
      }
    }, 100);
  };

  const handleLocalFileChange = (e) => {
  const file = e.target.files[0];
     if (file) {
       setSelectedFile(file);
      
      setTimeout(() => { 
          uploadLocal(file); 
      }, 0);
    }
 };

  
  

  // Ã¢Å“â€¦ NEW: Handle Google Picker file selection
  const handleGooglePickerFileSelected = async (fileId, fileName, mimeType) => {
    if (!email) {
        alert("Session lost. Please refresh or login again.");
        return;
    }

    console.log('Ã°Å¸â€œÂ File selected from Google Picker:', { fileId, fileName, mimeType });
    showLoader("Fetching file from Google Drive...");
    
    try {
      const emailParam = email ? `&email=${encodeURIComponent(email)}` : "";
      const res = await fetch(`${process.env.REACT_APP_BASE_BACKEND_URL}/api/drive/getfile?file_id=${fileId}${emailParam}`, {
        credentials: 'include'
      });
      const data = await res.json();
      
      if (!res.ok) {
        // Show detailed error message
        alert(`Ã¢ÂÅ’ Error: ${data.error}\n\n${data.details || ''}\n\n${data.suggestion || ''}`);
        throw new Error(data.error);
      }
      
      const safePath = data.local_path.replace(/\\/g, '/');
      window.location.href = `/profiling/preview?filename=${encodeURIComponent(fileName)}&local_path=${encodeURIComponent(safePath)}`;
    } catch (err) {
      console.error('Error fetching file:', err);
    } finally {
      hideLoader();
    }
  };
  const uploadLocal = async (fileToUpload) => {
    const file = fileToUpload || selectedFile;

    if (!file) return alert("Please select a file first");
    if (!email) return alert("Session lost. Please refresh or login again.");

    const form = new FormData();
    form.append('email', email);
    form.append('file', file);
    showLoader("Uploading file...");
    try {
      const res = await fetch(`${process.env.REACT_APP_BASE_BACKEND_URL}/api/upload_local`, { method: 'POST', body: form });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      const safePath = data.local_path.replace(/\\/g, '/');
      window.location.href = `/profiling/preview?filename=${encodeURIComponent(data.name)}&local_path=${encodeURIComponent(safePath)}`;
    } catch (err) {
      alert(err.message);
    } finally {
      hideLoader();
    }
  };
  const handleLogout = async () => {
    // 1. Clear Local Storage (Crucial)
    localStorage.removeItem("user_email");
    
    // 3. Redirect to Landing Page
    window.location.href = `${process.env.REACT_APP_BASE_FRONTEND_URL}?action=logout`;
  };


  useEffect(() => {
    showDrive();
  }, []);

  
  return (
    <div style={{
      background: 'linear-gradient(135deg, #f3f6fb 0%, #e8edf7 100%)',
      color: '#1a2b50',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100vh',
      height: '100vh',
      overflow: 'hidden',
      padding: '20px',
      fontFamily: "'Segoe UI', system-ui, -apple-system, sans-serif",
      margin: 0,
      boxSizing: 'border-box',
      position: 'relative'
    }}>
      <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
      
      {/* Top Right Buttons */}
      <div style={{ 
        position: 'fixed',
        top: '50px',
        right: '50px',
        display: 'flex',
        gap: '12px',
        alignItems: 'center',
        zIndex: 10
      }}>
        <button
          onClick={() => window.location.href = `/dashboard`}
          style={{
            background: 'linear-gradient(135deg, #1453c6, #2a6ce8)',
            color: 'white',
            border: 'none',
            borderRadius: '10px',
            padding: '10px 20px',
            fontWeight: '600',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '0.95rem',
            transition: 'all 0.3s',
            boxShadow: '0 4px 12px rgba(20, 83, 198, 0.2)'
          }}
          onMouseEnter={(e) => {
            e.target.style.transform = 'translateY(-2px)';
            e.target.style.boxShadow = '0 6px 16px rgba(20, 83, 198, 0.3)';
          }}
          onMouseLeave={(e) => {
            e.target.style.transform = 'translateY(0)';
            e.target.style.boxShadow = '0 4px 12px rgba(20, 83, 198, 0.2)';
          }}
        >
          <i className="fas fa-arrow-left"></i> Back
        </button>

        <button
          onClick={() => {
            if (window.confirm('Are you sure you want to logout?')) {
               handleLogout();
            }}
          }
          style={{ 
            background: '#dc3545',
            color: 'white',
            border: 'none',
            borderRadius: '10px',
            padding: '10px 20px',
            fontWeight: '600',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '0.95rem',
            transition: 'all 0.3s',
            boxShadow: '0 4px 12px rgba(220, 53, 69, 0.2)'
          }}
          onMouseEnter={(e) => {
            e.target.style.background = '#bb2d3b';
            e.target.style.transform = 'translateY(-2px)';
            e.target.style.boxShadow = '0 6px 16px rgba(220, 53, 69, 0.3)';
          }}
          onMouseLeave={(e) => {
            e.target.style.background = '#dc3545';
            e.target.style.transform = 'translateY(0)';
            e.target.style.boxShadow = '0 4px 12px rgba(220, 53, 69, 0.2)';
          }}
        >
          <i className="fas fa-sign-out-alt"></i> Logout
        </button>
      </div>
      
      <input
  type="file"
  ref={fileInputRef}
  onChange={handleLocalFileChange}
  style={{ display: 'none' }}
  // You might want to restrict file types
  accept=".csv,.xls,.xlsx" 
/>
      {/* Main Container */}
      <div style={{
        width: '100%',
        maxWidth: '700px'
      }}>
        <div style={{
          background: '#fff',
          padding: '30px',
          borderRadius: '20px',
          boxShadow: '0 15px 40px rgba(20, 83, 198, 0.12)',
          textAlign: 'center',
          position: 'relative',
          overflow: 'hidden'
        }}>
          <div style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: '4px',
            background: 'linear-gradient(90deg, #1453c6, #2a6ce8, #4d8eff)'
          }} />

          <div style={{ marginBottom: '25px' }}>
            <p style={{
              color: '#5a6c8d',
              fontSize: '1.5rem',
              margin: 0,
              fontWeight: '500'
            }}>Select the file on which you want me to work on!</p>
          </div>

          {/* Option Cards */}
          <div style={{
            display: 'flex',
            gap: '15px',
            marginBottom: '25px',
            justifyContent: 'center',
            flexWrap: 'wrap'
          }}>
            <div 
              onClick={showDrive}
              style={{
                background: activeOption === 'drive' ? 'linear-gradient(135deg, #f0f5ff, #e6eeff)' : '#f8faff',
                borderRadius: '14px',
                padding: '20px',
                width: '200px',
                cursor: 'pointer',
                transition: 'all 0.3s ease',
                border: activeOption === 'drive' ? '2px solid #2a6ce8' : '2px solid transparent',
                textAlign: 'center'
              }}
            >
              <div style={{
                width: '50px',
                height: '50px',
                background: 'linear-gradient(135deg, #eaf0ff, #d5e1ff)',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 12px',
                color: '#1453c6'
              }}>
                <i className="fab fa-google-drive" style={{ fontSize: '22px' }}></i>
              </div>
              <div style={{
                fontSize: '1.05rem',
                fontWeight: '600',
                marginBottom: '6px',
                color: '#1a2b50'
              }}>Google Drive</div>
              <div style={{
                color: '#5a6c8d',
                fontSize: '0.8rem',
                lineHeight: '1.4'
              }}>Access from Drive</div>
            </div>

            <div 
              onClick={showLocal}
              style={{
                background: activeOption === 'local' ? 'linear-gradient(135deg, #f0f5ff, #e6eeff)' : '#f8faff',
                borderRadius: '14px',
                padding: '20px',
                width: '200px',
                cursor: 'pointer',
                transition: 'all 0.3s ease',
                border: activeOption === 'local' ? '2px solid #2a6ce8' : '2px solid transparent',
                textAlign: 'center'
              }}
            >
              <div style={{
                width: '50px',
                height: '50px',
                background: 'linear-gradient(135deg, #eaf0ff, #d5e1ff)',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 12px',
                color: '#1453c6'
              }}>
                <i className="fas fa-upload" style={{ fontSize: '22px' }}></i>
              </div>
              <div style={{
                fontSize: '1.05rem',
                fontWeight: '600',
                marginBottom: '6px',
                color: '#1a2b50'
              }}>Local Upload</div>
              <div style={{
                color: '#5a6c8d',
                fontSize: '0.8rem',
                lineHeight: '1.4'
              }}>Upload from computer</div>
            </div>
          </div>
        </div>
      </div>
      
      <div style={{ display: 'none' }}>
    <GoogleDrivePicker 
      ref={drivePickerRef} 
      onFileSelected={handleGooglePickerFileSelected} 
      onReady = {() => {setIsPickerReady(true)}}
    />
</div>
      {/* Loader */}
      {loading && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          background: 'rgba(255, 255, 255, 0.95)',
          zIndex: 9999,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'column'
        }}>
          <div style={{
            border: '4px solid #e6eeff',
            borderTop: '4px solid #1a73e8',
            borderRadius: '50%',
            width: '50px',
            height: '50px',
            animation: 'spin 1s linear infinite',
            marginBottom: '15px'
          }} />
          <div style={{
            fontSize: '1.1rem',
            color: '#1a2b50',
            fontWeight: '600'
          }}>{loading}</div>
          <style>{`
            @keyframes spin {
              100% { transform: rotate(360deg); }
            }
          `}</style>
        </div>
      )}
    </div>
  );
};

export default ProfilingOptions;

