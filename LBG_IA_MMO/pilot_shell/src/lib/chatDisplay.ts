/** Nettoyage affichage chat — masquer le jargon intent/routing. */

const INTENT_PREFIX = /^Intent\s*:\s*[\w.]+\s*\n+/i;
const UNKNOWN_HINT =
  /Intent inconnu[^]*?essayez help[^]*?(?:\n\nAstuce[^\n]*)?/gi;
const ROUTING_BULLETS =
  /Voici les sujets sur lesquels je peux vous aider\s*:[\s\S]*?(?=\n\n|\Z)/i;

export function cleanChatReply(text: string): string {
  let s = text.trim();
  s = s.replace(INTENT_PREFIX, "");
  s = s.replace(UNKNOWN_HINT, "").trim();
  s = s.replace(ROUTING_BULLETS, "").trim();
  // P03 : enlever lignes « orientation vers les intents »
  s = s.replace(/^- Orientation vers les intents[^\n]*\n?/gim, "");
  s = s.replace(/\n{3,}/g, "\n\n");
  return s.trim();
}

/** Extrait la réponse lisible d'un body route (LBG_IA_MMO ou P03). */
export function extractAnyReply(body: Record<string, unknown>): string {
  const result = body.result as Record<string, unknown> | undefined;
  if (result) {
    const out = result.output as Record<string, unknown> | undefined;
    if (out) {
      const remote = out.remote as Record<string, unknown> | undefined;
      if (typeof remote?.reply === "string" && remote.reply.trim()) return remote.reply.trim();
      if (typeof out.reply === "string" && out.reply.trim()) return out.reply.trim();
      const brief = (out.brief ?? remote?.brief) as Record<string, unknown> | undefined;
      if (brief && typeof brief === "object") {
        return formatBriefInline(brief);
      }
    }
  }
  // P03 direct
  const dispatch = body.dispatch as Record<string, unknown> | undefined;
  if (dispatch) {
    if (typeof dispatch.reply === "string" && dispatch.reply.trim()) return dispatch.reply.trim();
    if (dispatch.agentic && typeof dispatch.reply === "string") return dispatch.reply.trim();
  }
  if (typeof body.reply === "string" && body.reply.trim()) return body.reply.trim();
  return "";
}

function formatBriefInline(brief: Record<string, unknown>): string {
  const parts: string[] = [];
  if (brief.current_step) parts.push(String(brief.current_step));
  const ms = brief.milestones;
  if (Array.isArray(ms) && ms.length) {
    const last = ms[ms.length - 1] as Record<string, unknown>;
    parts.push(`Dernier jalon : ${last.date ?? "?"} — ${last.summary ?? ""}`);
  }
  const hints = brief.hints;
  if (Array.isArray(hints) && hints[0]) parts.push(String(hints[0]));
  return parts.join("\n\n") || String(brief.title ?? "Point projet");
}
