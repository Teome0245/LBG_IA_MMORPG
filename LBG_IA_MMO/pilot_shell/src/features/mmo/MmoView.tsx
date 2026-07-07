import { useState } from "react";
import {
  fetchNpcRegistry,
  fetchWorldContent,
  fetchWorldLyra,
  postAid,
  postPlayerInventory,
  postReputation,
} from "../../api/pilotClient";
import { MmoClientFrame } from "../../components/MmoClientFrame";
import { FieldRow, Hint, JsonPre, Panel, ViewShell } from "../../components/ViewShell";
import { useSettings } from "../../stores/context";

const NPC_CHIPS = [
  "npc:merchant",
  "npc:smith",
  "npc:innkeeper",
  "npc:guard",
  "npc:healer",
  "npc:mayor",
];

type MmoTab = "client" | "tools";

export function MmoView() {
  const { settings } = useSettings();
  const [tab, setTab] = useState<MmoTab>("client");
  const [worldNpcId, setWorldNpcId] = useState("npc:merchant");
  const [playerId, setPlayerId] = useState("");
  const [itemId, setItemId] = useState("item:potion_test");
  const [qty, setQty] = useState(1);
  const [hint, setHint] = useState("");
  const [registry, setRegistry] = useState<unknown>(null);
  const [worldContent, setWorldContent] = useState<unknown>(null);
  const [lyra, setLyra] = useState<unknown>(null);

  const run = async (label: string, fn: () => Promise<{ status: number; body: Record<string, unknown> }>) => {
    setHint(`${label}…`);
    const { status, body } = await fn();
    setHint(`${label} → HTTP ${status}`);
    return body;
  };

  return (
    <ViewShell
      title="MMO — Core3 Prime"
      description="Client jeu intégré + outils debug pont monde (VM 246)."
      legacyHash="#/ops/mmo"
    >
      <div className="view-tabs">
        <button
          type="button"
          className={`view-tabs__btn${tab === "client" ? " view-tabs__btn--active" : ""}`}
          onClick={() => setTab("client")}
        >
          Client jeu
        </button>
        <button
          type="button"
          className={`view-tabs__btn${tab === "tools" ? " view-tabs__btn--active" : ""}`}
          onClick={() => setTab("tools")}
        >
          Outils API
        </button>
      </div>

      {tab === "client" && <MmoClientFrame className="mmo-frame--fill" />}

      {tab === "tools" && (
        <>
          <div className="view-grid">
            <Panel title="Cible PNJ">
              <FieldRow>
                <input className="field__input" value={worldNpcId} onChange={(e) => setWorldNpcId(e.target.value)} />
              </FieldRow>
              <div className="chip-row">
                {NPC_CHIPS.map((id) => (
                  <button key={id} type="button" className="chip" onClick={() => setWorldNpcId(id)}>
                    {id}
                  </button>
                ))}
              </div>
            </Panel>

            <Panel title="Réputation (sans LLM)">
              <div className="btn-row">
                <button type="button" className="btn btn--sm" onClick={() => void run("Rep +11", () => postReputation(settings, worldNpcId, 11))}>
                  +11
                </button>
                <button type="button" className="btn btn--sm" onClick={() => void run("Rep -5", () => postReputation(settings, worldNpcId, -5))}>
                  −5
                </button>
                <button type="button" className="btn btn--sm" onClick={() => void run("Reset", () => postReputation(settings, worldNpcId, 0))}>
                  Reset
                </button>
              </div>
            </Panel>

            <Panel title="Inventaire joueur">
              <FieldRow>
                <input className="field__input" placeholder="player_id UUID" value={playerId} onChange={(e) => setPlayerId(e.target.value)} />
                <input className="field__input" placeholder="item_id" value={itemId} onChange={(e) => setItemId(e.target.value)} />
                <input className="field__input field__input--narrow" type="number" value={qty} onChange={(e) => setQty(Number(e.target.value))} />
                <button
                  type="button"
                  className="btn btn--sm"
                  onClick={() =>
                    void run("Inventaire", () =>
                      postPlayerInventory(settings, {
                        npc_id: worldNpcId,
                        player_id: playerId,
                        item_id: itemId,
                        qty_delta: qty,
                      }),
                    )
                  }
                >
                  Appliquer
                </button>
              </FieldRow>
            </Panel>

            <Panel title="Monde (aid)">
              <div className="btn-row">
                <button
                  type="button"
                  className="btn btn--sm"
                  onClick={async () => {
                    await run("Aid", () => postAid(settings, { npc_id: worldNpcId, hunger_delta: -0.2, thirst_delta: -0.1, fatigue_delta: -0.2, reputation_delta: 5 }));
                    const ly = await fetchWorldLyra(settings, worldNpcId);
                    setLyra(ly.body);
                  }}
                >
                  Aider
                </button>
                <button
                  type="button"
                  className="btn btn--sm"
                  onClick={async () => {
                    await run("Reset jauges", () => postAid(settings, { npc_id: worldNpcId, reset_gauges: true }));
                    const ly = await fetchWorldLyra(settings, worldNpcId);
                    setLyra(ly.body);
                  }}
                >
                  Reset jauges
                </button>
                <button
                  type="button"
                  className="btn btn--sm"
                  onClick={async () => {
                    const ly = await fetchWorldLyra(settings, worldNpcId);
                    setLyra(ly.body);
                    setHint("Lyra snapshot");
                  }}
                >
                  Lire Lyra
                </button>
              </div>
              <JsonPre data={lyra} maxHeight="10rem" />
            </Panel>

            <Panel title="Registre & catalogue">
              <div className="btn-row">
                <button
                  type="button"
                  className="btn btn--sm"
                  onClick={async () => {
                    const r = await fetchNpcRegistry(settings, worldNpcId);
                    setRegistry(r.body);
                    setHint(`Registry HTTP ${r.status}`);
                  }}
                >
                  NPC registry
                </button>
                <button
                  type="button"
                  className="btn btn--sm"
                  onClick={async () => {
                    const r = await fetchWorldContent(settings);
                    setWorldContent(r.body);
                    setHint(`World-content HTTP ${r.status}`);
                  }}
                >
                  World-content
                </button>
              </div>
              <JsonPre data={registry} maxHeight="8rem" />
              <JsonPre data={worldContent} maxHeight="8rem" />
            </Panel>
          </div>
          <Hint>{hint}</Hint>
          <p className="view__note">
            Dialogue / quêtes : panneau <strong>Agent</strong> ou presets MMO.
          </p>
        </>
      )}
    </ViewShell>
  );
}
