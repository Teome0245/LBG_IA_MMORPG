/** URL du client MMO (`/mmo/`) — même origine en prod Nginx. */
export function mmoClientUrl(): string {
  const env = (import.meta.env.VITE_MMO_CLIENT_URL as string | undefined)?.trim();
  if (env) return env.replace(/\/?$/, "/");
  const { origin, pathname } = window.location;
  if (pathname.includes("/pilot/v2")) {
    return `${origin}/mmo/`;
  }
  return `${origin}/mmo/`;
}

/** Base API companion — proxy Nginx `/companion-api/` ou URL explicite. */
export function companionApiBase(): string {
  const env = (import.meta.env.VITE_COMPANION_BASE_URL as string | undefined)?.trim();
  if (env) return env.replace(/\/+$/, "");
  return "/companion-api";
}
