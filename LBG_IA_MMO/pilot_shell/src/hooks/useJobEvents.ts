import { useEffect, useRef } from "react";
import type { PilotSettings } from "../api/pilotApi";
import { useLogs } from "../stores/logsContext";

function apiRoot(settings: PilotSettings): string {
  const base = settings.apiBase.trim();
  return base ? base.replace(/\/$/, "") : "";
}

export function useJobEvents(
  settings: PilotSettings,
  jobId: string | null,
  onRefresh?: () => void,
): void {
  const { append } = useLogs();
  const onRefreshRef = useRef(onRefresh);
  onRefreshRef.current = onRefresh;

  useEffect(() => {
    if (!jobId) return;

    const url = `${apiRoot(settings)}/v1/pilot/jobs/${encodeURIComponent(jobId)}/events`;
    append("jobs", `SSE connecté — ${jobId}`);
    const es = new EventSource(url);

    es.onmessage = (e) => {
      append("jobs", e.data);
      onRefreshRef.current?.();
    };

    es.onerror = () => {
      append("jobs", `SSE erreur / fermé — ${jobId}`);
    };

    return () => {
      es.close();
      append("jobs", `SSE déconnecté — ${jobId}`);
    };
  }, [append, jobId, settings]);
}
