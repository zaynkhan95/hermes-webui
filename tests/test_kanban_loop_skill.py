from pathlib import Path
from unittest.mock import MagicMock


def test_kanban_loop_skill_content_encodes_guardrails():
    from api.kanban_loop_skill import SKILL_NAME, metadata, skill_content

    content = skill_content()
    data = metadata()

    assert SKILL_NAME == "conversation-to-kanban-triage"
    assert data["category"] == "workflows"
    assert "New conversation-derived cards default to `triage`" in content
    assert "Human approval is required before creating" in content
    assert "Do not run the Kanban dispatcher from this skill" in content
    assert "Never create directly in `running`" in content
    assert "Morning Review" in content
    assert "Conversation Closeout" in content
    assert "Evening Sweep" in content


def test_kanban_loop_skill_routes_are_registered():
    routes_source = (Path(__file__).resolve().parent.parent / "api" / "routes.py").read_text("utf-8")

    assert '"/api/kanban-loop/skill"' in routes_source
    assert '"/api/kanban-loop/skill/install"' in routes_source
    assert "_handle_kanban_loop_skill_install" in routes_source


def test_kanban_loop_skill_install_writes_to_active_profile(tmp_path, monkeypatch):
    from api.kanban_loop_skill import SKILL_NAME
    from api.routes import _handle_kanban_loop_skill_install

    skills_dir = tmp_path / "profile-home" / "skills"
    monkeypatch.setattr("api.routes._active_skills_dir", lambda: skills_dir)

    handler = MagicMock()
    handler.headers = {}
    handler.wfile.write = MagicMock()

    _handle_kanban_loop_skill_install(handler, {})

    skill_file = skills_dir / "workflows" / SKILL_NAME / "SKILL.md"
    assert skill_file.exists()
    content = skill_file.read_text(encoding="utf-8")
    assert f"name: {SKILL_NAME}" in content
    assert "default to `triage`" in content
    assert "Do not run the Kanban dispatcher" in content


def test_existing_skill_save_still_supports_category(tmp_path, monkeypatch):
    from api.routes import _write_skill_to_active_profile

    skills_dir = tmp_path / "skills"
    monkeypatch.setattr("api.routes._active_skills_dir", lambda: skills_dir)

    result = _write_skill_to_active_profile(
        "Example Skill",
        "---\nname: example-skill\n---\n\n# Example\n",
        "personal",
    )

    assert result["ok"] is True
    assert result["name"] == "example-skill"
    assert result["category"] == "personal"
    assert (skills_dir / "personal" / "example-skill" / "SKILL.md").exists()
