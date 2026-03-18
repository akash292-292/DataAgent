import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";

const BASE_URL = process.env.REACT_APP_BASE_BACKEND_URL;

const PROJECT_TYPES = [
  { label: "Data Integration (DI)", value: "DI" },
  { label: "Data Migration (DM)", value: "DM" },
];

const EMPTY_PICKLISTS = { phases: [], subphases_by_phase: {}, gate_checks_by_subphase: {}, statuses: [] };

const SELECT_ARROW =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='7' viewBox='0 0 10 7'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%235a6c8d' stroke-width='1.5' fill='none' stroke-linecap='round'/%3E%3C/svg%3E\")";

function newRow() {
  return { _key: crypto.randomUUID(), id: null, phase: "", subphase: "", gate_check: "", status: "", comments: "", planned_date: "", actual_date: "", document_link: "" };
}

// ─── Component ────────────────────────────────────────────────────────────────
const Governance = () => {
  const navigate = useNavigate();
  const userEmail = localStorage.getItem("user_email") || "";

  // view: 'list' | 'create' | 'edit'
  const [view, setView] = useState("list");

  // List state
  const [projects, setProjects] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [listError, setListError] = useState("");

  // Drive upload state
  const [driveLinks, setDriveLinks] = useState({});
  const [driveLoading, setDriveLoading] = useState({});

  // Create state
  const [createType, setCreateType] = useState("");
  const [createName, setCreateName] = useState("");
  const [isSavingCreate, setIsSavingCreate] = useState(false);
  const [createError, setCreateError] = useState("");

  // Edit state
  const [editProject, setEditProject] = useState(null);
  const [editType, setEditType] = useState("");
  const [editName, setEditName] = useState("");
  const [phaseRows, setPhaseRows] = useState([newRow()]);
  const [isSavingEdit, setIsSavingEdit] = useState(false);
  const [editError, setEditError] = useState("");
  const [picklists, setPicklists] = useState(EMPTY_PICKLISTS);
  const [picklistsLoading, setPicklistsLoading] = useState(false);
  const [tooltipKey, setTooltipKey] = useState(null);

  // ── Fetch projects ───────────────────────────────────────────────────────
  useEffect(() => {
    if (view === "list") fetchProjects();
  }, [view]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchProjects = async () => {
    setIsLoading(true);
    setListError("");
    try {
      const res = await fetch(
        `${BASE_URL}/api/governance/projects?email=${encodeURIComponent(userEmail)}`,
        { credentials: "include" }
      );
      if (!res.ok) throw new Error("Failed to load projects.");
      setProjects(await res.json());
    } catch (err) {
      setListError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  // ── Create handlers ──────────────────────────────────────────────────────
  const openCreate = () => {
    setCreateType("");
    setCreateName("");
    setCreateError("");
    setView("create");
  };

  const handleCreate = async () => {
    setCreateError("");
    setIsSavingCreate(true);
    try {
      const res = await fetch(`${BASE_URL}/api/governance/projects`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_email: userEmail, project_name: createName.trim(), project_type: createType }),
      });
      if (!res.ok) throw new Error("Failed to create project.");
      setView("list");
    } catch (err) {
      setCreateError(err.message);
    } finally {
      setIsSavingCreate(false);
    }
  };

  // ── Edit handlers ────────────────────────────────────────────────────────
  const openEdit = async (project) => {
    setEditProject(project);
    setEditType(project.project_type);
    setEditName(project.project_name);
    setEditError("");
    setPhaseRows([newRow()]);
    setPicklists(EMPTY_PICKLISTS);
    setPicklistsLoading(true);
    setView("edit");

    try {
      const [phasesRes, picklistsRes] = await Promise.all([
        fetch(`${BASE_URL}/api/governance/projects/${project.id}/phases`, { credentials: "include" }),
        fetch(`${BASE_URL}/api/governance/templates/${project.project_type}/picklists`, { credentials: "include" }),
      ]);
      if (!phasesRes.ok) throw new Error("Failed to load phases.");
      const data = await phasesRes.json();
      const pl = picklistsRes.ok ? await picklistsRes.json() : EMPTY_PICKLISTS;
      if (picklistsRes.ok) setPicklists(pl);
      if (data.length > 0) {
        setPhaseRows(data.map((p) => ({ ...p, _key: p.id })));
      } else if (pl.template_rows?.length > 0) {
        setPhaseRows(pl.template_rows.map((r) => ({ ...newRow(), phase: r.phase, subphase: r.subphase, gate_check: r.gate_check })));
      } else {
        setPhaseRows([newRow()]);
      }
    } catch (err) {
      setEditError(err.message);
    } finally {
      setPicklistsLoading(false);
    }
  };

  const updateRow = (key, field, value) => {
    setPhaseRows((rows) => rows.map((r) => (r._key === key ? { ...r, [field]: value } : r)));
  };

  const addRow = () => setPhaseRows((rows) => [...rows, newRow()]);

  const deleteRow = (key) => {
    setPhaseRows((rows) => {
      const updated = rows.filter((r) => r._key !== key);
      return updated.length === 0 ? [newRow()] : updated;
    });
  };

  const handleSaveEdit = async () => {
    setEditError("");
    setIsSavingEdit(true);
    try {
      const projRes = await fetch(`${BASE_URL}/api/governance/projects/${editProject.id}`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_email: userEmail, project_name: editName.trim(), project_type: editType }),
      });
      if (!projRes.ok) throw new Error("Failed to update project.");

      const validRows = phaseRows.filter((r) => r.phase || r.subphase || r.gate_check || r.status || r.comments || r.planned_date || r.actual_date || r.document_link);
      const phaseRes = await fetch(`${BASE_URL}/api/governance/projects/${editProject.id}/phases/bulk`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phases: validRows.map(({ _key, ...rest }) => rest) }),
      });
      if (!phaseRes.ok) throw new Error("Failed to save phases.");

      setView("list");
    } catch (err) {
      setEditError(err.message);
    } finally {
      setIsSavingEdit(false);
    }
  };

  // ── Delete project ───────────────────────────────────────────────────────
  const handleDelete = async (projectId) => {
    if (!window.confirm("Delete this project and all its phase records?")) return;
    try {
      const res = await fetch(
        `${BASE_URL}/api/governance/projects/${projectId}?email=${encodeURIComponent(userEmail)}`,
        { method: "DELETE", credentials: "include" }
      );
      if (!res.ok) throw new Error("Failed to delete project.");
      setProjects((prev) => prev.filter((p) => p.id !== projectId));
    } catch (err) {
      setListError(err.message);
    }
  };

  // ── Download filled template ─────────────────────────────────────────────
  const handleDownload = async (project) => {
    try {
      const res = await fetch(
        `${BASE_URL}/api/governance/projects/${project.id}/download?email=${encodeURIComponent(userEmail)}`,
        { credentials: "include" }
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Download failed.");
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${project.project_name}_${project.project_type}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setListError(err.message);
    }
  };

  // ── Upload to Google Drive ───────────────────────────────────────────────
  const handleUploadToDrive = async (project) => {
    setDriveLoading((prev) => ({ ...prev, [project.id]: true }));
    setListError("");
    try {
      const res = await fetch(
        `${BASE_URL}/api/governance/projects/${project.id}/upload-to-drive?email=${encodeURIComponent(userEmail)}`,
        { method: "POST", credentials: "include" }
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Upload to Drive failed.");
      }
      const data = await res.json();
      setDriveLinks((prev) => ({ ...prev, [project.id]: data.file_url }));
    } catch (err) {
      setListError(err.message);
    } finally {
      setDriveLoading((prev) => ({ ...prev, [project.id]: false }));
    }
  };

  // ── Error banner ─────────────────────────────────────────────────────────
  const ErrorBanner = ({ msg }) =>
    msg ? <div style={s.errorBox}>{msg}</div> : null;

  // ════════════════════════════════════════════════════════════════════════════
  // SCREEN 1 — List
  // ════════════════════════════════════════════════════════════════════════════
  if (view === "list") {
    return (
      <div style={s.page}>
        {/* Header */}
        <div style={s.header}>
          <button style={s.backBtn} onClick={() => navigate("/dashboard")}>
            <i className="fas fa-arrow-left" style={{ marginRight: 8 }} />
            Back
          </button>
          <div style={s.headerTitle}>
            <span style={{ fontSize: "2.5rem" }}>📋</span>
            <div>
              <h1 style={s.title}>Data Project Governance</h1>
              <p style={s.subtitle}>Track and manage your Data Projects</p>
            </div>
          </div>
          <button style={s.createBtn} onClick={openCreate}>
            <i className="fas fa-plus" style={{ marginRight: 8 }} />
            Create Project
          </button>
        </div>

        <ErrorBanner msg={listError} />

        {/* Table Card */}
        <div style={s.tableCard}>
          <div style={s.tableCardHeader}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <i className="fas fa-layer-group" style={{ color: "#1453c6" }} />
              <span style={s.tableCardTitle}>Projects</span>
              {!isLoading && (
                <span style={s.countBadge}>
                  {projects.length} project{projects.length !== 1 ? "s" : ""}
                </span>
              )}
            </div>
          </div>

          {isLoading ? (
            <div style={s.loadingMsg}>
              <i className="fas fa-spinner fa-spin" style={{ marginRight: 8 }} />
              Loading projects...
            </div>
          ) : projects.length === 0 ? (
            <div style={s.emptyState}>
              <div style={{ fontSize: "2.5rem", marginBottom: 12 }}>📋</div>
              <div style={{ color: "#5a6c8d", fontSize: "0.95rem" }}>
                No projects yet. Click <strong>Create Project</strong> to get started.
              </div>
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={s.table}>
                <thead>
                  <tr>
                    <th style={{ ...s.th, width: 40 }}>#</th>
                    <th style={s.th}>Project Type</th>
                    <th style={s.th}>Project Name</th>
                    <th style={{ ...s.th, textAlign: "center" }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {projects.map((p, i) => (
                    <tr key={p.id} style={s.tr}>
                      <td style={{ ...s.td, color: "#b0bcd4", fontWeight: 600, fontSize: "0.8rem" }}>
                        {i + 1}
                      </td>
                      <td style={s.td}>
                        <span style={p.project_type === "DI" ? s.typeChipDI : s.typeChipDM}>
                          <i className="fas fa-database" style={{ marginRight: 6, fontSize: "0.75rem" }} />
                          {p.project_type === "DI" ? "Data Integration" : "Data Migration"}
                        </span>
                      </td>
                      <td style={{ ...s.td, fontWeight: 600 }}>{p.project_name}</td>
                      <td style={{ ...s.td, textAlign: "center" }}>
                        <div style={{ display: "flex", gap: 6, justifyContent: "center", flexWrap: "wrap", alignItems: "center" }}>
                          <button onClick={() => openEdit(p)} style={s.actionBtnBlue} title="Edit project and phases">
                            <i className="fas fa-edit" style={{ marginRight: 5 }} />Edit
                          </button>
                          <button onClick={() => handleDownload(p)} style={s.actionBtnGhost} title="Download filled template">
                            <i className="fas fa-download" style={{ marginRight: 5 }} />Local
                          </button>
                          <button
                            onClick={() => handleUploadToDrive(p)}
                            disabled={driveLoading[p.id]}
                            style={{ ...s.actionBtnGreen, opacity: driveLoading[p.id] ? 0.7 : 1 }}
                            title="Save filled template to Google Drive"
                          >
                            <i className={`fas ${driveLoading[p.id] ? "fa-spinner fa-spin" : "fa-cloud-upload-alt"}`} style={{ marginRight: 5 }} />
                            {driveLoading[p.id] ? "Uploading..." : "Save to Drive"}
                          </button>
                          {driveLinks[p.id] && (
                            <a href={driveLinks[p.id]} target="_blank" rel="noopener noreferrer" style={s.driveLink}>
                              <i className="fas fa-external-link-alt" style={{ marginRight: 4, fontSize: "0.75rem" }} />
                              Open in Drive
                            </a>
                          )}
                          <button onClick={() => handleDelete(p.id)} style={s.actionBtnRed} title="Delete project">
                            <i className="fas fa-trash" style={{ marginRight: 5 }} />Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    );
  }

  // ════════════════════════════════════════════════════════════════════════════
  // SCREEN 2 — Create Project
  // ════════════════════════════════════════════════════════════════════════════
  if (view === "create") {
    const isValid = createType !== "" && createName.trim() !== "";
    return (
      <div style={{ ...s.page, alignItems: "center", justifyContent: "center" }}>
        <div style={s.createCard}>
          <div style={{ textAlign: "center", marginBottom: 32 }}>
            <div style={{ fontSize: "2.2rem", marginBottom: 10 }}>📋</div>
            <h2 style={{ margin: "0 0 6px", fontSize: "1.5rem", fontWeight: 700, color: "#1a2b50" }}>
              Create Project
            </h2>
            <p style={{ margin: 0, color: "#5a6c8d", fontSize: "0.9rem" }}>
              Select a type and enter a project name to get started.
            </p>
          </div>

          <div style={{ marginBottom: 20 }}>
            <label style={s.fieldLabel}>Project Type <span style={{ color: "#c0392b" }}>*</span></label>
            <select
              value={createType}
              onChange={(e) => setCreateType(e.target.value)}
              style={{
                ...s.fieldInput,
                color: createType ? "#0a1628" : "#5a6c8d",
                appearance: "none",
                backgroundImage: SELECT_ARROW,
                backgroundRepeat: "no-repeat",
                backgroundPosition: "right 14px center",
                paddingRight: 36,
              }}
            >
              <option value="" disabled>Select type...</option>
              {PROJECT_TYPES.map((pt) => (
                <option key={pt.value} value={pt.value}>{pt.label}</option>
              ))}
            </select>
          </div>

          <div style={{ marginBottom: 28 }}>
            <label style={s.fieldLabel}>Project Name <span style={{ color: "#c0392b" }}>*</span></label>
            <input
              type="text"
              value={createName}
              onChange={(e) => setCreateName(e.target.value)}
              placeholder="Enter project name..."
              style={s.fieldInput}
              onFocus={(e) => (e.target.style.borderColor = "#1453c6")}
              onBlur={(e) => (e.target.style.borderColor = "#d0d9f0")}
            />
          </div>

          <ErrorBanner msg={createError} />

          <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
            <button onClick={() => setView("list")} style={s.cancelBtn}>Cancel</button>
            <button
              onClick={handleCreate}
              disabled={!isValid || isSavingCreate}
              style={{ ...s.saveBtn, ...(isValid ? {} : s.saveBtnDisabled) }}
            >
              <i className="fas fa-save" style={{ marginRight: 8 }} />
              {isSavingCreate ? "Saving..." : "Save Project"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ════════════════════════════════════════════════════════════════════════════
  // SCREEN 3 — Edit Project (phase records table)
  // ════════════════════════════════════════════════════════════════════════════
  const cellSelect = (value, onChange, options, placeholder, disabled = false) => (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      style={{
        width: "100%",
        padding: "7px 28px 7px 10px",
        border: "1.5px solid #d0d9f0",
        borderRadius: 8,
        fontSize: "0.83rem",
        color: value ? "#0a1628" : "#5a6c8d",
        backgroundColor: disabled ? "#f0f2f8" : "#f8faff",
        outline: "none",
        boxSizing: "border-box",
        appearance: "none",
        backgroundImage: disabled ? "none" : SELECT_ARROW,
        backgroundRepeat: "no-repeat",
        backgroundPosition: "right 8px center",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.6 : 1,
      }}
    >
      <option value="">{placeholder}</option>
      {options.map((o) => <option key={o} value={o}>{o}</option>)}
    </select>
  );

  const configuredCount = phaseRows.filter((r) => r.phase || r.status).length;

  return (
    <div style={s.page}>
      {/* Header */}
      <div style={s.header}>
        <button style={s.backBtn} onClick={() => setView("list")}>
          <i className="fas fa-arrow-left" style={{ marginRight: 8 }} />
          Back
        </button>
        <div style={{ display: "flex", flexDirection: "column", gap: 4, flex: 1 }}>
          <h1 style={s.title}>{editType || "—"} - {editName || "—"}</h1>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          {/* {configuredCount > 0 && (
            <span style={s.configuredBadge}>
              <i className="fas fa-check-circle" style={{ marginRight: 6 }} />
              {configuredCount} phase{configuredCount !== 1 ? "s" : ""} configured
            </span>
          )} */}
          <button
            onClick={handleSaveEdit}
            disabled={isSavingEdit}
            style={{ ...s.saveBtn, ...(isSavingEdit ? s.saveBtnDisabled : {}) }}
          >
            <i className="fas fa-save" style={{ marginRight: 8 }} />
            {isSavingEdit ? "Saving..." : "Save Project"}
          </button>
        </div>
      </div>

      <ErrorBanner msg={editError} />

      {/* Phase records panel */}
      <div style={s.panel}>
        <div style={s.panelHeader}>
          <div style={{ display: "flex", alignItems: "center", fontWeight: 700, fontSize: "0.95rem", color: "#1a2b50", gap: 8, flexWrap: "wrap" }}>
            <i className="fas fa-table" style={{ color: "#1453c6" }} />
            Phases
            <span style={{ fontWeight: 400, fontSize: "0.8rem", color: "#5a6c8d" }}>
              Fill in phases, statuses, dates and document links
            </span>
            {picklistsLoading && (
              <span style={{ fontSize: "0.78rem", color: "#1453c6" }}>
                <i className="fas fa-spinner fa-spin" style={{ marginRight: 4 }} />
                Loading picklists...
              </span>
            )}
          </div>
          <button onClick={addRow} style={s.addRowBtn}>
            <i className="fas fa-plus" style={{ marginRight: 6 }} />
            Add Record
          </button>
        </div>

        <div style={{ flex: 1, overflowX: "auto", overflowY: "auto" }}>
          <table style={s.table}>
            <thead>
              <tr>
                <th style={{ ...s.th, width: 40 }}>#</th>
                <th style={{ ...s.th, minWidth: 180 }}>Phase</th>
                <th style={{ ...s.th, minWidth: 200 }}>Sub-Phase</th>
                <th style={{ ...s.th, minWidth: 160 }}>Status</th>
                <th style={{ ...s.th, minWidth: 260 }}>Comments</th>
                <th style={{ ...s.th, minWidth: 160 }}>Planned Date</th>
                <th style={{ ...s.th, minWidth: 160 }}>Actual Date</th>
                <th style={{ ...s.th, minWidth: 180 }}>Document Link</th>
                <th style={{ ...s.th, width: 44, textAlign: "center" }}></th>
              </tr>
            </thead>
            <tbody>
              {phaseRows.map((row, idx) => (
                <tr key={row._key} style={s.tr}>
                  <td style={{ ...s.td, color: "#b0bcd4", fontWeight: 600, fontSize: "0.78rem", textAlign: "center" }}>
                    {idx + 1}
                  </td>
                  <td style={s.td}>
                    {cellSelect(
                      row.phase,
                      (v) => setPhaseRows((rows) => rows.map((r) => r._key === row._key ? { ...r, phase: v, subphase: "", gate_check: "" } : r)),
                      picklists.phases,
                      "Select phase..."
                    )}
                  </td>
                  <td style={s.td}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      {cellSelect(
                        row.subphase,
                        (v) => setPhaseRows((rows) => rows.map((r) => r._key === row._key ? { ...r, subphase: v, gate_check: "" } : r)),
                        row.phase ? (picklists.subphases_by_phase[row.phase] || []) : [],
                        "Select sub-phase...",
                        !row.phase
                      )}
                      {row.subphase && row.gate_check && (
                        <div
                          style={{ position: "relative", flexShrink: 0 }}
                          onMouseEnter={() => setTooltipKey(row._key)}
                          onMouseLeave={() => setTooltipKey(null)}
                        >
                          <i className="fas fa-info-circle" style={{ color: "#1453c6", cursor: "help", fontSize: "0.95rem" }} />
                          {tooltipKey === row._key && (
                            <div style={{
                              position: "absolute", left: "50%", bottom: "calc(100% + 8px)",
                              transform: "translateX(-50%)", background: "#1a2b50", color: "white",
                              borderRadius: 8, padding: "8px 12px", fontSize: "0.78rem",
                              whiteSpace: "nowrap", zIndex: 200,
                              boxShadow: "0 4px 16px rgba(0,0,0,0.22)", minWidth: 160,
                            }}>
                              <div style={{ fontWeight: 700, marginBottom: 4, color: "#90b8ff" }}>Gate Check/Review Session</div>
                              <div>• {row.gate_check}</div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </td>
                  <td style={s.td}>
                    {cellSelect(row.status, (v) => updateRow(row._key, "status", v), picklists.statuses, "Select status...")}
                  </td>
                  <td style={s.td}>
                    <input
                      type="text"
                      value={row.comments || ""}
                      onChange={(e) => updateRow(row._key, "comments", e.target.value)}
                      placeholder="Add comments..."
                      maxLength={500}
                      style={s.cellInput}
                      onFocus={(e) => (e.target.style.borderColor = "#1453c6")}
                      onBlur={(e) => (e.target.style.borderColor = "#d0d9f0")}
                    />
                  </td>
                  <td style={s.td}>
                    <input
                      type="date"
                      value={row.planned_date || ""}
                      onChange={(e) => updateRow(row._key, "planned_date", e.target.value)}
                      style={s.cellInput}
                      onFocus={(e) => (e.target.style.borderColor = "#1453c6")}
                      onBlur={(e) => (e.target.style.borderColor = "#d0d9f0")}
                    />
                  </td>
                  <td style={s.td}>
                    <input
                      type="date"
                      value={row.actual_date || ""}
                      onChange={(e) => updateRow(row._key, "actual_date", e.target.value)}
                      style={s.cellInput}
                      onFocus={(e) => (e.target.style.borderColor = "#1453c6")}
                      onBlur={(e) => (e.target.style.borderColor = "#d0d9f0")}
                    />
                  </td>
                  <td style={s.td}>
                    <input
                      type="url"
                      value={row.document_link || ""}
                      onChange={(e) => updateRow(row._key, "document_link", e.target.value)}
                      placeholder="https://..."
                      style={s.cellInput}
                      onFocus={(e) => (e.target.style.borderColor = "#1453c6")}
                      onBlur={(e) => (e.target.style.borderColor = "#d0d9f0")}
                    />
                  </td>
                  <td style={{ ...s.td, textAlign: "center" }}>
                    <button onClick={() => deleteRow(row._key)} title="Remove row" style={s.removeRowBtn}>
                      <i className="fas fa-times" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
};

// ─── Styles ───────────────────────────────────────────────────────────────────
const s = {
  page: {
    height: "100vh",
    display: "flex",
    flexDirection: "column",
    background: "linear-gradient(135deg, #f3f6fb 0%, #e8edf7 100%)",
    fontFamily: "'Inter', system-ui, sans-serif",
    color: "#1a2b50",
    padding: "32px 40px",
    boxSizing: "border-box",
    display: "flex",
    flexDirection: "column",
    gap: 24,
  },

  /* Header */
  header: {
    display: "flex",
    alignItems: "center",
    gap: 24,
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
    fontSize: "0.95rem",
    boxShadow: "0 4px 12px rgba(20, 83, 198, 0.2)",
    whiteSpace: "nowrap",
  },
  headerTitle: {
    display: "flex",
    alignItems: "center",
    gap: 16,
    flex: 1,
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
  createBtn: {
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
    boxShadow: "0 4px 12px rgba(26, 122, 60, 0.25)",
    whiteSpace: "nowrap",
  },

  /* Edit header breadcrumb */
  breadcrumbType: {
    background: "#eaf0ff",
    color: "#1453c6",
    border: "1px solid #c5d4f7",
    borderRadius: 20,
    padding: "4px 12px",
    fontSize: "0.85rem",
    fontWeight: 600,
  },
  breadcrumbName: {
    background: "#f0eaff",
    color: "#5b21b6",
    border: "1px solid #c4b5fd",
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

  /* Table card (list screen) */
  tableCard: {
    background: "white",
    borderRadius: 20,
    boxShadow: "0 8px 32px rgba(20, 83, 198, 0.10)",
    overflow: "hidden",
  },
  tableCardHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "18px 24px",
    borderBottom: "1px solid #e8edf7",
    background: "linear-gradient(135deg, #f8faff, #f0f4ff)",
  },
  tableCardTitle: {
    fontWeight: 700,
    fontSize: "1rem",
    color: "#1a2b50",
  },
  countBadge: {
    background: "#eaf0ff",
    color: "#1453c6",
    borderRadius: 12,
    padding: "2px 10px",
    fontSize: "0.78rem",
    fontWeight: 600,
  },
  loadingMsg: {
    padding: "48px 24px",
    color: "#5a6c8d",
    textAlign: "center",
    fontSize: "0.9rem",
  },
  emptyState: {
    padding: "60px 24px",
    textAlign: "center",
  },

  /* Table */
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
  },
  td: {
    padding: "12px 16px",
    verticalAlign: "middle",
  },

  /* Type chips */
  typeChipDI: {
    background: "#eaf0ff",
    color: "#1453c6",
    border: "1px solid #c5d4f7",
    borderRadius: 20,
    padding: "4px 12px",
    fontSize: "0.82rem",
    fontWeight: 600,
    display: "inline-flex",
    alignItems: "center",
    whiteSpace: "nowrap",
  },
  typeChipDM: {
    background: "#eaf7ee",
    color: "#1a7a3c",
    border: "1px solid #c3e6d0",
    borderRadius: 20,
    padding: "4px 12px",
    fontSize: "0.82rem",
    fontWeight: 600,
    display: "inline-flex",
    alignItems: "center",
    whiteSpace: "nowrap",
  },

  /* Action buttons */
  actionBtnBlue: {
    background: "linear-gradient(135deg, #1453c6, #2a6ce8)",
    color: "white",
    border: "none",
    borderRadius: 7,
    padding: "6px 12px",
    fontSize: "0.8rem",
    fontWeight: 600,
    cursor: "pointer",
    display: "inline-flex",
    alignItems: "center",
    boxShadow: "0 2px 6px rgba(20,83,198,0.25)",
    whiteSpace: "nowrap",
  },
  actionBtnGhost: {
    background: "white",
    color: "#1453c6",
    border: "1.5px solid #c5d4f7",
    borderRadius: 7,
    padding: "5px 12px",
    fontSize: "0.8rem",
    fontWeight: 600,
    cursor: "pointer",
    display: "inline-flex",
    alignItems: "center",
    whiteSpace: "nowrap",
  },
  actionBtnGreen: {
    background: "white",
    color: "#1a7a3c",
    border: "1.5px solid #c3e6d0",
    borderRadius: 7,
    padding: "5px 12px",
    fontSize: "0.8rem",
    fontWeight: 600,
    cursor: "pointer",
    display: "inline-flex",
    alignItems: "center",
    whiteSpace: "nowrap",
  },
  actionBtnRed: {
    background: "#fff0f0",
    color: "#c0392b",
    border: "1.5px solid #f5c2c2",
    borderRadius: 7,
    padding: "5px 12px",
    fontSize: "0.8rem",
    fontWeight: 600,
    cursor: "pointer",
    display: "inline-flex",
    alignItems: "center",
    whiteSpace: "nowrap",
  },
  driveLink: {
    fontSize: "0.8rem",
    color: "#1a7a3c",
    fontWeight: 600,
    textDecoration: "none",
    display: "inline-flex",
    alignItems: "center",
    whiteSpace: "nowrap",
  },

  /* Error */
  errorBox: {
    padding: "10px 14px",
    background: "#fff0f0",
    border: "1px solid #f5c2c2",
    borderRadius: 8,
    color: "#c0392b",
    fontSize: "0.85rem",
  },

  /* Create card */
  createCard: {
    background: "white",
    borderRadius: 20,
    padding: "44px 48px",
    boxShadow: "0 8px 32px rgba(20, 83, 198, 0.12)",
    width: "100%",
    maxWidth: 500,
  },

  /* Edit: info card */
  infoCard: {
    background: "white",
    borderRadius: 16,
    boxShadow: "0 4px 20px rgba(20, 83, 198, 0.08)",
    overflow: "hidden",
  },
  infoCardHeader: {
    padding: "14px 20px",
    borderBottom: "1px solid #e8edf7",
    background: "linear-gradient(135deg, #f8faff, #f0f4ff)",
  },
  infoCardBody: {
    padding: "20px 24px",
    display: "flex",
    gap: 20,
    flexWrap: "wrap",
    alignItems: "flex-end",
  },

  /* Edit: phase panel */
  panel: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    background: "white",
    borderRadius: 16,
    boxShadow: "0 4px 20px rgba(20, 83, 198, 0.08)",
    overflow: "hidden",
    minHeight: 0,
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
  addRowBtn: {
    background: "linear-gradient(135deg, #1453c6, #2a6ce8)",
    color: "white",
    border: "none",
    borderRadius: 8,
    padding: "8px 16px",
    fontSize: "0.85rem",
    fontWeight: 600,
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    boxShadow: "0 2px 8px rgba(20,83,198,0.2)",
  },
  removeRowBtn: {
    width: 28,
    height: 28,
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
  cellInput: {
    width: "100%",
    padding: "7px 10px",
    border: "1.5px solid #d0d9f0",
    borderRadius: 8,
    fontSize: "0.83rem",
    color: "#1a2b50",
    background: "#f8faff",
    outline: "none",
    boxSizing: "border-box",
  },

  /* Shared field inputs */
  fieldLabel: {
    display: "block",
    fontWeight: 600,
    color: "#1a2b50",
    marginBottom: 6,
    fontSize: "0.85rem",
  },
  fieldInput: {
    width: "100%",
    padding: "11px 14px",
    borderRadius: 10,
    border: "1.5px solid #d0d9f0",
    fontSize: "0.9rem",
    color: "#1a2b50",
    background: "#f8faff",
    outline: "none",
    boxSizing: "border-box",
  },

  /* Save / Cancel */
  saveBtn: {
    background: "linear-gradient(135deg, #1a7a3c, #25a355)",
    color: "white",
    border: "none",
    borderRadius: 10,
    padding: "10px 22px",
    fontSize: "0.9rem",
    fontWeight: 700,
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    boxShadow: "0 4px 12px rgba(26,122,60,0.25)",
    whiteSpace: "nowrap",
  },
  saveBtnDisabled: {
    background: "#c8d3ea",
    boxShadow: "none",
    cursor: "not-allowed",
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
};

export default Governance;