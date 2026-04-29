# Spécification Lyra unifiée (fusion — phase B)

Document de **cible** pour aligner **LBG_IA** (`LyraEngineV2`, routes `/lyra/...`) et **LBG_IA_MMO** (`context.lyra` / `output.lyra`, jauges PNJ `mmo_server`). Complète **`lyra.md`** (contrat déjà implémenté côté monorepo) sans le remplacer : les règles **code** restent dans `lyra.md` jusqu’à refactor.

**Références** : ADR **`adr/0002-mmo-autorite-pont.md`**, **`plan_fusion_lbg_ia.md`** §3.2.

---

## 1. Deux rôles : assistant vs PNJ monde

| Rôle | Origine historique | Usage cible |
|------|-------------------|-------------|
| **Assistant / co‑pilote** | **LBG_IA** — jauges riches (énergie, chaleur, patience, confiance, profils…) | UI `/lyra`, conversation globale, pas lié à une entité jeu réseau. |
| **PNJ monde** | **LBG_IA_MMO** — `lyra_engine.gauges` (**faim**, **soif**, **fatigue** 0–1) + sync **`mmo_world`** | Dialogue PNJ, orchestrateur, agents ; lien **`world_npc_id`** / **`npc_id`**. |

**Décision de conception** : un seul objet **`context.lyra`** / **`output.lyra`** avec **discrimination explicite** pour éviter de mélanger les échelles dans un même paquet sans le savoir.

---

## 2. Enveloppe JSON recommandée (évolutive)

```json
{
  "version": "lyra-context-2",
  "kind": "npc_world | assistant",
  "gauges": {},
  "meta": {}
}
```

- **`kind`**  
  - **`npc_world`** : jauges **0–1** — clés **`hunger`**, **`thirst`**, **`fatigue`** (et extensions documentées). Aligné sur **`lyra.md`** et `GET /v1/world/lyra`.  
  - **`assistant`** : jauges **LBG_IA** — noms et plages **tels que** `LyraEngineV2` / API `/lyra` (souvent **0–100** ou entiers ; à figer lors du portage dans le monorepo).

- **`meta`** : déjà utilisé (`source`, `world_now_s`, `npc_id`, `npc_name`, `skip_mmo_sync`, …). Pour **`assistant`**, **`meta.source`** peut valoir `lbg_ia` ou `assistant_ui`.

Les composants qui ne comprennent qu’un profil **doivent ignorer** l’autre **`kind`** ou refuser avec log clair (pas de fusion silencieuse de jauges incompatibles).

---

## 3. Normalisation des plages (affichage / prompts)

| Domaine | Stockage recommandé | Affichage LLM (ex.) |
|---------|---------------------|---------------------|
| PNJ (`npc_world`) | **0–1** flottant | Pourcentages **0–100** dans le prompt (déjà fait dans `dialogue_llm.build_system_prompt`) |
| Assistant (`assistant`) | Selon **LBG_IA** (souvent **0–100**) | Reprendre les libellés métier LBG_IA après portage |

**Règle** : toute **conversion** 0–1 ↔ 0–100 se fait dans une **couche unique** (helper partagé) pour éviter les doubles conversions dans les agents.

---

## 4. Priorité de fusion `context.lyra` (ordre logique)

1. **`meta.source` = `mmo_world`** : instantané **`mmo_server`** — **ne pas** réappliquer `lyra_engine.step` côté agents (voir `lyra.md`).
2. **Override manuel / tests** : **`meta.skip_mmo_sync`** ou champs équivalents.
3. **Assistant seul** : pas d’appel **`LBG_MMO_SERVER_URL`** pour ce tour.

---

## 5. Travail d’implémentation ultérieur

- Schéma **Pydantic** unique `LyraContextV2` avec validation par **`kind`**.
- Portage **LBG_IA** : mapper les routes `/lyra` vers l’enveloppe **`kind: assistant`** dans le monorepo.
- Tests de non‑régression sur **`/pilot/`** et scénarios PNJ + assistant.

---

## 6. Propositions “dédoublonnage jauges” (recommandation actuelle)

Objectif : éviter deux “énergies”, deux “stress”, etc. en clarifiant ce qui est **stocké** vs **dérivé** et en gardant une
lecture simple côté UI et côté agents.

### 6.1 Décisions validées (pour le moment)

- **`energie`** : **jauge dérivée** (pas stockée) qui reflète la **moyenne** de `hunger/thirst/fatigue`.
- **`confiance`** : **canonique** (on garde le nom “positif”).
- **`stress`** : **alias de vue** (optionnel en UI), pas un second stockage.

### 6.2 Formules proposées

Pour `kind: npc_world` (0–1) :

- \(needs\_mean = mean(hunger, thirst, fatigue)\) (chaque jauge clamp 0–1)
- \(energie\_{0..100} = round(100 \\times (1 - needs\\_mean))\)
- Alias UI possible : \(stress\_{0..100} = 100 - confiance\_{0..100}\)

> Note : si tu veux “stress” en 0–1 au lieu de 0–100 en UI, utiliser \(stress\_{0..1} = 1 - confiance\_{0..1}\) après conversion.

### 6.3 Recharge par consommation — options

**Option A (recommandée)** — “consommer” agit sur les besoins :
- `eat` : diminue `hunger` (et un peu `fatigue`)
- `drink` : diminue `thirst`
- `rest` : diminue `fatigue` (avec éventuellement une légère hausse `hunger/thirst` pour éviter un repos “gratuit”)

L’**énergie remonte mécaniquement** via la formule dérivée (pas de jauge énergie stockée à synchroniser).

**Option B** — conversion inspirée `LyraEngineV2` :
- si `energie` (dérivée) < 30 : convertir une petite portion du besoin dominant en gain d’énergie “virtuel” (au final, se traduit par une baisse plus forte du besoin).

**Option C** — bonus “mental” :
- consommation réussie → `confiance += Δ` (clamp) ; contrainte/échec → `confiance -= Δ`

### 6.4 À arbitrer lors du passage “spec → code”

- Où vit `confiance` : `kind: assistant` uniquement, ou aussi `npc_world` (si on veut un mental PNJ) ?
- Échelles : conserver `npc_world` en 0–1 strict, et `assistant` en 0–100 (et conversions centralisées).
- Noms finaux côté UI : afficher “stress” comme vue dérivée de “confiance” (ou pas).

## Voir aussi

- `lyra.md` — contrat actuel monorepo + boucle `mmo_world`
- `fusion_pont_jeu_ia.md` — pont jeu ↔ état exposé aux agents
