import { readLegacyBool, readLegacyString, STORAGE_KEYS } from "../lib/storage";
import { formatRouteResponse } from "../lib/routeFormat";

export type PilotSettings = {
  serviceToken: string;
  token: string;
  approval: string;
  dryRun: boolean;
  agenticChat: boolean;
  metricsBearer: string;
  apiBase: string;
};

export type ToolCallDisplay = {
  id: string;
  tool: string;
  args: Record<string, unknown>;
  output?: string;
  ok?: boolean;
  status: "running" | "done" | "error";
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  meta?: string;
  tools?: ToolCallDisplay[];
  streaming?: boolean;
};

export type AssistantStreamEvent =
  | { kind: "token"; delta: string }
  | { kind: "tool_start"; tool: string; args: Record<string, unknown> }
  | {
      kind: "tool_result";
      tool: string;
      args?: Record<string, unknown>;
      ok?: boolean;
      output?: string;
    }
  | { kind: "done"; reply?: string; tools?: unknown[]; agent?: string }
  | { kind: "error"; error: string };

export function loadSettings(): PilotSettings {
  return {
    serviceToken: readLegacyString(STORAGE_KEYS.serviceToken),
    token: readLegacyString(STORAGE_KEYS.token),
    approval: readLegacyString(STORAGE_KEYS.approval),
    dryRun: readLegacyBool(STORAGE_KEYS.dryRun, true),
    agenticChat: readLegacyBool(STORAGE_KEYS.agenticChat, true),
    metricsBearer: readLegacyString(STORAGE_KEYS.metricsBearer),
    apiBase: readLegacyString(STORAGE_KEYS.apiBase),
  };
}

export function saveSettings(s: PilotSettings): void {
  localStorage.setItem(STORAGE_KEYS.serviceToken, s.serviceToken.trim());
  localStorage.setItem(STORAGE_KEYS.token, s.token.trim());
  localStorage.setItem(STORAGE_KEYS.approval, s.approval.trim());
  localStorage.setItem(STORAGE_KEYS.dryRun, s.dryRun ? "1" : "0");
  localStorage.setItem(STORAGE_KEYS.agenticChat, s.agenticChat ? "1" : "0");
  localStorage.setItem(STORAGE_KEYS.metricsBearer, s.metricsBearer.trim());
  localStorage.setItem(STORAGE_KEYS.apiBase, s.apiBase.trim());
}

function apiRoot(settings: PilotSettings): string {
  const base = settings.apiBase.trim();
  return base ? base.replace(/\/$/, "") : "";
}

export function authHeaders(settings: PilotSettings): HeadersInit {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  const service = settings.serviceToken.trim();
  const bearer = settings.token.trim();
  if (service) h["X-LBG-Service-Token"] = service;
  if (bearer) h.Authorization = `Bearer ${bearer}`;
  return h;
}

export function buildContext(
  settings: PilotSettings,
  extra: Record<string, unknown> = {},
): Record<string, unknown> {
  const ctx: Record<string, unknown> = { ...extra };
  ctx.prefer_agentic = settings.agenticChat;
  if (settings.dryRun) {
    ctx.devops_dry_run = true;
    ctx.desktop_dry_run = true;
  } else if (settings.approval.trim()) {
    ctx.devops_approval = settings.approval.trim();
    ctx.desktop_approval = settings.approval.trim();
  }
  return ctx;
}

export async function fetchStatus(settings: PilotSettings): Promise<Record<string, unknown>> {
  const r = await fetch(`${apiRoot(settings)}/v1/pilot/status`);
  if (!r.ok) throw new Error(`status HTTP ${r.status}`);
  return (await r.json()) as Record<string, unknown>;
}

export async function fetchCapabilities(settings: PilotSettings): Promise<string[]> {
  const r = await fetch(`${apiRoot(settings)}/v1/pilot/capabilities`);
  if (!r.ok) throw new Error(`capabilities HTTP ${r.status}`);
  const j = (await r.json()) as { capabilities?: string[] };
  return Array.isArray(j.capabilities) ? j.capabilities : [];
}

export async function postRoute(
  settings: PilotSettings,
  text: string,
  context: Record<string, unknown> = {},
): Promise<{ status: number; body: Record<string, unknown> }> {
  const r = await fetch(`${apiRoot(settings)}/v1/pilot/route`, {
    method: "POST",
    headers: authHeaders(settings),
    body: JSON.stringify({
      text,
      actor_id: "pilot:shell",
      context: buildContext(settings, context),
    }),
  });
  const body = (await r.json().catch(() => ({}))) as Record<string, unknown>;
  return { status: r.status, body };
}

export async function postActionProposal(
  settings: PilotSettings,
  text: string,
  context: Record<string, unknown> = {},
): Promise<{ status: number; body: Record<string, unknown> }> {
  const r = await fetch(`${apiRoot(settings)}/v1/pilot/action-proposal`, {
    method: "POST",
    headers: authHeaders(settings),
    body: JSON.stringify({
      text,
      actor_id: "pilot:shell",
      context: buildContext(settings, context),
    }),
  });
  const body = (await r.json().catch(() => ({}))) as Record<string, unknown>;
  return { status: r.status, body };
}

export function formatRouteReply(body: Record<string, unknown>): string {
  const intent = String(body.intent || "?");
  const dispatch = body.dispatch as Record<string, unknown> | undefined;
  if (!dispatch) return `Intent : ${intent}\n(pas de dispatch)`;
  if (intent === "agentic" || dispatch.agentic === true) {
    const from = dispatch.elevated_from ? ` (ex-${dispatch.elevated_from})` : "";
    const st = dispatch.state as Record<string, unknown> | undefined;
    let out = `Mode agentique${from}\n\n${String(dispatch.reply || dispatch.error || "")}`;
    if (st?.plan_source) out += `\n\nPlan : ${st.plan_source}`;
    if (st?.retries != null) out += `\nTentatives : ${st.retries}`;
    return out;
  }
  if (intent === "unknown" && dispatch.hint) {
    return `Intent : ${intent}\n\n${String(dispatch.hint)}`;
  }
  if (dispatch.ok === false) {
    const err = dispatch.error || dispatch.detail || dispatch.reply || "échec";
    let msg = `Intent : ${intent}\n${String(err)}`;
    if (intent === "core3" && dispatch.core3 && typeof dispatch.core3 === "object") {
      const c3 = dispatch.core3 as Record<string, unknown>;
      const hints = c3.remediation_hints;
      if (Array.isArray(hints) && hints.length) {
        msg += "\n\n" + hints.slice(0, 3).map(String).join("\n");
      }
    }
    return msg;
  }
  const reply = dispatch.reply || dispatch.echo;
  if (reply) return `Intent : ${intent}\n\n${String(reply)}`;
  return `Intent : ${intent}\n${JSON.stringify(dispatch, null, 2).slice(0, 2000)}`;
}

export async function postAssistantChat(
  settings: PilotSettings,
  text: string,
  context: Record<string, unknown> = {},
): Promise<{ status: number; body: Record<string, unknown> }> {
  const r = await fetch(`${apiRoot(settings)}/v1/pilot/assistant/chat`, {
    method: "POST",
    headers: authHeaders(settings),
    body: JSON.stringify({
      text,
      actor_id: "pilot:shell:chat",
      context: buildContext(settings, context),
    }),
  });
  const body = (await r.json().catch(() => ({}))) as Record<string, unknown>;
  return { status: r.status, body };
}

function parseSseDataLine(line: string): AssistantStreamEvent | null {
  const trimmed = line.trim();
  if (!trimmed.startsWith("data:")) return null;
  const payload = trimmed.slice(5).trim();
  if (!payload) return null;
  try {
    return JSON.parse(payload) as AssistantStreamEvent;
  } catch {
    return null;
  }
}

/** Chat assistant en SSE — tokens + outils. Repli JSON si stream indisponible. */
export async function streamAssistantChat(
  settings: PilotSettings,
  text: string,
  context: Record<string, unknown> = {},
  onEvent: (evt: AssistantStreamEvent) => void,
): Promise<{ status: number; reply: string }> {
  const url = `${apiRoot(settings)}/v1/pilot/assistant/chat/stream`;
  const r = await fetch(url, {
    method: "POST",
    headers: authHeaders(settings),
    body: JSON.stringify({
      text,
      actor_id: "pilot:shell:chat",
      context: buildContext(settings, context),
    }),
  });

  if (r.status !== 200 || !r.body) {
    const fallback = await postAssistantChat(settings, text, context);
    if (fallback.status !== 200) {
      onEvent({ kind: "error", error: httpErrorMessage(fallback.status, fallback.body, settings) });
      return { status: fallback.status, reply: "" };
    }
    const display = formatRouteResponse(fallback.body);
    onEvent({ kind: "token", delta: display.primaryText });
    onEvent({ kind: "done", reply: display.primaryText });
    return { status: 200, reply: display.primaryText };
  }

  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let reply = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n");
    buffer = parts.pop() ?? "";
    for (const line of parts) {
      const evt = parseSseDataLine(line);
      if (!evt) continue;
      onEvent(evt);
      if (evt.kind === "token") reply += evt.delta;
      if (evt.kind === "done" && evt.reply) reply = evt.reply;
    }
  }

  if (buffer.trim()) {
    const evt = parseSseDataLine(buffer);
    if (evt) {
      onEvent(evt);
      if (evt.kind === "token") reply += evt.delta;
      if (evt.kind === "done" && evt.reply) reply = evt.reply;
    }
  }

  return { status: 200, reply };
}

export async function postTaskRun(
  settings: PilotSettings,
  goal: string,
  context: Record<string, unknown> = {},
): Promise<{ status: number; body: Record<string, unknown> }> {
  const r = await fetch(`${apiRoot(settings)}/v1/pilot/tasks/run`, {
    method: "POST",
    headers: authHeaders(settings),
    body: JSON.stringify({
      goal,
      actor_id: "pilot:shell",
      context: buildContext(settings, context),
    }),
  });
  const body = (await r.json().catch(() => ({}))) as Record<string, unknown>;
  return { status: r.status, body };
}

export function formatTaskReply(body: Record<string, unknown>): string {
  if (body.detail && body.ok === false) {
    const d = body.detail;
    return typeof d === "string" ? d : JSON.stringify(d, null, 2);
  }
  const reply = String(body.reply || body.error || "");
  const status = String(body.status || "");
  const state = body.state as Record<string, unknown> | undefined;
  let out = reply || `Statut : ${status}`;
  if (state?.retries != null) out += `\n\nTentatives : ${state.retries}`;
  if (state?.plan_source) out += `\nPlan : ${state.plan_source}`;
  if (state?.job_id) out += `\nJob : ${state.job_id}`;
  return out;
}

export function httpErrorMessage(
  status: number,
  body: Record<string, unknown>,
  settings: PilotSettings,
): string {
  if (status === 401) {
    if (!settings.serviceToken.trim() && !settings.token.trim()) {
      return "Jeton manquant — ouvrez Réglages (service token ou Bearer).";
    }
    return "Jeton refusé (401).";
  }
  if (status === 503) {
    return `Service indisponible : ${String(body.detail || body.error || "supervisé désactivé")}`;
  }
  const detail = body.detail ?? body.message;
  return typeof detail === "string" ? detail : JSON.stringify(detail ?? body, null, 2);
}
