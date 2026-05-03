/**
 * Charge la carte race_id → libellé depuis l’agent dialogue (direct) ou le proxy pilot (backend).
 * Essaie plusieurs URL usuelles (8080 front unifié, 8000 backend, 8020 agent).
 */
const PILOT_WORLD_CONTENT = "/v1/pilot/agent-dialogue/world-content";

function normalizeRaceDisplay(obj) {
    if (!obj || typeof obj !== "object") return null;
    const out = Object.create(null);
    for (const [k, v] of Object.entries(obj)) {
        if (typeof k === "string" && k.trim() && typeof v === "string" && v.trim()) {
            out[k.trim()] = v.trim();
        }
    }
    return Object.keys(out).length ? out : null;
}

export async function loadRaceDisplayMap(host) {
    const h = typeof host === "string" ? host.trim() : "";
    const urls = [];

    if (typeof window !== "undefined" && window.location && String(window.location.origin || "").startsWith("http")) {
        urls.push(`${window.location.origin}${PILOT_WORLD_CONTENT}`);
    }
    if (h) {
        urls.push(`http://${h}:8080${PILOT_WORLD_CONTENT}`);
        urls.push(`http://${h}:8000${PILOT_WORLD_CONTENT}`);
        urls.push(`http://${h}:8020/world-content`);
    }

    const seen = new Set();
    const unique = urls.filter((u) => (seen.has(u) ? false : (seen.add(u), true)));

    if (!unique.length) return null;

    for (const url of unique) {
        try {
            const r = await fetch(url, { method: "GET", credentials: "omit" });
            if (!r.ok) continue;
            const j = await r.json();
            if (!j || j.ok !== true || !j.race_display) continue;
            const map = normalizeRaceDisplay(j.race_display);
            if (map) return map;
        } catch (_) {
            /* CORS, réseau, etc. */
        }
    }
    return null;
}
