"""Built-in Kanban loop workflow skill template.

The WebUI does not own Hermes Agent's skill runtime. This module only provides
the profile-local skill content that users can install through the WebUI skills
API. The generated skill is intentionally instruction-only: it captures the
bounded Kanban loop operating model without changing Kanban persistence or
dispatch behavior.
"""

from __future__ import annotations


SKILL_NAME = "conversation-to-kanban-triage"
SKILL_CATEGORY = "workflows"
SKILL_DESCRIPTION = (
    "Extract durable follow-up tasks from Hermes conversations into Kanban "
    "triage with human approval."
)

STATUS_FLOW = ("triage", "todo", "ready", "running", "blocked", "done")
WIP_LIMITS = {
    "running_per_domain": "1-2",
    "ready_total": "3-5",
}
ROUTINES = ("Morning Review", "Conversation Closeout", "Evening Sweep")


def skill_content() -> str:
    """Return the complete SKILL.md body for profile-local installation."""

    status_flow = "\n".join(f"- `{status}`" for status in STATUS_FLOW)
    routines = "\n".join(f"- {routine}" for routine in ROUTINES)
    return f"""---
name: {SKILL_NAME}
description: {SKILL_DESCRIPTION}
tags: kanban, triage, todos, workflow, loops
platforms: webui
---

# Conversation To Kanban Triage

Use this skill when a Hermes conversation has produced possible follow-up work
that should survive beyond the current chat. The goal is to keep Kanban clean
and trusted: extract fewer, better cards instead of turning every idea into
board noise.

## Operating Model

- Kanban is the durable cross-conversation queue.
- Todos are temporary scratch state for the active conversation only.
- New conversation-derived cards default to `triage`.
- Human approval is required before creating, moving, or dispatching cards.
- Do not run the Kanban dispatcher from this skill.
- Keep work in progress low: at most {WIP_LIMITS["running_per_domain"]} running
  tasks per domain/profile and {WIP_LIMITS["ready_total"]} ready tasks total.

## Status Flow

{status_flow}

Use statuses this way:

- `triage`: captured from a conversation, not yet committed.
- `todo`: accepted work, but not ready to run.
- `ready`: fully specified and safe for an agent or dispatcher.
- `running`: actively being worked; normally owned by the dispatcher/worker.
- `blocked`: waiting on human input, credentials, external state, or clearer
  scope.
- `done`: completed with evidence such as tests, files changed, PR, summary, or
  manual verification.

## Extraction Rules

Review the current conversation, or the named session if the user supplied one.
Extract only actionable follow-ups. Ignore vague ideas, duplicate asks, tasks
already completed in the conversation, and items that lack a concrete outcome.

Before proposing new cards, inspect the existing Kanban board for likely
duplicates by title, description, workspace, and acceptance criteria. Prefer
updating or commenting on an existing card over creating a near-duplicate.

## Candidate Shape

For each candidate, produce:

- title: short imperative phrase.
- description: concise context and source conversation summary.
- acceptance_criteria: bullet list of observable completion checks.
- source_session: conversation title or session id when available.
- workspace: repo or workspace path when available.
- profile: suggested Hermes profile/domain.
- priority: 0-3, where 3 is urgent/high leverage.
- blockers: missing decisions, credentials, external waits, or unclear scope.
- suggested_status: default `triage`.

## Approval Gate

Show the candidate list and ask for explicit approval before creating cards.
Accept approvals such as "create all", "create 1 and 3", or "skip". If the user
does not approve, do not write to Kanban.

When creating cards:

- Create them in `triage` unless the user explicitly chooses another status.
- Never create directly in `running`.
- Never auto-dispatch newly created cards.
- Add source context in the card body so the task can be understood later.
- Finish with a concise summary of created, skipped, duplicate, and blocked
  items.

## Bounded Routines

{routines}

Morning Review:

- Summarize `running`, `blocked`, and high-priority `triage`.
- Recommend today's top 3 tasks.
- Ask which cards, if any, should move to `ready`.

Conversation Closeout:

- Run this skill at the end of substantial conversations.
- Promote approved durable follow-ups to Kanban.
- End with a handoff summary for the conversation.

Evening Sweep:

- Find stale `running` work.
- Move stuck work to `blocked` only with a clear reason and user approval.
- Summarize completed work and unresolved decisions.

## Safety Constraints

- Do not modify Kanban persistence or schema.
- Do not delete or archive cards unless the user explicitly asks.
- Do not expose secrets from conversation content in card titles or descriptions.
- If a task depends on credentials, private logs, or destructive commands, mark
  it `blocked` or keep it in `triage` until the user confirms the path forward.
"""


def metadata() -> dict:
    """Return a compact description for API clients."""

    return {
        "name": SKILL_NAME,
        "category": SKILL_CATEGORY,
        "description": SKILL_DESCRIPTION,
        "status_flow": list(STATUS_FLOW),
        "wip_limits": dict(WIP_LIMITS),
        "routines": list(ROUTINES),
        "guards": [
            "human approval before card creation",
            "new cards default to triage",
            "no automatic dispatcher run",
            "no direct running status creation",
        ],
    }
