import { useCallback, useEffect, useState } from "react";
import {
  advanceJob,
  approveJob,
  cancelJob,
  createJob,
  fetchOllamaTags,
  getJob,
  listJobs,
} from "../../api/pilotClient";
import { FieldRow, Hint, JsonPre, Panel, ViewShell } from "../../components/ViewShell";
import { useJobEvents } from "../../hooks/useJobEvents";
import { useLayout, useSettings } from "../../stores/context";

type JobSummary = {
  id: string;
  objective?: string;
  status?: string;
  n_steps?: number;
  plan_source?: string;
};

export function JobsView() {
  const { settings } = useSettings();
  const { setLayout } = useLayout();
  const [actorId, setActorId] = useState("pilot:jobs");
  const [objective, setObjective] = useState("vérifie l'état du backend puis cherche le site de Cursor AI");
  const [contextJson, setContextJson] = useState("{}");
  const [approvalToken, setApprovalToken] = useState("");
  const [autoStart, setAutoStart] = useState(true);
  const [filterMine, setFilterMine] = useState(true);
  const [models, setModels] = useState<string[]>([]);
  const [model, setModel] = useState("");
  const [planner, setPlanner] = useState("");
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [approveToken, setApproveToken] = useState("");
  const [hint, setHint] = useState("");

  const refreshList = useCallback(async () => {
    const { status, body } = await listJobs(settings, filterMine ? actorId : undefined);
    if (status === 200) {
      const list = (body.jobs as JobSummary[]) ?? [];
      setJobs(Array.isArray(list) ? list : []);
    }
  }, [actorId, filterMine, settings]);

  useEffect(() => {
    void refreshList();
    void fetchOllamaTags(settings).then((b) => {
      const modelsRaw = (b.models as { name?: string }[]) ?? [];
      setModels(modelsRaw.map((m) => m.name ?? "").filter(Boolean));
    });
  }, [refreshList, settings]);

  const selectJob = async (id: string) => {
    setSelectedId(id);
    setLayout({ bottomPanelOpen: true, bottomTab: "logs" });
    const { body } = await getJob(settings, id);
    setDetail(body);
  };

  const refreshSelected = useCallback(async () => {
    if (!selectedId) return;
    const { body } = await getJob(settings, selectedId);
    setDetail(body);
    await refreshList();
  }, [refreshList, selectedId, settings]);

  useJobEvents(settings, selectedId, () => {
    void refreshSelected();
  });

  const launch = async () => {
    let context: Record<string, unknown> = {};
    try {
      context = JSON.parse(contextJson) as Record<string, unknown>;
    } catch {
      setHint("Context JSON invalide");
      return;
    }
    const payload: Record<string, unknown> = {
      actor_id: actorId,
      objective: objective.trim(),
      context,
      auto_start: autoStart,
    };
    if (approvalToken.trim()) payload.approval_token = approvalToken.trim();
    if (model) payload.model = model;
    if (planner) payload.planner = planner;

    setHint("Création…");
    const { status, body } = await createJob(settings, payload);
    if (status !== 200 || body.ok === false) {
      setHint(`Échec HTTP ${status}`);
      return;
    }
    const id = String(body.id ?? "");
    setHint(`Job créé ${id}`);
    await refreshList();
    if (id) await selectJob(id);
  };

  return (
    <ViewShell
      title="Jobs autonomes"
      description="Objectifs Cowork — planification, approbation, timeline."
      legacyHash="#/jobs"
    >
      <div className="view-grid view-grid--2col">
        <div className="view-stack">
          <Panel title="Nouvel objectif">
            <label className="field">
              <span className="field__label">actor_id</span>
              <input className="field__input" value={actorId} onChange={(e) => setActorId(e.target.value)} />
            </label>
            <label className="field">
              <span className="field__label">Objectif</span>
              <textarea className="field__input" rows={3} value={objective} onChange={(e) => setObjective(e.target.value)} />
            </label>
            <label className="field">
              <span className="field__label">context JSON</span>
              <textarea className="field__input mono" rows={3} value={contextJson} onChange={(e) => setContextJson(e.target.value)} />
            </label>
            <FieldRow>
              <select className="field__input" value={model} onChange={(e) => setModel(e.target.value)}>
                <option value="">Modèle (défaut)</option>
                {models.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
              <select className="field__input" value={planner} onChange={(e) => setPlanner(e.target.value)}>
                <option value="">Planner (défaut)</option>
                <option value="deterministic">Déterministe</option>
                <option value="llm">LLM</option>
              </select>
            </FieldRow>
            <label className="field">
              <span className="field__label">Token approbation</span>
              <input className="field__input" value={approvalToken} onChange={(e) => setApprovalToken(e.target.value)} />
            </label>
            <label className="field field--row">
              <input type="checkbox" checked={autoStart} onChange={(e) => setAutoStart(e.target.checked)} />
              <span>Démarrer tout de suite</span>
            </label>
            <button type="button" className="btn btn--primary btn--sm" onClick={() => void launch()}>
              Lancer un job
            </button>
          </Panel>

          <Panel
            title="Jobs récents"
            actions={
              <button type="button" className="btn btn--sm" onClick={() => void refreshList()}>
                Rafraîchir
              </button>
            }
          >
            <label className="field field--row">
              <input type="checkbox" checked={filterMine} onChange={(e) => setFilterMine(e.target.checked)} />
              <span>Seulement mes jobs</span>
            </label>
            <ul className="jobs-list">
              {jobs.length === 0 && <li className="muted">Aucun job</li>}
              {jobs.map((j) => (
                <li key={j.id}>
                  <button
                    type="button"
                    className={`jobs-card${selectedId === j.id ? " jobs-card--active" : ""}`}
                    onClick={() => void selectJob(j.id)}
                  >
                    <div className="jobs-card__obj">{j.objective ?? j.id}</div>
                    <div className="jobs-card__meta">
                      <span className={`badge badge--${j.status ?? "unknown"}`}>{j.status}</span>
                      {j.n_steps ?? 0} étape(s) · {j.plan_source ?? "?"}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          </Panel>
        </div>

        <Panel title="Détail du job">
          {!detail ? (
            <p className="muted">Sélectionnez un job.</p>
          ) : (
            <>
              <p className="jobs-detail-obj">{String(detail.objective ?? "")}</p>
              <FieldRow>
                <input
                  className="field__input"
                  placeholder="token approbation"
                  value={approveToken}
                  onChange={(e) => setApproveToken(e.target.value)}
                />
                <button
                  type="button"
                  className="btn btn--sm"
                  disabled={!selectedId}
                  onClick={() => selectedId && void approveJob(settings, selectedId, approveToken).then(() => selectJob(selectedId))}
                >
                  Approuver
                </button>
                <button
                  type="button"
                  className="btn btn--sm"
                  disabled={!selectedId}
                  onClick={() => selectedId && void advanceJob(settings, selectedId).then(() => selectJob(selectedId))}
                >
                  Avancer
                </button>
                <button
                  type="button"
                  className="btn btn--sm"
                  disabled={!selectedId}
                  onClick={() => selectedId && void cancelJob(settings, selectedId).then(() => refreshList())}
                >
                  Annuler
                </button>
              </FieldRow>
              <h4 className="panel__subtitle">Étapes</h4>
              <ul className="steps-list">
                {((detail.steps as Record<string, unknown>[]) ?? []).map((s, i) => (
                  <li key={i}>
                    <strong>{String(s.kind ?? s.capability ?? "?")}</strong> — {String(s.status ?? "")}
                  </li>
                ))}
              </ul>
              <h4 className="panel__subtitle">Timeline</h4>
              <JsonPre data={detail.events ?? detail.timeline} maxHeight="10rem" />
              <details>
                <summary className="muted-link">JSON brut</summary>
                <JsonPre data={detail} maxHeight="14rem" />
              </details>
            </>
          )}
        </Panel>
      </div>
      <Hint>{hint}</Hint>
    </ViewShell>
  );
}
