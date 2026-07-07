import { useEffect, useRef, useState } from "react";
import {
  companionTick,
  pollCompanionEvents,
  postCompanionChat,
  type SessionEvent,
} from "../api/companionApi";

const SESSION_KEY = "companion_session_id";

export function useCompanionChat(debug = false) {
  const [sessionId, setSessionIdState] = useState(
    () => localStorage.getItem(SESSION_KEY) || "main",
  );
  const afterIdRef = useRef(0);
  const [events, setEvents] = useState<SessionEvent[]>([]);
  const [status, setStatus] = useState("");
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const setSessionId = (v: string) => {
    const next = v.trim() || "main";
    setSessionIdState(next);
    localStorage.setItem(SESSION_KEY, next);
    afterIdRef.current = 0;
    setEvents([]);
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events.length]);

  useEffect(() => {
    let stopped = false;
    async function loop() {
      while (!stopped) {
        try {
          const res = await pollCompanionEvents({
            sessionId,
            afterId: afterIdRef.current,
            debug,
            limit: 50,
          });
          if (res.events?.length) {
            setEvents((prev) => [...prev, ...res.events]);
          }
          afterIdRef.current = res.last_message_id ?? afterIdRef.current;
          setStatus("");
        } catch (e) {
          setStatus(`poll: ${e instanceof Error ? e.message : String(e)}`);
        }
        await new Promise((r) => setTimeout(r, 1000));
      }
    }
    void loop();
    return () => {
      stopped = true;
    };
  }, [sessionId, debug]);

  const send = async (text: string) => {
    const t = text.trim();
    if (!t) return;
    setStatus("envoi…");
    try {
      await postCompanionChat({ sessionId, text: t, debug });
      setStatus("");
    } catch (e) {
      setStatus(`send: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  const tick = async () => {
    setStatus("tick…");
    try {
      await companionTick({ sessionId, debug });
      setStatus("");
    } catch (e) {
      setStatus(`tick: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  return { sessionId, setSessionId, events, status, bottomRef, send, tick };
}
