import { useState, useEffect, useRef, useCallback } from "react";
import ReactDOM from "react-dom";

const SearchableSelect = ({
  value,
  onChange,
  options = [],
  placeholder = "Select...",
  disabled = false,
}) => {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [dropPos, setDropPos] = useState({ top: 0, left: 0, width: 0 });
  const triggerRef = useRef(null);
  const portalRef = useRef(null);
  const searchRef = useRef(null);

  const selectedOption = options.find((o) => o.value === value);

  const filtered = options.filter((o) =>
    String(o.label ?? "").toLowerCase().includes(search.toLowerCase())
  );

  const reposition = useCallback(() => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    setDropPos({
      top: rect.bottom + 4,
      left: rect.left,
      width: rect.width,
    });
  }, []);

  useEffect(() => {
    if (!open) return;
    reposition();
    const t = setTimeout(() => searchRef.current?.focus(), 0);
    window.addEventListener("scroll", reposition, true);
    window.addEventListener("resize", reposition);
    return () => {
      clearTimeout(t);
      window.removeEventListener("scroll", reposition, true);
      window.removeEventListener("resize", reposition);
    };
  }, [open, reposition]);

  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (
        !triggerRef.current?.contains(e.target) &&
        !portalRef.current?.contains(e.target)
      ) {
        setOpen(false);
        setSearch("");
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const handleSelect = (val) => {
    onChange(val);
    setOpen(false);
    setSearch("");
  };

  const handleClear = (e) => {
    e.stopPropagation();
    onChange("");
  };

  const dropdown = open
    ? ReactDOM.createPortal(
        <div
          ref={portalRef}
          style={{
            position: "fixed",
            top: dropPos.top,
            left: dropPos.left,
            width: dropPos.width,
            zIndex: 9999,
            background: "white",
            border: "1.5px solid #1453c6",
            borderRadius: 10,
            boxShadow: "0 8px 24px rgba(20, 43, 80, 0.15)",
            overflow: "hidden",
            fontFamily: "'Inter', system-ui, sans-serif",
          }}
        >
          {/* Search input */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              padding: "8px 10px",
              borderBottom: "1px solid #e8edf7",
              gap: 6,
              background: "#f8faff",
            }}
          >
            <i
              className="fas fa-search"
              style={{ color: "#8a9bc0", fontSize: "0.8rem", flexShrink: 0 }}
            />
            <input
              ref={searchRef}
              type="text"
              placeholder="Search..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{
                flex: 1,
                border: "none",
                outline: "none",
                fontSize: "0.85rem",
                color: "#1a2b50",
                background: "transparent",
              }}
            />
            {search && (
              <button
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  color: "#8a9bc0",
                  fontSize: "0.75rem",
                  padding: 2,
                  lineHeight: 1,
                }}
                onMouseDown={(e) => {
                  e.preventDefault();
                  setSearch("");
                }}
              >
                <i className="fas fa-times" />
              </button>
            )}
          </div>

          {/* Options list */}
          <div style={{ maxHeight: 220, overflowY: "auto" }}>
            {filtered.length === 0 ? (
              <div
                style={{
                  padding: "10px 14px",
                  fontSize: "0.82rem",
                  color: "#8a9bc0",
                  textAlign: "center",
                }}
              >
                No results{search ? ` for "${search}"` : ""}
              </div>
            ) : (
              filtered.map((o) => (
                <div
                  key={o.value}
                  style={{
                    padding: "8px 14px",
                    fontSize: "0.85rem",
                    color: "#1a2b50",
                    cursor: "pointer",
                    background: o.value === value ? "#eaf0ff" : "transparent",
                    fontWeight: o.value === value ? 600 : 400,
                  }}
                  onMouseEnter={(e) => {
                    if (o.value !== value)
                      e.currentTarget.style.background = "#f4f7ff";
                  }}
                  onMouseLeave={(e) => {
                    if (o.value !== value)
                      e.currentTarget.style.background = "transparent";
                  }}
                  onMouseDown={() => handleSelect(o.value)}
                >
                  {o.label ?? o.value}
                </div>
              ))
            )}
          </div>
        </div>,
        document.body
      )
    : null;

  return (
    <>
      <div
        ref={triggerRef}
        style={{
          display: "flex",
          alignItems: "center",
          padding: "8px 12px",
          borderRadius: 8,
          border: `1.5px solid ${open ? "#1453c6" : "#d0d9f0"}`,
          background: disabled ? "#f0f4fb" : "#f8faff",
          cursor: disabled ? "not-allowed" : "pointer",
          fontSize: "0.88rem",
          color: value ? "#1a2b50" : "#8a9bc0",
          userSelect: "none",
          gap: 6,
          width: "100%",
          boxSizing: "border-box",
          opacity: disabled ? 0.7 : 1,
          transition: "border-color 0.15s",
          minHeight: 38,
        }}
        onClick={() => {
          if (!disabled) setOpen((prev) => !prev);
        }}
      >
        <span
          style={{
            flex: 1,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {selectedOption ? (selectedOption.label ?? selectedOption.value) : placeholder}
        </span>
        {value && !disabled && (
          <span
            style={{
              color: "#8a9bc0",
              fontSize: "0.75rem",
              flexShrink: 0,
              lineHeight: 1,
              padding: "2px 4px",
            }}
            onMouseDown={handleClear}
            title="Clear selection"
          >
            <i className="fas fa-times" />
          </span>
        )}
        <i
          className={`fas fa-chevron-${open ? "up" : "down"}`}
          style={{ color: "#5a6c8d", fontSize: "0.75rem", flexShrink: 0 }}
        />
      </div>
      {dropdown}
    </>
  );
};

export default SearchableSelect;
