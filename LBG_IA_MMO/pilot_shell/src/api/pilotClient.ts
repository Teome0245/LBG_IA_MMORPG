import { authHeaders, type PilotSettings } from "./pilotApi";

export type PilotFetchResult = { status: number; body: Record<string, unknown> };

function apiRoot(settings: PilotSettings): string {
  const base = settings.apiBase.trim();
  return base ? base.replace(/\/$/, "") : "";
}

export async function pilotFetch(
  settings: PilotSettings,
  path: string,
  init?: RequestInit,
): Promise<PilotFetchResult> {
  const r = await fetch(`${apiRoot(settings)}${path}`, {
    ...init,
    headers: { ...authHeaders(settings), ...(init?.headers as Record<string, string>) },
  });
  const body = (await r.json().catch(() => ({}))) as Record<string, unknown>;
  return { status: r.status, body };
}

export async function pilotGet(settings: PilotSettings, path: string): Promise<PilotFetchResult> {
  return pilotFetch(settings, path);
}

export async function pilotPost(
  settings: PilotSettings,
  path: string,
  payload: unknown,
): Promise<PilotFetchResult> {
  return pilotFetch(settings, path, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export const AGENT_HEALTHZ = [
  { id: "dialogue", path: "/v1/pilot/agent-dialogue/healthz", label: "Dialogue" },
  { id: "quests", path: "/v1/pilot/agent-quests/healthz", label: "Quêtes" },
  { id: "combat", path: "/v1/pilot/agent-combat/healthz", label: "Combat" },
  { id: "pm", path: "/v1/pilot/agent-pm/healthz", label: "PM" },
  { id: "desktop", path: "/v1/pilot/agent-desktop/healthz", label: "Desktop" },
  { id: "mmo", path: "/v1/pilot/mmo-server/healthz", label: "MMO HTTP" },
] as const;

export async function fetchOllamaTags(settings: PilotSettings): Promise<Record<string, unknown>> {
  const { body } = await pilotGet(settings, "/v1/pilot/ollama/tags");
  return body;
}

export async function fetchInfraAlerts(settings: PilotSettings): Promise<PilotFetchResult> {
  return pilotGet(settings, "/v1/pilot/infra-alerts?probe=true");
}

export async function fetchBrainStatus(settings: PilotSettings): Promise<PilotFetchResult> {
  return pilotGet(settings, "/v1/pilot/orchestrator/brain/status");
}

export async function brainToggle(settings: PilotSettings, enabled: boolean): Promise<PilotFetchResult> {
  return pilotPost(settings, "/v1/pilot/orchestrator/brain/toggle", { enabled });
}

export async function brainApprove(settings: PilotSettings, token: string): Promise<PilotFetchResult> {
  return pilotPost(settings, "/v1/pilot/orchestrator/brain/approve", { token });
}

export async function postReputation(
  settings: PilotSettings,
  npcId: string,
  delta: number,
): Promise<PilotFetchResult> {
  return pilotPost(settings, "/v1/pilot/reputation", { npc_id: npcId, delta });
}

export async function postPlayerInventory(
  settings: PilotSettings,
  payload: Record<string, unknown>,
): Promise<PilotFetchResult> {
  return pilotPost(settings, "/v1/pilot/player-inventory", payload);
}

export async function postAid(
  settings: PilotSettings,
  payload: Record<string, unknown>,
): Promise<PilotFetchResult> {
  return pilotPost(settings, "/v1/pilot/aid", payload);
}

export async function fetchWorldLyra(
  settings: PilotSettings,
  npcId?: string,
): Promise<PilotFetchResult> {
  const q = npcId ? `?npc_id=${encodeURIComponent(npcId)}` : "";
  return pilotGet(settings, `/v1/pilot/mmo-server/world-lyra${q}`);
}

export async function fetchNpcRegistry(
  settings: PilotSettings,
  npcId?: string,
): Promise<PilotFetchResult> {
  const q = npcId ? `?npc_id=${encodeURIComponent(npcId)}` : "";
  return pilotGet(settings, `/v1/pilot/agent-dialogue/npc-registry${q}`);
}

export async function fetchWorldContent(settings: PilotSettings): Promise<PilotFetchResult> {
  return pilotGet(settings, "/v1/pilot/agent-dialogue/world-content");
}

export async function invokeDialogue(
  settings: PilotSettings,
  payload: Record<string, unknown>,
): Promise<PilotFetchResult> {
  return pilotPost(settings, "/v1/pilot/agent-dialogue/invoke", payload);
}

export async function createJob(
  settings: PilotSettings,
  payload: Record<string, unknown>,
): Promise<PilotFetchResult> {
  return pilotPost(settings, "/v1/pilot/jobs", payload);
}

export async function listJobs(
  settings: PilotSettings,
  actorId?: string,
): Promise<PilotFetchResult> {
  const q = actorId ? `?actor_id=${encodeURIComponent(actorId)}` : "";
  return pilotGet(settings, `/v1/pilot/jobs${q}`);
}

export async function getJob(settings: PilotSettings, jobId: string): Promise<PilotFetchResult> {
  return pilotGet(settings, `/v1/pilot/jobs/${encodeURIComponent(jobId)}`);
}

export async function approveJob(
  settings: PilotSettings,
  jobId: string,
  token: string,
): Promise<PilotFetchResult> {
  return pilotPost(settings, `/v1/pilot/jobs/${encodeURIComponent(jobId)}/approve`, { token });
}

export async function cancelJob(settings: PilotSettings, jobId: string): Promise<PilotFetchResult> {
  return pilotPost(settings, `/v1/pilot/jobs/${encodeURIComponent(jobId)}/cancel`, {});
}

export async function advanceJob(settings: PilotSettings, jobId: string): Promise<PilotFetchResult> {
  return pilotPost(settings, `/v1/pilot/jobs/${encodeURIComponent(jobId)}/advance`, {});
}

export function extractPmBrief(resp: Record<string, unknown>): Record<string, unknown> | null {
  if (resp.brief && typeof resp.brief === "object") return resp.brief as Record<string, unknown>;
  const out = resp.output as Record<string, unknown> | undefined;
  if (out?.brief && typeof out.brief === "object") return out.brief as Record<string, unknown>;
  const r = resp.result as Record<string, unknown> | undefined;
  const rout = r?.output as Record<string, unknown> | undefined;
  if (rout?.brief && typeof rout.brief === "object") return rout.brief as Record<string, unknown>;
  return null;
}

export function pmBriefToMarkdown(brief: Record<string, unknown>): string {
  const lines: string[] = ["# Export PM — pilot_shell", ""];
  const milestones = Array.isArray(brief.milestones) ? brief.milestones : [];
  const tasks = Array.isArray(brief.tasks) ? brief.tasks : [];
  if (milestones.length) {
    lines.push("## Jalons", "");
    for (const m of milestones) {
      const row = m as Record<string, unknown>;
      lines.push(`- **${row.date ?? "?"}** — ${row.summary ?? ""}`);
    }
    lines.push("");
  }
  if (tasks.length) {
    lines.push("## Tâches", "");
    for (const t of tasks) {
      const row = t as Record<string, unknown>;
      lines.push(`- ${row.title ?? "?"} (${row.source ?? "?"})`);
    }
  }
  return lines.join("\n");
}
