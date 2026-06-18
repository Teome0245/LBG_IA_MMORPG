# Temps jeu, triplons et cycle de vie PNJ (Serveur Prime)

**Objectif** : ne pas empiler des « clones » — chaque slot de service est un **personnage passif distinct** (nom, mobile, logement, persona LBG). Pour un poste 24h/24 couvert, prévoir des **triplons** (3 personnages), pas seulement des doublons.

## Échelle de temps (convention LBG)

| Réel | Jeu |
|------|-----|
| **24 h réelles** | **4 jours jeu** |
| **6 h réelles** | **1 jour jeu** (durée d’un « jour IG » côté planning) |
| **2 h réelles** | **~8 h jeu** (un « quart » de journée IG) |

Dérivé : en continu, **1 h réelle ≈ 4 h jeu** (si la journée IG = 24 h horloge).

## Cycle personnel (trois huit)

Sur **chaque jour jeu** (bloc de **6 h réelles**), un PNJ pilote vit **trois phases** d’environ **2 h réelles** chacune :

| Phase | Durée (réel) | Comportement attendu |
|-------|----------------|----------------------|
| **travail** | ~2 h | Fonction primaire (poste, comptoir, instructeur, quête…) |
| **repos** | ~2 h | Hors service → **logement** (`binding.home` / cell à définir) |
| **loisir** | ~2 h | Déambulation, cantina, patrouille locale (`roam_patrol`) |

Ce n’est **pas** trois PNJ visibles en même temps au même endroit : c’est le **rythme d’un seul personnage** sur la journée jeu.

## Triplons (couverture du poste)

Pour un métier qui doit rester disponible (auberge, instructeur, quête…) :

| Règle | Détail |
|-------|--------|
| **3 slots** | 3 `pilot_id` / 3 noms / 3 profils LBG légers (même `profile_id` métier possible) |
| **exactly_one** au poste | Un seul en phase **travail** au point de service |
| **Les deux autres** | En **repos** ou **loisir** (despawn ou hors zone / logement) |
| **Pas de clone** | Tenues, âge, ton, objectifs différents dans `npc_registry.json` |

Rotation type (à affiner en UTC ou en « temps jeu ») :

```text
Jour jeu N (6 h réel) :
  Perso A : travail 0–2h | repos 2–4h | loisir 4–6h
  Perso B : repos 0–2h   | travail 2–4h | loisir 4–6h  ← au poste milieu de journée
  Perso C : loisir 0–2h  | repos 2–4h | travail 4–6h
```

Les décalages garantissent qu’**un** triplon est en travail au bon créneau pour le joueur.

## Implémentation technique (progressive)

| Niveau | Fichiers | Statut |
|--------|----------|--------|
| **C.4** | Roster Bige/Lyra (2 slots, UTC simple) | Fait (à migrer vers ce modèle) |
| **C.4b** | `game_time` dans catalogue + `getLifecyclePhase()` Lua — **terminé** (`docs/core3_ia_phase_c4b_game_time.md`) | OK |
| **C.5** | Donneur de quête : triplon + `offer_quest` stub — **terminé** (`docs/core3_ia_phase_c5_quest_giver.md`) | OK |
| **C.4 inn** | Triplon auberge Mos Eisley | Après C.5 ou en parallèle si pas de nouveau spawn vanilla |

Champs catalogue proposés (`schema_version` 3 ou extension v2) :

```json
{
  "game_time": {
    "real_hours_per_game_day": 6,
    "game_days_per_real_day": 4,
    "phase_hours_real": { "work": 2, "rest": 2, "leisure": 2 }
  },
  "slots": [{
    "pilot_id": "npc:core3_inn_mara",
    "shift_offset": 0,
    "binding": {
      "post": { "x": 0, "y": 0, "z": 0 },
      "home": { "cell": 0, "x": 0, "y": 0, "z": 0 }
    }
  }]
}
```

## Référence actuelle (Bige / Lyra)

Roster **2 slots** + horaires UTC : solution intermédiaire (pas encore triplon ni cycle repos/loisir). Migration prévue vers **triplon entertainer** ou conservation en **duo** si le poste n’a pas besoin de 24h.

## Validation C.4 (smoke)

```bash
bash infra/scripts/smoke_core3_ia_phase_c4_entertainer_roster_lan.sh
```

IG (Lia) : selon **heure UTC** — ex. 11h → Bige poste, Lyra absente ; 18–22h → Lyra poste, Bige cantina.
