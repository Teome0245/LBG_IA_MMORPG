import { useCallback, useEffect, useState } from "react";
import {
  AGENT_HEALTHZ,
  brainApprove,
  brainToggle,
  fetchBrainStatus,
  fetchInfraAlerts,
  pilotGet,
} from "../../api/pilotClient";
import { fetchCapabilities, fetchStatus } from "../../api/pilotApi";
import { postRoute } from "../../api/pilotApi";
import { FieldRow, Hint, JsonPre, Panel, ViewShell } from "../../components/ViewShell";
import { useSettings } from "../../stores/context";

export function HealthView() {
  const { settings } = useSettings();
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);
  const [caps, setCaps] = useState<string[]>([]);
  const [agents, setAgents] = useState<Record<string, unknown>>({});
  const [brain, setBrain] = useState<Record<string, unknown> | null>(null);
  const [alerts, setAlerts] = useState<Record<string, unknown> | null>(null);
  const [bench, setBench] = useState("");
  const [busy, setBusy] = useState(false);
  const [brainToken, setBrainToken] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [st, c] = await Promise.all([fetchStatus(settings), fetchCapabilities(settings)]);
      setStatus(st);
      setCaps(c);
      const agentResults: Record<string, unknown> = {};
      await Promise.all(
        AGENT_HEALTHZ.map(async (a) => {
          const { status: s, body } = await pilotGet(settings, a.path);
          agentResults[a.id] = { status: s, body };
        }),
      );
      setAgents(agentResults);
      const br = await fetchBrainStatus(settings);
      setBrain(br.body);
      const al = await fetchInfraAlerts(settings);
      setAlerts(al.body);
    } catch (e) {
      setStatus({ error: String(e) });
    }
  }, [settings]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const runBench = async () => {
    setBusy(true);
    setBench("Benchmark…");
    const times: number[] = [];
    for (let i = 0; i < 5; i++) {
      const { status, body } = await postRoute(settings, "healthz probe", {
        devops_action: { kind: "http_get", url: "http://127.0.0.1:8010/healthz" },
        devops_dry_run: true,
      });
      if (status === 200 && typeof body.elapsed_ms === "number") times.push(body.elapsed_ms);
    }
    setBench(
      times.length
        ? `n=${times.length} p50=${times.sort((a, b) => a - b)[Math.floor(times.length / 2)]}ms`
        : "Échec benchmark",
    );
    setBusy(false);
  };

  return (
    <ViewShell
      title="Santé & métriques"
      description="État agrégé, healthz agents, Brain orchestrateur, alertes infra."
      legacyHash="#/health"
    >
      <div className="view-grid">
        <Panel
          title="Plateforme"
          actions={
            <button type="button" className="btn btn--sm" onClick={() => void refresh()}>
              Rafraîchir
            </button>
          }
        >
          <div className="stat-grid">
            <div>
              <span className="stat-label">App</span>
              <span className="stat-value">{String(status?.app ?? "—")}</span>
            </div>
            <div>
              <span className="stat-label">Orchestrateur</span>
              <span className="stat-value">{String(status?.orchestrator_url ?? "—")}</span>
            </div>
            <div>
              <span className="stat-label">Capabilities</span>
              <span className="stat-value">{caps.length}</span>
            </div>
          </div>
          <JsonPre data={status} maxHeight="12rem" />
        </Panel>

        <Panel title="Agents (healthz)">
          <ul className="health-list">
            {AGENT_HEALTHZ.map((a) => {
              const r = agents[a.id] as { status?: number; body?: Record<string, unknown> } | undefined;
              const ok = r?.status === 200 && r.body?.ok !== false;
              return (
                <li key={a.id} className={ok ? "health-list__ok" : "health-list__err"}>
                  {a.label} — HTTP {r?.status ?? "?"}
                </li>
              );
            })}
          </ul>
        </Panel>

        <Panel
          title="Brain (autonomie)"
          actions={
            <>
              <button
                type="button"
                className="btn btn--sm"
                onClick={() => void brainToggle(settings, true).then(() => refresh())}
              >
                Activer
              </button>
              <button
                type="button"
                className="btn btn--sm"
                onClick={() => void brainToggle(settings, false).then(() => refresh())}
              >
                Désactiver
              </button>
            </>
          }
        >
          <FieldRow>
            <input
              className="field__input"
              placeholder="Token approbation Brain"
              value={brainToken}
              onChange={(e) => setBrainToken(e.target.value)}
            />
            <button
              type="button"
              className="btn btn--sm"
              onClick={() => void brainApprove(settings, brainToken).then(() => refresh())}
            >
              Approuver
            </button>
          </FieldRow>
          <JsonPre data={brain} maxHeight="10rem" />
        </Panel>

        <Panel title="Alertes infra">
          <JsonPre data={alerts} maxHeight="12rem" />
        </Panel>

        <Panel
          title="Benchmark rapide"
          subtitle="5 requêtes dry-run DevOps"
          actions={
            <button type="button" className="btn btn--sm" disabled={busy} onClick={() => void runBench()}>
              Lancer
            </button>
          }
        >
          <Hint>{bench || "—"}</Hint>
        </Panel>
      </div>
    </ViewShell>
  );
}
