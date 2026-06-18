# UI web — Companion Bot (Phase 2)

UI Vite/React minimaliste pour discuter avec le microservice `companion_bot` via :

- `POST /v1/chat`
- `GET /v1/session/{id}/events` (poll)
- `POST /v1/session/{id}/tick`

## Démarrer (dev LAN, port 5174)

```bash
cd LBG_IA_MMO/companion_bot/web
npm install
VITE_COMPANION_BASE_URL="http://192.168.0.140:8065" npm run dev
```

Ensuite ouvrir `http://<IP>:5174/`.

### Debug

Ajouter `?debug=1` à l’URL pour afficher un panneau debug (sinon invisible).

## CORS côté microservice

Sur la VM du microservice, autoriser l’origine Vite :

- `LBG_COMPANION_CORS_ORIGINS="http://192.168.0.110:5174"`

## Déploiement “comme le reste du projet” (Nginx front)

On sert l’UI sous `http://192.168.0.110:8080/compagnon/` (ou `:80` selon la conf Nginx).
L’API est exposée en same-origin via `http://192.168.0.110:8080/companion-api/` (proxy Nginx vers le microservice).

```bash
cd LBG_IA_MMO
bash infra/scripts/deploy_companion_web.sh
```

Le script build avec `--base=/compagnon/` et copie dans `pilot_web/compagnon/` (local + VM 110), puis restart Nginx.

