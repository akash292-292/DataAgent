import { createContext, useContext, useState, useEffect } from "react";

const MappingSessionContext = createContext(null);

const STORAGE_KEY = "metadata_mapping_sessions";

export const MappingSessionProvider = ({ children }) => {
  const [sessions, setSessions] = useState(() => {
    try {
      const stored = sessionStorage.getItem(STORAGE_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  // Keep sessionStorage in sync whenever sessions change
  useEffect(() => {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  }, [sessions]);

  const addSession = (session) => {
    setSessions((prev) => {
      // Replace existing entry if same source+target pair
      const idx = prev.findIndex(
        (s) => s.sourceTable === session.sourceTable && s.targetObject === session.targetObject
      );
      if (idx >= 0) {
        const updated = [...prev];
        updated[idx] = session;
        return updated;
      }
      return [...prev, session];
    });
  };

  const removeSession = (sourceTable, targetObject) => {
    setSessions((prev) =>
      prev.filter(
        (s) => !(s.sourceTable === sourceTable && s.targetObject === targetObject)
      )
    );
  };

  const clearSessions = () => setSessions([]);

  return (
    <MappingSessionContext.Provider value={{ sessions, addSession, removeSession, clearSessions }}>
      {children}
    </MappingSessionContext.Provider>
  );
};

export const useMappingSession = () => {
  const ctx = useContext(MappingSessionContext);
  if (!ctx) throw new Error("useMappingSession must be used within MappingSessionProvider");
  return ctx;
};
