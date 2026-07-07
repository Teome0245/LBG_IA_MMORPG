# ADR 0012 — Décommission `mmmorpg_server` WebSocket `:7733`

## Statut

Accepté — 2026-07-06

## Contexte

Le bac à sable Python `mmmorpg_server` (WebSocket `mmmorpg-ws/1`, port **7733**, HTTP interne **8773**) est **gelé** depuis juin 2026 ([`ARCHIVED_mmmorpg_sandbox.md`](../ARCHIVED_mmmorpg_sandbox.md)). L’autorité jeu est **Core3 Prime (VM 246)** ; le pont IA passe par Lua/JSON et le sidecar `:8791`.

Le service restait encore installé par défaut sur le rôle `mmo` (VM 245) et référencé dans le pilot legacy (test WS).

## Décision

1. **`mmmorpg_server :7733` est décommissionné** pour l’exploitation LAN/prod — ne plus démarrer ni documenter comme chemin actif.
2. Le **code** reste dans le dépôt (`mmmorpg_server/`) en **lecture seule** : tests CI, référence contrats pont, pas de suppression immédiate.
3. **Déploiement** : `lbg-mmmorpg-ws` uniquement si `LBG_DEPLOY_MMMORPG_WS=1` (opt-in explicite).
4. **Référence opérateur** : Core3 Prime VM **246** ; pilot v2 et docs ne pointent plus vers `:7733`.
5. **Redémarrage legacy** : procédure d’exception documentée dans `ARCHIVED_mmmorpg_sandbox.md` § *Réactivation exceptionnelle*.

## Conséquences

- `deploy_vm.sh` (rôle `mmo`) : plus de `enable --now lbg-mmmorpg-ws` par défaut.
- `install_local_mmo.sh` : skip `mmmorpg_server` sauf `LBG_DEPLOY_MMMORPG_WS=1`.
- `smoke_vm_lan.sh` : `lbg-mmmorpg-ws` retiré des services MMO par défaut.
- `lbg.env.example` : bloc `MMMORPG_*` marqué décommissionné.
- Smokes `smoke_mmmorpg_*` / `smoke_ws_*` : conservés pour réactivation opt-in, non requis au runbook LAN standard.

## Alternatives rejetées

| Option | Raison |
|--------|--------|
| Supprimer le dossier `mmmorpg_server/` | Perte tests/contrats ; réactivation debug plus coûteuse |
| Laisser le service actif sur 245 | Confusion ops, double autorité monde |

## Liens

- Gel initial : ADR 0005 amendé, `ARCHIVED_mmmorpg_sandbox.md`
- Remplacement : `core3_prime_runbook.md`, pont `ia_bridge_screenplay.lua`
