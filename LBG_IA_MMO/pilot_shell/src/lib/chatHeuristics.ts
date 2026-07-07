/** Heuristiques pour le mode Chat naturel (pilot_shell). */

export function isProjectMetaQuestion(text: string): boolean {
  const t = text.trim().toLowerCase();
  if (!t) return false;
  if (/\b(lbg[_\s-]?project|lbg[_\s-]?ia|lbg[_\s-]?mmo)\b/i.test(t)) return true;
  if (/\b(projet|avancement|progression|roadmap|initiateur|plan de route)\b/i.test(t)) return true;
  if (
    /\b(où en|ou en|comment avance|état du|etat du|que peut|que peux|dis[- ]?moi)\b/i.test(t) &&
    /\b(projet|lbg|mmo|infra)\b/i.test(t)
  ) {
    return true;
  }
  return false;
}

export function isGreetingOnly(text: string): boolean {
  const t = text.trim().toLowerCase();
  return /^(bonjour|salut|hello|coucou|bonsoir)[\s!?.]*$/i.test(t);
}

/** Extrait un hôte linux-N ou une IP depuis le texte opérateur. */
export function extractHostHint(text: string): string | null {
  const t = text.trim();
  const linux = t.match(/\blinux-(\d{1,3})\b/i);
  if (linux) return `linux-${linux[1]}`;
  const ip = t.match(/\b192\.168\.0\.(\d{1,3})\b/);
  if (ip) return `linux-${ip[1]}`;
  const trailing = t.match(/\b(?:sur|la|vm|host|core|front)\s+(?:la\s+)?(\d{2,3})\s*\??\s*$/i);
  if (trailing) return `linux-${trailing[1]}`;
  const bare = t.match(/\b(\d{2,3})\s*\??\s*$/);
  if (bare && Number(bare[1]) >= 100) return `linux-${bare[1]}`;
  return null;
}

export function enrichChatContext(
  base: Record<string, unknown>,
  text: string,
  assistantMode: "chat" | "ops" | "supervised",
): Record<string, unknown> {
  const ctx = { ...base };

  if (assistantMode === "chat") {
    ctx.pilot_chat = true;
    ctx.prefer_pm_llm = true;
    if (isProjectMetaQuestion(text)) {
      ctx.pm_focus = true;
      ctx.pm_include_plan = true;
      ctx.pm_include_structure = true;
    } else if (isGreetingOnly(text)) {
      ctx.pilot_greeting = true;
    }
    // Conversation multi-tours : le fil UI alimente history (voir useAgentChat).
  }

  if (assistantMode === "supervised") {
    const host = extractHostHint(text);
    if (host) {
      ctx.supervised_target_host = host;
      ctx.devops_target = host;
    }
    if (/\bcore3\b/i.test(text)) {
      ctx.core3_hint = true;
    }
  }

  return ctx;
}
