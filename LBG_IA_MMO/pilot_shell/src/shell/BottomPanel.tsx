import { useCallback, useEffect, useState } from "react";
import { XtermPanel } from "../components/XtermPanel";
import { useLayout, useSettings } from "../stores/context";
import { useLogs } from "../stores/logsContext";

const TABS = [
  { id: "terminal" as const, label: "Terminal" },
  { id: "logs" as const, label: "Logs" },
  { id: "metrics" as const, label: "Métriques" },
];

export function BottomPanel() {
  const { layout, setLayout } = useLayout();
  const { settings } = useSettings();
  const { lines, clear } = useLogs();
  const [metricsText, setMetricsText] = useState("");
  const [metricsBusy, setMetricsBusy] = useState(false);

  const fetchMetrics = useCallback(async () => {
    setMetricsBusy(true);
    try {
      const headers: Record<string, string> = {};
      const bearer = settings.metricsBearer.trim();
      if (bearer) headers.Authorization = `Bearer ${bearer}`;
      const r = await fetch("/metrics", { headers });
      const text = await r.text();
      setMetricsText(text.slice(0, 12000) || `HTTP ${r.status} (vide)`);
    } catch (e) {
      setMetricsText(`Erreur: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setMetricsBusy(false);
    }
  }, [settings.metricsBearer]);

  useEffect(() => {
    if (layout.bottomPanelOpen && layout.bottomTab === "metrics" && !metricsText) {
      void fetchMetrics();
    }
  }, [fetchMetrics, layout.bottomPanelOpen, layout.bottomTab, metricsText]);

  return (
    <section className="bottom-panel">
      <header className="bottom-panel__header">
        <div className="bottom-panel__tabs">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={`bottom-panel__tab${layout.bottomTab === tab.id ? " bottom-panel__tab--active" : ""}`}
              onClick={() => setLayout({ bottomTab: tab.id })}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="bottom-panel__actions">
          {layout.bottomTab === "logs" && (
            <button type="button" className="btn btn--ghost btn--xs" onClick={clear}>
              Effacer
            </button>
          )}
          {layout.bottomTab === "metrics" && (
            <button
              type="button"
              className="btn btn--ghost btn--xs"
              disabled={metricsBusy}
              onClick={() => void fetchMetrics()}
            >
              Rafraîchir
            </button>
          )}
          <button
            type="button"
            className="bottom-panel__close"
            onClick={() => setLayout({ bottomPanelOpen: false })}
            title="Fermer le panneau bas"
          >
            ×
          </button>
        </div>
      </header>
      <div className="bottom-panel__body">
        {layout.bottomTab === "terminal" && <XtermPanel settings={settings} />}
        {layout.bottomTab === "logs" && (
          <pre className="bottom-panel__mono bottom-panel__logs">
            {lines.length === 0
              ? "Journal vide — sélectionnez un job ou utilisez le terminal."
              : lines
                  .map((l) => {
                    const t = new Date(l.ts).toLocaleTimeString();
                    return `[${t}] ${l.source}: ${l.text}`;
                  })
                  .join("\n")}
          </pre>
        )}
        {layout.bottomTab === "metrics" && (
          <pre className="bottom-panel__mono">{metricsBusy ? "Chargement…" : metricsText || "—"}</pre>
        )}
      </div>
    </section>
  );
}
