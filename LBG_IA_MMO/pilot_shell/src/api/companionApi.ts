import { companionApiBase } from "../lib/urls";

export type SessionEvent = {
  id?: number | null;
  role: "user" | "assistant" | string;
  content: string;
  ts: number;
};

export type EventsResponse = {
  session_id: string;
  after_id: number;
  last_message_id: number;
  events: SessionEvent[];
  debug?: unknown | null;
};

export async function postCompanionChat(params: {
  sessionId: string;
  text: string;
  debug: boolean;
}): Promise<{ reply: string; session_id: string; debug?: unknown | null }> {
  const r = await fetch(`${companionApiBase()}/v1/chat?debug=${params.debug ? "true" : "false"}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ session_id: params.sessionId, text: params.text }),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()) as { reply: string; session_id: string; debug?: unknown | null };
}

export async function pollCompanionEvents(params: {
  sessionId: string;
  afterId: number;
  limit?: number;
  debug: boolean;
}): Promise<EventsResponse> {
  const q = new URLSearchParams();
  q.set("after_id", String(params.afterId));
  q.set("limit", String(params.limit ?? 50));
  q.set("debug", params.debug ? "true" : "false");
  const r = await fetch(
    `${companionApiBase()}/v1/session/${encodeURIComponent(params.sessionId)}/events?${q.toString()}`,
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()) as EventsResponse;
}

export async function companionTick(params: {
  sessionId: string;
  debug: boolean;
}): Promise<{ nudge?: string | null }> {
  const r = await fetch(
    `${companionApiBase()}/v1/session/${encodeURIComponent(params.sessionId)}/tick?debug=${params.debug ? "true" : "false"}`,
    { method: "POST" },
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()) as { nudge?: string | null };
}
