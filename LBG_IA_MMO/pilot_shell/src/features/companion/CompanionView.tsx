import { useMemo, useState } from "react";
import { ViewShell } from "../../components/ViewShell";
import { useCompanionChat } from "../../hooks/useCompanionChat";

export function CompanionView() {
  const debug = useMemo(() => new URLSearchParams(window.location.search).get("debug") === "1", []);
  const chat = useCompanionChat(debug);
  const [draft, setDraft] = useState("");

  const onSend = () => {
    const t = draft;
    setDraft("");
    void chat.send(t);
  };

  return (
    <ViewShell
      title="Companion Bot"
      description="Chat autonome — poll événements session, tick autonome."
      legacyHash=""
    >
      <div className="companion-view">
        <header className="companion-view__toolbar">
          <label className="field field--inline">
            <span className="field__label">Session</span>
            <input
              className="field__input field__input--narrow"
              value={chat.sessionId}
              onChange={(e) => chat.setSessionId(e.target.value)}
              spellCheck={false}
            />
          </label>
          <button type="button" className="btn btn--sm" onClick={() => void chat.tick()}>
            Tick autonome
          </button>
          {debug && <span className="badge">debug</span>}
        </header>

        <div className="companion-view__chat">
          {chat.events.length === 0 && <p className="muted">Aucun message — écrivez ci-dessous.</p>}
          {chat.events.map((m, idx) => (
            <div
              key={`${m.id ?? "x"}-${idx}`}
              className={`companion-msg companion-msg--${m.role === "user" ? "user" : "assistant"}`}
            >
              <div className="companion-msg__role">{m.role}</div>
              <div className="companion-msg__body">{m.content}</div>
            </div>
          ))}
          <div ref={chat.bottomRef} />
        </div>

        <footer className="companion-view__composer">
          <span className="companion-view__status">{chat.status}</span>
          <div className="companion-view__row">
            <textarea
              className="field__input"
              rows={2}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Message au companion…"
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                  e.preventDefault();
                  onSend();
                }
              }}
            />
            <button type="button" className="btn btn--primary btn--sm" disabled={!draft.trim()} onClick={onSend}>
              Envoyer
            </button>
          </div>
          <p className="muted">Ctrl+Entrée pour envoyer · Debug : <code>?debug=1</code></p>
        </footer>
      </div>
    </ViewShell>
  );
}
