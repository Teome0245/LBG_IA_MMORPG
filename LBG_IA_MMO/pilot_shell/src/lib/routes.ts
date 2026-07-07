export type ViewId =
  | "home"
  | "ops"
  | "mmo"
  | "jobs"
  | "pm"
  | "lyra"
  | "desktop"
  | "health"
  | "companion";

export type ViewDef = {
  id: ViewId;
  path: string;
  label: string;
  icon: string;
  description: string;
  legacyHash?: string;
};

export const VIEWS: ViewDef[] = [
  {
    id: "home",
    path: "/",
    label: "Accueil",
    icon: "⌂",
    description: "Chat orchestrateur et vue d'ensemble",
    legacyHash: "#/",
  },
  {
    id: "ops",
    path: "/ops",
    label: "Ops",
    icon: "◎",
    description: "Assistant Core — infra et propositions",
    legacyHash: "#/ops",
  },
  {
    id: "mmo",
    path: "/mmo",
    label: "MMO",
    icon: "🎮",
    description: "Debug Core3 Prime (VM 246) — PNJ, quêtes, pont",
    legacyHash: "#/ops/mmo",
  },
  {
    id: "jobs",
    path: "/jobs",
    label: "Jobs",
    icon: "⚡",
    description: "Jobs autonomes type Cowork",
    legacyHash: "#/jobs",
  },
  {
    id: "pm",
    path: "/pm",
    label: "PM",
    icon: "📋",
    description: "Chef de projet — jalons et tâches",
    legacyHash: "#/pm",
  },
  {
    id: "lyra",
    path: "/lyra",
    label: "Lyra",
    icon: "✦",
    description: "Jauges Lyra et régulation",
    legacyHash: "#/lyra",
  },
  {
    id: "desktop",
    path: "/desktop",
    label: "Desktop",
    icon: "🖥",
    description: "Actions poste hybride Windows/Linux",
    legacyHash: "#/desktop",
  },
  {
    id: "health",
    path: "/health",
    label: "Santé",
    icon: "♥",
    description: "Métriques, benchmark, Brain",
    legacyHash: "#/health",
  },
  {
    id: "companion",
    path: "/companion",
    label: "Companion",
    icon: "💬",
    description: "Chat autonome companion_bot",
    legacyHash: "",
  },
];

export function viewByPath(path: string): ViewDef | undefined {
  return VIEWS.find((v) => v.path === path);
}

export function viewById(id: ViewId): ViewDef {
  return VIEWS.find((v) => v.id === id) ?? VIEWS[0];
}
