import { useCallback, useEffect, useRef, useState } from "react";
import {
  formatTaskReply,
  httpErrorMessage,
  postActionProposal,
  postRoute,
  postTaskRun,
  streamAssistantChat,
  type AssistantStreamEvent,
  type ChatMessage,
  type PilotSettings,
  type ToolCallDisplay,
} from "../api/pilotApi";
import { cleanChatReply } from "../lib/chatDisplay";
import { enrichChatContext, extractHostHint } from "../lib/chatHeuristics";
import {
  appendDialogueHistory,
  getCombatKey,
  getNpcKey,
  loadEncounterState,
  loadIntentMode,
  loadNoCache,
  loadQuestState,
  loadShellChat,
  mergeContextFromStorage,
  normalizeHistory,
  persistStateFromResponse,
  saveIntentMode,
  saveNoCache,
  saveShellChat,
  type IntentClassifyMode,
} from "../lib/chatStorage";
import { presetByKey } from "../lib/presets";
import {
  dialogueReplyForHistory,
  formatProposalResponse,
  formatRouteResponse,
  type RouteDisplay,
} from "../lib/routeFormat";

export type AssistantMode = "chat" | "ops" | "supervised";

function uid(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function parseContextJson(raw: string): Record<string, unknown> {
  const trimmed = raw.trim();
  if (!trimmed) return {};
  const parsed = JSON.parse(trimmed) as unknown;
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Le contexte doit être un objet JSON.");
  }
  return parsed as Record<string, unknown>;
}

function threadHistory(messages: ChatMessage[]) {
  return normalizeHistory(
    messages
      .filter((m) => m.role === "user" || m.role === "assistant")
      .map((m) => ({ role: m.role, content: m.content })),
  );
}

function formatUserMeta(mode: AssistantMode, chatMode: "route" | "proposal"): string {
  if (chatMode === "proposal") return "proposition";
  if (mode === "supervised") return "supervisé";
  if (mode === "chat") return "chat";
  return "ops";
}

function formatAssistantMeta(
  display: RouteDisplay | null,
  taskBody: Record<string, unknown> | null,
  mode: AssistantMode,
): string {
  if (mode === "supervised" && taskBody) {
    const ok = taskBody.ok === true;
    return ok ? "succès" : String(taskBody.status || "échec");
  }
  if (mode === "chat") return "assistant";
  if (mode === "ops" && display) return display.metaLine || "ops";
  return display?.metaLine || "OK";
}

function supervisedGoal(text: string, messages: ChatMessage[]): string {
  const host = extractHostHint(text);
  const hostLine = host ? `\nCible explicite : ${host}.` : "";
  const hist = threadHistory(messages);
  if (hist.length < 2) return `${text}${hostLine}`;
  const lines = hist.slice(-6).map((m) => `${m.role === "user" ? "User" : "Assistant"}: ${m.content.slice(0, 300)}`);
  return `Contexte récent:\n${lines.join("\n")}\n\nObjectif: ${text}${hostLine}`;
}

export function useAgentChat(settings: PilotSettings) {
  const persisted = loadShellChat();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [contextJson, setContextJson] = useState(persisted.contextJson);
  const [intentMode, setIntentModeState] = useState<IntentClassifyMode>(() => loadIntentMode());
  const [noCache, setNoCacheState] = useState(() => loadNoCache());
  const [autoHistory, setAutoHistory] = useState(persisted.autoHistory);
  const [chatMode, setChatMode] = useState<"route" | "proposal">(persisted.chatMode);
  const [assistantMode, setAssistantMode] = useState<AssistantMode>(
    (persisted.assistantMode as AssistantMode) ?? "chat",
  );
  const [busy, setBusy] = useState(false);
  const [statusLine, setStatusLine] = useState("");
  const [lastDisplay, setLastDisplay] = useState<RouteDisplay | null>(null);
  const [contextOpen, setContextOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const messagesRef = useRef(messages);
  messagesRef.current = messages;

  useEffect(() => {
    saveShellChat({ contextJson, autoHistory, chatMode, assistantMode });
  }, [assistantMode, autoHistory, chatMode, contextJson]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, busy]);

  const pushMsg = useCallback((role: ChatMessage["role"], content: string, meta?: string) => {
    setMessages((prev) => [...prev, { id: uid(), role, content, meta }]);
  }, []);

  const applyStreamEvent = useCallback((assistantId: string, evt: AssistantStreamEvent) => {
    setMessages((prev) =>
      prev.map((m) => {
        if (m.id !== assistantId) return m;
        if (evt.kind === "token") {
          return { ...m, content: m.content + evt.delta };
        }
        if (evt.kind === "tool_start") {
          const tool: ToolCallDisplay = {
            id: uid(),
            tool: evt.tool,
            args: evt.args,
            status: "running",
          };
          return { ...m, tools: [...(m.tools ?? []), tool] };
        }
        if (evt.kind === "tool_result") {
          const tools = [...(m.tools ?? [])];
          const idx = [...tools].reverse().findIndex(
            (t) => t.tool === evt.tool && t.status === "running",
          );
          if (idx >= 0) {
            const realIdx = tools.length - 1 - idx;
            tools[realIdx] = {
              ...tools[realIdx],
              status: evt.ok === false ? "error" : "done",
              ok: evt.ok,
              output: evt.output,
            };
          } else {
            tools.push({
              id: uid(),
              tool: evt.tool,
              args: evt.args ?? {},
              status: evt.ok === false ? "error" : "done",
              ok: evt.ok,
              output: evt.output,
            });
          }
          return { ...m, tools };
        }
        if (evt.kind === "error") {
          return { ...m, content: evt.error, streaming: false };
        }
        if (evt.kind === "done") {
          const finalText = cleanChatReply(evt.reply || m.content);
          return { ...m, content: finalText, streaming: false };
        }
        return m;
      }),
    );
  }, []);

  const applyIntentMode = useCallback(
    (ctx: Record<string, unknown>): Record<string, unknown> => {
      const next = { ...ctx };
      const mode =
        intentMode === "auto" && assistantMode === "chat" ? "llm" : intentMode;
      if (mode === "llm") next._intent_classify = "llm";
      else if (mode === "deterministic") next._intent_classify = "deterministic";
      else delete next._intent_classify;
      return next;
    },
    [assistantMode, intentMode],
  );

  const prepareContext = useCallback(
    (text: string, contextOverride?: Record<string, unknown>): Record<string, unknown> => {
      const base = contextOverride ?? parseContextJson(contextJson);
      let ctx = mergeContextFromStorage(applyIntentMode({ ...base }));
      ctx = enrichChatContext(ctx, text, assistantMode);
      const hist = threadHistory(messagesRef.current);
      if (hist.length) ctx.history = hist;
      if (noCache) ctx._no_cache = true;
      else delete ctx._no_cache;
      return ctx;
    },
    [applyIntentMode, assistantMode, contextJson, noCache],
  );

  const send = useCallback(
    async (textOverride?: string, contextOverride?: Record<string, unknown>) => {
      const text = (textOverride ?? "").trim();
      if (!text || busy) return;

      let ctx: Record<string, unknown>;
      try {
        ctx = prepareContext(text, contextOverride);
      } catch (e) {
        setStatusLine(e instanceof Error ? e.message : String(e));
        return;
      }

      setBusy(true);
      const statusLabels = {
        chat: "…",
        ops: "Routage…",
        supervised: "Superviseur (jobs)…",
      } as const;
      setStatusLine(
        chatMode === "proposal" ? "Proposition…" : statusLabels[assistantMode],
      );
      pushMsg("user", text, formatUserMeta(assistantMode, chatMode));

      try {
        if (assistantMode === "supervised" && chatMode === "route") {
          const goal = supervisedGoal(text, messagesRef.current);
          const { status, body } = await postTaskRun(settings, goal, ctx);
          if (status !== 200 || body.ok === false) {
            const err =
              body.ok === false
                ? formatTaskReply(body)
                : httpErrorMessage(status, body, settings);
            pushMsg("assistant", err, `HTTP ${status}`);
            setStatusLine(`Erreur HTTP ${status}`);
            setLastDisplay(null);
            return;
          }
          const primary = cleanChatReply(formatTaskReply(body));
          pushMsg(
            "assistant",
            primary,
            formatAssistantMeta(null, body, "supervised"),
          );
          setLastDisplay(null);
          setStatusLine("");
          return;
        }

        let status: number;
        let body: Record<string, unknown>;

        if (chatMode === "proposal") {
          ({ status, body } = await postActionProposal(settings, text, ctx));
        } else if (assistantMode === "chat") {
          const assistantId = uid();
          setMessages((prev) => [
            ...prev,
            {
              id: assistantId,
              role: "assistant",
              content: "",
              meta: "assistant",
              tools: [],
              streaming: true,
            },
          ]);
          const { status: streamStatus, reply } = await streamAssistantChat(
            settings,
            text,
            ctx,
            (evt) => applyStreamEvent(assistantId, evt),
          );
          if (streamStatus !== 200) {
            setStatusLine(`Erreur HTTP ${streamStatus}`);
            setLastDisplay(null);
            return;
          }
          setLastDisplay(null);
          setStatusLine("");
          let nextCtx = ctx;
          if (autoHistory && reply) {
            nextCtx = appendDialogueHistory(nextCtx, text, reply);
          }
          setContextJson(JSON.stringify(nextCtx, null, 2));
          return;
        } else {
          ({ status, body } = await postRoute(settings, text, ctx));
        }

        if (status !== 200) {
          const err = httpErrorMessage(status, body, settings);
          pushMsg("assistant", err, `HTTP ${status}`);
          setStatusLine(`Erreur HTTP ${status}`);
          setLastDisplay(null);
          return;
        }

        const display =
          chatMode === "proposal" ? formatProposalResponse(body) : formatRouteResponse(body);
        const replyText =
          assistantMode === "chat" ? cleanChatReply(display.primaryText) : display.primaryText;
        setLastDisplay(display);
        pushMsg(
          "assistant",
          replyText,
          formatAssistantMeta(display, null, assistantMode),
        );
        setStatusLine(assistantMode === "chat" ? "" : display.metaLine || "OK");

        const result = body.result as Record<string, unknown> | undefined;
        let nextCtx = persistStateFromResponse(ctx, result);
        if (autoHistory && chatMode === "route") {
          const reply = dialogueReplyForHistory(body) || replyText;
          if (reply) nextCtx = appendDialogueHistory(nextCtx, text, reply);
        }
        setContextJson(JSON.stringify(nextCtx, null, 2));
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        pushMsg("assistant", msg, "erreur réseau");
        setStatusLine(msg);
      } finally {
        setBusy(false);
      }
    },
    [applyStreamEvent, assistantMode, autoHistory, busy, chatMode, prepareContext, pushMsg, settings],
  );

  const applyPreset = useCallback(
    (key: string) => {
      const preset = presetByKey(key);
      if (!preset) return;

      let ctx = JSON.parse(JSON.stringify(preset.context)) as Record<string, unknown>;

      if (preset.injectQuest) {
        const npcKey = getNpcKey(ctx);
        const stored = loadQuestState(npcKey) || loadQuestState("global");
        if (stored?.quest_id) ctx.quest_state = stored;
      }
      if (preset.injectEncounter) {
        const combatKey = getCombatKey(ctx);
        const stored = loadEncounterState(combatKey) || loadEncounterState("global");
        if (stored?.encounter_id) {
          ctx.encounter_state = stored;
          if (!ctx.enemy_name) ctx.enemy_name = stored.opponent ?? "Adversaire";
        }
      }

      setContextJson(JSON.stringify(ctx, null, 2));
      void send(preset.text, ctx);
    },
    [send],
  );

  const applySupervisedPreset = useCallback(
    (label: string, text: string) => {
      setAssistantMode("supervised");
      void send(text);
    },
    [send],
  );

  const clearThread = useCallback(() => {
    setMessages([]);
    setLastDisplay(null);
    setStatusLine("");
  }, []);

  const setIntentMode = useCallback((mode: IntentClassifyMode) => {
    setIntentModeState(mode);
    saveIntentMode(mode);
  }, []);

  const setNoCache = useCallback((on: boolean) => {
    setNoCacheState(on);
    saveNoCache(on);
  }, []);

  return {
    messages,
    contextJson,
    setContextJson,
    intentMode,
    setIntentMode,
    noCache,
    setNoCache,
    autoHistory,
    setAutoHistory,
    chatMode,
    setChatMode,
    assistantMode,
    setAssistantMode,
    busy,
    statusLine,
    lastDisplay,
    contextOpen,
    setContextOpen,
    bottomRef,
    send,
    applyPreset,
    applySupervisedPreset,
    clearThread,
  };
}
