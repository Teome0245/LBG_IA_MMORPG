import { useEffect, useRef } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import type { PilotSettings } from "../api/pilotApi";
import { postRoute } from "../api/pilotApi";
import { useLogs } from "../stores/logsContext";

type XtermPanelProps = {
  settings: PilotSettings;
};

const HELP = `Terminal pilot_shell — commandes :
  help          — cette aide
  clear         — effacer l'écran
  route <texte> — POST /v1/pilot/route
  logs          — basculer vers l'onglet Logs (palette)

Presets : core 140 · front 110 · core3 246 · desktop vghd
`;

export function XtermPanel({ settings }: XtermPanelProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const termRef = useRef<Terminal | null>(null);
  const { append } = useLogs();

  useEffect(() => {
    if (!containerRef.current) return;

    const term = new Terminal({
      cursorBlink: true,
      fontSize: 12,
      fontFamily: "JetBrains Mono, ui-monospace, monospace",
      theme: {
        background: "#0d1117",
        foreground: "#e6edf3",
        cursor: "#2dd4bf",
      },
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(containerRef.current);
    fit.fit();
    termRef.current = term;

    let line = "";
    term.writeln("LBG Pilot Shell — terminal intégré");
    term.writeln(HELP);
    term.write("$ ");

    const runRoute = async (text: string) => {
      term.writeln("");
      term.writeln(`→ route: ${text}`);
      append("terminal", `route: ${text}`);
      try {
        const { status, body } = await postRoute(settings, text);
        const out = JSON.stringify(body, null, 2).slice(0, 4000);
        term.writeln(`HTTP ${status}`);
        term.writeln(out);
        append("terminal", `HTTP ${status}`);
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        term.writeln(`Erreur: ${msg}`);
        append("terminal", msg);
      }
      term.write("$ ");
    };

    term.onData((data) => {
      if (data === "\r") {
        const cmd = line.trim();
        line = "";
        if (!cmd) {
          term.write("$ ");
          return;
        }
        if (cmd === "help") {
          term.writeln("");
          term.writeln(HELP);
          term.write("$ ");
          return;
        }
        if (cmd === "clear") {
          term.clear();
          term.write("$ ");
          return;
        }
        if (cmd.startsWith("route ")) {
          void runRoute(cmd.slice(6));
          return;
        }
        const presets: Record<string, string> = {
          "core 140": "diagnostic sur le core 140",
          "front 110": "healthz front 110",
          "core3 246": "sonde mmo core3 sur la 246",
          "desktop vghd": "lance vghd sur mon pc",
        };
        const preset = presets[cmd.toLowerCase()];
        if (preset) {
          void runRoute(preset);
          return;
        }
        void runRoute(cmd);
        return;
      }
      if (data === "\u007f") {
        if (line.length > 0) {
          line = line.slice(0, -1);
          term.write("\b \b");
        }
        return;
      }
      line += data;
      term.write(data);
    });

    const onResize = () => fit.fit();
    window.addEventListener("resize", onResize);

    return () => {
      window.removeEventListener("resize", onResize);
      term.dispose();
      termRef.current = null;
    };
  }, [append, settings]);

  return <div className="xterm-panel" ref={containerRef} />;
}
