# Création de personnage — limite « 1 / heure » (lab LBG)

## Pourquoi SWGEmu fait ça

Sur les **serveurs publics**, Core3 limite les comptes non-staff à **une création de personnage par heure et par galaxie** (y compris après une suppression, via la table `deleted_characters`). C’est un **anti-spam** contre les créations/suppressions en boucle.

Ce n’est **pas** une règle MMO gameplay : c’est une protection **opérationnelle** héritée du projet SWGEmu.

## Politique LBG (VM lab 245)

| Instance | `CharacterCreateCooldownMs` | Fichier |
|----------|----------------------------|---------|
| **Serveur Prime** (`core3-clean`) | **0** (désactivé) | `config-local.lua` |
| **PreCu** (`core3-swgemu`) | **0** recommandé en lab | idem si besoin |

Clé : `Core3.PlayerCreationManager.CharacterCreateCooldownMs`

- `0` = pas de limite (lab, tests Bot_IA, persos jetables)
- `3600000` = 1 heure (comportement SWGEmu d’origine)

Les comptes **Admin (4)** ignorent toujours la limite.

## Déploiement

```bash
bash LBG_IA_MMO/infra/scripts/apply_core3_lab_char_create_vm.sh
# puis rebuild + install core3 (clean et/ou stock)
```

SQL déblocage immédiat (sans rebuild) : `infra/snippets/core3-clear-char-create-cooldown.sql`

## Code

`server-core3/.../PlayerCreationManager.cpp` — lecture de `CharacterCreateCooldownMs`.
