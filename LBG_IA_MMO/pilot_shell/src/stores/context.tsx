import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  loadSettings,
  saveSettings,
  type PilotSettings,
} from "../api/pilotApi";
import {
  loadShellLayout,
  saveShellLayout,
  type ShellLayoutState,
} from "../lib/storage";

type SettingsContextValue = {
  settings: PilotSettings;
  updateSettings: (patch: Partial<PilotSettings>) => void;
  settingsOpen: boolean;
  setSettingsOpen: (open: boolean) => void;
};

const SettingsContext = createContext<SettingsContextValue | null>(null);

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<PilotSettings>(() => loadSettings());
  const [settingsOpen, setSettingsOpen] = useState(false);

  const updateSettings = useCallback((patch: Partial<PilotSettings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...patch };
      saveSettings(next);
      return next;
    });
  }, []);

  const value = useMemo(
    () => ({ settings, updateSettings, settingsOpen, setSettingsOpen }),
    [settings, updateSettings, settingsOpen],
  );

  return (
    <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>
  );
}

export function useSettings(): SettingsContextValue {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error("useSettings hors SettingsProvider");
  return ctx;
}

type LayoutContextValue = {
  layout: ShellLayoutState;
  setLayout: (patch: Partial<ShellLayoutState>) => void;
  toggleSidebar: () => void;
  toggleAgentPanel: () => void;
  toggleBottomPanel: () => void;
};

const LayoutContext = createContext<LayoutContextValue | null>(null);

export function LayoutProvider({ children }: { children: ReactNode }) {
  const [layout, setLayoutState] = useState<ShellLayoutState>(() => loadShellLayout());

  const setLayout = useCallback((patch: Partial<ShellLayoutState>) => {
    setLayoutState((prev) => {
      const next = { ...prev, ...patch };
      saveShellLayout(next);
      return next;
    });
  }, []);

  const toggleSidebar = useCallback(() => {
    setLayoutState((prev) => {
      const next = { ...prev, sidebarOpen: !prev.sidebarOpen };
      saveShellLayout(next);
      return next;
    });
  }, []);

  const toggleAgentPanel = useCallback(() => {
    setLayoutState((prev) => {
      const next = { ...prev, agentPanelOpen: !prev.agentPanelOpen };
      saveShellLayout(next);
      return next;
    });
  }, []);

  const toggleBottomPanel = useCallback(() => {
    setLayoutState((prev) => {
      const next = { ...prev, bottomPanelOpen: !prev.bottomPanelOpen };
      saveShellLayout(next);
      return next;
    });
  }, []);

  const value = useMemo(
    () => ({ layout, setLayout, toggleSidebar, toggleAgentPanel, toggleBottomPanel }),
    [layout, setLayout, toggleSidebar, toggleAgentPanel, toggleBottomPanel],
  );

  return <LayoutContext.Provider value={value}>{children}</LayoutContext.Provider>;
}

export function useLayout(): LayoutContextValue {
  const ctx = useContext(LayoutContext);
  if (!ctx) throw new Error("useLayout hors LayoutProvider");
  return ctx;
}
