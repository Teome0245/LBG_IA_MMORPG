export type ChatResponse = { reply: string; session_id: string; debug?: unknown | null };

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

function baseUrl(): string {
  const env = (import.meta.env.VITE_COMPANION_BASE_URL as string | undefined)?.trim();
  if (env) return env.replace(/\/+$/, "");
  // Prod LAN recommandé : same-origin via Nginx (/companion-api -> microservice)
  return "/companion-api";
}

export async function postChat(params: {
  sessionId: string;
  text: string;
  debug: boolean;
}): Promise<ChatResponse> {
  const r = await fetch(`${baseUrl()}/v1/chat?debug=${params.debug ? "true" : "false"}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ session_id: params.sessionId, text: params.text }),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()) as ChatResponse;
}

export async function pollEvents(params: {
  sessionId: string;
  afterId: number;
  limit?: number;
  debug: boolean;
}): Promise<EventsResponse> {
  const q = new URLSearchParams();
  q.set("after_id", String(params.afterId));
  q.set("limit", String(params.limit ?? 50));
  q.set("debug", params.debug ? "true" : "false");
  const r = await fetch(`${baseUrl()}/v1/session/${encodeURIComponent(params.sessionId)}/events?${q.toString()}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()) as EventsResponse;
}

export async function tick(params: { sessionId: string; debug: boolean }): Promise<{ nudge?: string | null }> {
  const r = await fetch(
    `${baseUrl()}/v1/session/${encodeURIComponent(params.sessionId)}/tick?debug=${params.debug ? "true" : "false"}`,
    { method: "POST" },
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()) as { nudge?: string | null };
}

