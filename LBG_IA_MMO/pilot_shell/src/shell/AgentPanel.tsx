import { AgentChat } from "../agent/AgentChat";

export function AgentPanel() {
  return (
    <aside className="agent-panel">
      <header className="agent-panel__header">
        <h2 className="agent-panel__title">Agent</h2>
      </header>
      <div className="agent-panel__body agent-panel__body--chat">
        <AgentChat />
      </div>
    </aside>
  );
}
