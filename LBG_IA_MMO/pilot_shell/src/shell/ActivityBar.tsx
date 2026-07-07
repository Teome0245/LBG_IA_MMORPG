import { NavLink } from "react-router-dom";
import { VIEWS } from "../lib/routes";
import { useLayout } from "../stores/context";

export function ActivityBar() {
  const { layout, toggleSidebar } = useLayout();

  return (
    <nav className="activity-bar" aria-label="Navigation principale">
      <div className="activity-bar__logo" title="LBG Pilot">
        L
      </div>
      {VIEWS.map((view) => (
        <NavLink
          key={view.id}
          to={view.path}
          end={view.path === "/"}
          className={({ isActive }) =>
            `activity-bar__item${isActive ? " activity-bar__item--active" : ""}`
          }
          title={view.label}
        >
          <span className="activity-bar__icon" aria-hidden>
            {view.icon}
          </span>
        </NavLink>
      ))}
      <div className="activity-bar__spacer" />
      <a
        className="activity-bar__item activity-bar__item--legacy"
        href="../?legacy=1"
        title="Pilot legacy (/pilot/)"
      >
        <span className="activity-bar__icon" aria-hidden>
          ↩
        </span>
      </a>
      <button
        type="button"
        className={`activity-bar__item activity-bar__toggle${layout.sidebarOpen ? "" : " activity-bar__item--muted"}`}
        onClick={toggleSidebar}
        title="Basculer sidebar (Ctrl+B)"
      >
        <span className="activity-bar__icon" aria-hidden>
          ☰
        </span>
      </button>
    </nav>
  );
}
