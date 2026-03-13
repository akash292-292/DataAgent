import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useMappingSession } from "../contexts/MappingSessionContext";
import SearchableSelect from "../components/SearchableSelect";

const BASE = process.env.REACT_APP_BASE_BACKEND_URL;

const MetadataComparison = () => {
  const navigate = useNavigate();
  const { sessions, removeSession, clearSessions } = useMappingSession();

  const [sourceTables, setSourceTables] = useState([]);
  const [targetObjects, setTargetObjects] = useState([]);
  const [selectedSource, setSelectedSource] = useState("");
  const [selectedTarget, setSelectedTarget] = useState("");
  const [loadingSource, setLoadingSource] = useState(true);
  const [loadingTarget, setLoadingTarget] = useState(true);
  const [sourceError, setSourceError] = useState(null);
  const [targetError, setTargetError] = useState(null);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState(null);

  useEffect(() => {
    const fetchSourceTables = async () => {
      try {
        const res = await fetch(`${BASE}/api/metadata/source-tables`, { credentials: "include" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setSourceTables(data.tables || []);
      } catch (err) {
        setSourceError("Failed to load source tables: " + err.message);
      } finally {
        setLoadingSource(false);
      }
    };

    const fetchTargetObjects = async () => {
      try {
        const res = await fetch(`${BASE}/api/metadata/target-objects`, { credentials: "include" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setTargetObjects(data.objects || []);
      } catch (err) {
        setTargetError("Failed to load target objects: " + err.message);
      } finally {
        setLoadingTarget(false);
      }
    };

    fetchSourceTables();
    fetchTargetObjects();
  }, []);

  const handleConfigure = () => {
    navigate(
      `/metadata-comparison/configure?source=${encodeURIComponent(selectedSource)}&target=${encodeURIComponent(selectedTarget)}`
    );
  };

  const handleExportAll = async () => {
    setExporting(true);
    setExportError(null);
    try {
      const res = await fetch(`${BASE}/api/metadata/export-mapping`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ sessions }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "metadata_mapping.xlsx";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError("Export failed: " + err.message);
    } finally {
      setExporting(false);
    }
  };

  const isConfigureEnabled = selectedSource && selectedTarget;

  return (
    <div style={styles.page}>
      {/* Header */}
      <div style={styles.header}>
        <button style={styles.backBtn} onClick={() => navigate("/dashboard")}>
          <i className="fas fa-arrow-left" style={{ marginRight: 8 }} />
          Back
        </button>
        <div style={styles.headerTitle}>
          <span style={styles.titleIcon}>🔍</span>
          <div>
            <h1 style={styles.title}>Metadata Comparison</h1>
            <p style={styles.subtitle}>
              Select a source table and a target object to compare their schemas
            </p>
          </div>
        </div>
      </div>

      {/* Main Card */}
      <div style={styles.card}>
        <div style={styles.dropdownRow}>
          {/* Source Table */}
          <div style={styles.dropdownGroup}>
            <label style={styles.label}>
              <i className="fas fa-database" style={{ marginRight: 8, color: "#1453c6" }} />
              Source Table
            </label>
            {sourceError ? (
              <div style={styles.errorBox}>{sourceError}</div>
            ) : (
              <SearchableSelect
                value={selectedSource}
                onChange={setSelectedSource}
                options={sourceTables.map((t) => ({ value: t, label: t }))}
                placeholder={loadingSource ? "Loading tables..." : "Select a table"}
                disabled={loadingSource}
              />
            )}
            {!loadingSource && !sourceError && (
              <span style={styles.countBadge}>{sourceTables.length} tables</span>
            )}
          </div>

          {/* Arrow between dropdowns */}
          <div style={styles.arrowSeparator}>
            <i className="fas fa-exchange-alt" style={{ color: "#1453c6", fontSize: "1.4rem" }} />
          </div>

          {/* Target Object */}
          <div style={styles.dropdownGroup}>
            <label style={styles.label}>
              <i className="fas fa-cloud" style={{ marginRight: 8, color: "#1453c6" }} />
              Target Object
            </label>
            {targetError ? (
              <div style={styles.errorBox}>{targetError}</div>
            ) : (
              <SearchableSelect
                value={selectedTarget}
                onChange={setSelectedTarget}
                options={targetObjects.map((o) => ({ value: o.name, label: o.displayName }))}
                placeholder={loadingTarget ? "Loading objects..." : "Select an object"}
                disabled={loadingTarget}
              />
            )}
            {!loadingTarget && !targetError && (
              <span style={styles.countBadge}>{targetObjects.length} objects</span>
            )}
          </div>
        </div>

        {/* Selected preview */}
        {(selectedSource || selectedTarget) && (
          <div style={styles.selectionPreview}>
            {selectedSource && (
              <span style={styles.previewChip}>
                <i className="fas fa-table" style={{ marginRight: 6 }} />
                {selectedSource}
              </span>
            )}
            {selectedSource && selectedTarget && (
              <i className="fas fa-long-arrow-alt-right" style={{ color: "#5a6c8d", margin: "0 12px" }} />
            )}
            {selectedTarget && (
              <span style={{ ...styles.previewChip, background: "#eaf7ee", color: "#1a7a3c", border: "1px solid #c3e6d0" }}>
                <i className="fas fa-cloud" style={{ marginRight: 6 }} />
                {selectedTarget}
              </span>
            )}
          </div>
        )}

        {/* Configure Button */}
        <div style={styles.buttonRow}>
          <button
            style={{
              ...styles.configureBtn,
              ...(isConfigureEnabled ? {} : styles.configureBtnDisabled),
            }}
            onClick={handleConfigure}
            disabled={!isConfigureEnabled}
            title={isConfigureEnabled ? "Configure mapping" : "Select both source and target first"}
          >
            <i className="fas fa-cog" style={{ marginRight: 10, fontSize: "1.1rem" }} />
            Configure
          </button>
          {!isConfigureEnabled && (
            <p style={styles.hintText}>
              Select both a source table and a target object to enable configuration
            </p>
          )}
        </div>
      </div>

      {/* Saved Sessions */}
      {sessions.length > 0 && (
        <div style={styles.sessionsCard}>
          <div style={styles.sessionsHeader}>
            <div style={styles.sessionsTitleRow}>
              <i className="fas fa-layer-group" style={{ color: "#1453c6", marginRight: 10 }} />
              <span style={styles.sessionsTitle}>Saved Mappings</span>
              <span style={styles.sessionCount}>{sessions.length} pair{sessions.length !== 1 ? "s" : ""}</span>
            </div>
            <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <button style={styles.clearBtn} onClick={clearSessions} title="Remove all sessions">
                <i className="fas fa-trash" style={{ marginRight: 6 }} />
                Clear All
              </button>
              <button
                style={{ ...styles.exportBtn, ...(exporting ? styles.exportBtnDisabled : {}) }}
                onClick={handleExportAll}
                disabled={exporting}
              >
                <i className={`fas ${exporting ? "fa-spinner fa-spin" : "fa-file-excel"}`} style={{ marginRight: 8 }} />
                {exporting ? "Exporting..." : "Export All to Excel"}
              </button>
            </div>
          </div>

          {exportError && <div style={{ ...styles.errorBox, margin: "0 0 12px" }}>{exportError}</div>}

          <div style={styles.sessionsTable}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>#</th>
                  <th style={styles.th}>Source Table</th>
                  <th style={styles.th}>Target Object</th>
                  <th style={styles.th}>Field Mappings</th>
                  <th style={styles.th}>Picklist Mappings</th>
                  <th style={{ ...styles.th, textAlign: "center" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((s, i) => {
                  const fieldCount = Object.values(s.rowSelections || {}).filter(Boolean).length;
                  const picklistCount = Object.keys(s.picklistMappings || {}).filter(
                    (k) => Object.keys(s.picklistMappings[k] || {}).length > 0
                  ).length;
                  return (
                    <tr key={`${s.sourceTable}-${s.targetObject}`} style={styles.tr}>
                      <td style={styles.td}>{i + 1}</td>
                      <td style={styles.td}>
                        <span style={styles.sourceChip}>
                          <i className="fas fa-database" style={{ marginRight: 6 }} />
                          {s.sourceTable}
                        </span>
                      </td>
                      <td style={styles.td}>
                        <span style={styles.targetChip}>
                          <i className="fas fa-cloud" style={{ marginRight: 6 }} />
                          {s.targetObject}
                        </span>
                      </td>
                      <td style={styles.td}>
                        <span style={styles.countPill}>
                          {fieldCount} field{fieldCount !== 1 ? "s" : ""}
                        </span>
                      </td>
                      <td style={styles.td}>
                        {picklistCount > 0 ? (
                          <span style={{ ...styles.countPill, background: "#fff8e1", color: "#a16800", border: "1px solid #f5d87a" }}>
                            {picklistCount} picklist{picklistCount !== 1 ? "s" : ""}
                          </span>
                        ) : (
                          <span style={styles.emptyCell}>—</span>
                        )}
                      </td>
                      <td style={{ ...styles.td, textAlign: "center" }}>
                        <div style={{ display: "flex", gap: 6, justifyContent: "center" }}>
                          <button
                            style={styles.editBtn}
                            title="Edit this mapping"
                            onClick={() =>
                              navigate(
                                `/metadata-comparison/configure?source=${encodeURIComponent(s.sourceTable)}&target=${encodeURIComponent(s.targetObject)}`
                              )
                            }
                          >
                            <i className="fas fa-edit" />
                          </button>
                          <button
                            style={styles.removeBtn}
                            title="Remove this mapping"
                            onClick={() => removeSession(s.sourceTable, s.targetObject)}
                          >
                            <i className="fas fa-times" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

const styles = {
  page: {
    minHeight: "100vh",
    background: "linear-gradient(135deg, #f3f6fb 0%, #e8edf7 100%)",
    fontFamily: "'Inter', system-ui, sans-serif",
    color: "#1a2b50",
    padding: "32px 40px",
    boxSizing: "border-box",
    display: "flex",
    flexDirection: "column",
    gap: 24,
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: 24,
  },
  backBtn: {
    background: "linear-gradient(135deg, #1453c6, #2a6ce8)",
    color: "white",
    border: "none",
    borderRadius: 10,
    padding: "10px 20px",
    fontWeight: 600,
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    fontSize: "0.95rem",
    boxShadow: "0 4px 12px rgba(20, 83, 198, 0.2)",
    whiteSpace: "nowrap",
  },
  headerTitle: {
    display: "flex",
    alignItems: "center",
    gap: 16,
  },
  titleIcon: {
    fontSize: "2.5rem",
  },
  title: {
    margin: 0,
    fontSize: "1.8rem",
    fontWeight: 700,
    color: "#1a2b50",
  },
  subtitle: {
    margin: "4px 0 0",
    color: "#5a6c8d",
    fontSize: "0.95rem",
  },
  card: {
    background: "white",
    borderRadius: 20,
    padding: "40px 48px",
    boxShadow: "0 8px 32px rgba(20, 83, 198, 0.10)",
    maxWidth: 900,
  },
  dropdownRow: {
    display: "flex",
    alignItems: "flex-start",
    gap: 20,
    flexWrap: "wrap",
  },
  dropdownGroup: {
    flex: 1,
    minWidth: 240,
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  label: {
    fontWeight: 600,
    fontSize: "0.95rem",
    color: "#1a2b50",
    display: "flex",
    alignItems: "center",
  },
  selectWrapper: {
    position: "relative",
  },
  select: {
    width: "100%",
    padding: "12px 40px 12px 16px",
    borderRadius: 10,
    border: "1.5px solid #d0d9f0",
    fontSize: "0.95rem",
    color: "#1a2b50",
    background: "#f8faff",
    appearance: "none",
    cursor: "pointer",
    outline: "none",
    boxSizing: "border-box",
  },
  selectArrow: {
    position: "absolute",
    right: 14,
    top: "50%",
    transform: "translateY(-50%)",
    color: "#5a6c8d",
    pointerEvents: "none",
    fontSize: "0.8rem",
  },
  countBadge: {
    fontSize: "0.78rem",
    color: "#5a6c8d",
    fontStyle: "italic",
  },
  arrowSeparator: {
    display: "flex",
    alignItems: "center",
    paddingTop: 36,
  },
  selectionPreview: {
    display: "flex",
    alignItems: "center",
    marginTop: 28,
    padding: "14px 20px",
    background: "#f4f7ff",
    borderRadius: 10,
    border: "1px solid #dce6fb",
    flexWrap: "wrap",
    gap: 8,
  },
  previewChip: {
    background: "#eaf0ff",
    color: "#1453c6",
    border: "1px solid #c5d4f7",
    borderRadius: 20,
    padding: "6px 14px",
    fontSize: "0.88rem",
    fontWeight: 600,
    display: "flex",
    alignItems: "center",
  },
  buttonRow: {
    marginTop: 36,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 12,
  },
  configureBtn: {
    background: "linear-gradient(135deg, #1453c6, #2a6ce8)",
    color: "white",
    border: "none",
    borderRadius: 12,
    padding: "14px 36px",
    fontSize: "1rem",
    fontWeight: 700,
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    boxShadow: "0 4px 16px rgba(20, 83, 198, 0.25)",
  },
  configureBtnDisabled: {
    background: "#c8d3ea",
    boxShadow: "none",
    cursor: "not-allowed",
  },
  hintText: {
    color: "#5a6c8d",
    fontSize: "0.85rem",
    margin: 0,
    textAlign: "center",
  },
  errorBox: {
    padding: "10px 14px",
    background: "#fff0f0",
    border: "1px solid #f5c2c2",
    borderRadius: 8,
    color: "#c0392b",
    fontSize: "0.85rem",
  },

  /* Sessions panel */
  sessionsCard: {
    background: "white",
    borderRadius: 20,
    boxShadow: "0 8px 32px rgba(20, 83, 198, 0.10)",
    overflow: "hidden",
  },
  sessionsHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "18px 24px",
    borderBottom: "1px solid #e8edf7",
    background: "linear-gradient(135deg, #f8faff, #f0f4ff)",
    flexWrap: "wrap",
    gap: 12,
  },
  sessionsTitleRow: {
    display: "flex",
    alignItems: "center",
    gap: 10,
  },
  sessionsTitle: {
    fontWeight: 700,
    fontSize: "1rem",
    color: "#1a2b50",
  },
  sessionCount: {
    background: "#eaf0ff",
    color: "#1453c6",
    borderRadius: 12,
    padding: "2px 10px",
    fontSize: "0.78rem",
    fontWeight: 600,
  },
  clearBtn: {
    background: "white",
    border: "1.5px solid #f5c2c2",
    color: "#c0392b",
    borderRadius: 8,
    padding: "8px 14px",
    fontSize: "0.85rem",
    fontWeight: 600,
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
  },
  exportBtn: {
    background: "linear-gradient(135deg, #1a7a3c, #25a355)",
    color: "white",
    border: "none",
    borderRadius: 10,
    padding: "10px 20px",
    fontSize: "0.9rem",
    fontWeight: 700,
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    boxShadow: "0 4px 12px rgba(26,122,60,0.25)",
  },
  exportBtnDisabled: {
    background: "#c8d3ea",
    boxShadow: "none",
    cursor: "not-allowed",
  },
  sessionsTable: {
    overflowX: "auto",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: "0.88rem",
  },
  th: {
    padding: "10px 16px",
    textAlign: "left",
    background: "#f4f7ff",
    color: "#5a6c8d",
    fontWeight: 600,
    fontSize: "0.78rem",
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    borderBottom: "1px solid #e8edf7",
  },
  tr: {
    borderBottom: "1px solid #f0f4fb",
  },
  td: {
    padding: "12px 16px",
    verticalAlign: "middle",
  },
  sourceChip: {
    background: "#eaf0ff",
    color: "#1453c6",
    border: "1px solid #c5d4f7",
    borderRadius: 20,
    padding: "4px 12px",
    fontSize: "0.82rem",
    fontWeight: 600,
    display: "inline-flex",
    alignItems: "center",
  },
  targetChip: {
    background: "#eaf7ee",
    color: "#1a7a3c",
    border: "1px solid #c3e6d0",
    borderRadius: 20,
    padding: "4px 12px",
    fontSize: "0.82rem",
    fontWeight: 600,
    display: "inline-flex",
    alignItems: "center",
  },
  countPill: {
    background: "#eaf0ff",
    color: "#1453c6",
    borderRadius: 12,
    padding: "3px 10px",
    fontSize: "0.78rem",
    fontWeight: 600,
    border: "1px solid #c5d4f7",
  },
  emptyCell: {
    color: "#b0bcd4",
    fontSize: "0.85rem",
  },
  editBtn: {
    width: 30,
    height: 30,
    borderRadius: 7,
    border: "none",
    background: "linear-gradient(135deg, #1453c6, #2a6ce8)",
    color: "white",
    cursor: "pointer",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "0.8rem",
    boxShadow: "0 2px 6px rgba(20,83,198,0.25)",
  },
  removeBtn: {
    width: 30,
    height: 30,
    borderRadius: 7,
    border: "none",
    background: "#fff0f0",
    color: "#c0392b",
    cursor: "pointer",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "0.8rem",
  },
};

export default MetadataComparison;
