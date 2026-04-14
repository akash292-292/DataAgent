import { useEffect, forwardRef, useImperativeHandle } from "react";


const GoogleDrivePicker = forwardRef(({ onFileSelected, onReady, accessToken: accessTokenProp, multiSelect = false }, ref) => {

  const getToken = () => accessTokenProp || localStorage.getItem("google_access_token");

  useImperativeHandle(ref, () => ({
    open: (tokenOverride) => handleButtonClick(tokenOverride)
  }));

  useEffect(() => {
    // Ensure the picker module is loaded (idempotent — safe to call even if already loaded)
    const loadPickerModule = () => {
      window.gapi.load("picker", {
        callback: () => {
          console.log("Google Picker API loaded successfully");
          if (onReady) onReady();
        },
      });
    };

    if (window.gapi) {
      loadPickerModule();
      return;
    }

    const script = document.createElement("script");
    script.src = "https://apis.google.com/js/api.js";
    script.onload = loadPickerModule;
    document.body.appendChild(script);

    return () => {
      if (document.body.contains(script)) {
        document.body.removeChild(script);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onReady]);

  const handleButtonClick = (tokenOverride) => {
    // Check window directly — no async state needed since index.html loads the picker module
    if (!window.google?.picker) {
      console.error("Google Picker API not ready. Please wait a moment.");
      return;
    }

    const token = tokenOverride || getToken();
    if (!token) {
      console.error("No access token available");
      return;
    }

    const apiKey = process.env.REACT_APP_GOOGLE_API_KEY;
    if (!apiKey) {
      console.error("REACT_APP_GOOGLE_API_KEY not found in environment");
      return;
    }

    console.log("Opening Google Picker...");

    const docsView = new window.google.picker.DocsView()
      .setIncludeFolders(true)
      .setSelectFolderEnabled(true)
      .setLabel("My Google Drive")
      .setParent("root");

    const builder = new window.google.picker.PickerBuilder()
      .addView(docsView)
      .setOAuthToken(token)
      .setDeveloperKey(apiKey)
      .setOrigin(window.location.protocol + '//' + window.location.host)
      .setCallback(pickerCallback);

    if (multiSelect) {
      builder.enableFeature(window.google.picker.Feature.MULTISELECT_ENABLED);
    }

    const picker = builder.build();
    picker.setVisible(true);
  };

  const pickerCallback = (data) => {
    console.log("Picker action:", data.action);
    if (data.action === window.google.picker.Action.PICKED) {
      if (multiSelect) {
        onFileSelected(data.docs);
      } else {
        const doc = data.docs[0];
        onFileSelected(doc.id, doc.name, doc.mimeType);
      }
    }
  };

  return null;
});

export default GoogleDrivePicker;