import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useMappingSession } from "../contexts/MappingSessionContext";
import SearchableSelect from "../components/SearchableSelect";

const MetadataComparisonDetail = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { addSession, sessions } = useMappingSession();
  const sourceTable = searchParams.get("source") || "";
  const targetObject = searchParams.get("target") || "";

  const [sourceColumns, setSourceColumns] = useState([]);
  const [targetFields, setTargetFields] = useState([]);
  const [loadingSource, setLoadingSource] = useState(true);
  const [loadingTarget, setLoadingTarget] = useState(true);
  const [sourceError, setSourceError] = useState(null);
  const [targetError, setTargetError] = useState(null);

  // Per-row target selection: { [colName]: targetFieldName }
  const [rowSelections, setRowSelections] = useState({});

  // Fields checked for composite duplicate detection: Set of colNames
  const [dupCheckFields, setDupCheckFields] = useState(new Set());

  // do_ column label map: { "do_xxx": "Company Nickname", ... }
  const [dynamicLabels, setDynamicLabels] = useState({});

  // Confirmed picklist mappings per column: { [colName]: { sourceValue: targetValue } }
  const [picklistMappings, setPicklistMappings] = useState({});

  // Modal state
  const [modal, setModal] = useState({ open: false, colName: null, targetFieldName: null, targetFieldDisplayName: null });
  const [sourcePicklist, setSourcePicklist] = useState([]);
  const [targetPicklist, setTargetPicklist] = useState([]);
  const [draftMappings, setDraftMappings] = useState({});
  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState(null);

  // Dependent picklist modal state
  const [isDependentField, setIsDependentField] = useState(false);
  // depEntries: array of { ControllingPicklistEntry, DependentPicklistEntries[] }
  const [depEntries, setDepEntries] = useState([]);
  // draftParentMappings: { [srcVal]: parentValue }
  const [draftParentMappings, setDraftParentMappings] = useState({});

  // Set of target field names that are dependent picklist fields (for inline icon)
  const [dependentFieldNames, setDependentFieldNames] = useState(new Set());
  const getDisplayName = (colName) =>
    colName && colName.startsWith("do_") && dynamicLabels[colName]
      ? dynamicLabels[colName]
      : colName;

  useEffect(() => {
    if (!sourceTable || !targetObject) return;

    const fetchSourceColumns = async () => {
      try {
        const res = await fetch(
          `${process.env.REACT_APP_BASE_BACKEND_URL}/api/metadata/source-columns?table=${encodeURIComponent(sourceTable)}`,
          { credentials: "include" }
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const cols = data.columns || [];
        setSourceColumns(cols);

        if (cols.some((c) => c.name.startsWith("do_"))) {
          try {
            const labelRes = await fetch(
              `${process.env.REACT_APP_BASE_BACKEND_URL}/api/metadata/dynamic-labels?table=${encodeURIComponent(sourceTable)}`,
              { credentials: "include" }
            );
            if (labelRes.ok) {
              const labelData = await labelRes.json();
              setDynamicLabels(labelData.labels || {});
            }
          } catch (_) {}
        }
      } catch (err) {
        setSourceError("Failed to load source columns: " + err.message);
      } finally {
        setLoadingSource(false);
      }
    };

    const fetchTargetFields = async () => {
      try {
        const res = await fetch(
          `${process.env.REACT_APP_BASE_BACKEND_URL}/api/metadata/target-fields?object=${encodeURIComponent(targetObject)}`,
          { credentials: "include" }
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setTargetFields(data.fields || []);
      } catch (err) {
        setTargetError("Failed to load target fields: " + err.message);
      } finally {
        setLoadingTarget(false);
      }
    };

    const fetchDependentFieldNames = async () => {
      try {
        const res = await fetch(
          `${process.env.REACT_APP_BASE_BACKEND_URL}/api/metadata/dependent-picklist-metadata?object=${encodeURIComponent(targetObject)}`,
          { credentials: "include" }
        );
        if (!res.ok) return;
        const data = await res.json();
        const names = new Set(
          (data.dependentPicklistMetadata || []).map((d) => d.DependentFieldName)
        );
        setDependentFieldNames(names);
      } catch (_) {}
    };

    fetchSourceColumns();
    fetchTargetFields();
    fetchDependentFieldNames();
  }, [sourceTable, targetObject]);

  // Restore saved session state when editing an existing session
  useEffect(() => {
    if (!sourceTable || !targetObject) return;
    const existing = sessions.find(
      (s) => s.sourceTable === sourceTable && s.targetObject === targetObject
    );
    if (existing) {
      setRowSelections(existing.rowSelections || {});
      setPicklistMappings(existing.picklistMappings || {});
      setDupCheckFields(new Set(existing.dupCheckFields || []));
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleTargetSelect = (colName, value) => {
    setRowSelections((prev) => ({ ...prev, [colName]: value }));
  };

  const handleDupCheckToggle = (colName) => {
    setDupCheckFields((prev) => {
      const next = new Set(prev);
      if (next.has(colName)) next.delete(colName);
      else next.add(colName);
      return next;
    });
  };

  const handleConfigure = async (colName) => {
    const targetFieldName = rowSelections[colName];
    const targetField = targetFields.find((f) => f.name === targetFieldName);
    const targetFieldDisplayName = targetField?.displayName || targetFieldName;
    setModal({ open: true, colName, targetFieldName, targetFieldDisplayName });
    setDraftMappings({ ...(picklistMappings[colName] || {}) });
    setDraftParentMappings({});
    setModalLoading(true);
    setModalError(null);
    setSourcePicklist([]);
    setTargetPicklist([]);
    setIsDependentField(false);
    setDepEntries([]);

    try {
      const [srcRes, depMetaRes] = await Promise.all([
        fetch(
          `${process.env.REACT_APP_BASE_BACKEND_URL}/api/metadata/source-picklist?table=${encodeURIComponent(sourceTable)}&column=${encodeURIComponent(colName)}`,
          { credentials: "include" }
        ),
        fetch(
          `${process.env.REACT_APP_BASE_BACKEND_URL}/api/metadata/dependent-picklist-metadata?object=${encodeURIComponent(targetObject)}`,
          { credentials: "include" }
        ),
      ]);

      if (!srcRes.ok) throw new Error(`Source picklist failed: HTTP ${srcRes.status}`);
      const srcData = await srcRes.json();
      setSourcePicklist(srcData.values || []);

      // Check if target field is a DependentFieldName
      let isDependent = false;
      if (depMetaRes.ok) {
        const depMetaData = await depMetaRes.json();
        const depMeta = depMetaData.dependentPicklistMetadata || [];
        const matchedDep = depMeta.find((d) => d.DependentFieldName === targetFieldName);
        if (matchedDep) {
          isDependent = true;
          setIsDependentField(true);
          setDepEntries(matchedDep.ControllingAndDependentPicklistEntries || []);
          // Pre-populate parent draft from saved mappings
          const saved = picklistMappings[colName] || {};
          const parentDraft = {};
          Object.keys(saved).forEach((srcVal) => {
            parentDraft[srcVal] = saved[`__parent__${srcVal}`] || "";
          });
          setDraftParentMappings(parentDraft);
        }
      }

      // Only fetch flat target picklist for non-dependent fields
      if (!isDependent) {
        const tgtRes = await fetch(
          `${process.env.REACT_APP_BASE_BACKEND_URL}/api/metadata/target-picklist?object=${encodeURIComponent(targetObject)}&field=${encodeURIComponent(targetFieldName)}`,
          { credentials: "include" }
        );
        if (!tgtRes.ok) throw new Error(`Target picklist failed: HTTP ${tgtRes.status}`);
        const tgtData = await tgtRes.json();
        setTargetPicklist(tgtData.values || []);
      }
    } catch (err) {
      setModalError("Failed to load picklist values: " + err.message);
    } finally {
      setModalLoading(false);
    }
  };

  const handleDraftChange = (sourceValue, targetValue) => {
    setDraftMappings((prev) => ({ ...prev, [sourceValue]: targetValue }));
  };

  // For dependent fields: track parent selection per source value
  const handleParentDraftChange = (srcVal, parentValue) => {
    setDraftParentMappings((prev) => ({ ...prev, [srcVal]: parentValue }));
    // Clear child when parent changes
    setDraftMappings((prev) => ({ ...prev, [srcVal]: "" }));
  };

  // Get available child options for a given parent value
  const getChildOptions = (parentValue) => {
    if (!parentValue) return [];
    const entry = depEntries.find((e) => e.ControllingPicklistEntry === parentValue);
    return (entry?.DependentPicklistEntries || [])
      .filter((d) => !d.IsDeprecated)
      .map((d) => ({ value: d.Value, label: d.DisplayText || d.Value }));
  };

  // All unique controlling (parent) values
  const allParentValues = depEntries.map((e) => ({
    value: e.ControllingPicklistEntry,
    label: e.ControllingPicklistEntry,
  }));

  const handleSaveMapping = () => {
    // For dependent fields, store child value (draftMappings) per src value.
    // Also persist parent selections using __parent__ keys so they can be
    // restored when the modal is reopened.
    if (isDependentField) {
      const merged = { ...draftMappings };
      Object.keys(draftParentMappings).forEach((srcVal) => {
        merged[`__parent__${srcVal}`] = draftParentMappings[srcVal];
      });
      setPicklistMappings((prev) => ({ ...prev, [modal.colName]: merged }));
    } else {
      setPicklistMappings((prev) => ({ ...prev, [modal.colName]: { ...draftMappings } }));
    }
    setModal({ open: false, colName: null, targetFieldName: null, targetFieldDisplayName: null });
  };

  const handleCancelModal = () => {
    setModal({ open: false, colName: null, targetFieldName: null, targetFieldDisplayName: null });
    setDraftMappings({});
    setDraftParentMappings({});
    setIsDependentField(false);
    setDepEntries([]);
  };

  const handleSaveSession = () => {
    addSession({
      sourceTable,
      targetObject,
      sourceColumns,
      targetFields,
      rowSelections,
      picklistMappings,
      dynamicLabels,
      dupCheckFields: Array.from(dupCheckFields),
    });
    navigate("/metadata-comparison");
  };

  const configuredCount = Object.values(rowSelections).filter(Boolean).length;

  // Count how many uuid columns have saved picklist mappings
  const picklistConfiguredCount = Object.keys(picklistMappings).filter((k) =>
    Object.entries(picklistMappings[k] || {}).some(([key, val]) => !key.startsWith("__parent__") && Boolean(val))
  ).length;

  return (
    <div style={styles.page}>
      {/* Header */}
      <div style={styles.header}>
        <button style={styles.backBtn} onClick={() => navigate("/metadata-comparison")}>
          <i className="fas fa-arrow-left" style={{ marginRight: 8 }} />
          Back
        </button>
        <div style={styles.headerCenter}>
          <h1 style={styles.title}>Schema Comparison</h1>
          <div style={styles.breadcrumb}>
            <span style={styles.breadcrumbSource}>
              <i className="fas fa-database" style={{ marginRight: 6 }} />
              {sourceTable}
            </span>
            <i
              className="fas fa-long-arrow-alt-right"
              style={{ color: "#5a6c8d", margin: "0 12px" }}
            />
            <span style={styles.breadcrumbTarget}>
              <i className="fas fa-cloud" style={{ marginRight: 6 }} />
              {targetObject}
            </span>
          </div>
        </div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
          {configuredCount > 0 && (
            <span style={styles.configuredBadge}>
              <i className="fas fa-check-circle" style={{ marginRight: 6 }} />
              {configuredCount} field mapping{configuredCount !== 1 ? "s" : ""}
            </span>
          )}
          {picklistConfiguredCount > 0 && (
            <span style={{ ...styles.configuredBadge, background: "#fff8e1", color: "#a16800", borderColor: "#f5d87a" }}>
              <i className="fas fa-list-ul" style={{ marginRight: 6 }} />
              {picklistConfiguredCount} picklist mapping{picklistConfiguredCount !== 1 ? "s" : ""}
            </span>
          )}
          {dupCheckFields.size > 0 && (
            <span style={{ ...styles.configuredBadge, background: "#f0eaff", color: "#5b21b6", borderColor: "#c4b5fd" }}>
              <i className="fas fa-copy" style={{ marginRight: 6 }} />
              {dupCheckFields.size} dup check field{dupCheckFields.size !== 1 ? "s" : ""}
            </span>
          )}
          <button
            style={{
              ...styles.saveSessionBtn,
              ...(configuredCount === 0 ? styles.saveSessionBtnDisabled : {}),
            }}
            disabled={configuredCount === 0}
            onClick={handleSaveSession}
            title={configuredCount === 0 ? "Map at least one field before saving" : "Save this mapping and add another pair"}
          >
            <i className="fas fa-save" style={{ marginRight: 8 }} />
            Save Session
          </button>
        </div>
      </div>

      {/* Errors */}
      {sourceError && <div style={styles.errorBox}>{sourceError}</div>}
      {targetError && <div style={styles.errorBox}>{targetError}</div>}

      {/* Single panel */}
      <div style={styles.panel}>
        <div style={styles.panelHeader}>
          <div style={styles.panelTitle}>
            <i className="fas fa-table" style={{ marginRight: 8, color: "#1453c6" }} />
            Field Mapping
            <span style={styles.hint}>
              Configure is available when source is{" "}
              <code style={styles.code}>uuid</code> and target is{" "}
              <code style={styles.code}>Picklist</code>
              {" · "}
              <code style={styles.code}>Dup Check</code> selects fields for composite duplicate detection in the Summary sheet
            </span>
          </div>
          <div style={styles.panelMeta}>
            {!loadingSource && !sourceError && (
              <span style={styles.countBadge}>{sourceColumns.length} columns</span>
            )}
            {!loadingTarget && !targetError && (
              <span style={{ ...styles.countBadge, background: "#eaf7ee", color: "#1a7a3c" }}>
                {targetFields.length} target fields
              </span>
            )}
          </div>
        </div>

        {loadingSource && <div style={styles.loadingMsg}>Loading columns...</div>}

        {!loadingSource && !sourceError && (
          <div style={styles.tableWrapper}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>Source Column</th>
                  <th style={styles.th}>Source Data Type</th>
                  <th style={{ ...styles.th, textAlign: "center", width: 60, padding: "10px 6px" }}
                    title={`Check fields to use for composite duplicate detection in the Summary sheet.\n${dupCheckFields.size} field${dupCheckFields.size !== 1 ? "s" : ""} selected.`}
                  >
                    Dup Check
                  </th>
                  <th style={styles.th}>Target Field</th>
                  <th style={styles.th}>Target Data Type</th>
                  <th style={{ ...styles.th, textAlign: "center", width: 100 }}>Configure</th>
                </tr>
              </thead>
              <tbody>
                {sourceColumns.map((col) => {
                  const selected = rowSelections[col.name] || "";
                  const selectedField = targetFields.find((f) => f.name === selected);
                  const isUuid = col.dataType === "uuid";
                  const isTargetPicklist = selectedField?.dataType === "Picklist";
                  const showConfigure = isUuid && isTargetPicklist;
                  const canConfigure = showConfigure;
                  const isMapped =
                    showConfigure &&
                    picklistMappings[col.name] &&
                    Object.entries(picklistMappings[col.name]).some(([k, v]) => !k.startsWith("__parent__") && Boolean(v));

                  return (
                    <tr
                      key={col.name}
                      style={{
                        ...styles.tr,
                        ...(isUuid ? styles.trUuid : {}),
                      }}
                    >
                      {/* Source Column */}
                      <td style={styles.td}>
                        <span style={styles.colName}>{getDisplayName(col.name)}</span>
                      </td>

                      {/* Source Data Type */}
                      <td style={styles.td}>
                        <span
                          style={{
                            ...styles.dataTypeBadge,
                            ...(isUuid ? styles.dataTypeBadgeUuid : {}),
                          }}
                        >
                          {col.dataType}
                        </span>
                      </td>

                      {/* Dup Check */}
                      <td style={{ ...styles.td, textAlign: "center", padding: "10px 6px" }}>
                        <input
                          type="checkbox"
                          checked={dupCheckFields.has(col.name)}
                          onChange={() => handleDupCheckToggle(col.name)}
                          title={`Include "${getDisplayName(col.name)}" in duplicate detection`}
                          style={styles.dupCheckbox}
                        />
                      </td>

                      {/* Target Field dropdown */}
                      <td style={styles.td}>
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <SearchableSelect
                            value={selected}
                            onChange={(val) => handleTargetSelect(col.name, val)}
                            options={targetFields.map((f) => ({ value: f.name, label: f.displayName || f.name }))}
                            placeholder={loadingTarget ? "Loading fields..." : "Select target field"}
                            disabled={loadingTarget}
                          />
                          {selected && dependentFieldNames.has(selected) && (
                            <i
                              className="fas fa-info-circle"
                              title="Dependent"
                              style={{ color: "#7c3aed", fontSize: "0.85rem", flexShrink: 0, cursor: "default" }}
                            />
                          )}
                        </div>
                      </td>

                      {/* Target Data Type */}
                      <td style={styles.td}>
                        {selectedField ? (
                          <span style={styles.targetDataTypeBadge}>
                            {selectedField.dataType}
                          </span>
                        ) : (
                          <span style={styles.emptyCell}>—</span>
                        )}
                      </td>

                      {/* Configure */}
                      <td style={{ ...styles.td, textAlign: "center" }}>
                        {showConfigure ? (
                          <button
                            style={{
                              ...styles.configureBtn,
                              ...(canConfigure
                                ? isMapped
                                  ? styles.configureBtnMapped
                                  : styles.configureBtnActive
                                : styles.configureBtnDisabled),
                            }}
                            disabled={!canConfigure}
                            onClick={() => handleConfigure(col.name)}
                            title={
                              canConfigure
                                ? isMapped
                                  ? `Edit picklist mapping for ${getDisplayName(col.name)}`
                                  : `Map picklist values: ${getDisplayName(col.name)} → ${selected}`
                                : "Select a target field to configure"
                            }
                          >
                            <i className="fas fa-cog" />
                          </button>
                        ) : (
                          <span
                            style={styles.noConfigureCell}
                            title="Only uuid columns can be configured"
                          >
                            —
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Picklist Mapping Modal */}
      {modal.open && (
        <div style={styles.modalOverlay} onClick={handleCancelModal}>
          <div style={{ ...styles.modalBox, width: isDependentField ? "min(920px, 96vw)" : "min(680px, 94vw)" }} onClick={(e) => e.stopPropagation()}>
            {/* Modal Header */}
            <div style={styles.modalHeader}>
              <div>
                <h2 style={styles.modalTitle}>Configure Picklist Mapping</h2>
                <div style={styles.modalSubtitle}>
                  <span style={styles.breadcrumbSource}>
                    <i className="fas fa-database" style={{ marginRight: 6 }} />
                    {getDisplayName(modal.colName)}
                  </span>
                  <i
                    className="fas fa-long-arrow-alt-right"
                    style={{ color: "#5a6c8d", margin: "0 10px" }}
                  />
                  <span style={styles.breadcrumbTarget}>
                    <i className="fas fa-cloud" style={{ marginRight: 6 }} />
                    {modal.targetFieldDisplayName}
                  </span>
                </div>
              </div>
              <button style={styles.modalCloseBtn} onClick={handleCancelModal} title="Cancel">
                <i className="fas fa-times" />
              </button>
            </div>

            {/* Modal Content */}
            <div style={styles.modalContent}>
              {modalLoading && (
                <div style={styles.loadingMsg}>
                  <i className="fas fa-spinner fa-spin" style={{ marginRight: 8 }} />
                  Loading picklist values...
                </div>
              )}
              {modalError && <div style={styles.errorBox}>{modalError}</div>}

              {!modalLoading && !modalError && (
                <>
                  {sourcePicklist.length === 0 ? (
                    <div style={styles.emptyMsg}>
                      <i className="fas fa-info-circle" style={{ marginRight: 8, color: "#5a6c8d" }} />
                      No picklist values found for this source column.
                    </div>
                  ) : isDependentField ? (
                    /* ── 3-column dependent picklist layout ── */
                    <>
                      <div style={styles.modalTableHint}>
                        Select a <strong>Tgt Parent Value</strong> first, then choose the dependent child value.
                        Unmapped values will be ignored.
                      </div>
                      <div style={styles.modalTableWrapper}>
                        <table style={{ ...styles.table, tableLayout: "fixed" }}>
                          <colgroup>
                            <col style={{ width: "30%" }} />
                            <col style={{ width: "35%" }} />
                            <col style={{ width: "35%" }} />
                          </colgroup>
                          <thead>
                            <tr>
                              <th style={styles.th}>Source Value</th>
                              <th style={styles.th}>Tgt Parent Value</th>
                              <th style={styles.th}>Tgt Child Value</th>
                            </tr>
                          </thead>
                          <tbody>
                            {sourcePicklist.map((srcVal) => {
                              const selectedParent = draftParentMappings[srcVal] || "";
                              const selectedChild = draftMappings[srcVal] || "";
                              const childOptions = getChildOptions(selectedParent);
                              return (
                                <tr key={srcVal} style={styles.tr}>
                                  <td style={styles.td}>
                                    <span style={styles.colName}>{srcVal}</span>
                                  </td>
                                  <td style={styles.td}>
                                    <SearchableSelect
                                      value={selectedParent}
                                      onChange={(val) => handleParentDraftChange(srcVal, val)}
                                      options={allParentValues}
                                      placeholder="— Select parent —"
                                    />
                                  </td>
                                  <td style={styles.td}>
                                    <SearchableSelect
                                      value={selectedChild}
                                      onChange={(val) => handleDraftChange(srcVal, val)}
                                      options={childOptions}
                                      placeholder={selectedParent ? "— Select child —" : "— Select parent first —"}
                                      disabled={!selectedParent}
                                    />
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </>
                  ) : (
                    /* ── Standard 2-column layout ── */
                    <>
                      <div style={styles.modalTableHint}>
                        Map each source value to a corresponding target value. Unmapped values will be ignored.
                      </div>
                      <div style={styles.modalTableWrapper}>
                        <table style={styles.table}>
                          <thead>
                            <tr>
                              <th style={styles.th}>Source Value</th>
                              <th style={styles.th}>Target Value</th>
                            </tr>
                          </thead>
                          <tbody>
                            {sourcePicklist.map((srcVal) => {
                              const currentVal = draftMappings[srcVal] || "";
                              return (
                                <tr key={srcVal} style={styles.tr}>
                                  <td style={styles.td}>
                                    <span style={styles.colName}>{srcVal}</span>
                                  </td>
                                  <td style={styles.td}>
                                    <SearchableSelect
                                      value={currentVal}
                                      onChange={(val) => handleDraftChange(srcVal, val)}
                                      options={targetPicklist.map((tgt) => ({ value: tgt.value, label: tgt.displayText }))}
                                      placeholder="— Select target value —"
                                    />
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )}
                </>
              )}
            </div>

            {/* Modal Footer */}
            <div style={styles.modalFooter}>
              <div style={styles.modalMappedCount}>
                {Object.entries(draftMappings).filter(([k, v]) => !k.startsWith("__parent__") && Boolean(v)).length} of {sourcePicklist.length} values mapped
              </div>
              <div style={styles.modalActions}>
                <button style={styles.cancelBtn} onClick={handleCancelModal}>
                  Cancel
                </button>
                <button
                  style={{
                    ...styles.saveBtn,
                    ...(sourcePicklist.length === 0 ? styles.saveBtnDisabled : {}),
                  }}
                  disabled={sourcePicklist.length === 0}
                  onClick={handleSaveMapping}
                >
                  <i className="fas fa-save" style={{ marginRight: 8 }} />
                  Save Mapping
                </button>
              </div>
            </div>
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
    padding: "28px 32px",
    boxSizing: "border-box",
    display: "flex",
    flexDirection: "column",
    gap: 20,
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: 20,
    flexWrap: "wrap",
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
    fontSize: "0.9rem",
    boxShadow: "0 4px 12px rgba(20, 83, 198, 0.2)",
    whiteSpace: "nowrap",
  },
  headerCenter: {
    display: "flex",
    flexDirection: "column",
    gap: 6,
    flex: 1,
  },
  title: {
    margin: 0,
    fontSize: "1.6rem",
    fontWeight: 700,
    color: "#1a2b50",
  },
  breadcrumb: {
    display: "flex",
    alignItems: "center",
  },
  breadcrumbSource: {
    background: "#eaf0ff",
    color: "#1453c6",
    border: "1px solid #c5d4f7",
    borderRadius: 20,
    padding: "4px 12px",
    fontSize: "0.85rem",
    fontWeight: 600,
  },
  breadcrumbTarget: {
    background: "#eaf7ee",
    color: "#1a7a3c",
    border: "1px solid #c3e6d0",
    borderRadius: 20,
    padding: "4px 12px",
    fontSize: "0.85rem",
    fontWeight: 600,
  },
  configuredBadge: {
    display: "flex",
    alignItems: "center",
    background: "#eaf7ee",
    color: "#1a7a3c",
    border: "1px solid #c3e6d0",
    borderRadius: 20,
    padding: "6px 14px",
    fontSize: "0.85rem",
    fontWeight: 600,
    whiteSpace: "nowrap",
  },
  panel: {
    background: "white",
    borderRadius: 16,
    boxShadow: "0 4px 20px rgba(20, 83, 198, 0.08)",
    overflow: "hidden",
    flex: 1,
  },
  panelHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "16px 20px",
    borderBottom: "1px solid #e8edf7",
    background: "linear-gradient(135deg, #f8faff, #f0f4ff)",
    flexWrap: "wrap",
    gap: 10,
  },
  panelTitle: {
    display: "flex",
    alignItems: "center",
    fontWeight: 700,
    fontSize: "0.95rem",
    color: "#1a2b50",
    gap: 8,
  },
  hint: {
    fontWeight: 400,
    fontSize: "0.8rem",
    color: "#5a6c8d",
  },
  code: {
    background: "#eaf0ff",
    color: "#1453c6",
    borderRadius: 4,
    padding: "1px 6px",
    fontFamily: "monospace",
    fontSize: "0.8rem",
  },
  panelMeta: {
    display: "flex",
    gap: 8,
    alignItems: "center",
  },
  countBadge: {
    fontSize: "0.78rem",
    color: "#5a6c8d",
    background: "#eaf0ff",
    borderRadius: 10,
    padding: "2px 10px",
    fontWeight: 500,
  },
  tableWrapper: {
    overflowY: "auto",
    maxHeight: "calc(100vh - 240px)",
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
    position: "sticky",
    top: 0,
    zIndex: 1,
  },
  tr: {
    borderBottom: "1px solid #f0f4fb",
    transition: "background 0.1s",
  },
  trUuid: {
    background: "#fafbff",
  },
  td: {
    padding: "10px 16px",
    verticalAlign: "middle",
  },
  colName: {
    fontWeight: 500,
    color: "#1a2b50",
  },
  dataTypeBadge: {
    display: "inline-block",
    background: "#f0f4fb",
    color: "#5a6c8d",
    borderRadius: 8,
    padding: "2px 10px",
    fontSize: "0.78rem",
    fontWeight: 500,
  },
  dataTypeBadgeUuid: {
    background: "#eaf0ff",
    color: "#1453c6",
    fontWeight: 600,
  },
  selectWrapper: {
    position: "relative",
  },
  select: {
    width: "100%",
    padding: "8px 32px 8px 12px",
    borderRadius: 8,
    border: "1.5px solid #d0d9f0",
    fontSize: "0.85rem",
    color: "#1a2b50",
    background: "#f8faff",
    appearance: "none",
    cursor: "pointer",
    outline: "none",
    boxSizing: "border-box",
    minWidth: 200,
  },
  selectArrow: {
    position: "absolute",
    right: 10,
    top: "50%",
    transform: "translateY(-50%)",
    color: "#5a6c8d",
    pointerEvents: "none",
    fontSize: "0.75rem",
  },
  targetDataTypeBadge: {
    display: "inline-block",
    background: "#eaf7ee",
    color: "#1a7a3c",
    borderRadius: 8,
    padding: "2px 10px",
    fontSize: "0.78rem",
    fontWeight: 500,
  },
  emptyCell: {
    color: "#b0bcd4",
    fontSize: "0.85rem",
  },
  configureBtn: {
    width: 32,
    height: 32,
    borderRadius: 8,
    border: "none",
    fontSize: "0.9rem",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    transition: "all 0.2s",
  },
  configureBtnActive: {
    background: "linear-gradient(135deg, #1453c6, #2a6ce8)",
    color: "white",
    cursor: "pointer",
    boxShadow: "0 2px 8px rgba(20,83,198,0.3)",
  },
  configureBtnMapped: {
    background: "linear-gradient(135deg, #1a7a3c, #25a355)",
    color: "white",
    cursor: "pointer",
    boxShadow: "0 2px 8px rgba(26,122,60,0.3)",
  },
  configureBtnDisabled: {
    background: "#e8edf7",
    color: "#b0bcd4",
    cursor: "not-allowed",
  },
  noConfigureCell: {
    color: "#b0bcd4",
    fontSize: "0.85rem",
  },
  dupCheckbox: {
    width: 16,
    height: 16,
    cursor: "pointer",
    accentColor: "#1453c6",
  },
  loadingMsg: {
    padding: "40px 20px",
    color: "#5a6c8d",
    textAlign: "center",
    fontSize: "0.9rem",
  },
  errorBox: {
    padding: "10px 14px",
    background: "#fff0f0",
    border: "1px solid #f5c2c2",
    borderRadius: 8,
    color: "#c0392b",
    fontSize: "0.85rem",
  },

  /* ── Modal ────────────────────────────────── */
  modalOverlay: {
    position: "fixed",
    inset: 0,
    background: "rgba(20, 43, 80, 0.45)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1000,
    backdropFilter: "blur(2px)",
  },
  modalBox: {
    background: "white",
    borderRadius: 18,
    boxShadow: "0 16px 48px rgba(20, 43, 80, 0.22)",
    width: "min(680px, 94vw)",
    maxHeight: "85vh",
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
  },
  modalHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    padding: "20px 24px 16px",
    borderBottom: "1px solid #e8edf7",
    background: "linear-gradient(135deg, #f8faff, #f0f4ff)",
  },
  modalTitle: {
    margin: "0 0 8px",
    fontSize: "1.15rem",
    fontWeight: 700,
    color: "#1a2b50",
  },
  modalSubtitle: {
    display: "flex",
    alignItems: "center",
    flexWrap: "wrap",
    gap: 4,
  },
  modalCloseBtn: {
    background: "none",
    border: "none",
    cursor: "pointer",
    color: "#5a6c8d",
    fontSize: "1.1rem",
    padding: 4,
    lineHeight: 1,
  },
  modalContent: {
    flex: 1,
    overflowY: "auto",
    padding: "0 0 4px",
  },
  modalTableHint: {
    padding: "12px 20px 8px",
    fontSize: "0.82rem",
    color: "#5a6c8d",
    fontStyle: "italic",
  },
  modalTableWrapper: {
    overflowY: "auto",
    maxHeight: "48vh",
  },
  emptyMsg: {
    padding: "32px 24px",
    color: "#5a6c8d",
    fontSize: "0.9rem",
    textAlign: "center",
  },
  modalFooter: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "14px 24px",
    borderTop: "1px solid #e8edf7",
    background: "#fafbff",
    gap: 12,
    flexWrap: "wrap",
  },
  modalMappedCount: {
    fontSize: "0.82rem",
    color: "#5a6c8d",
  },
  modalActions: {
    display: "flex",
    gap: 10,
  },
  cancelBtn: {
    background: "white",
    border: "1.5px solid #d0d9f0",
    borderRadius: 10,
    padding: "9px 20px",
    fontSize: "0.9rem",
    fontWeight: 600,
    color: "#5a6c8d",
    cursor: "pointer",
  },
  saveBtn: {
    background: "linear-gradient(135deg, #1453c6, #2a6ce8)",
    border: "none",
    borderRadius: 10,
    padding: "9px 22px",
    fontSize: "0.9rem",
    fontWeight: 700,
    color: "white",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    boxShadow: "0 4px 12px rgba(20,83,198,0.25)",
  },
  saveBtnDisabled: {
    background: "#c8d3ea",
    boxShadow: "none",
    cursor: "not-allowed",
  },
  saveSessionBtn: {
    background: "linear-gradient(135deg, #1a7a3c, #25a355)",
    color: "white",
    border: "none",
    borderRadius: 10,
    padding: "10px 20px",
    fontWeight: 700,
    fontSize: "0.9rem",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    boxShadow: "0 4px 12px rgba(26,122,60,0.25)",
    whiteSpace: "nowrap",
  },
  saveSessionBtnDisabled: {
    background: "#c8d3ea",
    boxShadow: "none",
    cursor: "not-allowed",
  },
};

export default MetadataComparisonDetail;
