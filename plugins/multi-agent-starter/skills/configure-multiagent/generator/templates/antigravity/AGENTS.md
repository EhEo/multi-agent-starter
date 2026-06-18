# Antigravity MultiAgent Orchestration — Operating Rules

## External/Paid Model Approval

- Do not run external or paid model CLIs, MCPs, or agent bridges without explicit user approval for that specific task.
- This includes, but is not limited to, `claude`, `gemini`, `openai`, `llm`, Claude Code MCP, Gemini MCP, and similar tools.
- A request to translate, summarize, review, research, or process a large file does not imply approval to use external paid models.
- Before using an external paid model, state the exact tool/model, why it is needed, and that it may consume tokens, quota, or money. Wait for explicit approval.
- Local shell commands, file parsing, format validation, current Antigravity reasoning, and edits inside this workspace are allowed unless the user says otherwise.

## Architecture

```
Orchestrator (Antigravity session — agy/IDE, Gemini 3.1 Pro High — internal reasoning)
└── Worker Pool (separate worker/model calls — approval required)
    ├── claude-main     main coding · debugging · design · architecture · strategy
    ├── codex-main      bounded implementation · analysis · tests · local verification
    └── codex-critic    output review · adversarial critique (independent of the Gemini orchestrator)
```

멀티모달(이미지/스크린샷)·긴 문서는 **오케스트레이터(Gemini 3.1 Pro High)가 직접** 처리한다 — 같은 벤더의 `gemini` 워커는 두지 않는다(독립성 이득 없음).

**Important**: Antigravity Orchestrator's internal reasoning is not a worker. A separate `claude-main`, `codex-main`, or `codex-critic` call is a worker/model call and must pass the approval gate for the task. 워커 호출은 `_shared/backends.json` + `python3 _shared/adapters/call_worker.py <role> <brief-file>` 디스패처를 거친다.

## Task Lifecycle

1. Create `tasks/<task-name>/task.md` (`status: pending`).
2. Read `_shared/routing.md` and choose the minimum worker set.
3. Confirm **target_repo** when the task will produce external files:
   - If `codex-main` is planned, or the task creates code, docs, or images for another repo, ask for `target_repo` before filling `task.md`.
   - If the user says there is no external target, or the task is analysis/review/planning only, keep outputs under `tasks/<task>/artifacts/`.
   - If the user already provided a path, do not ask again.
4. Record explicit worker approvals in `task.md` before any worker call.
5. Write each worker's brief **exactly at `tasks/<task>/workers/<role>/brief.md`** (Korean <= 1200 chars / English <= 240 words). Use a per-worker folder — do NOT flatten to `<role>_brief.md`.
6. Run the approved worker and save the original response **at `tasks/<task>/workers/<role>/result.md`** (same per-worker folder).
7. Execute the `result.md` Verification Checklist.
8. Append verification results to `log.md` with `[VERIFICATION]`. When the task is finished, update `status` in `task.md` to `done`.
9. On completion, append reusable lessons only when they are genuinely reusable:
   - System-level lessons: `_shared/learnings.md`
   - Project-specific lessons: `_local/learnings.md` (not loaded unless explicitly requested)

> When resuming an existing task, start with `_shared/orchestrator-rules.md` section 3 re-entry protocol, not step 1.

## Context Rules

| File | Limit | Purpose |
|------|-------|---------|
| `context.md` | Korean <= 1500 chars / English <= 300 words | Current snapshot only, not history |
| `brief.md` | Korean <= 1200 chars / English <= 240 words | Only what the worker needs |
| `sources/` | Unlimited | Source material, referenced by path |
| `artifacts/` | Unlimited | Raw outputs and generated files |

Measurement:

```bash
wc -m tasks/<task>/context.md
wc -w tasks/<task>/context.md
```

If `context.md` exceeds the limit, append history to `log.md`, then keep only the current snapshot. Never inline long source files into `context.md` or `brief.md`; pass paths.

## Approval Gate

- Never call a worker that is missing from `workers_approved`.
- Worker approval is task-specific and includes purpose and any external write scope.
- Antigravity Orchestrator internal reasoning does not require approval.
- External paid model tools still require explicit user approval even if the task is already created.

## Verification

Before accepting a worker result, execute the `result.md` Verification Checklist and append the result to `log.md`.

Default checks:
- [ ] output matches `brief.md` `Output Format`
- [ ] referenced paths exist
- [ ] `task.md` constraints are satisfied
- [ ] `Do NOT` items are not violated

## log.md Rules

- Append-only. Do not edit or delete prior log entries.
- Format: `[YYYY-MM-DD HH:MM] [TAG] content`
- Allowed tags: `DECISION | WORKER_CALL | VERIFICATION | ERROR | APPROVAL | COMPLETE`

## Worker File Write Policy

| Worker | Default write permission | External repo write |
|--------|--------------------------|---------------------|
| codex-main | `tasks/<task>/` outputs/diffs | Conditional |
| codex-critic | None; Orchestrator records response | Never |
| claude-main | tasks/<task>/ 내부(외부는 4조건) | 조건부 |

### `write_scope` Values

- `none` — no writes
- `tasks-only` — write only inside `tasks/<task>/`
- `"src/**, tests/**"` style patterns — external repo paths allowed only when all 4 conditions below are met

### Worker External Repo Write Conditions (claude-main / codex-main)

All 4 are required:

1. `brief.md` includes `target_repo: <absolute path>`.
2. `brief.md` includes `write_scope: <allowed path pattern>`.
3. `task.md` `workers_approved` includes the worker and the approved `write_scope`.
4. `log.md` has a separate `[APPROVAL]` entry for external write approval.

If any condition is missing, the worker writes only inside `tasks/<task>/`, preferably as a diff or patch for user/orchestrator application.

Workers must never edit `_shared/`, `_templates/`, or another task folder unless the current task is explicitly a system maintenance task.

## AGENTS.md Scope

These rules apply when Antigravity is working in `<설치한-폴더>` or its subdirectories. Do not copy this orchestration policy into unrelated projects.
