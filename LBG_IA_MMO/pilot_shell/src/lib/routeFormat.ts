/** Formatage des réponses POST /v1/pilot/route et action-proposal. */

export type RouteDisplay = {
  primaryText: string;
  metaLine: string;
  lyraJson: string | null;
  profileResolved: string | null;
  intent: string | null;
  traceId: string | null;
  elapsedMs: number | null;
  raw: Record<string, unknown>;
};

function asRecord(v: unknown): Record<string, unknown> | null {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : null;
}

function formatPmBrief(brief: Record<string, unknown>): string {
  const lines: string[] = [];
  const title = brief.title ? String(brief.title) : "Point projet";
  lines.push(title);

  const step = brief.current_step;
  if (typeof step === "string" && step.trim()) {
    lines.push("", "Étape actuelle :", step.trim());
  }

  const fa = brief.file_attente;
  if (typeof fa === "string" && fa.trim()) {
    lines.push("", "File d'attente :", fa.trim());
  }

  const milestones = Array.isArray(brief.milestones) ? brief.milestones : [];
  if (milestones.length) {
    lines.push("", "Derniers jalons :");
    for (const m of milestones.slice(-5)) {
      const row = asRecord(m);
      if (!row) continue;
      lines.push(`• ${row.date ?? "?"} — ${String(row.summary ?? row.raw ?? "").slice(0, 160)}`);
    }
  }

  const tasks = Array.isArray(brief.tasks) ? brief.tasks : [];
  if (tasks.length) {
    lines.push("", "Tâches suggérées :");
    for (const t of tasks.slice(0, 6)) {
      const row = asRecord(t);
      if (!row) continue;
      lines.push(`• ${String(row.title ?? "?")}`);
    }
  }

  const hints = Array.isArray(brief.hints) ? brief.hints : [];
  if (hints.length) {
    lines.push("", "Pistes :");
    for (const h of hints.slice(0, 3)) {
      lines.push(`— ${String(h)}`);
    }
  }

  const docs = Array.isArray(brief.docs) ? brief.docs : [];
  if (docs.length) {
    lines.push("", `Docs : ${docs.map(String).join(", ")}`);
  }

  return lines.join("\n").trim();
}

function extractReply(result: Record<string, unknown> | null): string {
  if (!result) return "";
  const out = asRecord(result.output);
  if (!out) return "";

  const remote = asRecord(out.remote);
  if (remote?.reply && typeof remote.reply === "string") return remote.reply.trim();

  const om = asRecord(out.orchestrator_route_meta);
  if (om?.assistant_reply && typeof om.assistant_reply === "string") {
    return om.assistant_reply.trim();
  }

  if (typeof out.reply === "string") return out.reply.trim();
  if (typeof out.echo === "string") return out.echo.trim();

  const brief = asRecord(out.brief) ?? asRecord(remote?.brief);
  if (brief) return formatPmBrief(brief);

  return "";
}

export function formatRouteResponse(body: Record<string, unknown>): RouteDisplay {
  const traceId = typeof body.trace_id === "string" ? body.trace_id : null;
  const elapsedMs = typeof body.elapsed_ms === "number" ? body.elapsed_ms : null;

  if (body.ok === false) {
    const err = String(body.error ?? body.detail ?? "échec");
    return {
      primaryText: err,
      metaLine: traceId ? `${traceId} · ${elapsedMs ?? "?"} ms` : "",
      lyraJson: null,
      profileResolved: null,
      intent: null,
      traceId,
      elapsedMs,
      raw: body,
    };
  }

  // P03 : { intent, dispatch } sans enveloppe result
  const p03Intent = body.intent != null ? String(body.intent) : null;
  const p03Dispatch = asRecord(body.dispatch);
  if (p03Intent && p03Dispatch && !body.result) {
    let primaryText = "";
    if (p03Dispatch.agentic) {
      primaryText = String(p03Dispatch.reply || p03Dispatch.error || "");
    } else if (typeof p03Dispatch.reply === "string") {
      primaryText = p03Dispatch.reply;
    } else if (p03Intent === "unknown" && p03Dispatch.hint) {
      primaryText = String(p03Dispatch.hint);
    }
    return {
      primaryText: primaryText || `(${p03Intent})`,
      metaLine: `intent: ${p03Intent}`,
      lyraJson: null,
      profileResolved: null,
      intent: p03Intent,
      traceId,
      elapsedMs,
      raw: body,
    };
  }

  const result = asRecord(body.result);
  const intent = result?.intent != null ? String(result.intent) : null;
  const out = asRecord(result?.output);
  const remote = asRecord(out?.remote);
  const rmeta = asRecord(remote?.meta);

  let primaryText = extractReply(result);
  if (!primaryText && intent) {
    primaryText = formatRouteReplyLegacy(body);
  }
  if (!primaryText) {
    primaryText = intent ? `Intent : ${intent}\n(réponse sans texte lisible)` : JSON.stringify(body, null, 2).slice(0, 1500);
  }

  const metaBits: string[] = [];
  if (intent) metaBits.push(`intent: ${intent}`);
  if (result?.routed_to) metaBits.push(String(result.routed_to));
  if (elapsedMs != null) metaBits.push(`${elapsedMs} ms`);
  if (traceId) metaBits.push(traceId.slice(0, 12));

  const om = asRecord(out?.orchestrator_route_meta);
  if (om?.intent_source) metaBits.push(`source: ${om.intent_source}`);

  const cr = asRecord(body.commit_result);
  if (cr) {
    metaBits.push(`commit: ${cr.accepted === true ? "ok" : cr.attempted ? "refusé" : "—"}`);
  }

  if (rmeta?.cache_hit != null) metaBits.push(`cache: ${rmeta.cache_hit}`);
  const profile =
    (out?.dialogue_profile_resolved as string | undefined) ||
    (rmeta?.dialogue_profile_resolved as string | undefined) ||
    null;

  let lyraJson: string | null = null;
  if (out?.lyra) {
    try {
      lyraJson = JSON.stringify(out.lyra, null, 2);
    } catch {
      lyraJson = String(out.lyra);
    }
  }

  return {
    primaryText,
    metaLine: metaBits.join(" · "),
    lyraJson,
    profileResolved: profile && String(profile).trim() ? String(profile) : null,
    intent,
    traceId,
    elapsedMs,
    raw: body,
  };
}

/** Compat P03 / dispatch direct (fallback). */
function formatRouteReplyLegacy(body: Record<string, unknown>): string {
  const intent = String(body.intent || "");
  const dispatch = asRecord(body.dispatch);
  if (!dispatch) return "";
  if (dispatch.reply) return String(dispatch.reply);
  if (dispatch.echo) return String(dispatch.echo);
  if (intent === "unknown" && dispatch.hint) return String(dispatch.hint);
  return "";
}

export function formatProposalResponse(body: Record<string, unknown>): RouteDisplay {
  if (body.ok === false) {
    return formatRouteResponse(body);
  }
  const proposal = asRecord(body.proposal);
  if (!proposal) {
    return {
      primaryText: JSON.stringify(body, null, 2).slice(0, 2000),
      metaLine: "action-proposal",
      lyraJson: null,
      profileResolved: null,
      intent: null,
      traceId: null,
      elapsedMs: null,
      raw: body,
    };
  }

  const lines = [
    `Capability : ${proposal.capability ?? "?"}`,
    `Résumé : ${proposal.summary ?? "—"}`,
    `Risque : ${proposal.risk_level ?? "?"}`,
    proposal.requires_review ? "⚠ Revue requise" : "",
    "",
    "Action proposée :",
    JSON.stringify(proposal.action ?? proposal.context_patch ?? {}, null, 2),
  ].filter(Boolean);

  return {
    primaryText: lines.join("\n"),
    metaLine: `proposal · ${proposal.source ?? "?"}`,
    lyraJson: null,
    profileResolved: null,
    intent: String(proposal.capability ?? ""),
    traceId: null,
    elapsedMs: null,
    raw: body,
  };
}

export function dialogueReplyForHistory(body: Record<string, unknown>): string {
  const result = asRecord(body.result);
  const out = asRecord(result?.output);
  const remote = asRecord(out?.remote);
  if (remote?.reply && typeof remote.reply === "string") return remote.reply.trim();
  if (out?.reply && typeof out.reply === "string") return String(out.reply).trim();
  const dispatch = asRecord(body.dispatch);
  if (dispatch?.reply && typeof dispatch.reply === "string") return dispatch.reply.trim();
  return "";
}
