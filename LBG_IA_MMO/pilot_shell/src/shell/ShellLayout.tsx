import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { ActivityBar } from "./ActivityBar";
import { AgentPanel } from "./AgentPanel";
import { BottomPanel } from "./BottomPanel";
import { CommandPalette } from "./CommandPalette";
import { Sidebar } from "./Sidebar";
import { SettingsDialog } from "./SettingsDialog";
import { useLayout } from "../stores/context";

type ShellLayoutProps = {
  children: ReactNode;
};

export function ShellLayout({ children }: ShellLayoutProps) {
  const { layout, setLayout, toggleSidebar, toggleAgentPanel, toggleBottomPanel } = useLayout();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const dragRef = useRef<{ kind: "sidebar" | "agent" | "bottom"; start: number; size: number } | null>(
    null,
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "p") {
        e.preventDefault();
        setPaletteOpen(true);
      }
      if (e.ctrlKey && e.key.toLowerCase() === "b") {
        e.preventDefault();
        toggleSidebar();
      }
      if (e.ctrlKey && e.key.toLowerCase() === "j") {
        e.preventDefault();
        toggleBottomPanel();
      }
      if (e.ctrlKey && e.key.toLowerCase() === "l") {
        e.preventDefault();
        toggleAgentPanel();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggleAgentPanel, toggleBottomPanel, toggleSidebar]);

  const onDragStart = useCallback(
    (kind: "sidebar" | "agent" | "bottom", startPos: number) => {
      const size =
        kind === "sidebar"
          ? layout.sidebarWidth
          : kind === "agent"
            ? layout.agentPanelWidth
            : layout.bottomPanelHeight;
      dragRef.current = { kind, start: startPos, size };
    },
    [layout.agentPanelWidth, layout.bottomPanelHeight, layout.sidebarWidth],
  );

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      const d = dragRef.current;
      if (!d) return;
      const delta =
        d.kind === "bottom" ? d.start - e.clientY : e.clientX - d.start;
      const next = Math.round(d.size + delta);
      if (d.kind === "sidebar") {
        setLayout({ sidebarWidth: Math.min(480, Math.max(180, next)) });
      } else if (d.kind === "agent") {
        setLayout({ agentPanelWidth: Math.min(640, Math.max(280, next)) });
      } else {
        setLayout({ bottomPanelHeight: Math.min(480, Math.max(120, next)) });
      }
    };
    const onUp = () => {
      dragRef.current = null;
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [setLayout]);

  return (
    <div className="shell">
      <ActivityBar />
      <div className="shell__body">
        {layout.sidebarOpen && (
          <>
            <div className="shell__sidebar" style={{ width: layout.sidebarWidth }}>
              <Sidebar />
            </div>
            <div
              className="shell__resizer shell__resizer--vertical"
              onMouseDown={(e) => onDragStart("sidebar", e.clientX)}
              role="separator"
              aria-orientation="vertical"
            />
          </>
        )}

        <div className="shell__center">
          <header className="shell__toolbar">
            <button type="button" className="btn btn--ghost btn--sm" onClick={() => setPaletteOpen(true)}>
              ⌘ Palette
            </button>
            <div className="shell__toolbar-spacer" />
            <button
              type="button"
              className={`btn btn--ghost btn--sm${layout.bottomPanelOpen ? " btn--active" : ""}`}
              onClick={toggleBottomPanel}
            >
              Panneau bas
            </button>
            <button
              type="button"
              className={`btn btn--ghost btn--sm${layout.agentPanelOpen ? " btn--active" : ""}`}
              onClick={toggleAgentPanel}
            >
              Agent
            </button>
          </header>

          <main className="shell__main">{children}</main>

          {layout.bottomPanelOpen && (
            <>
              <div
                className="shell__resizer shell__resizer--horizontal"
                onMouseDown={(e) => onDragStart("bottom", e.clientY)}
                role="separator"
                aria-orientation="horizontal"
              />
              <div className="shell__bottom" style={{ height: layout.bottomPanelHeight }}>
                <BottomPanel />
              </div>
            </>
          )}
        </div>

        {layout.agentPanelOpen && (
          <>
            <div
              className="shell__resizer shell__resizer--vertical"
              onMouseDown={(e) => onDragStart("agent", e.clientX)}
              role="separator"
              aria-orientation="vertical"
            />
            <div className="shell__agent" style={{ width: layout.agentPanelWidth }}>
              <AgentPanel />
            </div>
          </>
        )}
      </div>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
      <SettingsDialog />
    </div>
  );
}
