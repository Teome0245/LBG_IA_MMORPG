/**
 * Miroir léger du package Python `LBG_IA_MMO/hybrid_proactive_agent/`.
 * pour UI / agents web (sans dépendance).
 */

export type ProactifMode = "proactif_leger" | "proactif_avance" | "autonome";

export type InternalGoalStatus = "en_cours" | "bloque" | "termine";

export interface InternalGoal {
  id: string;
  progression: number;
  status: InternalGoalStatus;
}

export type ActionKind =
  | "question"
  | "suggestion"
  | "plan"
  | "wait"
  | "autonomous_nudge";

export type QuestionCategory =
  | "clarification"
  | "exploration"
  | "hypothese"
  | "projection"
  | "suggestion"
  | "verification";

export interface ProactiveAction {
  kind: ActionKind;
  message: string;
  mode: ProactifMode;
  questionCategory?: QuestionCategory;
  meta?: Record<string, unknown>;
}

export interface AgentInternalState {
  curiosite: number;
  tension: number;
  mode: ProactifMode;
  objectifs: InternalGoal[];
  memoireCourte: string[];
  lastUserTs: number;
  silenceSecondsEst: number;
}

const DEFAULT_GOALS = (): InternalGoal[] => [
  { id: "comprendre_utilisateur", progression: 0.2, status: "en_cours" },
  { id: "clarifier_contexte", progression: 0.1, status: "en_cours" },
  { id: "proposer_plan", progression: 0.0, status: "en_cours" },
  { id: "verifier_coherence", progression: 0.05, status: "en_cours" },
];

function clamp01(x: number): number {
  return Math.min(1, Math.max(0, x));
}

export class HybridProactiveEngineWeb {
  tensionAutonomeSeuil = 0.6;
  state: AgentInternalState;

  constructor() {
    this.state = {
      curiosite: 0.5,
      tension: 0.2,
      mode: "proactif_leger",
      objectifs: DEFAULT_GOALS(),
      memoireCourte: [],
      lastUserTs: Date.now() / 1000,
      silenceSecondsEst: 0,
    };
  }

  observeUserTurn(userMessage: string | null, context: Record<string, unknown> = {}): void {
    const now = Date.now() / 1000;
    this.state.lastUserTs = now;
    this.state.silenceSecondsEst = 0;
    if (userMessage?.trim()) {
      const text = userMessage.trim();
      this.state.memoireCourte.push(text.slice(-500));
      this.state.memoireCourte = this.state.memoireCourte.slice(-12);
      this.bumpGoal("comprendre_utilisateur", 0.15);
    }
    this.applyContextSignals(context, userMessage);
  }

  tickSilence(dtSeconds: number): void {
    this.state.silenceSecondsEst += Math.max(0, dtSeconds);
    if (this.state.silenceSecondsEst > 30) {
      this.state.tension = clamp01(this.state.tension + 0.03 * (dtSeconds / 30));
    }
    if (this.state.silenceSecondsEst > 120) {
      this.state.curiosite = clamp01(this.state.curiosite + 0.01 * (dtSeconds / 120));
    }
    this.stagnationTension();
  }

  private applyContextSignals(ctx: Record<string, unknown>, userMessage: string | null): void {
    const keys = ["intent", "objectif", "contraintes"] as const;
    let missing = 0;
    for (const k of keys) {
      if (!ctx[k]) missing++;
    }
    if (missing) {
      this.state.curiosite = clamp01(this.state.curiosite + 0.08 * missing);
      this.setGoalStatus("clarifier_contexte", "en_cours");
    } else {
      this.bumpGoal("clarifier_contexte", 0.2);
    }
    if (ctx.incoherent) {
      this.state.tension = clamp01(this.state.tension + 0.25);
      this.setGoalStatus("verifier_coherence", "bloque");
    }
    this.stagnationTension();
    const t = (userMessage ?? "").toLowerCase();
    if (/(flou|pas sûr|je sais pas|jsp|maybe)/i.test(t)) {
      this.state.curiosite = clamp01(this.state.curiosite + 0.12);
      this.state.tension = clamp01(this.state.tension + 0.1);
    }
  }

  private bumpGoal(goalId: string, delta: number): void {
    for (const g of this.state.objectifs) {
      if (g.id !== goalId) continue;
      g.progression = clamp01(g.progression + delta);
      if (g.progression >= 0.95) g.status = "termine";
      else if (g.status === "bloque" && delta > 0) g.status = "en_cours";
      break;
    }
  }

  private setGoalStatus(goalId: string, status: InternalGoalStatus): void {
    for (const g of this.state.objectifs) {
      if (g.id === goalId) {
        g.status = status;
        break;
      }
    }
  }

  private stagnationTension(): void {
    for (const g of this.state.objectifs) {
      if (g.status === "en_cours" && g.progression < 0.35) {
        this.state.tension = clamp01(this.state.tension + 0.04);
      }
      if (g.status === "bloque") {
        this.state.tension = clamp01(this.state.tension + 0.08);
      }
    }
  }

  chooseMode(context: Record<string, unknown> = {}): ProactifMode {
    if (
      this.state.tension >= this.tensionAutonomeSeuil ||
      (this.state.silenceSecondsEst >= 45 &&
        this.state.objectifs.some((g) => g.status === "bloque"))
    ) {
      this.state.mode = "autonome";
      return "autonome";
    }
    const fuzzy = Boolean(context.objectif_flou) || this.state.curiosite >= 0.55;
    if (fuzzy || context.missing_info || this.state.curiosite >= 0.65) {
      this.state.mode = "proactif_avance";
      return "proactif_avance";
    }
    this.state.mode = "proactif_leger";
    return "proactif_leger";
  }

  decide(context: Record<string, unknown> = {}): ProactiveAction {
    const mode = this.chooseMode(context);
    if (mode === "proactif_leger") {
      if (!context.intent) {
        return {
          kind: "question",
          mode,
          questionCategory: "clarification",
          message:
            "Souhaites-tu plutôt une assistance ponctuelle, de l'exploration, ou un agent intégré à un pipeline ?",
        };
      }
      return {
        kind: "suggestion",
        mode,
        questionCategory: "suggestion",
        message:
          "Je peux reformuler ce que j'ai compris et proposer la prochaine micro-étape utile — tu veux que je le fasse ?",
      };
    }
    if (mode === "proactif_avance") {
      this.bumpGoal("proposer_plan", 0.1);
      return {
        kind: "plan",
        mode,
        questionCategory: "verification",
        message:
          "Voici une structure possible : (1) perception, (2) motivation/tension, (3) action. On valide cette découpe ?",
        meta: { sousObjectifs: ["perception", "motivation", "action"] },
      };
    }
    const blocked = this.state.objectifs
      .filter((g) => g.status === "bloque")
      .map((g) => g.id);
    return {
      kind: "autonomous_nudge",
      mode: "autonome",
      questionCategory: "hypothese",
      message: `Je manque de signal sur l'objectif principal (bloqué : ${blocked.join(", ") || "rien"}). Quelle piste te correspond ?`,
    };
  }

  cooldownDecay(factor = 0.92): void {
    this.state.tension *= factor;
    this.state.curiosite *= Math.sqrt(factor);
  }
}

export function mmoOrchestratorHints(
  state: AgentInternalState,
  world: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    hybrid_proactive_mode: state.mode,
    hybrid_tension: Math.round(state.tension * 1000) / 1000,
    hybrid_curiosite: Math.round(state.curiosite * 1000) / 1000,
    suggest_clarify_intent: state.mode !== "proactif_leger",
    allow_autonomous_followup: state.mode === "autonome",
    ...(typeof world.npc_id === "string" ? { mmo_npc_id: world.npc_id } : {}),
    ...(typeof world.session_id === "string" ? { mmo_session_id: world.session_id } : {}),
  };
}
