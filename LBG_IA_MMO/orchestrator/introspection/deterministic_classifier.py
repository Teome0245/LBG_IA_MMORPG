import re


class DeterministicIntentClassifier:
    """
    Classifieur déterministe (baseline) destiné à être remplacé/augmenté par des modèles.
    """

    def classify(self, text: str) -> tuple[str, float]:
        t = text.strip().lower()
        if not t:
            return ("unknown", 0.0)

        if re.search(
            r"\b(chef de projet|product owner|état d'avancement|statut du projet|point d'avancement|"
            r"plan de route|roadmap|vision produit)\b",
            t,
        ):
            return ("project_pm", 0.78)
        if re.search(
            r"\b(jalon|milestone)\b.*\b(projet|produit|mmo|release)\b|"
            r"\b(projet|produit|mmo)\b.*\b(jalon|milestone)\b",
            t,
        ):
            return ("project_pm", 0.74)
        if re.search(r"\b(opengame|prototype\s+jeu|prototype\s+game|mini-jeu|mini\s+jeu)\b", t):
            return ("prototype_game", 0.7)
        if re.search(r"\b(quest|quête|mission|tâche|tache|travail|travaux)\b", t):
            return ("quest_request", 0.75)
        if re.search(r"\b(parler|dialogue|discuter)\b", t):
            return ("npc_dialogue", 0.7)
        if re.search(r"\b(combat|attaquer|taper)\b", t):
            return ("combat_action", 0.7)
        if re.search(r"\b(devops|sonde\s+devops|probe\s+devops|healthz\s+(backend|orchestrator))\b", t):
            return ("devops_probe", 0.72)
        return ("unknown", 0.4)

