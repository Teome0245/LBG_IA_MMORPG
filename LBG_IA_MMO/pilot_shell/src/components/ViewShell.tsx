import type { ReactNode } from "react";

type ViewShellProps = {
  title: string;
  description?: string;
  children: ReactNode;
  legacyHash?: string;
};

export function ViewShell({ title, description, children, legacyHash }: ViewShellProps) {
  return (
    <div className="view">
      <header className="view__header">
        <h2 className="view__title">{title}</h2>
        {description && <p className="view__desc">{description}</p>}
      </header>
      {children}
      {legacyHash && (
        <a className="view__legacy-btn view__legacy-link" href={`../${legacyHash}`}>
          Legacy — fonctions avancées
        </a>
      )}
    </div>
  );
}

type PanelProps = {
  title: string;
  subtitle?: string;
  children: ReactNode;
  actions?: ReactNode;
};

export function Panel({ title, subtitle, children, actions }: PanelProps) {
  return (
    <section className="panel">
      <header className="panel__header">
        <div>
          <h3 className="panel__title">{title}</h3>
          {subtitle && <p className="panel__subtitle">{subtitle}</p>}
        </div>
        {actions && <div className="panel__actions">{actions}</div>}
      </header>
      <div className="panel__body">{children}</div>
    </section>
  );
}

export function JsonPre({ data, maxHeight }: { data: unknown; maxHeight?: string }) {
  const text =
    data === undefined || data === null
      ? "—"
      : typeof data === "string"
        ? data
        : JSON.stringify(data, null, 2);
  return (
    <pre className="json-pre" style={maxHeight ? { maxHeight } : undefined}>
      {text}
    </pre>
  );
}

export function Hint({ children, error }: { children: ReactNode; error?: boolean }) {
  return <p className={`hint${error ? " hint--error" : ""}`}>{children}</p>;
}

export function FieldRow({ children }: { children: ReactNode }) {
  return <div className="field-row">{children}</div>;
}
