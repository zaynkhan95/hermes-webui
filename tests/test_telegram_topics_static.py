from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
PANELS_JS = (ROOT / "static" / "panels.js").read_text(encoding="utf-8")
UI_JS = (ROOT / "static" / "ui.js").read_text(encoding="utf-8")
STYLE_CSS = (ROOT / "static" / "style.css").read_text(encoding="utf-8")


def test_agents_tab_replaces_visible_telegram_panel():
    assert 'data-panel="agents"' in INDEX_HTML
    assert 'id="panelAgents"' in INDEX_HTML
    assert 'id="mainAgents"' in INDEX_HTML
    assert 'data-panel="telegram"' not in INDEX_HTML
    assert "nextPanel === 'agents'" in PANELS_JS
    assert "loadMissionControlAgents" in PANELS_JS
    assert "loadTelegramTopics" in PANELS_JS
    assert "main.main.showing-agents > #mainAgents" in STYLE_CSS


def test_agents_surface_has_required_mvp_tabs():
    for label in ("Conversations", "Knowledge", "Missions", "Settings"):
        assert label in INDEX_HTML
    assert "agent-source-badge" in STYLE_CSS
    assert "loadTelegramTopics" in PANELS_JS
    assert "Deliver to Telegram thread" not in PANELS_JS
    assert "agentMissionDeliver" not in PANELS_JS
    assert "also send" not in PANELS_JS.lower()


def test_topbar_surfaces_telegram_topic_context():
    assert "function _topbarTelegramTopicContext" in UI_JS
    assert "session.thread_id" in UI_JS
    assert "session.chat_id" in UI_JS
