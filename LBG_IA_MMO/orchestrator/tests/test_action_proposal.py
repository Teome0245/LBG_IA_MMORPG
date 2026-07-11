from fastapi.testclient import TestClient

from orchestrator.main import app


def test_action_proposal_notepad_append() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/action-proposal",
        json={
            "actor_id": "user:1",
            "text": "ouvre notepad et écris bonjour Lyra",
            "context": {"desktop_default_notepad_path": r"C:\Users\Public\notes.txt"},
        },
    )
    assert r.status_code == 200
    proposal = r.json()["proposal"]
    assert proposal["capability"] == "desktop_control"
    assert proposal["action_context_key"] == "desktop_action"
    assert proposal["action"]["kind"] == "notepad_append"
    assert proposal["action"]["path"] == r"C:\Users\Public\notes.txt"
    assert "bonjour Lyra" in proposal["action"]["text"]
    assert proposal["context_patch"]["desktop_dry_run"] is True


def test_action_proposal_web_search() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/action-proposal",
        json={"actor_id": "user:1", "text": "cherche sur internet le site de Cursor AI", "context": {}},
    )
    assert r.status_code == 200
    proposal = r.json()["proposal"]
    assert proposal["capability"] == "desktop_control"
    assert proposal["action"]["kind"] == "search_web_open"
    assert proposal["action"]["query"] == "Cursor AI"
    assert proposal["context_patch"]["desktop_action"]["kind"] == "search_web_open"


def test_action_proposal_mail_preview_sender() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/action-proposal",
        json={"actor_id": "user:1", "text": "regarde si j'ai un mail de Intel", "context": {}},
    )
    assert r.status_code == 200
    proposal = r.json()["proposal"]
    assert proposal["capability"] == "desktop_control"
    assert proposal["action"]["kind"] == "mail_imap_preview"
    assert proposal["action"]["from_contains"] == "Intel"
    assert proposal["context_patch"]["desktop_dry_run"] is True


def test_action_proposal_open_app_vghd_fr() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/action-proposal",
        json={"actor_id": "user:1", "text": "ouvrir vghd sur mon PC", "context": {}},
    )
    assert r.status_code == 200
    proposal = r.json()["proposal"]
    assert proposal is not None
    assert proposal["capability"] == "desktop_control"
    assert proposal["action"]["kind"] == "open_app"
    assert proposal["action"]["app"] == "vghd"
    assert proposal["action"]["args"] == []
    # learn:true par défaut (allowlist auto-apprise sur le worker — LBG_DESKTOP_OPEN_APP_LEARN).
    assert proposal["action"].get("learn") is True
    assert proposal["context_patch"]["desktop_dry_run"] is True


def test_action_proposal_open_app_alias_and_exe_path() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/action-proposal",
        json={
            "actor_id": "user:1",
            "text": "lance swg sur mon pc (J:\\swgemu\\StarWarsGalaxies\\SWGEmu.exe)",
            "context": {},
        },
    )
    assert r.status_code == 200
    proposal = r.json()["proposal"]
    assert proposal is not None
    assert proposal["action"]["kind"] == "open_app"
    # Alias swg → swgemu et chemin .exe rapatrié dans command.
    assert proposal["action"]["app"] == "swgemu"
    assert proposal["action"]["command"] == "J:\\swgemu\\StarWarsGalaxies\\SWGEmu.exe"
    assert proposal["action"].get("learn") is True
    assert proposal["context_patch"]["desktop_dry_run"] is True


def test_action_proposal_open_app_launch_en() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/action-proposal",
        json={"actor_id": "user:1", "text": "launch vlc please", "context": {}},
    )
    assert r.status_code == 200
    proposal = r.json()["proposal"]
    assert proposal is not None
    assert proposal["action"]["kind"] == "open_app"
    assert proposal["action"]["app"] == "vlc"


def test_action_proposal_open_app_rejects_path() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/action-proposal",
        json={"actor_id": "user:1", "text": "open C:\\\\Windows\\\\notepad.exe", "context": {}},
    )
    assert r.status_code == 200
    assert r.json()["proposal"] is None


def test_action_proposal_infra_selfcheck() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/action-proposal",
        json={"actor_id": "ops:1", "text": "vérifie l'état du backend et de l'orchestrateur", "context": {}},
    )
    assert r.status_code == 200
    proposal = r.json()["proposal"]
    assert proposal["capability"] == "devops_probe"
    assert proposal["action_context_key"] == "devops_action"
    assert proposal["action"] == {"kind": "selfcheck"}
    assert proposal["context_patch"] == {"devops_action": {"kind": "selfcheck"}}


def test_action_proposal_file_path_pm_not_web() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/action-proposal",
        json={"actor_id": "ops:1", "text": "donne moi le chemin du fichier a modifier", "context": {}},
    )
    assert r.status_code == 200
    proposal = r.json()["proposal"]
    assert proposal is not None
    assert proposal["capability"] == "project_pm"
    assert proposal["context_patch"].get("pm_focus") is True


def test_action_proposal_logs_consult_dialogue() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/action-proposal",
        json={
            "actor_id": "ops:1",
            "text": "ajoute un système de logs pour le débogage, rétention 30 jours",
            "context": {},
        },
    )
    assert r.status_code == 200
    proposal = r.json()["proposal"]
    assert proposal["capability"] == "npc_dialogue"
    assert proposal["context_patch"].get("_dialogue_consult") is True


def test_action_proposal_desktop_target_ad() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/action-proposal",
        json={
            "actor_id": "ops:1",
            "text": "lance notepad sur le serveur ad",
            "context": {},
        },
    )
    assert r.status_code == 200
    proposal = r.json()["proposal"]
    assert proposal is not None
    assert proposal["capability"] == "desktop_control"
    assert proposal["context_patch"].get("desktop_target") == "ad"


def test_action_proposal_network_inventory_fr() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/action-proposal",
        json={
            "actor_id": "pilot:jobs",
            "text": "cartographie le réseau LAN et les appareils présents",
            "context": {},
        },
    )
    assert r.status_code == 200
    proposal = r.json()["proposal"]
    assert proposal is not None
    assert proposal["capability"] == "network_inventory"
    assert proposal["routed_to"] == "agent.network"


def test_action_proposal_capabilities_inventory_fr() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/action-proposal",
        json={
            "actor_id": "pilot:jobs",
            "text": "établie la liste des agents disponible et leurs capacité",
            "context": {},
        },
    )
    assert r.status_code == 200
    proposal = r.json()["proposal"]
    assert proposal is not None
    assert proposal["capability"] == "npc_dialogue"
    assert proposal["context_patch"].get("_capabilities_inventory") is True


def test_action_proposal_auto_checkup_fr() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/action-proposal",
        json={
            "actor_id": "ops:1",
            "text": "peut tu me faire un auto checkup et me dire ce qui pourrait être amélioré",
            "context": {},
        },
    )
    assert r.status_code == 200
    proposal = r.json()["proposal"]
    assert proposal["capability"] == "devops_probe"
    assert proposal["action"] == {"kind": "selfcheck"}


def test_action_proposal_no_match() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/action-proposal",
        json={"actor_id": "user:1", "text": "raconte-moi une histoire de taverne", "context": {}},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["proposal"] is None
    assert "Aucune action" in data["reason"]


def test_action_proposal_mmo_bridge_opengame_prototype() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/action-proposal",
        json={
            "actor_id": "user:1",
            "text": "forge un prototype sandbox pour une évolution MMO",
            "context": {
                "session_summary": {"tracked_quest": "aide au village", "player_note": "hier"},
                "mmo_bridge": {"source": "mmo_session_summary", "imported_at": "2026-05-06T10:00:00Z"},
            },
        },
    )
    assert r.status_code == 200
    proposal = r.json()["proposal"]
    assert proposal is not None
    assert proposal["capability"] == "prototype_game"
    assert proposal["action"]["kind"] == "generate_prototype"
    assert proposal["source"] == "mmo_session_bridge"
    assert proposal["mmo_trace"]["bridge_source"] == "mmo_session_summary"
    assert "desktop_action" not in proposal["context_patch"]
    assert proposal["context_patch"].get("opengame_dry_run") is True


def test_action_proposal_mmo_dev_requires_explicit_bridge() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/action-proposal",
        json={
            "actor_id": "user:1",
            "text": "forge un prototype sandbox",
            "context": {"session_summary": {"tracked_quest": "x"}},
        },
    )
    assert r.status_code == 200
    assert r.json()["proposal"] is None


def test_action_proposal_team_dev_game_forge_qa_followup() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/action-proposal",
        json={
            "actor_id": "system:team_qa_followup",
            "text": "Analyser échec smoke — proposition correctif gameplay",
            "context": {
                "dev_game_focus": True,
                "_qa_followup": True,
                "parent_task_id": "qa-123",
                "qa_failure_summary": {"smoke_ok": False, "smoke_exit_code": 1},
            },
        },
    )
    assert r.status_code == 200
    proposal = r.json()["proposal"]
    assert proposal is not None
    assert proposal["capability"] == "prototype_game"
    assert proposal["source"] == "team_dev_game"
    assert proposal["action"]["kind"] == "generate_prototype"
    assert proposal["context_patch"].get("opengame_dry_run") is True
    assert proposal["mmo_trace"]["qa_followup"] is True
