export type PresetDef = {
  key: string;
  label: string;
  group: string;
  text: string;
  context: Record<string, unknown>;
  injectQuest?: boolean;
  injectEncounter?: boolean;
};

export const CHAT_PRESETS: PresetDef[] = [
  {
    key: "forge",
    label: "Forgeron",
    group: "Dialogue",
    text: "Je veux parler au forgeron",
    context: { npc_name: "Hagen le forgeron", world_npc_id: "npc:smith", history: [] },
  },
  {
    key: "healer",
    label: "Guérisseuse",
    group: "Dialogue",
    text: "Je ne me sens pas bien… peux-tu m'aider ?",
    context: { npc_name: "Guérisseuse du village", world_npc_id: "npc:healer", history: [] },
  },
  {
    key: "mayor",
    label: "Maire",
    group: "Dialogue",
    text: "Y a-t-il des problèmes récents au village ?",
    context: { npc_name: "Maire", world_npc_id: "npc:mayor", history: [] },
  },
  {
    key: "quete",
    label: "Quête",
    group: "Quête",
    text: "Je cherche une quête ou une mission.",
    context: { history: [] },
  },
  {
    key: "quete_avancement",
    label: "Avancement quête",
    group: "Quête",
    text: "J'ai avancé sur la quête.",
    context: { history: [] },
    injectQuest: true,
  },
  {
    key: "combat",
    label: "Combat",
    group: "Combat",
    text: "Je veux attaquer le gobelin",
    context: { enemy_name: "Gobelin des égouts", history: [] },
  },
  {
    key: "combat_avancement",
    label: "Avancement combat",
    group: "Combat",
    text: "Je continue le combat en frappant",
    context: { history: [] },
    injectEncounter: true,
  },
  {
    key: "devops_sonde",
    label: "DevOps healthz",
    group: "Ops",
    text: "Sonde DevOps — healthz orchestrator",
    context: {
      devops_action: { kind: "http_get", url: "http://127.0.0.1:8010/healthz" },
      history: [],
    },
  },
  {
    key: "lyra_test",
    label: "Lyra test",
    group: "Lyra",
    text: "Ping état Lyra (fallback)",
    context: {
      history: [],
      lyra: { gauges: { hunger: 0.1, thirst: 0.05, fatigue: 0.2 }, dt_s: 3600, version: "0.1" },
    },
  },
  {
    key: "pm",
    label: "Chef de projet",
    group: "Ops",
    text: "jalons et tâches du plan de route",
    context: { project_pm: true, pm_include_plan: true, pm_include_structure: true, history: [] },
  },
  {
    key: "selfcheck",
    label: "Selfcheck",
    group: "Ops",
    text: "devops selfcheck (dry-run) : diagnostique et propose une action concrète.",
    context: {
      devops_action: { kind: "selfcheck" },
      devops_dry_run: true,
      devops_selfcheck: true,
      history: [],
    },
  },
];

export function presetByKey(key: string): PresetDef | undefined {
  return CHAT_PRESETS.find((p) => p.key === key);
}
