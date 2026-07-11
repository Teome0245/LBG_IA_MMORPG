# Jalon Infographiste IA — intégration équipe virtuelle

**Date** : 2026-07-11  
**Statut** : **en cours** (pipeline GLB, pas de blocage produit)  
**Persona équipe** : **Pygmalion** (`dev_game` + sous-projet `infographiste_ia`)

---

## Rôle dans la réunification

| Élément | Détail |
|---------|--------|
| Sous-projet | `infographiste_ia` — registre `/v1/team/meta` |
| Owner technique | `dev_game` (Dédale) |
| Affichage Pilot | **Pygmalion (infographiste_ia)** sur les tâches dédiées |
| Lié | `client_godot`, `docs/pipeline_assets_swg_godot.md` |

L'Infographiste n'est pas un rôle API séparé : c'est une **piste dev_game** avec persona et sonde dédiée, comme Godot/lbg-ws/2.

---

## Ce que fait la Team

### Sonde L1 (`infographiste_probe`)
- Lit `lbg_client_godot/assets/avatars/manifest.json` (+ world si présent)
- Compte les `.glb` attendus vs présents sur disque
- Vérifie `docs/pipeline_assets_swg_godot.md`
- **OK structurel** même si 0 GLB (phase en cours)

### Workflow (`infographiste_workflow`)
- Brief PM focalisé sous-projet
- `action_proposal` forge (pipeline assets / export Blender)
- Résultat : `kind: infographiste_workflow`

### Superviseur Godot
- Piste `infographiste_assets` incluse en mode `full` (timer 6h)

### Timer dédié
- `lbg-team-infographiste-job` — **12 h**, actor `system:team_infographiste`

---

## Usage Pilot `#/team`

1. Raccourci **Infographiste IA** → **Lancer**
2. Ou plan NL : *« audit pipeline assets glb infographiste »*
3. Filtre liste : `actor: system:team_infographiste`

---

## Variables

```bash
LBG_TEAM_INFOGRAPHISTE_JOB_ENABLED=1
LBG_TEAM_INFOGRAPHISTE_JOB_ACTOR_ID=system:team_infographiste
LBG_INFOGRAPHISTE_GODOT_ROOT=/opt/LBG_IA_MMO/lbg_client_godot  # optionnel
```

Install timer :
```bash
bash infra/scripts/install_team_infographiste_job_vm.sh
```

---

## Prochaines étapes (humain / forge)

1. Premier export `human_male_base.glb` (Blender) — voir pipeline doc §4
2. Valider import Godot (remplace `PlaceholderHumanoid.tscn`)
3. Cantina bloc GLB (pilier B `plan_client_godot_prime_rendu.md`)

---

## Références

- [`pipeline_assets_swg_godot.md`](pipeline_assets_swg_godot.md)
- [`equipe_autonome_godot.md`](equipe_autonome_godot.md)
- [`runbook_promotion_prototype_core3.md`](runbook_promotion_prototype_core3.md)
