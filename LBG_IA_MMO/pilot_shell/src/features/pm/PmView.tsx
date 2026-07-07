import { useState } from "react";
import { extractPmBrief, pilotGet, pmBriefToMarkdown } from "../../api/pilotClient";
import { postRoute } from "../../api/pilotApi";
import { Hint, JsonPre, Panel, ViewShell } from "../../components/ViewShell";
import { useSettings } from "../../stores/context";

const DEFAULT_CTX = `{
  "project_pm": true,
  "pm_include_plan": true,
  "pm_include_structure": true,
  "history": []
}`;

export function PmView() {
  const { settings } = useSettings();
  const [text, setText] = useState("jalons et tâches du plan de route");
  const [contextJson, setContextJson] = useState(DEFAULT_CTX);
  const [brief, setBrief] = useState<Record<string, unknown> | null>(null);
  const [raw, setRaw] = useState<Record<string, unknown> | null>(null);
  const [hint, setHint] = useState("");

  const send = async () => {
    let ctx: Record<string, unknown>;
    try {
      ctx = JSON.parse(contextJson) as Record<string, unknown>;
    } catch {
      setHint("JSON contexte invalide");
      return;
    }
    setHint("…");
    const { status, body } = await postRoute(settings, text.trim() || "jalons", ctx);
    setRaw(body);
    setBrief(extractPmBrief(body));
    setHint(status === 200 ? "OK" : `HTTP ${status}`);
  };

  const exportMd = () => {
    if (!brief) return;
    const md = pmBriefToMarkdown(brief);
    void navigator.clipboard.writeText(md);
    setHint("Markdown copié");
  };

  const milestones = Array.isArray(brief?.milestones) ? (brief!.milestones as Record<string, unknown>[]) : [];
  const tasks = Array.isArray(brief?.tasks) ? (brief!.tasks as Record<string, unknown>[]) : [];

  return (
    <ViewShell title="Chef de projet" description="agent.pm — jalons et tâches du plan de route." legacyHash="#/pm">
      <Panel title="Interroger le PM">
        <textarea className="field__input" rows={2} value={text} onChange={(e) => setText(e.target.value)} />
        <textarea className="field__input mono" rows={6} value={contextJson} onChange={(e) => setContextJson(e.target.value)} />
        <div className="btn-row">
          <button type="button" className="btn btn--primary btn--sm" onClick={() => void send()}>
            Interroger
          </button>
          <button type="button" className="btn btn--sm" onClick={() => void pilotGet(settings, "/v1/pilot/agent-pm/healthz").then((r) => setHint(`PM healthz ${r.status}`))}>
            Healthz PM
          </button>
          <button type="button" className="btn btn--sm" disabled={!brief} onClick={exportMd}>
            Export MD
          </button>
        </div>
        <Hint>{hint}</Hint>
      </Panel>

      <div className="view-grid view-grid--2col">
        <Panel title="Jalons">
          <ul className="pm-list">
            {milestones.length === 0 && <li className="muted">—</li>}
            {milestones.map((m, i) => (
              <li key={i}>
                <strong>{String(m.date ?? "")}</strong> — {String(m.summary ?? "")}
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title="Tâches">
          <ul className="pm-list">
            {tasks.length === 0 && <li className="muted">—</li>}
            {tasks.map((t, i) => (
              <li key={i}>
                {String(t.title ?? "")} <span className="muted">({String(t.source ?? "")})</span>
              </li>
            ))}
          </ul>
        </Panel>
      </div>

      <details>
        <summary className="muted-link">JSON brut</summary>
        <JsonPre data={raw} maxHeight="14rem" />
      </details>
    </ViewShell>
  );
}
