import { useState } from "react";
import { JsonEditor } from "../components/JsonEditor";
import { useSettings } from "../stores/context";
import { useAgentChat } from "../hooks/useAgentChat";
import { CHAT_PRESETS } from "../lib/presets";
import type { IntentClassifyMode } from "../lib/chatStorage";

const SUPERVISED_PRESETS = [
  { label: "Core 140", text: "diagnostic sur le core 140" },
  { label: "Core3 246", text: "sonde mmo core3 sur la 246" },
  { label: "Front 110", text: "healthz front 110" },
  { label: "Desktop vghd", text: "lance vghd sur mon pc" },
  { label: "Ops selfcheck", text: "devops selfcheck sur linux-140" },
];

export function AgentChat() {
  const { settings, setSettingsOpen } = useSettings();
  const chat = useAgentChat(settings);
  const [draft, setDraft] = useState("");
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const presetGroups = CHAT_PRESETS.reduce<Record<string, typeof CHAT_PRESETS>>((acc, p) => {
    (acc[p.group] ??= []).push(p);
    return acc;
  }, {});

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const t = draft.trim();
    if (!t) return;
    setDraft("");
    void chat.send(t);
  };

  const placeholder =
    chat.assistantMode === "supervised"
      ? "Objectif supervisé (plan → exécution → validation)…"
      : chat.assistantMode === "chat"
        ? "Question sur le projet, l'infra, le MMO…"
        : "Intention technique (devops, core3, desktop…)";

  return (
    <div className="agent-chat">
      <div className="agent-chat__toolbar">
        <div className="agent-chat__mode-group" role="tablist">
          <button
            type="button"
            className={`agent-chat__mode-btn${chat.assistantMode === "chat" ? " agent-chat__mode-btn--active" : ""}`}
            onClick={() => chat.setAssistantMode("chat")}
          >
            Chat
          </button>
          <button
            type="button"
            className={`agent-chat__mode-btn${chat.assistantMode === "supervised" ? " agent-chat__mode-btn--active" : ""}`}
            onClick={() => chat.setAssistantMode("supervised")}
          >
            Supervisé
          </button>
          <button
            type="button"
            className={`agent-chat__mode-btn${chat.assistantMode === "ops" ? " agent-chat__mode-btn--active" : ""}`}
            onClick={() => chat.setAssistantMode("ops")}
          >
            Ops
          </button>
          <button
            type="button"
            className={`agent-chat__mode-btn${chat.chatMode === "proposal" ? " agent-chat__mode-btn--active" : ""}`}
            onClick={() => chat.setChatMode(chat.chatMode === "proposal" ? "route" : "proposal")}
            title="Basculer propositions d'action"
          >
            Proposition
          </button>
        </div>
        <button
          type="button"
          className={`btn btn--ghost btn--xs${advancedOpen ? " btn--active" : ""}`}
          onClick={() => setAdvancedOpen(!advancedOpen)}
        >
          Avancé
        </button>
      </div>

      {advancedOpen && (
        <div className="agent-chat__advanced">
          <select
            className="agent-chat__select"
            value={chat.intentMode}
            onChange={(e) => chat.setIntentMode(e.target.value as IntentClassifyMode)}
            title="Classification intention"
          >
            <option value="auto">Intent auto</option>
            <option value="llm">Intent LLM</option>
            <option value="deterministic">Intent mots-clés</option>
          </select>
          <button
            type="button"
            className={`btn btn--ghost btn--xs${chat.contextOpen ? " btn--active" : ""}`}
            onClick={() => chat.setContextOpen(!chat.contextOpen)}
          >
            Context JSON
          </button>
        </div>
      )}

      {chat.contextOpen && (
        <div className="agent-chat__context">
          <JsonEditor value={chat.contextJson} onChange={chat.setContextJson} height="10rem" />
        </div>
      )}

      {chat.assistantMode === "supervised" && (
        <div className="agent-chat__presets">
          <div className="agent-chat__preset-group">
            <span className="agent-chat__preset-label">Supervisé</span>
            {SUPERVISED_PRESETS.map((p) => (
              <button
                key={p.label}
                type="button"
                className="agent-chat__preset-btn"
                disabled={chat.busy}
                onClick={() => chat.applySupervisedPreset(p.label, p.text)}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {chat.assistantMode === "ops" && (
        <div className="agent-chat__presets">
          {Object.entries(presetGroups).map(([group, items]) => (
            <div key={group} className="agent-chat__preset-group">
              <span className="agent-chat__preset-label">{group}</span>
              {items.map((p) => (
                <button
                  key={p.key}
                  type="button"
                  className="agent-chat__preset-btn"
                  disabled={chat.busy}
                  onClick={() => chat.applyPreset(p.key)}
                >
                  {p.label}
                </button>
              ))}
            </div>
          ))}
        </div>
      )}

      <div className="agent-chat__messages">
        {chat.messages.length === 0 && !chat.busy && (
          <p className="agent-chat__empty">
            <strong>Chat</strong> — assistant projet (plan de route + LLM).
            <strong> Supervisé</strong> — objectif explicite, boucle jobs.
            <strong> Ops</strong> — routage technique.
          </p>
        )}
        {chat.messages.map((m) => (
          <div key={m.id} className={`agent-chat__bubble agent-chat__bubble--${m.role}`}>
            <div className="agent-chat__bubble-meta agent-chat__bubble-meta--top">
              {m.role}
              {m.meta ? ` · ${m.meta}` : ""}
            </div>
            {m.tools && m.tools.length > 0 && (
              <div className="agent-chat__tools">
                {m.tools.map((t) => (
                  <details
                    key={t.id}
                    className={`agent-chat__tool agent-chat__tool--${t.status}`}
                    open={t.status === "running"}
                  >
                    <summary>
                      <span className="agent-chat__tool-name">{t.tool}</span>
                      <span className="agent-chat__tool-status">
                        {t.status === "running" ? "…" : t.ok === false ? "échec" : "ok"}
                      </span>
                    </summary>
                    {Object.keys(t.args).length > 0 && (
                      <pre className="agent-chat__tool-args">
                        {JSON.stringify(t.args, null, 2)}
                      </pre>
                    )}
                    {t.output && (
                      <pre className="agent-chat__tool-out">{t.output.slice(0, 2000)}</pre>
                    )}
                  </details>
                ))}
              </div>
            )}
            <div className="agent-chat__bubble-text">
              {m.content}
              {m.streaming && <span className="agent-chat__cursor">▍</span>}
            </div>
          </div>
        ))}
        {chat.busy && (
          <div className="agent-chat__bubble agent-chat__bubble--assistant agent-chat__bubble--typing">
            …
          </div>
        )}
        <div ref={chat.bottomRef} />
      </div>

      {chat.lastDisplay && chat.assistantMode === "ops" && (
        <details className="agent-chat__details">
          <summary>Détails réponse</summary>
          {chat.lastDisplay.profileResolved && (
            <p className="agent-chat__detail-line">
              Profil résolu : <code>{chat.lastDisplay.profileResolved}</code>
            </p>
          )}
          {chat.lastDisplay.lyraJson && (
            <pre className="agent-chat__lyra">{chat.lastDisplay.lyraJson}</pre>
          )}
        </details>
      )}

      <form className="agent-chat__composer" onSubmit={onSubmit}>
        <textarea
          className="agent-chat__input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={placeholder}
          rows={2}
          disabled={chat.busy}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
              e.preventDefault();
              onSubmit(e);
            }
          }}
        />
        <div className="agent-chat__composer-footer">
          <label className="agent-chat__check">
            <input
              type="checkbox"
              checked={chat.noCache}
              onChange={(e) => chat.setNoCache(e.target.checked)}
            />
            No cache
          </label>
          <label className="agent-chat__check">
            <input
              type="checkbox"
              checked={chat.autoHistory}
              onChange={(e) => chat.setAutoHistory(e.target.checked)}
            />
            Historique
          </label>
          <span className="agent-chat__status">{chat.statusLine}</span>
          <button type="button" className="btn btn--ghost btn--xs" onClick={chat.clearThread}>
            Effacer
          </button>
          <button type="submit" className="btn btn--primary btn--sm" disabled={chat.busy || !draft.trim()}>
            Envoyer
          </button>
        </div>
      </form>

      <footer className="agent-panel__footer">
        <button type="button" className="btn btn--ghost btn--sm" onClick={() => setSettingsOpen(true)}>
          Réglages
        </button>
      </footer>
    </div>
  );
}
