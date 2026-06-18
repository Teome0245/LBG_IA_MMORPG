# ADR 0006 — Refonte des niveaux admin LBG-MMO-Core3

**Statut** : accepté (décisions produit, 2026-05-20)  
**Contexte** : serveur privé Core3 (instance Clean, VM 245). Hiérarchie SWGEmu/Basilisk jugée trop large, god mode lié au compte admin, besoin d’une grille LBG lisible.

---

## Décisions actées

| Sujet | Choix |
|-------|--------|
| Nombre de niveaux | **5** (sans `helper`) — les rôles supérieurs couvrent le rôle helper |
| Ordre des privilèges (croissant) | **Player → GM → Moderator → Dev → Admin** |
| Admin vs Owner | **Fusion** : un seul sommet **Admin** (plus de rang Owner séparé) |
| Teome | Compte **Admin (4)** uniquement ; pas de second rang « owner » |
| God mode | **Manuel** pour les niveaux **≥ Admin (4)** ; persos **0 par défaut** ; jamais hérité du compte à la création |
| Jedi / spawn / économie lourde | Réservés au palier **Admin (4)** (pas Dev) |
| UI web comptes | Échelle **0–4** + texte d’aide par niveau |
| Rétrocompatibilité | **Double lecture** ancien ↔ nouveau pendant **2 semaines**, puis migration SQL **one-shot** |

---

## Grille officielle LBG (0–4)

| ID | Nom | Tag (proposé) | Compte (SQL / UI web) | Perso par défaut | God / staff en jeu |
|----|-----|---------------|------------------------|------------------|-------------------|
| **0** | `player` | — | Joueur standard | Aucun skill staff | Non |
| **1** | `gm` | `LBG-GM` | Joueur (pas gestion comptes UI) | Aucun ou GM minimal à l’activation | Non — pas de god auto |
| **2** | `moderator` | `LBG-Mod` | Lecture / modération comptes (UI selon politique) | Staff modération à l’activation | Non |
| **3** | `dev` | `LBG-Dev` | Comme mod + outils debug (hors prod sensible) | Debug / script / spawn avancé à l’activation | Non |
| **4** | `admin` | `LBG-Admin` | CRUD comptes UI, login serveur verrouillé | Tous pouvoirs LBG ; **god manuel** (`/staffmode` ou `/setGodMode`) | **Opt-in** uniquement |

**Ordre de privilège** : `0 < 1 < 2 < 3 < 4`.  
**Dev (3) < Admin (4)** — l’administrateur serveur est au-dessus du développeur (inverse de la hiérarchie SWGEmu classique).

### Répartition fonctionnelle (cible)

- **GM (1)** : animation, téléport terrain, revive léger, broadcast zone, spawn simple, lecture quêtes — tout ce qu’on aurait mis sur « helper ».
- **Moderator (2)** : + kick, ban perso, `getAccountInfo`, crédits limités, noms, modération chat.
- **Dev (3)** : + `script`, stats, ressources, spawn technique, logs — **sans** jedi / économie globale / config serveur critique.
- **Admin (4)** : + jedi, spawn management complet, économie (`credits`, `money`, etc.), `database`, météo, stats serveur, gestion comptes IG complète ; seul palier avec **god manuel** autorisé.

---

## Règles compte vs perso

1. `accounts.admin_level` = plafond **compte** (UI web, connexion si serveur plein/verrouillé, qui peut promouvoir qui).
2. `PlayerObject.adminLevel` = niveau **perso** ; par défaut **0** à la création (`inheritAccountAdminLevel = 0`, maintenu).
3. Un perso ne peut pas dépasser le niveau de son compte via `/setGodMode`.
4. **God** = ability `admin` active **et** opt-in explicite ; réservé aux persos dont le niveau effectif est **4** (phase 2 C++ : ne plus lier `hasGodMode()` à `adminLevel > 0` seul).
5. **Teome** : `admin_level = 4` en base ; jouer en `player` (0) sur les persos loisir ; activer staff/god uniquement pour modération.

---

## Mapping rétrocompat (2 semaines)

Pendant la période de double lecture, le code et/ou l’UI acceptent **ancien ID (0–15)** et **nouveau ID (0–4)** :

| Ancien `admin_level` | Nouveau | Rôle LBG |
|----------------------|---------|----------|
| 0 | 0 | player |
| 1 intern | 1 | gm |
| 2–3 qa/dev basilisk | 1 | gm |
| 6 tester (si présent) | 1 | gm |
| 7–8 cc, ct | 2 | moderator |
| 9–12 csi, eci, ec, csr | 2 | moderator |
| 13 qa | 3 | dev |
| 14 dev | 3 | dev |
| 15 admin | 4 | admin |

**Migration one-shot** (après 2 semaines) :

```sql
UPDATE accounts SET admin_level = CASE
  WHEN admin_level IN (0) THEN 0
  WHEN admin_level IN (1,2,3,6) THEN 1
  WHEN admin_level IN (7,8,9,10,11,12) THEN 2
  WHEN admin_level IN (13,14) THEN 3
  WHEN admin_level >= 15 THEN 4
  ELSE 0
END;
```

Les persos en jeu : migration optionnelle séparée ou reset via `/setGodMode … player` + réaffectation manuelle (à documenter en phase 1).

---

## Seuils moteur (cible phase 2–3)

Remplacer les seuils SWGEmu (`> 6`, `> 10`, `== 15`) par :

| Concept | Proposition LBG |
|---------|-----------------|
| `hasGodMode()` | `adminLevel == 4` **et** ability `admin` (opt-in) |
| `isPrivileged()` | `adminLevel >= 2` (moderator+) **et** staff actif si on généralise l’opt-in |
| `isStaff()` | `adminLevel >= 4` |
| `isAdmin()` | `adminLevel == 4` |
| Commandes C++ aujourd’hui `< 15` | Mapper sur `< 4` (admin) |
| Commandes jedi/spawn/économie lourde | Vérifier skill Admin (4), pas Dev (3) |

*(Affiner en implémentation : GM/mod peuvent avoir un « staff mode » sans god.)*

---

## UI web (`core3_account_admin`)

- Liste et formulaires : **0–4** uniquement.
- Aide repliable : rôle, tag, droits compte, droits perso, god manuel (oui/non).
- Libellés : Player, GM, Moderator, Dev, Admin.
- Teome affiché comme **Admin (4)**.

---

## Plan d’implémentation (rappel)

| Phase | Contenu | Priorité |
|-------|---------|----------|
| **0** | ADR + checklist commandes par niveau | Fait (ce document) |
| **1** | `staff/levels/lbg_*.lua`, skills `lbg_*`, double lecture, doc, UI 0–4 | **En cours** (2026-05-20 : Lua + SQL + UI déployés VM ; rebuild C++ si disque OK) |
| **2** | God opt-in niveau 4 ; `hasGodMode()` = niveau 4 + ability `admin` ; seuils commandes 15→4 | **En cours** (2026-05-20) |
| **3** | Rebuild **deux** binaires (`install_core3_dual_after_build.sh`) | **En cours** |
| **4** | Migration SQL one-shot ; retrait niveaux Basilisk | Après 2 semaines |

---

## Stratégie retenue (produit)

**C — Aligné** : grille LBG **0–4 sur les deux instances** (PreCu + Serveur Prime), un seul `admin_level` en SQL, même sémantique partout. Plus simple à l’usage.

| Instance | Scripts staff | Binaire |
|----------|---------------|---------|
| LBG SWGEMU PreCu (galaxy 2) | LBG 0–4 | `core3-swgemu` — rebuild avec `AdminLevelCompat` recommandé à terme |
| LBG MMO Serveur Prime (galaxy 3) | LBG 0–4 | `core3-clean` |

## Hors scope (pour l’instant)

- Comptes bots IA (`Bot_IA`) : rester **0** sauf besoin explicite.
- Phase 2 god (`hasGodMode` = opt-in niveau 4) : les deux binaires après rebuild.

---

## Références code actuel

- Niveaux SWGEmu : `Core3/MMOCoreORB/bin/scripts/staff/levels/`
- Création perso : `player_creation_manager.lua`, `PlayerCreationManager.cpp`
- God : `PlayerObject.idl` (`hasGodMode`, …)
- UI : `LBG_IA_MMO/tools/core3_account_admin/`
