import sqlite3
import time


def _make_state_db(path, rows):
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            source TEXT,
            title TEXT,
            model TEXT,
            started_at REAL,
            message_count INTEGER,
            user_id TEXT,
            chat_id TEXT,
            chat_type TEXT,
            thread_id TEXT,
            session_key TEXT,
            origin_chat_id TEXT,
            origin_user_id TEXT,
            platform TEXT,
            parent_session_id TEXT,
            ended_at REAL,
            end_reason TEXT
        );
        CREATE TABLE messages (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            role TEXT,
            content TEXT,
            timestamp REAL
        );
        """
    )
    base = time.time() - len(rows) * 10
    for idx, row in enumerate(rows):
        started = row.get("started_at", base + idx * 10)
        sid = row["id"]
        conn.execute(
            """
            INSERT INTO sessions
            (id, source, title, model, started_at, message_count, user_id, chat_id,
             chat_type, thread_id, session_key, origin_chat_id, origin_user_id,
             platform, parent_session_id, ended_at, end_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sid,
                row.get("source", "telegram"),
                row.get("title", sid),
                row.get("model", "openai/gpt-5"),
                started,
                row.get("message_count", 2),
                row.get("user_id"),
                row.get("chat_id"),
                row.get("chat_type"),
                row.get("thread_id"),
                row.get("session_key"),
                row.get("origin_chat_id"),
                row.get("origin_user_id"),
                row.get("platform"),
                row.get("parent_session_id"),
                row.get("ended_at"),
                row.get("end_reason"),
            ),
        )
        conn.execute(
            "INSERT INTO messages (id, session_id, role, content, timestamp) VALUES (?, ?, 'user', 'hello', ?)",
            (f"{sid}-u", sid, started),
        )
        conn.execute(
            "INSERT INTO messages (id, session_id, role, content, timestamp) VALUES (?, ?, 'assistant', 'hi', ?)",
            (f"{sid}-a", sid, started + 1),
        )
    conn.commit()
    conn.close()


def _patch_topic_env(monkeypatch, tmp_path, rows, gateway_map=None):
    import api.routes as routes

    db_path = tmp_path / "state.db"
    _make_state_db(db_path, rows)
    monkeypatch.setattr(routes, "_active_state_db_path", lambda: db_path)
    monkeypatch.setattr(routes, "TELEGRAM_TOPIC_PROFILES_FILE", tmp_path / "telegram_topics.json")
    monkeypatch.setattr(routes, "_load_gateway_session_identity_map", lambda: gateway_map or {})
    return routes


def test_telegram_topics_keep_same_group_different_threads(monkeypatch, tmp_path):
    routes = _patch_topic_env(
        monkeypatch,
        tmp_path,
        [
            {"id": "tg_thread_a", "title": "Topic A", "chat_id": "group_1", "chat_type": "group", "thread_id": "a"},
            {"id": "tg_thread_b", "title": "Topic B", "chat_id": "group_1", "chat_type": "group", "thread_id": "b"},
        ],
    )

    payload = routes._telegram_topics_payload()
    identities = {topic["identity"] for topic in payload["topics"]}

    assert "telegram|chat_type:group|chat_id:group_1|thread_id:a" in identities
    assert "telegram|chat_type:group|chat_id:group_1|thread_id:b" in identities
    assert payload["count"] == 2


def test_telegram_topic_session_key_groups_to_latest(monkeypatch, tmp_path):
    routes = _patch_topic_env(
        monkeypatch,
        tmp_path,
        [
            {"id": "tg_old", "title": "Old Topic", "session_key": "topic-key", "started_at": 100.0},
            {"id": "tg_new", "title": "New Topic", "session_key": "topic-key", "started_at": 200.0},
        ],
    )

    payload = routes._telegram_topics_payload()

    assert payload["count"] == 1
    assert payload["topics"][0]["identity"] == "telegram|session_key:topic-key"
    assert payload["topics"][0]["session_id"] == "tg_new"


def test_telegram_topic_profile_mapping_is_returned(monkeypatch, tmp_path):
    routes = _patch_topic_env(
        monkeypatch,
        tmp_path,
        [{"id": "tg_profile", "title": "Profile Topic", "chat_id": "chat_1", "thread_id": "general"}],
    )
    routes._save_telegram_topic_profile_map({
        "telegram|chat_id:chat_1|thread_id:general": "writer",
    })

    payload = routes._telegram_topics_payload()

    assert payload["topics"][0]["assigned_profile"] == "writer"
    assert payload["topics"][0]["effective_profile"] == "writer"


def test_apply_telegram_topic_profile_updates_imported_sidecar(monkeypatch, tmp_path):
    routes = _patch_topic_env(
        monkeypatch,
        tmp_path,
        [{"id": "tg_sidecar", "title": "Sidecar Topic", "chat_id": "chat_2", "thread_id": "ops"}],
    )
    import api.models as models

    session_dir = tmp_path / "sessions"
    session_dir.mkdir()
    monkeypatch.setattr(models, "SESSION_DIR", session_dir)
    monkeypatch.setattr(models, "SESSION_INDEX_FILE", session_dir / "_index.json")

    Session = models.Session

    session = Session(
        session_id="tg_sidecar",
        title="Sidecar Topic",
        messages=[{"role": "user", "content": "hello"}],
        raw_source="telegram",
        session_source="messaging",
        chat_id="chat_2",
        thread_id="ops",
    )
    session.save(touch_updated_at=False)

    updated = routes._apply_telegram_topic_profile(
        "telegram|chat_id:chat_2|thread_id:ops",
        "researcher",
    )

    assert updated == ["tg_sidecar"]
    assert Session.load("tg_sidecar").profile == "researcher"
