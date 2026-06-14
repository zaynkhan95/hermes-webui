from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
UI_JS = (REPO / "static" / "ui.js").read_text(encoding="utf-8")


def _function_body(src: str, signature: str) -> str:
    start = src.index(signature)
    brace = src.index("{", start)
    depth = 0
    for i in range(brace, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[start : i + 1]
    raise AssertionError(f"function body not found: {signature}")


def test_reduced_motion_and_haptic_helpers_are_progressive_enhancement():
    reduced = _function_body(UI_JS, "function _prefersReducedMotion")
    haptic = _function_body(UI_JS, "function _triggerHaptic")

    assert "matchMedia('(prefers-reduced-motion: reduce)')" in reduced
    assert "try{" in reduced and "catch(_)" in reduced
    assert "_prefersReducedMotion()" in haptic
    assert "typeof navigator==='undefined'" in haptic
    assert "typeof navigator.vibrate!=='function'" in haptic
    assert "window.__HERMES_DESKTOP__" in haptic
    assert "desktopBridge.haptic({duration})" in haptic
    assert "navigator.vibrate(duration)" in haptic
    assert "return false" in haptic


def test_smooth_bottom_scroll_is_explicit_reduced_motion_safe_and_latched():
    set_bottom = _function_body(UI_JS, "function _setMessageScrollToBottom")
    scroll = _function_body(UI_JS, "function scrollToBottom")
    pinned = _function_body(UI_JS, "function scrollIfPinned")
    settle = _function_body(UI_JS, "function _settleMessageScrollToBottom")

    assert "function _setMessageScrollToBottom(options)" in set_bottom
    assert "options&&options.smooth" in set_bottom
    assert "!_prefersReducedMotion()" in set_bottom
    assert "typeof el.scrollTo==='function'" in set_bottom
    assert "_programmaticScroll=true" in set_bottom
    assert "el.scrollTo({top:el.scrollHeight,behavior:'smooth'})" in set_bottom
    assert "let _smoothScrollToken=0;" in UI_JS
    assert "const token=++_smoothScrollToken" in set_bottom
    assert "try{" in set_bottom
    assert "catch(_)" in set_bottom
    assert "_smoothScrollToken++" in set_bottom
    assert "el.scrollTop=el.scrollHeight" in set_bottom
    assert "if(token!==_smoothScrollToken) return;" in set_bottom
    assert "_releaseProgrammaticScroll()" in set_bottom
    assert "setTimeout(()=>" in set_bottom
    assert "},360)" in set_bottom

    assert "_setMessageScrollToBottom({smooth:true})" in scroll
    assert "_settleMessageScrollToBottom(true,{afterSmooth:true})" in scroll
    assert "_setMessageScrollToBottom({smooth:true})" not in pinned
    assert "_settleMessageScrollToBottom(false)" in pinned
    assert "[0,16,80,180]" in settle
    assert "[360,420,520,700]" in settle
    assert "if(options&&options.afterSmooth) return;" in settle


def test_todo_completion_haptics_are_batched_and_not_panel_dependent():
    schedule = _function_body(UI_JS, "function scheduleTodosRefresh")
    check = _function_body(UI_JS, "function _checkAndFireTodoHaptic")
    completed = _function_body(UI_JS, "function _todoIsCompleted")
    sync_seen = _function_body(UI_JS, "function _syncCompletedTodoSeenSet")
    hydrate = _function_body(UI_JS, "function _hydrateTodosFromSession")
    reset_scroll = _function_body(UI_JS, "function _resetScrollDirectionTracker")

    assert "let _todosCompletedIdsSeen=new Set();" in UI_JS
    assert "item.status==='completed'" in completed
    assert "_triggerHaptic(30)" in check
    assert "newlyCompleted" in check
    assert "_todosCompletedIdsSeen.add(id)" in check
    assert "_todosCompletedIdsSeen.delete(id)" in check

    raf_haptic_idx = schedule.index("_checkAndFireTodoHaptic(S.todos);")
    panel_idx = schedule.index("if(!_todosPanelIsActive()) return;")
    assert raf_haptic_idx < panel_idx
    assert schedule.count("_checkAndFireTodoHaptic(S.todos);") == 2

    assert "_syncCompletedTodoSeenSet(S.todos);" in hydrate
    assert hydrate.index("_syncCompletedTodoSeenSet(S.todos);") > hydrate.index("S.todos=[]")
    assert "_todosCompletedIdsSeen=new Set();" in sync_seen
    assert "_syncCompletedTodoSeenSet([]);" in reset_scroll
