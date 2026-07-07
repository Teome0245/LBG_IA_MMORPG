/** Clés localStorage legacy (pilot_web) + nouvelles clés pilot_shell. */

export const STORAGE_KEYS = {
  /** Legacy pilot_web */
  apiBase: "lbg_pilot_api_base",
  serviceToken: "lbg_pilot_service_token_v1",
  token: "lbg_pilot_token",
  approval: "lbg_devops_approval",
  dryRun: "lbg_pilot_dry_run",
  agenticChat: "lbg_pilot_agentic_chat",
  metricsBearer: "lbg_pilot_metrics_bearer_v1",
  panelLayout: "lbg_pilot_panel_layout_v1",
  /** pilot_shell */
  shellLayout: "lbg_pilot_shell_layout_v1",
} as const;

export type ShellLayoutState = {
  sidebarOpen: boolean;
  agentPanelOpen: boolean;
  bottomPanelOpen: boolean;
  sidebarWidth: number;
  agentPanelWidth: number;
  bottomPanelHeight: number;
  bottomTab: "terminal" | "logs" | "metrics";
};

const DEFAULT_LAYOUT: ShellLayoutState = {
  sidebarOpen: true,
  agentPanelOpen: true,
  bottomPanelOpen: false,
  sidebarWidth: 260,
  agentPanelWidth: 380,
  bottomPanelHeight: 200,
  bottomTab: "logs",
};

export function loadShellLayout(): ShellLayoutState {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.shellLayout);
    if (!raw) return { ...DEFAULT_LAYOUT };
    const parsed = JSON.parse(raw) as Partial<ShellLayoutState>;
    return { ...DEFAULT_LAYOUT, ...parsed };
  } catch {
    return { ...DEFAULT_LAYOUT };
  }
}

export function saveShellLayout(layout: ShellLayoutState): void {
  localStorage.setItem(STORAGE_KEYS.shellLayout, JSON.stringify(layout));
}

export function readLegacyString(key: string, fallback = ""): string {
  return localStorage.getItem(key) ?? fallback;
}

export function readLegacyBool(key: string, defaultValue = true): boolean {
  const v = localStorage.getItem(key);
  if (v === null) return defaultValue;
  return v !== "0" && v !== "false";
}
