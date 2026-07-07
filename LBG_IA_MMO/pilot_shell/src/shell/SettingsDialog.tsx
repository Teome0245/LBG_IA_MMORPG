import { useSettings } from "../stores/context";

export function SettingsDialog() {
  const { settings, updateSettings, settingsOpen, setSettingsOpen } = useSettings();

  if (!settingsOpen) return null;

  return (
    <div className="palette-overlay" role="presentation" onClick={() => setSettingsOpen(false)}>
      <div
        className="settings-dialog"
        role="dialog"
        aria-label="Réglages"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="settings-dialog__header">
          <h2>Réglages</h2>
          <button type="button" className="btn btn--ghost btn--sm" onClick={() => setSettingsOpen(false)}>
            Fermer
          </button>
        </header>

        <div className="settings-dialog__body">
          <label className="field">
            <span className="field__label">Service token (X-LBG-Service-Token)</span>
            <input
              className="field__input"
              type="password"
              value={settings.serviceToken}
              onChange={(e) => updateSettings({ serviceToken: e.target.value })}
              placeholder="lbg_pilot_service_token_v1"
              autoComplete="off"
            />
          </label>

          <label className="field">
            <span className="field__label">Bearer token (optionnel)</span>
            <input
              className="field__input"
              type="password"
              value={settings.token}
              onChange={(e) => updateSettings({ token: e.target.value })}
              autoComplete="off"
            />
          </label>

          <label className="field">
            <span className="field__label">Jeton approbation DevOps / desktop</span>
            <input
              className="field__input"
              type="text"
              value={settings.approval}
              onChange={(e) => updateSettings({ approval: e.target.value })}
              autoComplete="off"
            />
          </label>

          <label className="field">
            <span className="field__label">URL backend (vide = proxy WSL → 140)</span>
            <input
              className="field__input"
              type="url"
              value={settings.apiBase}
              onChange={(e) => updateSettings({ apiBase: e.target.value })}
              placeholder="vide ou http://192.168.0.140:8000"
            />
          </label>

          <label className="field field--row">
            <input
              type="checkbox"
              checked={settings.dryRun}
              onChange={(e) => updateSettings({ dryRun: e.target.checked })}
            />
            <span>Dry-run DevOps / desktop par défaut</span>
          </label>

          <label className="field field--row">
            <input
              type="checkbox"
              checked={settings.agenticChat}
              onChange={(e) => updateSettings({ agenticChat: e.target.checked })}
            />
            <span>Mode agentique (prefer_agentic)</span>
          </label>

          <label className="field">
            <span className="field__label">Bearer métriques Prometheus</span>
            <input
              className="field__input"
              type="password"
              value={settings.metricsBearer}
              onChange={(e) => updateSettings({ metricsBearer: e.target.value })}
              autoComplete="off"
            />
          </label>
        </div>

        <footer className="settings-dialog__footer">
          <p className="settings-dialog__hint">
            Prod LAN : UI sur <strong>110:8080</strong>, API sur <strong>140:8000</strong>.
            En WSL test (<code>npm run dev</code>), laisser l’URL backend vide — le proxy Vite
            joint la prod (voir <code>.env.development</code>).
          </p>
        </footer>
      </div>
    </div>
  );
}
