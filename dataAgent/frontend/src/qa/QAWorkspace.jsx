import React, { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import * as XLSX from "xlsx";
import GoogleDrivePicker from "../pages/profiling/GoogleDrivePicker";

const EXCEL_EXTS = ["xlsx", "xls"];

const getExt = (name = "") => name.split(".").pop().toLowerCase();

const QAWorkspace = ({ title, helperText, mode }) => {
  const navigate = useNavigate();
  const pickerRef = useRef();

  // =========================
  // STATE
  // =========================
  const [uploadedFile, setUploadedFile] = useState(null);  // local File object (CSV after sheet selection)
  const [driveFileId, setDriveFileId] = useState(null);    // Google Drive file ID
  const [fileName, setFileName] = useState("");             // display name

  const [query, setQuery] = useState("");        // requirements: optional focus area
  const [userStory, setUserStory] = useState(""); // test cases: user story text

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [analysis, setAnalysis] = useState(null);      // requirements result
  const [tcSummary, setTcSummary] = useState(null);    // test case summary
  const [downloadUrl, setDownloadUrl] = useState(null);
  const [totalTestCases, setTotalTestCases] = useState(null);

  // Excel / sheet selection
  const [excelSheets, setExcelSheets] = useState([]);
  const [showSheetModal, setShowSheetModal] = useState(false);
  const [selectedSheet, setSelectedSheet] = useState("");
  const [pendingExcelBuffer, setPendingExcelBuffer] = useState(null);
  const [excelSourceName, setExcelSourceName] = useState(""); // original Excel filename

  // =========================
  // RESET ON MOUNT
  // =========================
  useEffect(() => {
    setUploadedFile(null);
    setDriveFileId(null);
    setFileName("");
    setQuery("");
    setUserStory("");
    setLoading(false);
    setError("");
    setAnalysis(null);
    setTcSummary(null);
    setDownloadUrl(null);
    setTotalTestCases(null);
    setExcelSheets([]);
    setShowSheetModal(false);
    setSelectedSheet("");
    setPendingExcelBuffer(null);
    setExcelSourceName("");
  }, []);

  // =========================
  // EXCEL HELPERS
  // =========================
  const processExcelBuffer = (buffer, originalName) => {
    const workbook = XLSX.read(buffer, { type: "array" });
    const sheets = workbook.SheetNames;
    setExcelSourceName(originalName);
    setExcelSheets(sheets);
    setSelectedSheet(sheets[0]);
    setPendingExcelBuffer(buffer);
    setShowSheetModal(true);
  };

  const applySheetSelection = (buffer, sheetName, originalName) => {
    const workbook = XLSX.read(buffer, { type: "array" });
    const worksheet = workbook.Sheets[sheetName];
    const csv = XLSX.utils.sheet_to_csv(worksheet);
    const blob = new Blob([csv], { type: "text/csv" });
    const csvFile = new File([blob], `${sheetName}.csv`, { type: "text/csv" });

    setUploadedFile(csvFile);
    setDriveFileId(null);
    setFileName(`${originalName}  ›  ${sheetName}`);

    // Pre-fill focus area with sheet name if currently empty
    if (mode === "requirements") {
      setQuery(prev => prev.trim() ? prev : sheetName);
    } else {
      setUserStory(prev => prev.trim() ? prev : sheetName);
    }

    setShowSheetModal(false);
    setPendingExcelBuffer(null);
    setExcelSourceName("");
  };

  const handleSheetConfirm = () => {
    if (!selectedSheet || !pendingExcelBuffer) return;
    applySheetSelection(pendingExcelBuffer, selectedSheet, excelSourceName);
  };

  const handleSheetCancel = () => {
    setShowSheetModal(false);
    setPendingExcelBuffer(null);
    setExcelSourceName("");
    setFileName("");
    setUploadedFile(null);
    setDriveFileId(null);
  };

  // =========================
  // FILE HANDLERS
  // =========================
  const handleLocalUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const ext = getExt(file.name);

    setAnalysis(null);
    setTcSummary(null);
    setDownloadUrl(null);
    setTotalTestCases(null);
    setError("");

    if (EXCEL_EXTS.includes(ext)) {
      setFileName(file.name);
      setUploadedFile(null);
      setDriveFileId(null);
      const reader = new FileReader();
      reader.onload = (evt) => processExcelBuffer(evt.target.result, file.name);
      reader.readAsArrayBuffer(file);
    } else {
      setUploadedFile(file);
      setDriveFileId(null);
      setFileName(file.name);
    }
  };

  const handleDriveFileSelected = async (fileId, pickedFileName) => {
    const ext = getExt(pickedFileName);
    setFileName(pickedFileName);
    setAnalysis(null);
    setTcSummary(null);
    setDownloadUrl(null);
    setTotalTestCases(null);
    setError("");

    if (EXCEL_EXTS.includes(ext)) {
      // Fetch raw bytes from backend so SheetJS can parse them client-side
      setLoading(true);
      try {
        const formData = new FormData();
        formData.append("file_id", fileId);
        const email = localStorage.getItem("user_email");
        if (email) formData.append("email", email);

        const res = await fetch(
          `${process.env.REACT_APP_BASE_BACKEND_URL}/api/qa/excel/fetch-bytes`,
          { method: "POST", credentials: "include", body: formData }
        );
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || "Failed to fetch Excel file from Drive");
        }
        const arrayBuffer = await res.arrayBuffer();
        setDriveFileId(fileId);
        setUploadedFile(null);
        processExcelBuffer(arrayBuffer, pickedFileName);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    } else {
      setDriveFileId(fileId);
      setUploadedFile(null);
    }
  };

  // =========================
  // SUBMIT
  // =========================
  const handleSubmit = async () => {
    if (loading) return;
    setLoading(true);
    setError("");
    setAnalysis(null);
    setTcSummary(null);
    setDownloadUrl(null);
    setTotalTestCases(null);

    try {
      if (mode === "requirements") {
        const formData = new FormData();

        if (uploadedFile) {
          formData.append("file", uploadedFile);
          const email = localStorage.getItem("user_email");
          if (email) formData.append("email", email);
        } else if (driveFileId) {
          formData.append("file_id", driveFileId);
          if (fileName) formData.append("drive_filename", fileName);
          const email = localStorage.getItem("user_email");
          if (email) formData.append("email", email);
        }

        if (query.trim()) formData.append("user_prompt", query);

        const response = await fetch(
          `${process.env.REACT_APP_BASE_BACKEND_URL}/api/qa/requirements/analyze`,
          { method: "POST", credentials: "include", body: formData }
        );
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Analysis failed");
        setAnalysis(data.analysis);

      } else {
        const formData = new FormData();

        if (uploadedFile) {
          formData.append("file", uploadedFile);
          const email = localStorage.getItem("user_email");
          if (email) formData.append("email", email);
        } else if (driveFileId) {
          formData.append("file_id", driveFileId);
          if (fileName) formData.append("drive_filename", fileName);
          const email = localStorage.getItem("user_email");
          if (email) formData.append("email", email);
        }

        if (userStory.trim()) formData.append("user_story", userStory);

        const response = await fetch(
          `${process.env.REACT_APP_BASE_BACKEND_URL}/api/qa/test-cases/generate`,
          { method: "POST", credentials: "include", body: formData }
        );
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Generation failed");
        setTcSummary(data.summary || "Test cases generated successfully.");
        setDownloadUrl(`${process.env.REACT_APP_BASE_BACKEND_URL}${data.download_url}`);
        setTotalTestCases(data.total_test_cases);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const hasFile = uploadedFile || driveFileId;

  const isDisabled =
    loading ||
    !hasFile;

  return (
    <div style={pageWrap}>
      <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />

      {/* HEADER */}
      <div style={headerRow}>
        <div>
          <h2 style={{ margin: 0, color: "#1a2b50", fontSize: "1.4rem" }}>{title}</h2>
          <p style={{ margin: "4px 0 0", color: "#5a6c8d", fontSize: "0.9rem" }}>{helperText}</p>
        </div>
        <button onClick={() => navigate("/qa")} style={backBtn}>
          <i className="fas fa-arrow-left" /> Back
        </button>
      </div>

      {/* INPUT CARD */}
      <div style={card}>
        <div style={accentBar} />

        {/* ── REQUIREMENTS MODE ── */}
        {mode === "requirements" && (
          <>
            <p style={sectionLabel}>Upload Document</p>

            <div style={uploadRow}>
              <label style={uploadBox}>
                <i className="fas fa-folder-open" style={{ color: "#1453c6", marginRight: 8 }} />
                Upload from Local
                <input type="file" hidden accept=".txt,.pdf,.docx,.xlsx,.xls" onChange={handleLocalUpload} />
              </label>

              <button style={driveBox} onClick={() => pickerRef.current?.open()}>
                <i className="fab fa-google-drive" style={{ color: "#1453c6", marginRight: 8 }} />
                Upload from Drive
              </button>
            </div>

            {fileName ? (
              <div style={fileChip}>
                <i className="fas fa-file-alt" style={{ color: "#1453c6", marginRight: 6 }} />
                {fileName}
              </div>
            ) : (
              <p style={hint}>Supported: .txt, .pdf, .docx, .xlsx, .xls</p>
            )}

            <p style={{ ...sectionLabel, marginTop: 20 }}>
              Focus Area{" "}
              <span style={{ color: "#aaa", fontWeight: 400 }}>(optional)</span>
            </p>
            <textarea
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="e.g. Focus on security and integration requirements only…"
              rows={3}
              style={textarea}
            />
          </>
        )}

        {/* ── TEST CASES MODE ── */}
        {mode === "testcases" && (
          <>
            <p style={sectionLabel}>Upload Requirements Document</p>

            <div style={uploadRow}>
              <label style={uploadBox}>
                <i className="fas fa-folder-open" style={{ color: "#1453c6", marginRight: 8 }} />
                Upload from Local
                <input type="file" hidden accept=".txt,.pdf,.docx,.xlsx,.xls" onChange={handleLocalUpload} />
              </label>

              <button style={driveBox} onClick={() => pickerRef.current?.open()}>
                <i className="fab fa-google-drive" style={{ color: "#1453c6", marginRight: 8 }} />
                Upload from Drive
              </button>
            </div>

            {fileName ? (
              <div style={fileChip}>
                <i className="fas fa-file-alt" style={{ color: "#1453c6", marginRight: 6 }} />
                {fileName}
              </div>
            ) : (
              <p style={hint}>Supported: .txt, .pdf, .docx, .xlsx, .xls</p>
            )}

            <p style={{ ...sectionLabel, marginTop: 20 }}>
              User Story / Focus Area{" "}
              <span style={{ color: "#aaa", fontWeight: 400 }}>(optional)</span>
            </p>
            <textarea
              value={userStory}
              onChange={e => setUserStory(e.target.value)}
              placeholder="e.g. Focus on the password reset flow, or paste a specific user story to narrow the test scope…"
              rows={4}
              style={textarea}
            />
          </>
        )}

        {/* ACTION BUTTON */}
        <button
          onClick={handleSubmit}
          disabled={isDisabled}
          style={{
            ...actionBtn,
            ...(isDisabled
              ? { background: "#a0aec0", cursor: "not-allowed", opacity: 0.7 }
              : {})
          }}
        >
          {loading ? (
            <>
              <i className="fas fa-spinner fa-spin" style={{ marginRight: 8 }} />
              Processing…
            </>
          ) : mode === "requirements" ? (
            <>
              <i className="fas fa-search" style={{ marginRight: 8 }} />
              Analyze Requirements
            </>
          ) : (
            <>
              <i className="fas fa-magic" style={{ marginRight: 8 }} />
              Generate Test Cases
            </>
          )}
        </button>

        {/* LOADING INDICATOR */}
        {loading && (
          <div style={loadingBox}>
            <div style={spinnerStyle} />
            <span>Processing your document… Please wait</span>
          </div>
        )}

        {/* ERROR */}
        {error && (
          <div style={errorBox}>
            <i className="fas fa-exclamation-circle" style={{ marginRight: 8 }} />
            {error}
          </div>
        )}
      </div>

      {/* RESULT CARD — REQUIREMENTS */}
      {analysis && (
        <div style={resultCard}>
          <div style={accentBar} />
          <div style={resultHeader}>
            <h3 style={{ margin: 0, color: "#1a2b50" }}>
              <i className="fas fa-check-circle" style={{ color: "#198754", marginRight: 8 }} />
              Analysis Complete
            </h3>
            <button
              style={rerunBtn}
              onClick={() => { setAnalysis(null); setError(""); }}
            >
              <i className="fas fa-redo" style={{ marginRight: 6 }} />
              Re-analyze
            </button>
          </div>
          <pre style={preStyle}>{analysis}</pre>
        </div>
      )}

      {/* RESULT CARD — TEST CASES */}
      {tcSummary && (
        <div style={resultCard}>
          <div style={accentBar} />
          <div style={resultHeader}>
            <h3 style={{ margin: 0, color: "#1a2b50" }}>
              <i className="fas fa-check-circle" style={{ color: "#198754", marginRight: 8 }} />
              Test Cases Generated
            </h3>
            <button
              style={rerunBtn}
              onClick={() => {
                setTcSummary(null);
                setDownloadUrl(null);
                setTotalTestCases(null);
                setError("");
              }}
            >
              <i className="fas fa-redo" style={{ marginRight: 6 }} />
              Generate Again
            </button>
          </div>

          <pre style={preStyle}>{tcSummary}</pre>

          {downloadUrl && (
            <div style={{ marginTop: 16, display: "flex", alignItems: "center", gap: 16 }}>
              <a
                href={downloadUrl}
                target="_blank"
                rel="noopener noreferrer"
                style={downloadLink}
              >
                <i className="fas fa-file-excel" style={{ marginRight: 8 }} />
                Download Excel
              </a>
              {totalTestCases !== null && (
                <span style={{ fontSize: 13, color: "#5a6c8d" }}>
                  Total: <strong>{totalTestCases}</strong> test cases
                </span>
              )}
            </div>
          )}
        </div>
      )}

      {/* DRIVE PICKER — available in both modes */}
      <GoogleDrivePicker ref={pickerRef} onFileSelected={handleDriveFileSelected} />

      {/* SHEET SELECTION MODAL */}
      {showSheetModal && (
        <div style={modalOverlay}>
          <div style={modalCard}>
            <h3 style={{ margin: "0 0 8px", color: "#1a2b50", fontSize: "1.1rem" }}>
              <i className="fas fa-table" style={{ marginRight: 8, color: "#1453c6" }} />
              Select Sheet to Analyze
            </h3>
            <p style={{ color: "#5a6c8d", fontSize: 13, margin: "0 0 20px", lineHeight: 1.5 }}>
              <strong>{excelSourceName}</strong> contains{" "}
              {excelSheets.length} sheet{excelSheets.length !== 1 ? "s" : ""}.
              Select which sheet to use as the requirements document.
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 24, maxHeight: 260, overflowY: "auto", paddingRight: 4 }}>
              {excelSheets.map(sheet => (
                <label key={sheet} style={sheetOptionStyle(sheet === selectedSheet)}>
                  <input
                    type="radio"
                    name="sheet"
                    value={sheet}
                    checked={sheet === selectedSheet}
                    onChange={() => setSelectedSheet(sheet)}
                    style={{ marginRight: 10, accentColor: "#1453c6" }}
                  />
                  <i
                    className="fas fa-table"
                    style={{ marginRight: 8, fontSize: 12, color: sheet === selectedSheet ? "#1453c6" : "#8a9bb5" }}
                  />
                  {sheet}
                </label>
              ))}
            </div>

            <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
              <button style={cancelModalBtn} onClick={handleSheetCancel}>
                Cancel
              </button>
              <button style={confirmModalBtn} onClick={handleSheetConfirm}>
                <i className="fas fa-check" style={{ marginRight: 6 }} />
                Use This Sheet
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        @keyframes spin {
          0%   { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};

/* ========================= STYLES ========================= */

const pageWrap = {
  minHeight: "100vh",
  background: "linear-gradient(135deg, #f3f6fb 0%, #e8edf7 100%)",
  padding: "28px 36px",
  fontFamily: "'Segoe UI', system-ui, -apple-system, sans-serif",
  boxSizing: "border-box",
};

const headerRow = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  marginBottom: 24,
};

const backBtn = {
  background: "linear-gradient(135deg, #1453c6, #2a6ce8)",
  color: "white",
  border: "none",
  padding: "10px 20px",
  borderRadius: 10,
  fontWeight: 600,
  cursor: "pointer",
  fontSize: "0.95rem",
  display: "flex",
  alignItems: "center",
  gap: 8,
  boxShadow: "0 4px 12px rgba(20, 83, 198, 0.2)",
};

const card = {
  background: "#fff",
  borderRadius: 20,
  padding: "32px 28px",
  boxShadow: "0 10px 30px rgba(20, 83, 198, 0.1)",
  position: "relative",
  overflow: "hidden",
  maxWidth: 860,
  marginBottom: 24,
};

const resultCard = {
  background: "#fff",
  borderRadius: 20,
  padding: "32px 28px",
  boxShadow: "0 10px 30px rgba(20, 83, 198, 0.1)",
  position: "relative",
  overflow: "hidden",
  maxWidth: 860,
  marginBottom: 24,
};

const accentBar = {
  position: "absolute",
  top: 0,
  left: 0,
  right: 0,
  height: 4,
  background: "linear-gradient(90deg, #1453c6, #2a6ce8, #4d8eff)",
};

const sectionLabel = {
  fontWeight: 600,
  color: "#1a2b50",
  fontSize: "0.95rem",
  marginBottom: 10,
  marginTop: 0,
};

const uploadRow = {
  display: "flex",
  gap: 12,
  marginBottom: 12,
};

const uploadBox = {
  flex: 1,
  padding: "14px 16px",
  border: "1px dashed #1453c6",
  borderRadius: 12,
  cursor: "pointer",
  background: "#f8faff",
  color: "#1a2b50",
  fontWeight: 500,
  textAlign: "center",
};

const driveBox = {
  flex: 1,
  padding: "14px 16px",
  border: "1px solid #cdd5e0",
  borderRadius: 12,
  cursor: "pointer",
  background: "#f8faff",
  color: "#1a2b50",
  fontWeight: 500,
  fontSize: "1rem",
};

const fileChip = {
  display: "inline-flex",
  alignItems: "center",
  background: "#eef3ff",
  border: "1px solid #c7d7f9",
  borderRadius: 8,
  padding: "6px 12px",
  fontSize: 13,
  color: "#1453c6",
  fontWeight: 500,
  marginBottom: 4,
};

const hint = {
  fontSize: 12,
  color: "#888",
  margin: "4px 0 0",
};

const textarea = {
  width: "100%",
  padding: 12,
  borderRadius: 10,
  border: "1px solid #cdd5e0",
  resize: "vertical",
  fontFamily: "inherit",
  fontSize: 14,
  lineHeight: 1.5,
  boxSizing: "border-box",
};

const actionBtn = {
  marginTop: 20,
  padding: "13px 28px",
  background: "linear-gradient(135deg, #1453c6, #2a6ce8)",
  color: "white",
  border: "none",
  borderRadius: 12,
  fontWeight: 600,
  fontSize: "1rem",
  cursor: "pointer",
  display: "inline-flex",
  alignItems: "center",
  boxShadow: "0 4px 12px rgba(20, 83, 198, 0.2)",
};

const loadingBox = {
  marginTop: 16,
  display: "flex",
  alignItems: "center",
  gap: 12,
  color: "#5a6c8d",
  fontSize: "0.95rem",
  padding: 14,
  background: "#f8faff",
  borderRadius: 12,
  border: "1px solid #e6eeff",
};

const spinnerStyle = {
  width: 22,
  height: 22,
  border: "3px solid rgba(20, 83, 198, 0.2)",
  borderTop: "3px solid #1453c6",
  borderRadius: "50%",
  animation: "spin 1s linear infinite",
  flexShrink: 0,
};

const errorBox = {
  marginTop: 16,
  padding: 14,
  background: "#fff5f5",
  border: "1px solid #fca5a5",
  borderRadius: 10,
  color: "#b91c1c",
  fontSize: "0.9rem",
};

const resultHeader = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  marginBottom: 20,
};

const rerunBtn = {
  padding: "8px 14px",
  background: "#f0f5ff",
  border: "1px solid #c7d7f9",
  borderRadius: 8,
  color: "#1453c6",
  cursor: "pointer",
  fontWeight: 500,
  fontSize: "0.85rem",
  display: "flex",
  alignItems: "center",
};

const preStyle = {
  whiteSpace: "pre-wrap",
  wordBreak: "break-word",
  fontFamily: "inherit",
  fontSize: 14,
  lineHeight: 1.7,
  margin: 0,
  color: "#2c3e50",
};

const downloadLink = {
  display: "inline-flex",
  alignItems: "center",
  padding: "10px 18px",
  background: "#198754",
  color: "white",
  borderRadius: 10,
  textDecoration: "none",
  fontWeight: 600,
  fontSize: "0.9rem",
  boxShadow: "0 4px 10px rgba(25, 135, 84, 0.2)",
};

// ── Modal styles ──────────────────────────────────────────

const modalOverlay = {
  position: "fixed",
  inset: 0,
  background: "rgba(15, 23, 42, 0.5)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  zIndex: 1000,
  backdropFilter: "blur(2px)",
};

const modalCard = {
  background: "#fff",
  borderRadius: 20,
  padding: "32px",
  boxShadow: "0 25px 60px rgba(0,0,0,0.25)",
  maxWidth: 460,
  width: "90%",
  maxHeight: "85vh",
  display: "flex",
  flexDirection: "column",
};

const sheetOptionStyle = (selected) => ({
  display: "flex",
  alignItems: "center",
  padding: "12px 16px",
  borderRadius: 10,
  border: `1.5px solid ${selected ? "#1453c6" : "#e2e8f0"}`,
  background: selected ? "#eef3ff" : "#f8faff",
  cursor: "pointer",
  color: selected ? "#1453c6" : "#1a2b50",
  fontWeight: selected ? 600 : 400,
  fontSize: 14,
});

const cancelModalBtn = {
  padding: "10px 20px",
  background: "#f0f5ff",
  border: "1px solid #cdd5e0",
  borderRadius: 10,
  color: "#5a6c8d",
  cursor: "pointer",
  fontWeight: 500,
  fontSize: "0.9rem",
};

const confirmModalBtn = {
  padding: "10px 22px",
  background: "linear-gradient(135deg, #1453c6, #2a6ce8)",
  border: "none",
  borderRadius: 10,
  color: "white",
  cursor: "pointer",
  fontWeight: 600,
  fontSize: "0.9rem",
  display: "flex",
  alignItems: "center",
  boxShadow: "0 4px 12px rgba(20, 83, 198, 0.3)",
};

export default QAWorkspace;
