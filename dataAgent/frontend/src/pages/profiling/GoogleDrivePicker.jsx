import React, { useEffect, useState, forwardRef, useImperativeHandle } from "react";

const GoogleDrivePicker = forwardRef(({ onFileSelected, onReady }, ref) => {
  const [isApiLoaded, setIsApiLoaded] = useState(false);
  const [googleAccessToken, setGoogleAccessToken] = useState(null);
  const [tokenError, setTokenError] = useState("");

  const fetchPickerToken = async () => {
    try {
      const storedEmail = localStorage.getItem("user_email");
      const emailParam = storedEmail ? `?email=${encodeURIComponent(storedEmail)}` : "";
      const tokenResp = await fetch(
        `${process.env.REACT_APP_BASE_BACKEND_URL}/api/drive/picker-token${emailParam}`,
        { credentials: "include" }
      );
      if (!tokenResp.ok) {
        setTokenError("Failed to get Drive session token.");
        return null;
      }
      const data = await tokenResp.json();
      if (data?.access_token) {
        setGoogleAccessToken(data.access_token);
        setTokenError("");
        return data.access_token;
      }
      setTokenError("Invalid Drive token response.");
      return null;
    } catch (_err) {
      setTokenError("Unable to reach backend for Drive token.");
      return null;
    }
  };

  useImperativeHandle(ref, () => ({
    open: handleButtonClick,
  }));

  useEffect(() => {
    const init = async () => {
      await fetchPickerToken();

      const script = document.createElement("script");
      script.src = "https://apis.google.com/js/api.js";
      script.onload = () => {
        window.gapi.load("picker", {
          callback: () => {
            setIsApiLoaded(true);
            if (onReady) onReady();
          },
        });
      };
      document.body.appendChild(script);
    };

    init();

    return () => {
      const scripts = document.querySelectorAll('script[src="https://apis.google.com/js/api.js"]');
      scripts.forEach((s) => {
        if (document.body.contains(s)) {
          document.body.removeChild(s);
        }
      });
    };
  }, [onReady]);

  const pickerCallback = (data) => {
    if (data.action === window.google.picker.Action.PICKED) {
      const doc = data.docs[0];
      onFileSelected(doc.id, doc.name, doc.mimeType);
    }
  };

  const handleButtonClick = () => {
    if (!isApiLoaded) return;
    const apiKey = process.env.REACT_APP_GOOGLE_API_KEY;
    if (!apiKey) return;

    const openPicker = async () => {
      const token = googleAccessToken || (await fetchPickerToken());
      if (!token) return;

      const docsView = new window.google.picker.DocsView()
        .setIncludeFolders(true)
        .setSelectFolderEnabled(true)
        .setLabel("My Google Drive")
        .setParent("root");

      const picker = new window.google.picker.PickerBuilder()
        .addView(docsView)
        .setOAuthToken(token)
        .setDeveloperKey(apiKey)
        .setCallback(pickerCallback)
        .build();

      picker.setVisible(true);
    };

    openPicker();
  };

  if (!isApiLoaded || tokenError) {
    return <div style={{ padding: "10px", color: "#666" }}>Loading Google Picker...</div>;
  }

  return null;
});

export default GoogleDrivePicker;
