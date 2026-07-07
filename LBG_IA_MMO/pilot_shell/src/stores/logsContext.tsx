import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

export type LogLine = {
  id: string;
  ts: number;
  source: string;
  text: string;
};

type LogsContextValue = {
  lines: LogLine[];
  append: (source: string, text: string) => void;
  clear: () => void;
};

const LogsContext = createContext<LogsContextValue | null>(null);

let logSeq = 0;

export function LogsProvider({ children }: { children: ReactNode }) {
  const [lines, setLines] = useState<LogLine[]>([]);

  const append = useCallback((source: string, text: string) => {
    const entry: LogLine = {
      id: `${Date.now()}-${++logSeq}`,
      ts: Date.now(),
      source,
      text,
    };
    setLines((prev) => [...prev.slice(-499), entry]);
  }, []);

  const clear = useCallback(() => setLines([]), []);

  const value = useMemo(() => ({ lines, append, clear }), [append, clear, lines]);

  return <LogsContext.Provider value={value}>{children}</LogsContext.Provider>;
}

export function useLogs(): LogsContextValue {
  const ctx = useContext(LogsContext);
  if (!ctx) throw new Error("useLogs hors LogsProvider");
  return ctx;
}
