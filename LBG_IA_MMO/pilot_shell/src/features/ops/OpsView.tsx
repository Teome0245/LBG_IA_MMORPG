import { useEffect, useState } from "react";
import { fetchInfraAlerts } from "../../api/pilotClient";
import { postActionProposal } from "../../api/pilotApi";
import { Hint, JsonPre, Panel, ViewShell } from "../../components/ViewShell";
import { formatProposalResponse } from "../../lib/routeFormat";
import { useSettings } from "../../stores/context";

const OPS_QUICK = [
  { label: "Selfcheck", text: "devops selfcheck dry-run", ctx: { devops_selfcheck: true, devops_dry_run: true } },
  { label: "Healthz orch", text: "sonde healthz orchestrator", ctx: { devops_action: { kind: "http_get", url: "http://127.0.0.1:8010/healthz" }, devops_dry_run: true } },
  { label: "Core3 246", text: "sonde core3 prime vm 246", ctx: { prefer_agentic: false } },
];

export function OpsView() {
  const { settings } = useSettings();
  const [alerts, setAlerts] = useState<Record<string, unknown> | null>(null);
  const [proposal, setProposal] = useState("");
  const [lastRaw, setLastRaw] = useState<Record<string, unknown> | null>(null);
  const [text, setText] = useState("diagnostic infra et prochaine action concrète");
  const [hint, setHint] = useState("");

  useEffect(() => {
    void fetchInfraAlerts(settings).then((r) => setAlerts(r.body));
  }, [settings]);

  const propose = async (payloadText?: string, ctx: Record<string, unknown> = {}) => {
    const t = (payloadText ?? text).trim();
    if (!t) return;
    setHint("Proposition…");
    const { status, body } = await postActionProposal(settings, t, { history: [], ...ctx });
    if (status !== 200) {
      setHint(`HTTP ${status}`);
      setLastRaw(body);
      return;
    }
    const d = formatProposalResponse(body);
    setProposal(d.primaryText);
    setLastRaw(body);
    setHint(d.metaLine);
  };

  return (
    <ViewShell
      title="Ops — Assistant Core"
      description="Alertes infra et propositions ActionProposal — exécution via le panneau Agent (mode Proposition ou Route)."
      legacyHash="#/ops"
    >
      <div className="view-grid">
        <Panel title="Alertes infra">
          <JsonPre data={alerts} maxHeight="14rem" />
        </Panel>

        <Panel title="ActionProposal">
          <textarea
            className="field__input"
            rows={2}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <div className="btn-row">
            {OPS_QUICK.map((q) => (
              <button key={q.label} type="button" className="btn btn--sm" onClick={() => void propose(q.text, q.ctx)}>
                {q.label}
              </button>
            ))}
            <button type="button" className="btn btn--primary btn--sm" onClick={() => void propose()}>
              Proposer
            </button>
          </div>
          <Hint>{hint || "Utilisez le panneau Agent en mode « Proposition » pour itérer."}</Hint>
          {proposal && <pre className="proposal-text">{proposal}</pre>}
          <details>
            <summary className="muted-link">JSON brut</summary>
            <JsonPre data={lastRaw} maxHeight="12rem" />
          </details>
        </Panel>
      </div>
    </ViewShell>
  );
}
