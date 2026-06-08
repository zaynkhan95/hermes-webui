import io
import json
from urllib.parse import urlparse

import pytest


class _FakeHandler:
    def __init__(self, body=None):
        raw = b"" if body is None else json.dumps(body).encode("utf-8")
        self.headers = {"Content-Length": str(len(raw))}
        self.rfile = io.BytesIO(raw)
        self.wfile = self
        self.status = None
        self.body = bytearray()
        self.sent_headers = []
        self.client_address = ("127.0.0.1", 12345)

    def send_response(self, code):
        self.status = code

    def send_header(self, key, value):
        self.sent_headers.append((key, value))

    def end_headers(self):
        pass

    def write(self, data):
        self.body.extend(data if isinstance(data, (bytes, bytearray)) else data.encode("utf-8"))

    def get_json(self):
        return json.loads(self.body.decode("utf-8"))


@pytest.fixture()
def isolated_mission_control(monkeypatch, tmp_path):
    from api import mission_control

    monkeypatch.setattr(mission_control, "AGENTS_FILE", tmp_path / "agents.json")
    monkeypatch.setattr(mission_control, "MISSIONS_FILE", tmp_path / "agent_missions.json")
    return mission_control


def test_seed_agents_are_exact_active_profiles(isolated_mission_control):
    agents = isolated_mission_control.list_agents()

    assert [agent["id"] for agent in agents] == ["default", "finx1", "health"]
    assert [agent["profile"] for agent in agents] == ["default", "finx1", "health"]
    assert len(agents) == 3
    assert agents[0]["telegramChatId"] == "-1003967646300"
    assert agents[0]["telegramThreadId"] == "1"


def test_patch_agent_persists_only_safe_fields(isolated_mission_control, tmp_path):
    context_root = tmp_path / "My Vault" / "10-Agents" / "main" / "Context"
    context_root.mkdir(parents=True)

    agent = isolated_mission_control.patch_agent(
        "default",
        {
            "name": "General Ops",
            "purpose": "Personal operations",
            "profile": "default",
            "telegramThreadId": "1",
            "contextRoot": str(context_root),
            "defaultWorkspace": str(context_root),
            "status": "ready",
        },
        known_profiles={"default"},
    )

    assert agent["name"] == "General Ops"
    assert isolated_mission_control.get_agent("default")["contextRoot"] == str(context_root.resolve())

    with pytest.raises(ValueError):
        isolated_mission_control.patch_agent("default", {"secret": "nope"})


def test_knowledge_read_save_and_traversal_guard(isolated_mission_control, tmp_path):
    context_root = tmp_path / "My Vault" / "10-Agents" / "main" / "Context"
    context_root.mkdir(parents=True)
    note = context_root / "daily.md"
    note.write_text("before\n", encoding="utf-8")
    secret = tmp_path / "secret.md"
    secret.write_text("secret", encoding="utf-8")
    isolated_mission_control.patch_agent(
        "default",
        {"contextRoot": str(context_root), "defaultWorkspace": str(context_root)},
    )

    files = isolated_mission_control.list_knowledge_files("default")
    assert files["files"][0]["path"] == "daily.md"

    loaded = isolated_mission_control.read_knowledge_file("default", "daily.md")
    assert loaded["content"] == "before\n"

    saved = isolated_mission_control.save_knowledge_file("default", "daily.md", "after\n")
    assert saved["ok"] is True
    assert note.read_text(encoding="utf-8") == "after\n"

    with pytest.raises(ValueError):
        isolated_mission_control.read_knowledge_file("default", "../secret.md")
    with pytest.raises(ValueError):
        isolated_mission_control.read_knowledge_file("default", "image.png")


def test_missions_persist_without_launching_jobs(isolated_mission_control):
    mission = isolated_mission_control.create_mission(
        "health",
        {"title": "Plan week", "description": "Draft priorities"},
    )

    assert mission["status"] == "queued"
    assert mission["agentId"] == "health"
    assert mission["deliverToTelegramThread"] is True
    assert isolated_mission_control.list_missions("health")["missions"][0]["id"] == mission["id"]


def test_agents_and_hermes_status_routes(monkeypatch, isolated_mission_control):
    from api import routes

    monkeypatch.setattr(routes.mission_control, "hermes_status_payload", lambda: {
        "defaultGatewayRunning": True,
        "profiles": [{"name": "default", "gateway": "running", "model": "openai/gpt-5"}],
        "telegramTargets": [{"name": "General", "chatId": "-1003967646300", "threadId": "1"}],
    })

    handler = _FakeHandler()
    routes.handle_get(handler, urlparse("http://example.com/api/agents"))
    payload = handler.get_json()
    assert payload["count"] == 3
    assert payload["agents"][0]["id"] == "default"

    handler = _FakeHandler()
    routes.handle_get(handler, urlparse("http://example.com/api/hermes/status"))
    status = handler.get_json()
    assert status["defaultGatewayRunning"] is True
    assert "token" not in json.dumps(status).lower()


def test_agent_patch_and_mission_routes(monkeypatch, isolated_mission_control, tmp_path):
    from api import routes

    monkeypatch.setattr(routes, "_check_csrf", lambda _handler: True)
    monkeypatch.setattr(routes, "_mission_control_known_profiles", lambda: {"default"})
    context_root = tmp_path / "My Vault" / "10-Agents" / "main" / "Context"
    context_root.mkdir(parents=True)

    handler = _FakeHandler({
        "name": "General",
        "purpose": "General assistant",
        "profile": "default",
        "telegramThreadId": "1",
        "contextRoot": str(context_root),
        "defaultWorkspace": str(context_root),
        "status": "ready",
    })
    routes.handle_patch(handler, urlparse("http://example.com/api/agents/default"))
    assert handler.get_json()["agent"]["contextRoot"] == str(context_root.resolve())

    handler = _FakeHandler({"title": "Follow up", "description": "Check priorities"})
    routes.handle_post(handler, urlparse("http://example.com/api/agents/default/missions"))
    assert handler.status == 201
    assert handler.get_json()["mission"]["status"] == "queued"
