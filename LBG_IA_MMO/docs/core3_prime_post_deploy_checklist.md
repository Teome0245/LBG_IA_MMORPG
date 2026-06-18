# Checklist — après déploiement / build Prime

À exécuter quand la tâche de déploiement ou build VM est terminée (ex. agent `c037b15a-…`).

## 1. Vérifier le serveur

```bash
ssh lbg@192.168.0.245 'pgrep -a core3-clean; tail -n 30 /tmp/core3-clean.log'
```

Attendu : processus `core3-clean` actif, pas de `FATAL` récent.

## 2. Vérifier les fichiers déployés

```bash
ssh lbg@192.168.0.245 'ls -la /opt/LBG_IA_MMO/content/core3/*.json; ls -la /opt/lbg-new-mmo-clean/MMOCoreORB/bin/scripts/custom_scripts/screenplays/ia_bridge_screenplay.lua'
```

## 3. Smoke consolidé

```bash
cd LBG_IA_MMO
bash infra/scripts/smoke_core3_prime_world_lan.sh --with-think --demo-pending
```

## 4. Preuves in-game / fichiers

Sur la VM :

```bash
tail -n 20 /opt/lbg-new-mmo-clean/MMOCoreORB/bin/ia_bridge/quest_state.jsonl
tail -n 5 /opt/lbg-new-mmo-clean/MMOCoreORB/bin/ia_bridge/world_events.jsonl   # si rebuild C++ OK
```

## 5. Documentation à jour

- [ ] [`content/core3/README.md`](../content/core3/README.md) — index catalogues
- [ ] [`docs/core3_prime_runbook.md`](core3_prime_runbook.md) — opérations
- [ ] [`docs/plan_de_route.md`](plan_de_route.md) — ligne Historique

## 6. Commit suggéré (quand tu le demandes)

Séparer si possible :

1. `content/core3` + screenplay Lua + scripts smoke/demo
2. `new_mmo` — DirectorManager GameTime/EventBus (C++)
