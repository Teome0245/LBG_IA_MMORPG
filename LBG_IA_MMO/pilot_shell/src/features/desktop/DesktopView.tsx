import { useEffect, useState } from "react";
import { invokeDialogue, pilotGet } from "../../api/pilotClient";
import { postActionProposal, postRoute } from "../../api/pilotApi";
import { FieldRow, Hint, JsonPre, Panel, ViewShell } from "../../components/ViewShell";
import { formatRouteResponse, formatProposalResponse } from "../../lib/routeFormat";
import { readLegacyString } from "../../lib/storage";
import { useSettings } from "../../stores/context";

const DESKTOP_DRY_KEY = "lbg_pilot_desktop_dry_run_v1";
const MMO_SUMMARY_KEY = "lbg_pilot_mmo_session_summary_json";

const PRESETS: { label: string; action: Record<string, unknown>; text: string }[] = [
  { label: "open_url", text: "ouvre example.org", action: { kind: "open_url", url: "https://example.org" } },
  { label: "notepad", text: "note test pilot", action: { kind: "notepad_append", text: "Hello from pilot_shell\n" } },
  { label: "search_web", text: "cherche Cursor AI", action: { kind: "search_web_open", query: "Cursor AI IDE" } },
];

export function DesktopView() {
  const { settings } = useSettings();
  const [text, setText] = useState("ouvre https://example.org dans le navigateur");
  const [actionJson, setActionJson] = useState('{\n  "kind": "open_url",\n  "url": "https://example.org"\n}');
  const [contextJson, setContextJson] = useState('{\n  "history": []\n}');
  const [mmoSummary, setMmoSummary] = useState(() => readLegacyString(MMO_SUMMARY_KEY));
  const [dryRun, setDryRun] = useState(() => readLegacyString(DESKTOP_DRY_KEY, "1") !== "0");
  const [result, setResult] = useState("");
  const [raw, setRaw] = useState<Record<string, unknown> | null>(null);
  const [hint, setHint] = useState("");

  useEffect(() => {
    localStorage.setItem(DESKTOP_DRY_KEY, dryRun ? "1" : "0");
  }, [dryRun]);

  useEffect(() => {
    localStorage.setItem(MMO_SUMMARY_KEY, mmoSummary);
  }, [mmoSummary]);

  const buildContext = (): Record<string, unknown> => {
    let ctx: Record<string, unknown> = {};
    try {
      ctx = JSON.parse(contextJson) as Record<string, unknown>;
    } catch {
      throw new Error("context JSON invalide");
    }
    let action: Record<string, unknown>;
    try {
      action = JSON.parse(actionJson) as Record<string, unknown>;
    } catch {
      throw new Error("desktop_action JSON invalide");
    }
    ctx.desktop_action = action;
    if (dryRun) ctx.desktop_dry_run = true;
    if (mmoSummary.trim()) {
      try {
        ctx.session_summary = JSON.parse(mmoSummary);
      } catch {
        /* ignore invalid summary */
      }
    }
    return ctx;
  };

  const sendRoute = async () => {
    try {
      const ctx = buildContext();
      setHint("Route…");
      const { status, body } = await postRoute(settings, text.trim(), ctx);
      const d = formatRouteResponse(body);
      setResult(d.primaryText);
      setRaw(body);
      setHint(`HTTP ${status}`);
    } catch (e) {
      setHint(e instanceof Error ? e.message : String(e));
    }
  };

  const propose = async () => {
    try {
      const ctx = buildContext();
      delete ctx.desktop_action;
      setHint("Proposition…");
      const { status, body } = await postActionProposal(settings, text.trim(), ctx);
      const d = formatProposalResponse(body);
      setResult(d.primaryText);
      setRaw(body);
      setHint(`HTTP ${status}`);
    } catch (e) {
      setHint(e instanceof Error ? e.message : String(e));
    }
  };

  const proposeLlm = async () => {
    setHint("Dialogue invoke…");
    const { status, body } = await invokeDialogue(settings, {
      text: text.trim(),
      context: { desktop_plan: true, history: [] },
    });
    setRaw(body);
    setHint(`Invoke HTTP ${status}`);
    const remote = (body as Record<string, unknown>).reply;
    if (typeof remote === "string") setResult(remote);
  };

  return (
    <ViewShell title="Desktop hybride" description="Actions poste via desktop_action — dry-run, approval, pont MMO." legacyHash="#/desktop">
      <Panel title="Action desktop">
        <textarea className="field__input" rows={2} value={text} onChange={(e) => setText(e.target.value)} />
        <label className="field">
          <span className="field__label">desktop_action JSON</span>
          <textarea className="field__input mono" rows={5} value={actionJson} onChange={(e) => setActionJson(e.target.value)} />
        </label>
        <label className="field">
          <span className="field__label">context JSON</span>
          <textarea className="field__input mono" rows={4} value={contextJson} onChange={(e) => setContextJson(e.target.value)} />
        </label>
        <label className="field">
          <span className="field__label">session_summary (pont MMO)</span>
          <textarea className="field__input mono" rows={2} value={mmoSummary} onChange={(e) => setMmoSummary(e.target.value)} />
        </label>
        <label className="field field--row">
          <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
          <span>desktop_dry_run</span>
        </label>
        <div className="btn-row">
          {PRESETS.map((p) => (
            <button
              key={p.label}
              type="button"
              className="btn btn--sm"
              onClick={() => {
                setText(p.text);
                setActionJson(JSON.stringify(p.action, null, 2));
              }}
            >
              {p.label}
            </button>
          ))}
        </div>
        <FieldRow>
          <button type="button" className="btn btn--primary btn--sm" onClick={() => void sendRoute()}>
            Envoyer (route)
          </button>
          <button type="button" className="btn btn--sm" onClick={() => void propose()}>
            Proposer (orchestrateur)
          </button>
          <button type="button" className="btn btn--sm" onClick={() => void proposeLlm()}>
            Proposer via IA
          </button>
          <button type="button" className="btn btn--sm" onClick={() => void pilotGet(settings, "/v1/pilot/agent-desktop/healthz").then((r) => setHint(`Desktop healthz ${r.status}`))}>
            Healthz
          </button>
        </FieldRow>
        <Hint>{hint}</Hint>
        {result && <pre className="proposal-text">{result}</pre>}
        <JsonPre data={raw} maxHeight="12rem" />
      </Panel>
    </ViewShell>
  );
}
