# Mos Eisley — Cantina & théâtre (contenu IA LBG)

Référence rapide des POI IA dans le cantina Mos Eisley (Tatooine Prime).

**Handoff session** : [`world_editor_handoff_demain.md`](world_editor_handoff_demain.md)

---

## Cellules

| Cell | Emplacement | Contenu LBG |
|------|-------------|-------------|
| `1082877` | Salle principale / bar | Barmans, Lia (entrée bar) |
| `1105851` | Scène théâtre | Loisir entertainers (show) |
| `1105853` | Mezzanine | PNJ vanilla `theater_manager` — **ne pas** y envoyer les pilotes LBG loisir |

Corrections 2026-06-01 : l’ancien `ia_bridge` inversait `1082877` et `1105853`.

---

## Rosters actifs

| `roster_id` | Pilotes | Fichier location |
|-------------|---------|------------------|
| `roster:mos_eisley_cantina_barman` | Jax, Sira, Torrik | `locations/mos_eisley_cantina_bar.json` |
| `roster:mos_entertainer_trainer` | Bige, Lyra, Talen | `locations/mos_eisley_training_center.json` (poste ME) |

---

## Coordonnées bar (barmans)

```json
{
  "x": 7.26,
  "y": 1.15,
  "z": -0.89,
  "heading": 30.2,
  "cell": 1082877
}
```

`y = 1.15` : côté client du comptoir (conversation ~3 m impossible si `y = 2.8` derrière le bar).

### Lia (joueur IA) — face client

Même cellule, mais **pas** le poste barman : Lia est un joueur, pas un PNJ derrière le comptoir.

| Champ | Valeur |
|-------|--------|
| x / y / z | `7.26` / `0.35` / `0.91` |
| cell | `1082877` |

Constantes Lua : `IA_BRIDGE_CANTINA_LIA_GUEST_*` (`housing_enter`, `contain_cantina` si encore sur le poste bar).

---

## Coordonnées scène (entertainers — loisir)

```json
{
  "x": 0.34,
  "y": 51.19,
  "z": 2.13,
  "heading": 173.9,
  "cell": 1105851
}
```

Dump validé IG (Teome, 2026-06-01).

---

## Économie / quêtes bar

- Shop : `shop:mos_cantina_bar` (`core3_economy.json`)
- Craft : `craft:mos_bar_drink`
- Quêtes stub : `quest:mos_gather_bar_fruit`, `quest:mos_gather_bar_spice`

**À faire** : `vendor_sell`, UI bartender complète.

---

## Constantes Lua

`ia_bridge_screenplay.lua` :

- `IA_BRIDGE_CANTINA_BAR_*` → bar `1082877` (barmans)
- `IA_BRIDGE_CANTINA_LIA_GUEST_*` → Lia côté salle
- `IA_BRIDGE_THEATER_*` → scène `1105851`
