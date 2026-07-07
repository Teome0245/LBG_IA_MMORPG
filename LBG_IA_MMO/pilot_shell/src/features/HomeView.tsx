export function HomeView() {
  return (
    <div className="view">
      <header className="view__header">
        <h2 className="view__title">Accueil</h2>
        <p className="view__desc">
          Interface opérateur <strong>pilot_shell</strong> — layout type IDE Cursor.
          Chat orchestrateur dans le panneau <strong>Agent</strong> ; client MMO et companion dans la barre d&apos;activité.
        </p>
      </header>
      <div className="view__card">
        <span className="view__badge">Phases 4–6</span>
        <ul className="view__list">
          <li>
            <kbd>Ctrl+L</kbd> — panneau Agent (Monaco JSON, presets)
          </li>
          <li>
            <kbd>Ctrl+J</kbd> — terminal xterm, logs SSE jobs, métriques
          </li>
          <li>MMO → onglet <strong>Client jeu</strong> (iframe <code>/mmo/</code>)</li>
          <li>Companion → chat autonome (<code>/companion-api</code>)</li>
          <li>Monde : Core3 Prime VM 246</li>
        </ul>
      </div>
    </div>
  );
}
