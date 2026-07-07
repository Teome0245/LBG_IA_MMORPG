/** Persistance chat legacy (pilot_web) — historique PNJ, quêtes, combats. */

export const CHAT_STORAGE = {
  historyPrefix: "lbg_pilot_history_v1:",
  questPrefix: "lbg_pilot_quest_state_v1:",
  combatPrefix: "lbg_pilot_encounter_state_v1:",
  intentMode: "lbg_pilot_home_orch_intent_mode_v1",
  noCache: "lbg_pilot_no_cache_v1",
  shellChat: "lbg_pilot_shell_chat_v1",
} as const;

export type HistoryMessage = { role: "user" | "assistant"; content: string };

export type IntentClassifyMode = "auto" | "llm" | "deterministic";

export function getNpcKey(context: Record<string, unknown>): string {
  const npc = context.npc_name;
  if (typeof npc === "string" && npc.trim()) return npc.trim();
  return "global";
}

export function getCombatKey(context: Record<string, unknown>): string {
  for (const k of ["enemy_name", "target_name", "opponent"] as const) {
    const v = context[k];
    if (typeof v === "string" && v.trim()) return v.trim();
  }
  return "global";
}

export function normalizeHistory(history: unknown): HistoryMessage[] {
  if (!Array.isArray(history)) return [];
  const out: HistoryMessage[] = [];
  for (const m of history) {
    if (!m || typeof m !== "object") continue;
    const role = (m as HistoryMessage).role;
    const content = (m as HistoryMessage).content;
    if ((role !== "user" && role !== "assistant") || typeof content !== "string") continue;
    const c = content.trim();
    if (!c) continue;
    out.push({ role, content: c });
  }
  return out.length > 24 ? out.slice(out.length - 24) : out;
}

export function loadHistory(npcKey: string): HistoryMessage[] {
  try {
    const raw = localStorage.getItem(CHAT_STORAGE.historyPrefix + npcKey);
    if (!raw) return [];
    return normalizeHistory(JSON.parse(raw));
  } catch {
    return [];
  }
}

export function saveHistory(npcKey: string, history: HistoryMessage[]): void {
  try {
    localStorage.setItem(CHAT_STORAGE.historyPrefix + npcKey, JSON.stringify(history));
  } catch {
    /* ignore */
  }
}

export function loadQuestState(npcKey: string): Record<string, unknown> | null {
  try {
    const raw = localStorage.getItem(CHAT_STORAGE.questPrefix + npcKey);
    if (!raw) return null;
    const j = JSON.parse(raw) as unknown;
    return j && typeof j === "object" && !Array.isArray(j) ? (j as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

export function saveQuestState(npcKey: string, state: Record<string, unknown> | null): void {
  try {
    const key = CHAT_STORAGE.questPrefix + npcKey;
    if (!state) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(state));
  } catch {
    /* ignore */
  }
}

export function loadEncounterState(combatKey: string): Record<string, unknown> | null {
  try {
    const raw = localStorage.getItem(CHAT_STORAGE.combatPrefix + combatKey);
    if (!raw) return null;
    const j = JSON.parse(raw) as unknown;
    return j && typeof j === "object" && !Array.isArray(j) ? (j as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

export function saveEncounterState(combatKey: string, state: Record<string, unknown> | null): void {
  try {
    const key = CHAT_STORAGE.combatPrefix + combatKey;
    if (!state) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(state));
  } catch {
    /* ignore */
  }
}

export function loadIntentMode(): IntentClassifyMode {
  const v = localStorage.getItem(CHAT_STORAGE.intentMode);
  if (v === "llm" || v === "deterministic" || v === "auto") return v;
  return "auto";
}

export function saveIntentMode(mode: IntentClassifyMode): void {
  localStorage.setItem(CHAT_STORAGE.intentMode, mode);
}

export function loadNoCache(): boolean {
  return localStorage.getItem(CHAT_STORAGE.noCache) === "1";
}

export function saveNoCache(on: boolean): void {
  localStorage.setItem(CHAT_STORAGE.noCache, on ? "1" : "0");
}

export type ShellChatPersist = {
  contextJson: string;
  autoHistory: boolean;
  chatMode: "route" | "proposal";
  assistantMode: "chat" | "ops" | "supervised";
};

export function loadShellChat(): ShellChatPersist {
  const defaults: ShellChatPersist = {
    contextJson: '{\n  "history": []\n}',
    autoHistory: true,
    chatMode: "route",
    assistantMode: "chat",
  };
  try {
    const raw = localStorage.getItem(CHAT_STORAGE.shellChat);
    if (!raw) return defaults;
    const p = JSON.parse(raw) as Partial<ShellChatPersist>;
    return { ...defaults, ...p };
  } catch {
    return defaults;
  }
}

export function saveShellChat(data: ShellChatPersist): void {
  localStorage.setItem(CHAT_STORAGE.shellChat, JSON.stringify(data));
}

export function mergeContextFromStorage(
  context: Record<string, unknown>,
): Record<string, unknown> {
  const npcKey = getNpcKey(context);
  const combatKey = getCombatKey(context);

  const merged = { ...context };

  if (!Array.isArray(merged.history)) {
    merged.history = loadHistory(npcKey);
  } else {
    merged.history = normalizeHistory(merged.history);
    saveHistory(npcKey, merged.history as HistoryMessage[]);
  }

  if (merged.quest_state == null) {
    const qs = loadQuestState(npcKey);
    if (qs) merged.quest_state = qs;
  } else if (typeof merged.quest_state === "object" && !Array.isArray(merged.quest_state)) {
    saveQuestState(npcKey, merged.quest_state as Record<string, unknown>);
  } else {
    delete merged.quest_state;
    saveQuestState(npcKey, null);
  }

  if (merged.encounter_state == null) {
    const es = loadEncounterState(combatKey);
    if (es) merged.encounter_state = es;
  } else if (typeof merged.encounter_state === "object" && !Array.isArray(merged.encounter_state)) {
    saveEncounterState(combatKey, merged.encounter_state as Record<string, unknown>);
  } else {
    delete merged.encounter_state;
    saveEncounterState(combatKey, null);
  }

  return merged;
}

export function persistStateFromResponse(
  context: Record<string, unknown>,
  result: Record<string, unknown> | undefined,
): Record<string, unknown> {
  if (!result) return context;
  const out = result.output as Record<string, unknown> | undefined;
  if (!out) return context;
  const remote = out.remote as Record<string, unknown> | undefined;
  const npcKey = getNpcKey(context);
  const combatKey = getCombatKey(context);
  const next = { ...context };

  const qs =
    (out.quest_state as Record<string, unknown> | undefined) ||
    (remote?.quest_state as Record<string, unknown> | undefined);
  if (qs && typeof qs === "object") {
    next.quest_state = qs;
    saveQuestState(npcKey, qs);
  }

  const enc =
    (out.encounter as Record<string, unknown> | undefined) ||
    (remote?.encounter as Record<string, unknown> | undefined);
  if (enc && typeof enc === "object" && enc.encounter_id) {
    next.encounter_state = {
      encounter_id: enc.encounter_id,
      round: enc.round,
      opponent: enc.opponent,
      hp: enc.hp,
      status: enc.status ?? "ongoing",
    };
    saveEncounterState(combatKey, next.encounter_state as Record<string, unknown>);
  }

  return next;
}

export function appendDialogueHistory(
  context: Record<string, unknown>,
  userText: string,
  assistantReply: string,
): Record<string, unknown> {
  const npcKey = getNpcKey(context);
  const history = normalizeHistory(loadHistory(npcKey));
  history.push({ role: "user", content: userText.trim() || "(…)" });
  history.push({ role: "assistant", content: assistantReply });
  const capped = normalizeHistory(history);
  saveHistory(npcKey, capped);
  return { ...context, history: capped };
}
