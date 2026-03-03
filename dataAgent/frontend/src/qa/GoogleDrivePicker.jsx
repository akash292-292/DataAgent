import React, { useEffect, useState, forwardRef, useImperativeHandle } from "react";


const GoogleDrivePicker = forwardRef(({ onFileSelected, onReady }, ref) => {
  const [isApiLoaded, setIsApiLoaded] = useState(false);
  const googleAccessToken = localStorage.getItem("google_access_token");
  
  console.log("Google Access Token:", googleAccessToken);
 
  useImperativeHandle(ref, () => ({
    open: handleButtonClick
  }));

  useEffect(() => {
    if (!googleAccessToken) {
      console.error("Google access token missing! Please log in again.");
      return;
    }
     if (googleAccessToken) {
    // 🔍 Check what scopes this token has
    fetch(`https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=${googleAccessToken}`)
      .then(res => res.json())
      .then(data => {
        console.log("🔍 Token Info:", data);
        console.log("📋 Token Scopes:", data.scope);
        console.log("⏰ Expires in:", data.expires_in, "seconds");
        
        // Check if it has drive scope
        const hasPickerScope = data.scope && (
          data.scope.includes('drive') || 
          data.scope.includes('drive.file')
        );
        
        if (!hasPickerScope) {
          console.error("❌ Token missing 'drive' or 'drive.file' scope!");
          console.error("❌ Current scopes:", data.scope);
          alert("Your session doesn't have Drive access. Please logout and login again.");
        } else {
          console.log("✅ Token has required Drive scopes");
        }
        
        // Check if token expired
        if (data.expires_in < 0) {
          console.error("❌ Token has EXPIRED!");
          alert("Your session has expired. Please login again.");
          localStorage.clear();
          window.location.href = '/';
        }
      })
      .catch(err => {
        console.error("❌ Token validation failed:", err);
      });
  }
  
    const script = document.createElement("script");
    script.src = "https://apis.google.com/js/api.js";
    script.onload = () => {
      window.gapi.load("picker", {
        callback: () => {
          console.log("✅ Google Picker API loaded successfully");
          setIsApiLoaded(true);
          
          // ✅ Notify parent that picker is ready
          if (onReady) {
            onReady();
          }
        },
      });
    };

    document.body.appendChild(script);

    return () => {
      if (document.body.contains(script)) {
        document.body.removeChild(script);
      }
    };
  }, [googleAccessToken, onReady]);

  const pickerCallback = (data) => {
    console.log("inside picker call back");
    if (data.action === window.google.picker.Action.PICKED) {
      const doc = data.docs[0];
      const fileId = doc.id;
      const fileName = doc.name;
      const mimeType = doc.mimeType;
      console.log("✅ File selected:", { fileId, fileName, mimeType });
      onFileSelected(fileId, fileName, mimeType);
    }
  };

  const handleButtonClick = () => {
    if (!isApiLoaded) {
      console.error("❌ Google Picker API not loaded yet. Please wait...");
      return;
    }

    if (!googleAccessToken) {
      console.error("❌ No access token available");
      return;
    }

    console.log("🚀 Opening Google Picker...");
    
    const docsView = new window.google.picker.DocsView()
      .setIncludeFolders(true)
      .setSelectFolderEnabled(true)
      .setLabel("My Google Drive")
      .setParent("root");
    
    const apiKey = process.env.REACT_APP_GOOGLE_API_KEY;
    console.log(apiKey);
    
    if (!apiKey) {
      console.error("❌ REACT_APP_GOOGLE_API_KEY not found in environment");
      return;
    }
   console.log("before picker variable");
    const picker = new window.google.picker.PickerBuilder()
      .addView(docsView)
      .setOAuthToken(googleAccessToken)
      
      .setDeveloperKey(apiKey)
      .setCallback(pickerCallback)
      .build();
    console.log("after picker variable");
    picker.setVisible(true);
  };

  // Show loading state
  if (!isApiLoaded) {
    return (
      <div style={{ padding: '10px', color: '#666' }}>
        Loading Google Picker...
      </div>
    );
  }

  return null;
});

export default GoogleDrivePicker;
