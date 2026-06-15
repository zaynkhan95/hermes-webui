from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SESSIONS_JS = (ROOT / "static" / "sessions.js").read_text(encoding="utf-8")
PANELS_JS = (ROOT / "static" / "panels.js").read_text(encoding="utf-8")
STYLE_CSS = (ROOT / "static" / "style.css").read_text(encoding="utf-8")


def _block(start_marker: str, end_marker: str) -> str:
    start = SESSIONS_JS.find(start_marker)
    assert start != -1, f"{start_marker} not found"
    end = SESSIONS_JS.find(end_marker, start)
    assert end != -1, f"{end_marker} not found after {start_marker}"
    return SESSIONS_JS[start:end]


def test_profile_filter_control_is_rendered_in_responsive_slots():
    render_block = _block("function _renderSessionProfileFilterControl", "function _normalizeMessageForCliImportComparison")
    index_html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")

    assert "session-profile-filter-bar" in render_block
    assert "titlebarProfileFilterSlot" in render_block
    assert "sidebarProfileFilterSlot" in render_block
    assert "function _sessionProfileFilterTargetSlot()" in SESSIONS_JS
    assert "window.matchMedia('(max-width: 640px)').matches" in SESSIONS_JS
    assert "sessionProfileFilter" in render_block
    assert "Filter conversations by profile" in render_block
    assert "All profiles" in render_block
    assert "Active: ${activeName}" in render_block
    assert "select.onchange = () => _setSessionProfileFilter(select.value);" in render_block
    assert 'id="titlebarProfileFilterSlot"' in index_html
    assert 'id="sidebarProfileFilterSlot"' in index_html
    assert ".session-profile-filter-bar" in STYLE_CSS
    assert ".session-profile-filter-select" in STYLE_CSS
    assert ".sidebar-profile-context-slot" in STYLE_CSS
    assert ".app-titlebar-context{display:none;}" in STYLE_CSS


def test_profile_filter_uses_aggregate_fetch_only_when_needed():
    refresh_block = _block("async function _runRenderSessionListRefresh", "async function _drainRenderSessionListQueue")
    set_block = _block("async function _setSessionProfileFilter(value)", "function _sortSessionProfileOptions")

    assert "const allProfilesQS = _showAllProfiles ? '?all_profiles=1' : ''" in refresh_block
    assert "_syncShowAllProfilesFromSessionProfileFilter();" in refresh_block
    assert "value !== SESSION_PROFILE_FILTER_ACTIVE" in SESSIONS_JS
    assert "_syncShowAllProfilesFromSessionProfileFilter();" in set_block
    assert "_persistSessionProfileFilter();" in set_block
    assert "renderSessionList();" in set_block


def test_specific_profile_filter_switches_active_profile_context_only_before_chat_starts():
    set_block = _block("async function _setSessionProfileFilter(value)", "function _sortSessionProfileOptions")

    assert "const selectedName = _sessionProfileFilterSelectedName(next);" in set_block
    assert "typeof switchToProfile === 'function'" in set_block
    assert "!_sessionProfilesEquivalent(selectedName, S.activeProfile || 'default')" in set_block
    assert "const hasStartedConversation = typeof _activeConversationHasStarted === 'function' && _activeConversationHasStarted();" in set_block
    assert "const profileSwitchAllowed = shouldSwitchProfile && !hasStartedConversation;" in set_block
    assert "await switchToProfile(selectedName);" in set_block
    assert "return;" in set_block[set_block.find("await switchToProfile(selectedName);"):]
    assert "resetSessionProfileFilterToAll();" not in set_block


def test_specific_profile_filter_preserves_root_alias_matching():
    roots_block = _block("function _sessionRootProfileNames", "function _sessionProfilesEquivalent")
    equivalent_block = _block("function _sessionProfilesEquivalent", "function _sessionMatchesSelectedProfile")
    render_cache_block = _block("function renderSessionListFromCache", "function _sessionAttentionState")

    assert "if(S.activeProfileIsDefault)" in roots_block
    assert "if(p && p.is_default)" in roots_block
    assert "roots.has(left) && roots.has(right)" in equivalent_block
    assert "sourceFiltered.filter(s=>_sessionMatchesSelectedProfile(s,_sessionProfileFilter))" in render_cache_block
    assert "SESSION_PROFILE_FILTER_ACTIVE) return _sessionProfilesEquivalent" in SESSIONS_JS


def test_profile_switch_keeps_all_profiles_filter():
    assert "resetSessionProfileFilterToAll();" in PANELS_JS
    assert "function resetSessionProfileFilterToAll()" in SESSIONS_JS
    assert "_sessionProfileFilter = SESSION_PROFILE_FILTER_ALL;" in SESSIONS_JS
    assert "let _sessionProfileFilter = SESSION_PROFILE_FILTER_ALL;" in SESSIONS_JS
    assert "let _showAllProfiles = true;" in SESSIONS_JS


def test_profile_switch_is_blocked_after_conversation_started():
    start = PANELS_JS.find("async function switchToProfile(name) {")
    assert start != -1
    end = PANELS_JS.find("function openProfileCreate", start)
    assert end != -1
    switch_block = PANELS_JS[start:end]
    assert "function _activeConversationHasStarted()" in PANELS_JS
    assert "if (_activeConversationHasStarted())" in switch_block
    assert "profile_switch_started_blocked" in switch_block


def test_hermes_profile_switch_is_disabled_but_list_filter_stays_enabled_when_conversation_started():
    assert "function syncProfileLockState()" in PANELS_JS
    assert "chip.disabled = locked;" in PANELS_JS
    assert "select.disabled = false;" in PANELS_JS
    assert "select.classList.remove('locked');" in PANELS_JS
    assert "if (_activeConversationHasStarted())" in PANELS_JS[PANELS_JS.find("function toggleProfileDropdown()"):PANELS_JS.find("function closeProfileDropdown()")]
    assert "if(typeof syncProfileLockState === 'function') syncProfileLockState();" in SESSIONS_JS
    ui_js = (ROOT / "static" / "ui.js").read_text(encoding="utf-8")
    assert "if(typeof syncProfileLockState === 'function') syncProfileLockState();" in ui_js
    assert ".composer-profile-chip.locked" in STYLE_CSS


def test_loading_session_restores_its_profile_context():
    load_block = _block("async function loadSession(sid)", "// ── Handoff hint logic")
    assert "restoreProfileContextForSession(S.session)" in load_block
    assert "if (_loadingSessionId !== sid) return;" in load_block[load_block.find("restoreProfileContextForSession(S.session)"):]
    assert "async function restoreProfileContextForSession(session)" in PANELS_JS
    restore_block = PANELS_JS[PANELS_JS.find("async function restoreProfileContextForSession(session)"):PANELS_JS.find("async function loadProfilesPanel")]
    assert "api('/api/profile/switch'" in restore_block
    assert "S.activeProfile = data.active || target;" in restore_block
    assert "resetSessionProfileFilterToAll();" in restore_block
    assert "_refreshProfileSwitchBackground(gen);" in restore_block
