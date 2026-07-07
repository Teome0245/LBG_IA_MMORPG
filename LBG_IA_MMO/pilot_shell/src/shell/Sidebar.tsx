import { NavLink, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { fetchCapabilities, fetchStatus } from "../api/pilotApi";
import { VIEWS, viewByPath } from "../lib/routes";
import { useSettings } from "../stores/context";

export function Sidebar() {
  const location = useLocation();
  const { settings } = useSettings();
  const [stackLine, setStackLine] = useState("Chargement…");
  const [online, setOnline] = useState<boolean | null>(null);
  const current = viewByPath(location.pathname) ?? VIEWS[0];

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [st, caps] = await Promise.all([
          fetchStatus(settings),
          fetchCapabilities(settings),
        ]);
        if (cancelled) return;
        setOnline(true);
        const app = String(st.app || "LBG");
        const orch = String(st.orchestrator_url || "—");
        const cap = caps.slice(0, 4).join(" · ");
        setStackLine(`${app} · ${cap}${caps.length > 4 ? "…" : ""} · ${orch}`);
      } catch {
        if (!cancelled) {
          setOnline(false);
          setStackLine("Backend hors ligne — vérifier :8000");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [settings]);

  return (
    <aside className="sidebar">
      <header className="sidebar__header">
        <h1 className="sidebar__title">{current.label}</h1>
        <p className="sidebar__subtitle">{current.description}</p>
      </header>

      <section className="sidebar__section">
        <h2 className="sidebar__section-title">Vues</h2>
        <ul className="sidebar__nav">
          {VIEWS.map((view) => (
            <li key={view.id}>
              <NavLink
                to={view.path}
                end={view.path === "/"}
                className={({ isActive }) =>
                  `sidebar__link${isActive ? " sidebar__link--active" : ""}`
                }
              >
                <span className="sidebar__link-icon">{view.icon}</span>
                {view.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </section>

      <section className="sidebar__section sidebar__section--grow">
        <h2 className="sidebar__section-title">Stack</h2>
        <div className={`sidebar__status${online === false ? " sidebar__status--offline" : ""}`}>
          <span
            className={`sidebar__dot${online ? " sidebar__dot--ok" : online === false ? " sidebar__dot--err" : ""}`}
          />
          <span className="sidebar__status-text">{stackLine}</span>
        </div>
        <p className="sidebar__hint">
          Monde jeu : <strong>Core3 Prime</strong> (VM 246)
        </p>
      </section>

      <footer className="sidebar__footer">
        <span className="sidebar__version">pilot_shell v0.1</span>
        {current.legacyHash && (
          <a className="sidebar__legacy-link" href={`../${current.legacyHash}`}>
            Ouvrir en legacy
          </a>
        )}
      </footer>
    </aside>
  );
}
