import React, { useEffect, useMemo, useRef, useState } from "react";
import { pollEvents, postChat, tick, type SessionEvent } from "../lib/api";

function useDebugFlag(): boolean {
  return useMemo(() => new URLSearchParams(window.location.search).get("debug") === "1", []);
}

function useSessionId(): [string, (v: string) => void] {
  const [sid, setSid] = useState(() => localStorage.getItem("companion_session_id") || "main");
  const set = (v: string) => {
    const nv = v.trim() || "main";
    setSid(nv);
    localStorage.setItem("companion_session_id", nv);
  };
  return [sid, set];
}

export function App() {
  const debug = useDebugFlag();
  const [sessionId, setSessionId] = useSessionId();
  const [afterId, setAfterId] = useState(0);
  const [events, setEvents] = useState<SessionEvent[]>([]);
  const [text, setText] = useState("");
  const [status, setStatus] = useState<string>("");
  const [debugPayload, setDebugPayload] = useState<unknown>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const canSend = text.trim().length > 0;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events.length]);

  useEffect(() => {
    let stopped = false;
    async function loop() {
      while (!stopped) {
        try {
          const res = await pollEvents({ sessionId, afterId, debug, limit: 50 });
          if (res.events?.length) {
            setEvents((prev) => [...prev, ...res.events]);
          }
          setAfterId(res.last_message_id ?? afterId);
          if (debug && res.debug) setDebugPayload(res.debug);
          setStatus("");
        } catch (e: any) {
          setStatus(`poll: ${String(e?.message || e)}`);
        }
        await new Promise((r) => setTimeout(r, 1000));
      }
    }
    loop();
    return () => {
      stopped = true;
    };
  }, [sessionId, afterId, debug]);

  async function onSend() {
    const t = text.trim();
    if (!t) return;
    setText("");
    setStatus("envoi...");
    try {
      const res = await postChat({ sessionId, text: t, debug });
      if (debug && res.debug) setDebugPayload(res.debug);
      setStatus("");
      // le message utilisateur/assistant sera récupéré au prochain poll
    } catch (e: any) {
      setStatus(`send: ${String(e?.message || e)}`);
    }
  }

  async function onTick() {
    setStatus("tick...");
    try {
      const res = await tick({ sessionId, debug });
      if (res?.nudge) {
        // nudge sera ajouté à l'historique par le serveur ; poll le récupérera
      }
      setStatus("");
    } catch (e: any) {
      setStatus(`tick: ${String(e?.message || e)}`);
    }
  }

  return (
    <div style={styles.page}>
      <header style={styles.header}>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <strong>Companion Bot</strong>
          <span style={styles.badge}>phase 2</span>
          {debug ? <span style={styles.badgeDebug}>debug</span> : null}
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <label style={styles.label}>session</label>
          <input
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            style={styles.inputSmall}
            spellCheck={false}
          />
          <button onClick={onTick} style={styles.buttonSecondary} title="Fait avancer le tick autonome">
            Tick
          </button>
        </div>
      </header>

      <main style={styles.main}>
        <div style={styles.chat}>
          {events.map((m, idx) => (
            <div
              key={`${m.id ?? "x"}-${idx}`}
              style={{
                ...styles.msg,
                ...(m.role === "user" ? styles.msgUser : styles.msgAssistant),
              }}
            >
              <div style={styles.msgRole}>{m.role}</div>
              <div style={styles.msgContent}>{m.content}</div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        {debug ? (
          <aside style={styles.debugPanel}>
            <div style={styles.debugTitle}>Debug (caché sans `?debug=1`)</div>
            <pre style={styles.debugPre}>{JSON.stringify(debugPayload, null, 2)}</pre>
          </aside>
        ) : null}
      </main>

      <footer style={styles.footer}>
        <div style={styles.status}>{status}</div>
        <div style={styles.composer}>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            style={styles.textarea}
            placeholder="Écris ici…"
            rows={2}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) onSend();
            }}
          />
          <button onClick={onSend} disabled={!canSend} style={styles.buttonPrimary}>
            Envoyer
          </button>
        </div>
        <div style={styles.hint}>Entrée : Ctrl+Entrée pour envoyer. Debug : ajouter `?debug=1` à l’URL.</div>
      </footer>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    height: "100vh",
    display: "flex",
    flexDirection: "column",
    fontFamily: "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Ubuntu",
    background: "#0b1220",
    color: "#e7eefc",
  },
  header: {
    padding: "10px 14px",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    borderBottom: "1px solid rgba(255,255,255,0.08)",
    background: "#0b1220",
  },
  badge: {
    padding: "2px 8px",
    borderRadius: 999,
    background: "rgba(255,255,255,0.08)",
    fontSize: 12,
  },
  badgeDebug: {
    padding: "2px 8px",
    borderRadius: 999,
    background: "rgba(255, 165, 0, 0.18)",
    fontSize: 12,
    border: "1px solid rgba(255, 165, 0, 0.35)",
  },
  main: { flex: 1, display: "flex", gap: 12, padding: 12, overflow: "hidden" },
  chat: {
    flex: 1,
    overflow: "auto",
    padding: 12,
    borderRadius: 12,
    background: "rgba(255,255,255,0.04)",
    border: "1px solid rgba(255,255,255,0.06)",
  },
  msg: {
    maxWidth: 860,
    padding: "10px 12px",
    marginBottom: 10,
    borderRadius: 12,
    border: "1px solid rgba(255,255,255,0.08)",
    whiteSpace: "pre-wrap",
  },
  msgUser: { marginLeft: "auto", background: "rgba(90, 160, 255, 0.14)" },
  msgAssistant: { marginRight: "auto", background: "rgba(255,255,255,0.06)" },
  msgRole: { opacity: 0.7, fontSize: 12, marginBottom: 6 },
  msgContent: { fontSize: 14, lineHeight: 1.35 },
  footer: {
    padding: 12,
    borderTop: "1px solid rgba(255,255,255,0.08)",
    background: "#0b1220",
  },
  composer: { display: "flex", gap: 10, alignItems: "stretch" },
  textarea: {
    flex: 1,
    resize: "none",
    borderRadius: 10,
    padding: 10,
    background: "rgba(255,255,255,0.06)",
    border: "1px solid rgba(255,255,255,0.10)",
    color: "#e7eefc",
    outline: "none",
  },
  buttonPrimary: {
    padding: "10px 14px",
    borderRadius: 10,
    border: "1px solid rgba(255,255,255,0.12)",
    background: "rgba(90, 160, 255, 0.25)",
    color: "#e7eefc",
    cursor: "pointer",
  },
  buttonSecondary: {
    padding: "8px 10px",
    borderRadius: 10,
    border: "1px solid rgba(255,255,255,0.12)",
    background: "rgba(255,255,255,0.06)",
    color: "#e7eefc",
    cursor: "pointer",
  },
  inputSmall: {
    width: 160,
    padding: "7px 10px",
    borderRadius: 10,
    border: "1px solid rgba(255,255,255,0.12)",
    background: "rgba(255,255,255,0.06)",
    color: "#e7eefc",
    outline: "none",
  },
  label: { opacity: 0.7, fontSize: 12 },
  status: { minHeight: 18, opacity: 0.75, fontSize: 12, marginBottom: 8 },
  hint: { marginTop: 8, opacity: 0.65, fontSize: 12 },
  debugPanel: {
    width: 520,
    overflow: "hidden",
    borderRadius: 12,
    background: "rgba(255,255,255,0.04)",
    border: "1px solid rgba(255,255,255,0.06)",
    display: "flex",
    flexDirection: "column",
  },
  debugTitle: { padding: 10, borderBottom: "1px solid rgba(255,255,255,0.06)", fontSize: 12, opacity: 0.8 },
  debugPre: { margin: 0, padding: 10, overflow: "auto", fontSize: 12, lineHeight: 1.25 },
};

