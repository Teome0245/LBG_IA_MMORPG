import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { VIEWS } from "../lib/routes";
import { useLayout, useSettings } from "../stores/context";

type Command = {
  id: string;
  label: string;
  group: string;
  keywords: string;
  run: () => void;
};

type CommandPaletteProps = {
  open: boolean;
  onClose: () => void;
};

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const navigate = useNavigate();
  const { setSettingsOpen } = useSettings();
  const { toggleSidebar, toggleAgentPanel, toggleBottomPanel, setLayout } = useLayout();
  const [query, setQuery] = useState("");

  const commands: Command[] = useMemo(
    () => [
      ...VIEWS.map((v) => ({
        id: `nav-${v.id}`,
        label: `Aller : ${v.label}`,
        group: "Navigation",
        keywords: `${v.label} ${v.description}`,
        run: () => {
          navigate(v.path);
          onClose();
        },
      })),
      {
        id: "toggle-sidebar",
        label: "Basculer la sidebar",
        group: "Layout",
        keywords: "sidebar panneau gauche",
        run: () => {
          toggleSidebar();
          onClose();
        },
      },
      {
        id: "toggle-agent",
        label: "Basculer le panneau Agent",
        group: "Layout",
        keywords: "agent chat droite",
        run: () => {
          toggleAgentPanel();
          onClose();
        },
      },
      {
        id: "toggle-bottom",
        label: "Basculer le panneau bas",
        group: "Layout",
        keywords: "terminal logs metrics bas",
        run: () => {
          toggleBottomPanel();
          onClose();
        },
      },
      {
        id: "bottom-terminal",
        label: "Ouvrir Terminal (panneau bas)",
        group: "Layout",
        keywords: "terminal ssh",
        run: () => {
          setLayout({ bottomPanelOpen: true, bottomTab: "terminal" });
          onClose();
        },
      },
      {
        id: "settings",
        label: "Ouvrir les réglages",
        group: "Système",
        keywords: "token service bearer dry-run",
        run: () => {
          setSettingsOpen(true);
          onClose();
        },
      },
      {
        id: "legacy",
        label: "Ouvrir pilot legacy",
        group: "Système",
        keywords: "ancien index html",
        run: () => {
          window.location.href = "../?legacy=1";
        },
      },
    ],
    [navigate, onClose, setLayout, setSettingsOpen, toggleAgentPanel, toggleBottomPanel, toggleSidebar],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;
    return commands.filter(
      (c) =>
        c.label.toLowerCase().includes(q) ||
        c.group.toLowerCase().includes(q) ||
        c.keywords.toLowerCase().includes(q),
    );
  }, [commands, query]);

  useEffect(() => {
    if (!open) setQuery("");
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="palette-overlay" role="presentation" onClick={onClose}>
      <div
        className="palette"
        role="dialog"
        aria-label="Palette de commandes"
        onClick={(e) => e.stopPropagation()}
      >
        <input
          className="palette__input"
          type="text"
          placeholder="Tapez une commande…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoFocus
        />
        <ul className="palette__list">
          {filtered.length === 0 && (
            <li className="palette__empty">Aucune commande correspondante</li>
          )}
          {filtered.map((cmd) => (
            <li key={cmd.id}>
              <button type="button" className="palette__item" onClick={cmd.run}>
                <span className="palette__item-label">{cmd.label}</span>
                <span className="palette__item-group">{cmd.group}</span>
              </button>
            </li>
          ))}
        </ul>
        <footer className="palette__footer">
          <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>P</kbd> · <kbd>Esc</kbd> fermer
        </footer>
      </div>
    </div>
  );
}
