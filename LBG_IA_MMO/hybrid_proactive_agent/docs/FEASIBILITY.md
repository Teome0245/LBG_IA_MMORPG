# Faisabilité : un agent aux caractéristiques « proactif / curieux / autonome »

## Réponse courte

**Oui.** Les ingrédients que tu as listés (modes de comportement, objectifs internes, tension, curiosité, questions déclenchées, boucle quand l’utilisateur se tait) sont **exactement** ce qu’une architecture logicielle peut encoder **sans magie** : il s’agit d’un **contrôleur** qui maintient un état et choisit une action selon des règles ou des modèles.

## Ce que ce dépôt livre déjà

Le paquet `hybrid_proactive_agent` implémente :

- **Trois modes** : `proactif_leger`, `proactif_avance`, `autonome`, sélectionnés à partir de la tension, de la curiosité, du contexte et du silence.
- **Objectifs internes** avec progression et statut (`en_cours`, `bloque`, `termine`).
- **Actions typées** : question, suggestion, plan, relance autonome (`autonomous_nudge`).
- **Mémoire longue** simple (JSONL + rappel lexical) pour enrichir le contexte de décision.
- **Multi-rôles** : trois moteurs parallèles avec biais différents, agrégation par « force » de mode.

C’est une **base de motivation et d’initiative** : elle répond à « est-ce que l’agent *peut* vouloir agir ? » au sens **déclencher une intention interne** et une **sortie structurée**.

## Ce qui manque pour un agent « plénement fonctionnel » côté produit

Ce paquet ne remplace pas :

1. **La couche langagière riche** : les messages par défaut sont des modèles ; un LLM (ou des templates métier) donne la voix naturelle et contextuelle.
2. **L’exécution** : outils, MMO, desktop — tout reste **derrière** des appels que *tu* brancheras (orchestrateur, agents, WebSocket).
3. **La gouvernance** : fréquence max des relances, consentement utilisateur, traçabilité — indispensables pour ne pas « spammer ».

## Conclusion

Tu peux considérer ce module comme **le squelette comportemental** : il **rend possibles** les caractéristiques décrites. La **pleine fonctionnalité** = ce squelette + langage + politique d’envoi + greffon dans ton pipeline (voir `GREFFON.md`).
