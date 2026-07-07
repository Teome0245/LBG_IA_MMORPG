import { useCallback, useEffect, useRef, useState } from "react";
import { fetchBrainStatus } from "../../api/pilotClient";
import { postRoute } from "../../api/pilotApi";
import { Hint, JsonPre, Panel, ViewShell } from "../../components/ViewShell";
import { formatRouteResponse } from "../../lib/routeFormat";
import { useSettings } from "../../stores/context";

type LyraMode = "world" | "assistant";

const WORLD_GAUGES = ["hunger", "thirst", "fatigue"] as const;
const ASSISTANT_GAUGES = ["motivation", "focus", "patience"] as const;

function defaultGauges(mode: LyraMode): Record<string, number> {
  if (mode === "world") return { hunger: 0.3, thirst: 0.2, fatigue: 0.25 };
  return { motivation: 50, focus: 60, patience: 55 };
}

export function LyraView() {
  const { settings } = useSettings();
  const [mode, setMode] = useState<LyraMode>("world");
  const [dtS, setDtS] = useState(60);
  const [gauges, setGauges] = useState(defaultGauges("world"));
  const [output, setOutput] = useState<Record<string, unknown> | null>(null);
  const [brain, setBrain] = useState<Record<string, unknown> | null>(null);
  const [hint, setHint] = useState("");
  const [auto, setAuto] = useState(false);
  const autoRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    setGauges(defaultGauges(mode));
  }, [mode]);

  const step = useCallback(async () => {
    setHint("Step…");
    const { status, body } = await postRoute(settings, "Lyra step", {
      lyra: { gauges, dt_s: dtS, version: "0.1" },
      history: [],
    });
    const d = formatRouteResponse(body);
    setHint(`${d.metaLine} (HTTP ${status})`);
    const result = body.result as Record<string, unknown> | undefined;
    const out = result?.output as Record<string, unknown> | undefined;
    if (out?.lyra) setOutput(out.lyra as Record<string, unknown>);
    else setOutput(body);
  }, [dtS, gauges, settings]);

  useEffect(() => {
    if (autoRef.current) clearInterval(autoRef.current);
    if (auto) {
      autoRef.current = setInterval(() => void step(), 5000);
    }
    return () => {
      if (autoRef.current) clearInterval(autoRef.current);
    };
  }, [auto, step]);

  const refreshBrain = async () => {
    const r = await fetchBrainStatus(settings);
    setBrain(r.body);
  };

  useEffect(() => {
    void refreshBrain();
  }, [settings]);

  const gaugeKeys = mode === "world" ? WORLD_GAUGES : ASSISTANT_GAUGES;
  const max = mode === "world" ? 1 : 100;

  return (
    <ViewShell title="Lyra" description="Simulation jauges hors MMO — POST /v1/pilot/route." legacyHash="#/lyra">
      <div className="view-grid view-grid--2col">
        <Panel title="Entrée (context.lyra)">
          <div className="btn-row">
            <label className="field field--row">
              <input type="radio" checked={mode === "world"} onChange={() => setMode("world")} />
              PNJ monde (0–1)
            </label>
            <label className="field field--row">
              <input type="radio" checked={mode === "assistant"} onChange={() => setMode("assistant")} />
              Assistant (0–100)
            </label>
          </div>
          <label className="field">
            <span className="field__label">dt_s</span>
            <input className="field__input field__input--narrow" type="number" value={dtS} onChange={(e) => setDtS(Number(e.target.value))} />
          </label>
          {gaugeKeys.map((k) => (
            <label key={k} className="field">
              <span className="field__label">{k}</span>
              <input
                className="field__input"
                type="range"
                min={0}
                max={max}
                step={mode === "world" ? 0.01 : 1}
                value={Number(gauges[k] ?? 0)}
                onChange={(e) => setGauges((g) => ({ ...g, [k]: Number(e.target.value) }))}
              />
              <span className="muted">{Number(gauges[k] ?? 0).toFixed(mode === "world" ? 2 : 0)}</span>
            </label>
          ))}
          <div className="btn-row">
            <button type="button" className="btn btn--primary btn--sm" onClick={() => void step()}>
              Step
            </button>
            <button type="button" className="btn btn--sm" onClick={() => setGauges(defaultGauges(mode))}>
              Reset
            </button>
            <button type="button" className="btn btn--sm" onClick={() => setGauges({ hunger: 0.9, thirst: 0.85, fatigue: 0.8, motivation: 20, focus: 15, patience: 10 })}>
              Stress
            </button>
            <label className="field field--row">
              <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} />
              Auto 5s
            </label>
          </div>
          <Hint>{hint}</Hint>
        </Panel>

        <Panel title="Sortie output.lyra">
          <JsonPre data={output} maxHeight="16rem" />
          <h4 className="panel__subtitle">Brain orchestrateur</h4>
          <button type="button" className="btn btn--sm" onClick={() => void refreshBrain()}>
            Rafraîchir
          </button>
          <JsonPre data={brain} maxHeight="10rem" />
        </Panel>
      </div>
    </ViewShell>
  );
}
