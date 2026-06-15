# Kanban Loop Workflow

Hermes WebUI includes a profile-local skill template for a bounded
"Claude loops"-style workflow. It uses Kanban as the durable queue, Todos as
per-conversation scratch state, and explicit approval gates before any
conversation follow-up becomes a Kanban card.

## Install the skill

Preview the bundled template:

```bash
curl http://127.0.0.1:8787/api/kanban-loop/skill
```

Install or refresh it in the active Hermes profile:

```bash
curl -X POST http://127.0.0.1:8787/api/kanban-loop/skill/install \
  -H 'Content-Type: application/json' \
  -d '{}'
```

The skill is written to:

```text
<active-profile-home>/skills/workflows/conversation-to-kanban-triage/SKILL.md
```

It does not change Kanban storage, create tasks by itself, or run the Kanban
dispatcher.

## Operating model

- Use Kanban for durable cross-conversation work.
- Use Todos for the current conversation's temporary checklist.
- Capture conversation follow-ups into `triage` first.
- Move only fully specified work to `ready`.
- Keep `running` owned by active work or the dispatcher.
- Use `blocked` when a card needs human input, credentials, external state, or
  clearer scope.
- Mark `done` only with evidence.

Recommended WIP limits:

- 1-2 `running` tasks per domain/profile.
- 3-5 `ready` tasks total.

## Suggested routines

Morning Review:

- Summarize `running`, `blocked`, and high-priority `triage`.
- Recommend the top 3 tasks for today.
- Ask which cards should move to `ready`.

Conversation Closeout:

- Run the skill at the end of substantial conversations.
- Promote approved durable follow-ups to Kanban.
- End with a handoff summary.

Evening Sweep:

- Find stale `running` work.
- Move stuck work to `blocked` only with a clear reason and approval.
- Summarize completed work and unresolved decisions.
