"""Mission Control registry, knowledge, status, and mission helpers."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path

from api.config import MAX_FILE_BYTES, STATE_DIR
from api.workspace import (
    open_anchored_create_fd,
    open_anchored_fd,
    read_file_content,
    safe_resolve_ws,
)


TELEGRAM_CHAT_ID = "-1003967646300"
AGENTS_FILE = STATE_DIR / "agents.json"
MISSIONS_FILE = STATE_DIR / "agent_missions.json"
KNOWLEDGE_EXTENSIONS = {".md", ".markdown", ".txt"}
MISSION_STATUSES = {"queued", "running", "blocked", "complete"}
AGENT_STATUSES = {"ready", "unknown", "offline", "degraded"}
SAFE_AGENT_PATCH_FIELDS = {
    "name",
    "profile",
    "telegramThreadId",
    "contextRoot",
    "defaultWorkspace",
    "purpose",
    "status",
}


SEED_AGENTS = [
    {
        "id": "default",
        "agentId": "default",
        "name": "General",
        "telegramChatId": TELEGRAM_CHAT_ID,
        "telegramThreadId": "1",
        "profile": "default",
        "contextRoot": "/Users/zaynkhan/Documents/My Vault/10-Agents/main/Context",
        "defaultWorkspace": "/Users/zaynkhan/Documents/My Vault/10-Agents/main/Context",
        "purpose": "General assistant, Hermes Admin, Life Coach, personal operating system, and live Telegram gateway",
        "status": "ready",
    },
    {
        "id": "finx1",
        "agentId": "finx1",
        "name": "FINx1",
        "telegramChatId": TELEGRAM_CHAT_ID,
        "telegramThreadId": "12",
        "profile": "finx1",
        "contextRoot": "/Users/zaynkhan/Documents/My Vault/10-Agents/finx1_cpo/Context",
        "defaultWorkspace": "/Users/zaynkhan/Documents/My Vault/10-Agents/finx1_cpo/Context",
        "purpose": "FINx1 work domain: product, marketing, sales, partnerships, banking infrastructure, and work MCP/OAuth isolation",
        "status": "ready",
    },
    {
        "id": "health",
        "agentId": "health",
        "name": "Health",
        "telegramChatId": TELEGRAM_CHAT_ID,
        "telegramThreadId": "39",
        "profile": "health",
        "contextRoot": "/Users/zaynkhan/Documents/My Vault/10-Agents/pt_health_coach/Context",
        "defaultWorkspace": "/Users/zaynkhan/Documents/My Vault/10-Agents/pt_health_coach/Context",
        "purpose": "Personal health domain: PT, physio, rehab, nutrition, labs, supplements, Apple Health, and Ultrahuman",
        "status": "ready",
    },
]


def _atomic_write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, ensure_ascii=False, indent=2)
    tmp = path.with_suffix(f".tmp.{os.getpid()}.{threading.current_thread().ident}.{uuid.uuid4().hex[:8]}")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(raw)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _read_json(path: Path, fallback):
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback
    return raw if isinstance(raw, type(fallback)) else fallback


def _load_agent_overrides() -> dict[str, dict]:
    raw = _read_json(AGENTS_FILE, {})
    if isinstance(raw.get("agents"), dict):
        raw = raw["agents"]
    out: dict[str, dict] = {}
    for agent_id, fields in raw.items():
        if not isinstance(fields, dict):
            continue
        clean = {
            key: str(value).strip()
            for key, value in fields.items()
            if key in SAFE_AGENT_PATCH_FIELDS and value is not None
        }
        if clean:
            out[str(agent_id)] = clean
    return out


def _save_agent_overrides(overrides: dict[str, dict]) -> None:
    clean = {
        str(agent_id): {
            key: value
            for key, value in fields.items()
            if key in SAFE_AGENT_PATCH_FIELDS and value is not None
        }
        for agent_id, fields in overrides.items()
        if isinstance(fields, dict)
    }
    _atomic_write_json(AGENTS_FILE, {"agents": clean})


def _public_agent(agent: dict) -> dict:
    out = dict(agent)
    out["id"] = str(out.get("id") or out.get("agentId") or "")
    out["agentId"] = out["id"]
    out["telegramChatId"] = str(out.get("telegramChatId") or TELEGRAM_CHAT_ID)
    out["telegramThreadId"] = str(out.get("telegramThreadId") or "")
    out["profile"] = str(out.get("profile") or "default")
    out["contextRoot"] = str(out.get("contextRoot") or "")
    out["defaultWorkspace"] = str(out.get("defaultWorkspace") or out.get("contextRoot") or "")
    out["status"] = str(out.get("status") or "unknown")
    return out


def list_agents() -> list[dict]:
    overrides = _load_agent_overrides()
    agents: list[dict] = []
    for seed in SEED_AGENTS:
        merged = dict(seed)
        merged.update(overrides.get(seed["id"], {}))
        agents.append(_public_agent(merged))
    return agents


def get_agent(agent_id: str) -> dict:
    wanted = str(agent_id or "").strip()
    for agent in list_agents():
        if agent["id"] == wanted:
            return agent
    raise KeyError("Agent not found")


def patch_agent(agent_id: str, body: dict, *, known_profiles: set[str] | None = None) -> dict:
    if not isinstance(body, dict):
        raise ValueError("JSON object body required")
    agent = get_agent(agent_id)
    unknown = sorted(set(body) - SAFE_AGENT_PATCH_FIELDS)
    if unknown:
        raise ValueError(f"Unsupported agent field: {unknown[0]}")

    clean: dict[str, str] = {}
    for key in SAFE_AGENT_PATCH_FIELDS:
        if key not in body:
            continue
        value = str(body.get(key) or "").strip()
        if key in {"name", "purpose", "profile", "contextRoot", "defaultWorkspace"} and not value:
            raise ValueError(f"{key} is required")
        if key == "status" and value and value not in AGENT_STATUSES:
            raise ValueError("Invalid agent status")
        if key == "telegramThreadId" and not value:
            raise ValueError("telegramThreadId is required")
        if key == "profile" and known_profiles is not None and value not in known_profiles:
            raise KeyError("Profile not found")
        if key in {"contextRoot", "defaultWorkspace"}:
            value = str(Path(value).expanduser().resolve())
        clean[key] = value

    overrides = _load_agent_overrides()
    current = dict(overrides.get(agent["id"], {}))
    current.update(clean)
    overrides[agent["id"]] = current
    _save_agent_overrides(overrides)
    return get_agent(agent["id"])


def _agent_context_root(agent: dict) -> Path:
    root = Path(str(agent.get("contextRoot") or "")).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Context root not found: {root}")
    return root


def _validate_knowledge_path(rel_path: str) -> str:
    if not isinstance(rel_path, str) or not rel_path.strip():
        raise ValueError("path is required")
    rel = rel_path.strip()
    candidate = Path(rel)
    if candidate.is_absolute():
        raise ValueError("Knowledge path must be relative")
    if candidate.suffix.lower() not in KNOWLEDGE_EXTENSIONS:
        raise ValueError("Only markdown and text files are editable")
    return rel


def list_knowledge_files(agent_id: str, *, limit: int = 500) -> dict:
    agent = get_agent(agent_id)
    root = _agent_context_root(agent)
    files = []
    for path in root.rglob("*"):
        if len(files) >= limit:
            break
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        if not path.is_file() or path.suffix.lower() not in KNOWLEDGE_EXTENSIONS:
            continue
        rel = str(path.relative_to(root))
        try:
            target = safe_resolve_ws(root, rel)
        except ValueError:
            continue
        if not target.is_file():
            continue
        try:
            st = target.stat()
        except OSError:
            continue
        files.append({
            "path": rel,
            "name": target.name,
            "size": st.st_size,
            "mtime_ns": st.st_mtime_ns,
            "extension": target.suffix.lower(),
        })
    files.sort(key=lambda item: item["path"].lower())
    return {"files": files, "count": len(files), "limit": limit, "contextRoot": str(root)}


def read_knowledge_file(agent_id: str, rel_path: str) -> dict:
    rel = _validate_knowledge_path(rel_path)
    root = _agent_context_root(get_agent(agent_id))
    payload = read_file_content(root, rel)
    payload["contextRoot"] = str(root)
    return payload


def save_knowledge_file(agent_id: str, rel_path: str, content: str) -> dict:
    rel = _validate_knowledge_path(rel_path)
    if not isinstance(content, str):
        raise ValueError("content must be a string")
    data = content.encode("utf-8")
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f"File too large ({len(data)} bytes, max {MAX_FILE_BYTES})")

    root = _agent_context_root(get_agent(agent_id))
    target = safe_resolve_ws(root, rel)
    if not target.is_file():
        raise FileNotFoundError(f"Not a file: {rel}")
    fd = open_anchored_fd(root, target, want_dir=False)
    os.close(fd)

    tmp_rel = str(Path(rel).parent / f".{target.name}.tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}")
    if tmp_rel.startswith("./"):
        tmp_rel = tmp_rel[2:]
    tmp_path = safe_resolve_ws(root, tmp_rel)
    write_fd = open_anchored_create_fd(root, tmp_path)
    try:
        with os.fdopen(write_fd, "wb", closefd=True) as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, target)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise
    st = target.stat()
    return {
        "ok": True,
        "path": rel,
        "size": st.st_size,
        "mtime_ns": st.st_mtime_ns,
        "contextRoot": str(root),
    }


def _load_missions() -> list[dict]:
    raw = _read_json(MISSIONS_FILE, {})
    if isinstance(raw, dict):
        raw = raw.get("missions", [])
    if not isinstance(raw, list):
        return []
    missions = [m for m in raw if isinstance(m, dict) and m.get("id") and m.get("agentId")]
    return missions


def _save_missions(missions: list[dict]) -> None:
    _atomic_write_json(MISSIONS_FILE, {"missions": missions})


def list_missions(agent_id: str) -> dict:
    get_agent(agent_id)
    missions = [m for m in _load_missions() if m.get("agentId") == agent_id]
    missions.sort(key=lambda item: float(item.get("createdAt") or 0), reverse=True)
    return {"missions": missions, "count": len(missions)}


def create_mission(agent_id: str, body: dict) -> dict:
    agent = get_agent(agent_id)
    if not isinstance(body, dict):
        raise ValueError("JSON object body required")
    title = str(body.get("title") or "").strip()
    if not title:
        raise ValueError("title is required")
    description = str(body.get("description") or "").strip()
    profile = str(body.get("profile") or agent.get("profile") or "default").strip()
    source_conversation_id = str(body.get("sourceConversationId") or "").strip() or None
    workdir = str(body.get("workdir") or "").strip() or None
    deliver_default = bool(agent.get("telegramThreadId"))
    deliver = body.get("deliverToTelegramThread", deliver_default)
    now = time.time()
    mission = {
        "id": f"mission_{uuid.uuid4().hex[:12]}",
        "agentId": agent["id"],
        "title": title,
        "description": description,
        "profile": profile,
        "sourceConversationId": source_conversation_id,
        "workdir": workdir,
        "deliverToTelegramThread": bool(deliver),
        "status": "queued",
        "createdAt": now,
        "updatedAt": now,
    }
    missions = _load_missions()
    missions.append(mission)
    _save_missions(missions)
    return mission


def hermes_status_payload() -> dict:
    try:
        from api.agent_health import build_agent_health_payload

        health = build_agent_health_payload()
    except Exception:
        health = {"alive": None, "details": {"reason": "unavailable"}}
    try:
        from api.profiles import list_profiles_api

        raw_profiles = list_profiles_api()
    except Exception:
        raw_profiles = []

    profiles = []
    for profile in raw_profiles if isinstance(raw_profiles, list) else []:
        if not isinstance(profile, dict):
            continue
        name = str(profile.get("name") or "")
        if not name:
            continue
        running = bool(profile.get("gateway_running"))
        model = profile.get("model") or profile.get("default_model") or profile.get("default_model_provider")
        profiles.append({
            "name": name,
            "gateway": "running" if running else "stopped",
            "model": model,
        })

    targets = [
        {
            "name": agent["name"],
            "agentId": agent["id"],
            "chatId": agent["telegramChatId"],
            "threadId": agent["telegramThreadId"],
        }
        for agent in list_agents()
    ]
    return {
        "defaultGatewayRunning": health.get("alive") is True,
        "profiles": profiles,
        "telegramTargets": targets,
        "health": {
            "alive": health.get("alive"),
            "state": (health.get("details") or {}).get("state") if isinstance(health.get("details"), dict) else None,
            "reason": (health.get("details") or {}).get("reason") if isinstance(health.get("details"), dict) else None,
        },
    }
