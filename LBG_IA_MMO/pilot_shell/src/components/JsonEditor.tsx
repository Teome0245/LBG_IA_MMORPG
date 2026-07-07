import { lazy, Suspense } from "react";

const Monaco = lazy(() => import("@monaco-editor/react"));

type JsonEditorProps = {
  value: string;
  onChange: (value: string) => void;
  height?: string;
  readOnly?: boolean;
};

export function JsonEditor({ value, onChange, height = "12rem", readOnly = false }: JsonEditorProps) {
  return (
    <Suspense fallback={<textarea className="field__input mono" rows={6} value={value} readOnly />}>
      <div className="json-editor" style={{ height }}>
        <Monaco
          height={height}
          defaultLanguage="json"
          theme="vs-dark"
          value={value}
          onChange={(v) => onChange(v ?? "")}
          options={{
            readOnly,
            minimap: { enabled: false },
            fontSize: 12,
            lineNumbers: "off",
            scrollBeyondLastLine: false,
            wordWrap: "on",
            automaticLayout: true,
            padding: { top: 8, bottom: 8 },
          }}
        />
      </div>
    </Suspense>
  );
}
