import React, { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate } from "react-router-dom";
import GoogleDrivePicker from '../profiling/GoogleDrivePicker';

const DriveSelection = () => {
    const location = useLocation();
    const navigate = useNavigate();
    const [sourceFile, setSourceFile] = useState(null);
    const [targetFile, setTargetFile] = useState(null);
    const [loading, setLoading] = useState(false);
    const [currentPickerTarget, setCurrentPickerTarget] = useState(null);
    const [cardVisible, setCardVisible] = useState(false);
    const [email, setEmail] = useState(null);
    const showLoader = (msg = "Loading...") => setLoading(msg);
    const hideLoader = () => setLoading(false);
    const drivePickerRef = useRef(null);
    
    useEffect(() => {
        // 1. Get params from URL (Passed from MappingOptions)
        const queryParams = new URLSearchParams(window.location.search);
        const urlEmail = queryParams.get("email");

        // 2. Get params from LocalStorage (Refresh / Back Button)
        const storedEmail = localStorage.getItem("user_email");

        if (urlEmail && urlEmail !== "undefined") {
            console.log("📥 Receiving Session in Drive Selection...");
            
            // Save valid data to storage
            localStorage.setItem("user_email", urlEmail);

            // Update State
            setEmail(urlEmail);

            // 🧹 Clean the URL
            window.history.replaceState({}, document.title, window.location.pathname);
        } 
        else if (storedEmail && storedEmail !== "undefined") {
            console.log("♻️ Restoring Session from Storage...");
            setEmail(storedEmail);
        } 
        else {
            console.warn("⛔ No session found. Redirecting...");
            // Optional: Redirect to landing page
            // window.location.href = process.env.REACT_APP_BASE_FRONTEND_URL || '/';
        }
        
        setTimeout(() => setCardVisible(true), 100);
    }, []);

    useEffect(() => {
        setTimeout(() => setCardVisible(true), 100);
    }, []);

    const handleSourceSelect = () => {
        showLoader("Opening Google Picker...");
        setCurrentPickerTarget('source');
        if (drivePickerRef.current) {
            drivePickerRef.current.open();
        }
        setTimeout(hideLoader, 500);
    };

    const handleTargetSelect = () => {
        showLoader("Opening Google Picker...");
        setCurrentPickerTarget('target');
        if (drivePickerRef.current) {
            drivePickerRef.current.open();
        }
        setTimeout(hideLoader, 500);
    };

    // ✅ FIXED: Just store file metadata, don't navigate
    const handleGooglePickerFileSelected = async (fileId, fileName, mimeType) => {
        console.log('📁 File selected from Google Picker:', { fileId, fileName, mimeType });
        
        const fileData = {
            id: fileId,
            name: fileName,
            mimeType: mimeType
        };

        // ✅ FIX: Check which file is empty and fill that
    if (!sourceFile && currentPickerTarget === 'source') {
        setSourceFile(fileData);
        console.log('✅ Source file set:', fileData);
    } else if (!targetFile && currentPickerTarget === 'target') {
        setTargetFile(fileData);
        console.log('✅ Target file set:', fileData);
    } else if (!sourceFile) {
        // Fallback: if source is empty, set as source
        setSourceFile(fileData);
        console.log('✅ Source file set (fallback):', fileData);
    } else if (!targetFile) {
        // Fallback: if target is empty, set as target
        setTargetFile(fileData);
        console.log('✅ Target file set (fallback):', fileData);
    }

    setCurrentPickerTarget(null);

    };

    // ✅ NEW: Handle Continue button - make backend API call for mapping
    const handleContinue = async () => {
        if (sourceFile && targetFile) {
            if (!email) {
                alert("Session expired. Please refresh the page.");
                return;
            }

            showLoader("Creating mapping...");

            try {
                // Call backend mapping API
                const formData = new FormData();
                formData.append('email', email);
                console.log(email);
                formData.append('host_file_id', sourceFile.id);
                formData.append('target_file_id', targetFile.id);
                formData.append('host_file_type','source');
                formData.append('target_file_type' , 'target');
                formData.append('host_system', 'Host System'); // You can make this dynamic
                formData.append('target_system', 'Target System'); // You can make this dynamic

                const response = await fetch(`${process.env.REACT_APP_BASE_BACKEND_URL}/api/mapping/smart_mapping_with_files`, {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();

                if (!response.ok) {
                    console.log('response not ok');
                    throw new Error(result.detail || 'Mapping failed');
                }

                console.log('✅ Mapping successful:', result);

                hideLoader();
                alert(`Mapping successful! Result saved to Drive. URL: ${result.file_url}`);

                // Navigate to results page with mapping data
                navigate('/finallink', {
                    state: {
                        sourceFile,
                        targetFile,
                        mappingResult: result,
                        fileUrl: result.file_url,
                        email : email
                    }
                });

            } catch (error) {
                console.error('❌ Mapping error:', error);
                alert(`Error creating mapping: ${error.message}`);
            } finally {
                hideLoader();
            }
        }
    };

    const handleLogout = async () => {
    // 1. Clear Local Storage (Crucial)
    localStorage.removeItem("user_email");
    
    // 3. Redirect to Landing Page
    window.location.href = `${process.env.REACT_APP_BASE_FRONTEND_URL}?action=logout`;
  };


    const isReadyToContinue = sourceFile !== null && targetFile !== null;

    return (
        <>
            <link
                rel="stylesheet"
                href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"
            />

            {/* FIXED TOP-RIGHT LOGOUT BUTTON */}
            <div
                style={{
                    position: "fixed",
                    top: "50px",
                    right: "50px",
                    display: "flex",
                    gap: "12px",
                    zIndex: 9999,
                }}
            >
                <button
                    onClick={() => {
            if (window.confirm('Are you sure you want to logout?')) {
               handleLogout();
            }}}
                    style={{
                        background: "#dc3545",
                        color: "white",
                        border: "none",
                        borderRadius: "10px",
                        padding: "10px 20px",
                        fontWeight: "600",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                        fontSize: "0.95rem",
                        transition: "all 0.3s",
                        boxShadow: "0 4px 12px rgba(220, 53, 69, 0.2)",
                    }}
                    onMouseEnter={(e) => {
                        e.target.style.background = "#bb2d3b";
                        e.target.style.transform = "translateY(-2px)";
                        e.target.style.boxShadow = "0 6px 16px rgba(220, 53, 69, 0.3)";
                    }}
                    onMouseLeave={(e) => {
                        e.target.style.background = "#dc3545";
                        e.target.style.transform = "translateY(0)";
                        e.target.style.boxShadow = "0 4px 12px rgba(220, 53, 69, 0.2)";
                    }}
                >
                    <i className="fas fa-sign-out-alt"></i> Logout
                </button>
            </div>

            {/* Full Screen Container */}
            <div
                style={{
                    background: "linear-gradient(135deg, #f3f6fb 0%, #e8edf7 100%)",
                    color: "#1a2b50",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    height: "100vh",
                    padding: "10px",
                    overflow: "hidden",
                    fontFamily: "'Segoe UI', system-ui, -apple-system, sans-serif",
                }}
            >
                <style>{`
                    @keyframes pulse {
                        0% { transform: scale(1); }
                        50% { transform: scale(1.05); }
                        100% { transform: scale(1); }
                    }
                    @keyframes spin {
                        0% { transform: rotate(0deg); }
                        100% { transform: rotate(360deg); }
                    }
                `}</style>

                {/* Main Card */}
                <div
                    style={{
                        background: "#fff",
                        padding: "35px 28px",
                        borderRadius: "20px",
                        boxShadow: "0 10px 30px rgba(20, 83, 198, 0.12)",
                        textAlign: "center",
                        width: "100%",
                        maxWidth: "480px",
                        position: "relative",
                        overflow: "hidden",
                        opacity: cardVisible ? 1 : 0,
                        transform: cardVisible ? "translateY(0)" : "translateY(20px)",
                        transition: "opacity 0.5s ease, transform 0.5s ease",
                    }}
                >
                    {/* Top Accent */}
                    <div
                        style={{
                            position: "absolute",
                            top: 0,
                            left: 0,
                            right: 0,
                            height: "4px",
                            background: "linear-gradient(90deg, #1453c6, #2a6ce8, #4d8eff)",
                        }}
                    />

                    {/* File Icon */}
                    <div
                        style={{
                            width: "80px",
                            height: "80px",
                            background: "linear-gradient(135deg, #eaf0ff 0%, #d5e1ff 100%)",
                            borderRadius: "20px",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            margin: "0 auto 20px",
                            fontSize: "32px",
                            color: "#1453c6",
                            boxShadow: "0 10px 20px rgba(20, 83, 198, 0.15)",
                            animation: "pulse 2s infinite",
                        }}
                    >
                        <i className="fas fa-folder-open"></i>
                    </div>

                    {/* Title */}
                    <p
                        style={{
                            color: "#5a6c8d",
                            fontSize: "1.25rem",
                            marginBottom: "22px",
                        }}
                    >
                        Select Source and Target Files
                    </p>

                    {/* SOURCE FILE SELECTION */}
                    <div
                        style={{
                            background: "#f8faff",
                            borderRadius: "14px",
                            padding: "16px",
                            marginBottom: "16px",
                            border: "1px solid #e6eeff",
                        }}
                    >
                        <span
                            style={{
                                display: "block",
                                fontSize: "0.85rem",
                                color: "#5a6c8d",
                                marginBottom: "10px",
                            }}
                        >
                            Source File
                        </span>

                        <button
                            onClick={handleSourceSelect}
                            style={{
                                background: "linear-gradient(135deg, #1453c6, #2a6ce8)",
                                color: "white",
                                border: "none",
                                borderRadius: "10px",
                                padding: "10px 20px",
                                fontWeight: "600",
                                cursor: "pointer",
                                fontSize: "0.95rem",
                                transition: "all 0.3s",
                                boxShadow: "0 4px 12px rgba(20, 83, 198, 0.2)",
                                width: "100%",
                            }}
                            onMouseEnter={(e) => {
                                e.target.style.transform = "translateY(-2px)";
                                e.target.style.boxShadow = "0 6px 16px rgba(20, 83, 198, 0.3)";
                            }}
                            onMouseLeave={(e) => {
                                e.target.style.transform = "translateY(0)";
                                e.target.style.boxShadow = "0 4px 12px rgba(20, 83, 198, 0.2)";
                            }}
                        >
                            <i className="fab fa-google-drive"></i> {sourceFile ? 'Change Source File' : 'Select Source File from Drive'}
                        </button>

                        {sourceFile && (
                            <div
                                style={{
                                    marginTop: "12px",
                                    fontWeight: "700",
                                    color: "#1453c6",
                                    fontSize: "0.95rem",
                                    wordBreak: "break-word",
                                }}
                            >
                                <i className="fas fa-check-circle" style={{ color: "#2ecc71", marginRight: "6px" }}></i>
                                {sourceFile.name}
                            </div>
                        )}
                    </div>

                    {/* TARGET FILE SELECTION */}
                    <div
                        style={{
                            background: "#f8faff",
                            borderRadius: "14px",
                            padding: "16px",
                            marginBottom: "20px",
                            border: "1px solid #e6eeff",
                        }}
                    >
                        <span
                            style={{
                                display: "block",
                                fontSize: "0.85rem",
                                color: "#5a6c8d",
                                marginBottom: "10px",
                            }}
                        >
                            Target File
                        </span>

                        <button
                            onClick={handleTargetSelect}
                            style={{
                                background: "linear-gradient(135deg, #1453c6, #2a6ce8)",
                                color: "white",
                                border: "none",
                                borderRadius: "10px",
                                padding: "10px 20px",
                                fontWeight: "600",
                                cursor: "pointer",
                                fontSize: "0.95rem",
                                transition: "all 0.3s",
                                boxShadow: "0 4px 12px rgba(230, 126, 34, 0.2)",
                                width: "100%",
                            }}
                            onMouseEnter={(e) => {
                                e.target.style.transform = "translateY(-2px)";
                                e.target.style.boxShadow = "0 6px 16px rgba(230, 126, 34, 0.3)";
                            }}
                            onMouseLeave={(e) => {
                                e.target.style.transform = "translateY(0)";
                                e.target.style.boxShadow = "0 4px 12px rgba(230, 126, 34, 0.2)";
                            }}
                        >
                            <i className="fab fa-google-drive"></i> {targetFile ? 'Change Target File' : 'Select Target File from Drive'}
                        </button>

                        {targetFile && (
                            <div
                                style={{
                                    marginTop: "12px",
                                    fontWeight: "700",
                                    color: "#1453c6",
                                    fontSize: "0.95rem",
                                    wordBreak: "break-word",
                                }}
                            >
                                <i className="fas fa-check-circle" style={{ color: "#2ecc71", marginRight: "6px" }}></i>
                                {targetFile.name}
                            </div>
                        )}
                    </div>

                    {/* CONFIRM BUTTON */}
                    <button
                        onClick={handleContinue}
                        disabled={!isReadyToContinue || loading}
                        style={{
                            background: !isReadyToContinue || loading
                                ? "#ccc"
                                : "linear-gradient(135deg, #27ae60, #2ecc71)",
                            color: "#fff",
                            padding: "14px 26px",
                            border: "none",
                            borderRadius: "12px",
                            fontSize: "1rem",
                            fontWeight: "600",
                            cursor: !isReadyToContinue || loading ? "not-allowed" : "pointer",
                            transition: "all 0.3s ease",
                            display: "inline-flex",
                            alignItems: "center",
                            justifyContent: "center",
                            gap: "10px",
                            width: "100%",
                        }}
                    >
                        {loading ? (
                            <>
                                <i className="fas fa-spinner fa-spin"></i> {loading}
                            </>
                        ) : (
                            <>
                                <i className="fas fa-check-circle"></i>
                                Confirm & Continue
                            </>
                        )}
                    </button>

                    {/* Loader */}
                    {loading && (
                        <div
                            style={{
                                marginTop: "20px",
                                color: "#5a6c8d",
                                fontSize: "0.95rem",
                                padding: "14px",
                                background: "#f8faff",
                                borderRadius: "12px",
                                border: "1px solid #e6eeff",
                                display: "flex",
                                gap: "10px",
                                justifyContent: "center",
                                alignItems: "center",
                            }}
                        >
                            <div
                                style={{
                                    border: "3px solid rgba(20, 83, 198, 0.2)",
                                    borderTop: "3px solid #1453c6",
                                    borderRadius: "50%",
                                    width: "22px",
                                    height: "22px",
                                    animation: "spin 1s linear infinite",
                                }}
                            />
                            <span>Processing your selection... Please wait</span>
                        </div>
                    )}

                    <div
                        style={{
                            marginTop: "15px",
                            fontSize: "0.8rem",
                            color: "#8a9bb8",
                        }}
                    >
                        Your data is processed securely and never stored.
                    </div>
                </div>

                {/* Back link */}
                <div
                    style={{
                        marginTop: "10px",
                        color: "#5a6c8d",
                        fontSize: "0.9rem",
                    }}
                >
                    <a
                        href={`/mapping/optionsMapping`}
                        style={{
                            color: "#1453c6",
                            textDecoration: "none",
                            display: "inline-flex",
                            gap: "5px",
                            alignItems: "center",
                        }}
                    >
                        <i className="fas fa-arrow-left"></i> Back to Options
                    </a>
                </div>

                {/* Hidden Google Drive Picker */}
                <div style={{ display: 'none' }}>
                    <GoogleDrivePicker
                        ref={drivePickerRef}
                        onFileSelected={handleGooglePickerFileSelected}
                    />
                </div>
            </div>
        </>
    );
};

export default DriveSelection;
