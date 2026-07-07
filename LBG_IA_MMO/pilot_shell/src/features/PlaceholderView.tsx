import type { ReactNode } from "react";

type PlaceholderViewProps = {
  title: string;
  description: string;
  phase: string;
  legacyHash: string;
  children?: ReactNode;
};

export function PlaceholderView({
  title,
  description,
  phase,
  legacyHash,
  children,
}: PlaceholderViewProps) {
  return (
    <div className="view">
      <header className="view__header">
        <h2 className="view__title">{title}</h2>
        <p className="view__desc">{description}</p>
      </header>
      <div className="view__card">
        <span className="view__badge">{phase}</span>
        {children ?? (
          <p>
            Cette vue sera migrée depuis le pilot legacy. En attendant, utilisez le lien ci-dessous
            pour accéder aux fonctionnalités complètes.
          </p>
        )}
        <a className="view__legacy-btn" href={`../${legacyHash}`}>
          Ouvrir {title} (legacy)
        </a>
      </div>
    </div>
  );
}
