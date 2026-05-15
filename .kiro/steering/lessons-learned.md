---
inclusion: auto
description: Project-specific patterns, preferences, and lessons learned over time (user-editable)
---

# Lessons Learned

This file captures project-specific patterns, coding preferences, common pitfalls, and architectural decisions that emerge during development. It serves as a workaround for continuous learning by allowing you to document patterns manually.

**How to use this file:**
1. The `extract-patterns` hook will suggest patterns after agent sessions
2. Review suggestions and add genuinely useful patterns below
3. Edit this file directly to capture team conventions
4. Keep it focused on project-specific insights, not general best practices

---

## Project-Specific Patterns

*Document patterns unique to this project that the team should follow.*

### Example: API Error Handling
```typescript
// Always use our custom ApiError class for consistent error responses
throw new ApiError(404, 'Resource not found', { resourceId });
```

---

## Code Style Preferences

*Document team preferences that go beyond standard linting rules.*

### Example: Import Organization
```typescript
// Group imports: external, internal, types
import { useState } from 'react';
import { Button } from '@/components/ui';
import type { User } from '@/types';
```

---

## Kiro Hooks

### `install.sh` is additive-only — it won't update existing installations
The installer skips any file that already exists in the target (`if [ ! -f ... ]`). Running it against a folder that already has `.kiro/` will not overwrite or update hooks, agents, or steering files. To push updates to an existing project, manually copy the changed files or remove the target files first before re-running the installer.

### README.md mirrors hook configurations — keep them in sync
The hooks table and Example 5 in README.md document the action type (`runCommand` vs `askAgent`) and behavior of each hook. When changing a hook's `then.type` or behavior, update both the hook file and the corresponding README entries to avoid misleading documentation.

### Prefer `askAgent` over `runCommand` for file-event hooks
`runCommand` hooks on `fileEdited` or `fileCreated` events spawn a new terminal session every time they fire, creating friction. Use `askAgent` instead so the agent handles the task inline. Reserve `runCommand` for `userTriggered` hooks where a manual, isolated terminal run is intentional (e.g., `quality-gate`).

---

## Environment & Tooling

### Shell is CMD, not PowerShell or bash
This workspace runs on Windows with CMD as the default shell. Bash is not available (no WSL). PowerShell commands must be wrapped with `powershell -ExecutionPolicy Bypass -Command "..."` or written to a `.ps1` file and invoked with `powershell -ExecutionPolicy Bypass -File script.ps1`. For multi-line scripts, the temp-file approach is more reliable than inline commands with escaped quotes.

---

## Common Pitfalls

*Document mistakes that have been made and how to avoid them.*

### Stale session state bleeds across turns in ProjectSqlAgent
In multi-turn sessions, `query_context`, `project_validation_result`, and other state keys persist from previous turns. When a new `empcode: / message:` pair arrives in the same session, the orchestrator may skip re-running `query_context_agent` if it sees existing state — causing the new question to inherit the old metric/filter. Any new flow that reads from session state (e.g., `awaiting_query`, confirmation flow) must explicitly clear or re-derive stale keys like `query_context`, `faq_match_result`, `reference_sql`, `selected_projects`, and `scope_filters` when a genuinely new question is detected. Test multi-turn scenarios where the user changes metric or project between turns.

### `__pycache__/*.pyc` files block git pull on deploy machines
Some `.pyc` files were historically tracked in git. Although commit `1d02f1e` removed them and `.gitignore` now excludes `__pycache__/`, any machine that still has locally modified `.pyc` files will get `error: Your local changes would be overwritten by merge` on `git pull`. Fix: `git checkout -- **/__pycache__/ && git pull`. This has happened repeatedly on both the Windows dev machine and the Ubuntu deploy server. If it keeps recurring, run `git rm -r --cached **/__pycache__/` on the affected machine to fully untrack them.

### Empcode parsing has two independent code paths — both must handle all input formats
`ProjectSqlAgent._run_async_impl` has **two separate empcode parsing blocks**: first-turn (~line 565) and follow-up turn (~line 630). They are not shared code. When a new input format is added (JSON, comma-separated, etc.) or a parsing bug is fixed, **both blocks must be updated** or they silently diverge. The follow-up block is easy to miss because it's inside a `for event in reversed(ctx.session.events)` loop. Currently supported formats: JSON (`{"empcode":"XX", "message":"YY"}`), comma-separated single-line (`empcode:XX, message:YY`), and newline-separated (`empcode: XX\nmessage: YY`).

### A2A multi-turn confirmation breaks if master agent doesn't preserve session_id
The confirmation flow in `ProjectSqlAgent` relies on `project_validation_result` persisting in session state between turns. When called via A2A, session lookup uses `metadata.session_id` or `context.context_id`. If the master agent sends a **different session_id per turn**, each reply creates a fresh `InMemorySessionService` session with no prior state → `pending_confirmation` is False → the orchestrator re-runs the full pipeline instead of resolving the confirmation → infinite confirmation loop. The fallback `_extract_confirmation_context_from_history` also fails because the new session has no prior events. **Any A2A caller must send the same `session_id` for all turns in a conversation.** If that can't be guaranteed, the orchestrator needs a stateless confirmation fallback.

### A2A confirmation replies loop when master agent re-sends empcode every turn
Even with correct session_id, if the master agent wraps every follow-up message with empcode (e.g., `empcode: AP005032\nmessage: ทั้งหมด`), the orchestrator's first-turn parser fires instead of the follow-up path. The `_is_new_question` check sees `empcode:` + `message:` and treats it as a new question. Although `_looks_like_confirmation_reply("ทั้งหมด")` prevents state clearing, the orchestrator still takes the first-turn flow and re-runs `project_validate` → which finds the same ambiguous projects → asks for confirmation again → infinite loop. **Fix**: The orchestrator should check `pending_confirmation` in state BEFORE deciding first-turn vs follow-up routing. If `needs_confirmation` is True and the message body (after stripping empcode) looks like a confirmation reply, route to confirmation handling regardless of whether empcode is present.

### No class-level constants on Pydantic BaseAgent subclasses
`ProjectSqlAgent` extends ADK's `BaseAgent` which is a Pydantic model. Any class-level attribute that isn't a declared Pydantic field (e.g., `_GENERIC_METRIC_KEYWORDS = {"a", "b"}`) gets wrapped as a `ModelPrivateAttr`. Operations like `x in cls._MY_SET` then fail with `argument of type 'ModelPrivateAttr' is not iterable`. Always use local variables inside methods or module-level constants instead of class-level sets/dicts/lists on `ProjectSqlAgent` or any `BaseAgent`/`LlmAgent` subclass.

### LLM sub-agents hallucinate on empty iteration targets — guard in the orchestrator
When the orchestrator passes state with an empty list that the sub-agent's prompt says to iterate over (e.g., `filter_type: "brand"` with `brands: []`), the LLM invents something to process — like searching for the literal word "brand" as a brand name. This applies to any sub-agent whose prompt contains "for EACH X in list, do Y". **Always add a deterministic check in the orchestrator before calling the sub-agent**: if the list is empty and there's nothing to validate, skip the sub-agent and produce a synthetic passthrough result. Don't rely on the LLM to handle the "nothing to do" case gracefully. See `_has_no_items_to_validate()` and `_synthetic_passthrough_validation()` in `ProjectSqlAgent` for the pattern.

### LLM sub-agents ignore access-control branching in prompts — enforce deterministically
The `PROJECT_VALIDATE_INSTRUCTION` prompt says: for `access_level = "project_filter"` with `filter_type = "project"`, "Match against projectcode_list only (no DB query needed)." In practice, the LLM ignores this and queries `dim_project` anyway — finding projects the user can't access, then asking them to confirm. **Any access-control decision that depends on the LLM reading a conditional branch in a prompt is unreliable.** Add a deterministic Python check in the orchestrator *before* calling the sub-agent. See `_check_project_access_deterministic()` in `ProjectSqlAgent`: it matches requested project names against `projectcode_list` in Python and either denies immediately or produces a pre-filtered result, so the LLM never gets a chance to bypass the access boundary. Apply this pattern to any future access-control logic — don't trust the LLM to follow "if access_level == X, then do Y" instructions.

### Guard empty/missing required inputs before calling LLM sub-agents
When a required input (like `empcode`) is empty, the orchestrator should catch it and respond immediately instead of forwarding to an LLM sub-agent. Sending empty empcode to `emp_validate_agent` wastes an MCP/Redshift round-trip (~6 seconds) just to get "ไม่พบ empcode ในระบบ" — and the error message is confusing because the user never provided one. **Pattern**: Before calling any sub-agent that requires specific state values, add a deterministic guard in the orchestrator: check if the value exists, and if not, yield a helpful prompt asking the user to provide it. This is cheaper, faster, and gives a better UX than letting the LLM discover the missing input via a failed tool call.

### Metric clarification loses prior-turn context — avoid re-running upstream agents on replies
When the orchestrator asks "which metric?" and the user replies "ทั้งหมด", the `query_context_agent` re-runs on just that word and produces `filter_type: "none"` with empty filters — losing the project/brand from the original question. The `saved_qc` in the metric clarification handler partially mitigates this, but only for fields correctly extracted in the first pass. **Never trigger multi-turn clarification flows that re-run upstream agents on the reply.** Instead, patch the saved context deterministically in the orchestrator (like the metric map does) and skip re-running `query_context_agent`. This applies to any future clarification flow (time period, dimension, etc.).

### Prompt column references must match actual Redshift schema — verify before deploying
The `TEXT_TO_SQL_INSTRUCTION` prompt references `SUM(total_spending)` but the actual column in `marketing_perf_daily` has a different name. When the LLM follows the prompt's example SQL, it generates queries with non-existent columns → runtime errors. **Any time a column name is added to or changed in a prompt, verify it against the actual Redshift schema first.** The FAQ SQL entries in `analytics_ai.faq_sql` are a reliable reference for correct column names since they are known-working queries.

### `not_found` ≠ `no_access` — always branch on access_level before interpreting validation status
The `project_validate_agent` returns `status: "not_found"` when a brand/zone/project doesn't exist in `dim_project`, and `status: "no_access"` when the user can't access it. For `access_level: "all"` users, `not_found` means the data simply doesn't exist — it is **not** a permission issue. But multiple orchestrator methods (`_is_comparison_partially_denied`, `_build_comparison_denial_message`, `_is_fully_denied`) originally treated both statuses identically, causing full-access users to see "ไม่มีสิทธิ์เข้าถึง" (no access) when the correct message is "ไม่พบในระบบ" (not found). **Rule**: Any code that interprets `proj_data["projects"][*]["status"]` must check `access_level` first. For `access_level: "all"`, only `"no_access"` is a permission denial; `"not_found"` is informational. For restricted levels (`bg_filter`, `project_filter`), both statuses can be treated as denials since the user may be probing outside their scope. This applies to every current and future method that reads validation status.

### `project_filter` access leaks data when queries use brand/zone/bg scope_filters without selected_projects
When a `project_filter` user queries by brand (e.g., "ข้อมูลของ Centro"), the `project_validate_agent` confirms the brand exists and passes `scope_filters.brands = ["Centro"]`. But if `selected_projects` is empty, `text_to_sql_agent` queries ALL projects of that brand — not just the user's allowed subset. This is a **data leakage bug** that applies to all non-project filter types (brand, zone, bg, mixed). **Rule**: For `project_filter` users, every filter_type handler in `PROJECT_VALIDATE_INSTRUCTION` must populate `selected_projects` with the intersection of the requested dimension and `projectcode_list`. The `TEXT_TO_SQL_INSTRUCTION` must always apply `WHERE projectno IN (projectcode_list)` as the ultimate access boundary, even when scope_filters are present. Defense-in-depth: both the scope validator and the SQL generator must enforce the boundary independently.

---

## Architecture Decisions

*Document key architectural decisions and their rationale.*

### ADK Guardrails: Deterministic callbacks over LLM sub-agents
- **Decision**: Use deterministic Python functions (`before_agent_callback`, `after_model_callback`) for security guardrails instead of adding new LlmAgent sub-agents
- **Rationale**: Zero latency/cost overhead, deterministic blocking (not probabilistic), follows ADK's recommended callback patterns from their safety docs
- **Trade-offs**: Regex-based detection can't catch sophisticated obfuscated attacks — but the Redshift MCP `execute_query` runs in READ ONLY mode as a fallback safety net
- **Pattern**: Input validation → orchestrator-level check before pipeline. Output scrubbing → `after_model_callback` on the final-response agents only.

### ADK callback wiring: after_model_callback goes on agent_factory, not orchestrator
- **Decision**: Attach `after_model_callback` in `agent_factory.py` when constructing `LlmAgent` instances, not in the orchestrator
- **Rationale**: ADK callbacks are properties of `LlmAgent`, not `BaseAgent`. The orchestrator (`ProjectSqlAgent`) extends `BaseAgent` and manually calls `sub_agent.run_async(ctx)` — the callback fires inside the sub-agent's LLM loop automatically. No orchestrator changes needed for output guardrails.

### ProjectSqlAgent has 4 output paths to the user
When adding response-level guardrails or formatting, remember all 4 places that yield user-visible content:
1. `emp_validate_agent` — denial messages (LLM-generated)
2. Orchestrator deterministic messages — `_build_confirmation_message`, `_build_denial_message`, `_build_comparison_denial_message` (safe, Python-built)
3. `text_to_sql_agent` — query results formatted by LLM (needs output guardrail)
4. `sql_executor_agent` — FAQ SQL results formatted by LLM (needs output guardrail)
Only #3 and #4 need output scrubbing. #2 is deterministic Python. #1 rarely contains sensitive data but could be added later.

### A2A empcode: pass via session state, not message text
- **Decision**: The A2A executor (`executor_a2a.py`) injects `empcode` from `metadata.user_id` into `session.state["empcode"]` before the agent runs. The orchestrator checks state first, falling back to parsing `empcode:/message:` from text.
- **Rationale**: A2A callers shouldn't need to format messages with `empcode: XX\nmessage: YY`. Passing identity via session state is cleaner and separates auth context from user content.
- **Backward compatibility**: The legacy text-parsing path is preserved for `adk web` testing where messages are typed manually. Any new input channel should inject empcode into session state rather than embedding it in message text.

### Empcode/message parsing has 4 input paths — keep them in sync
The orchestrator parses empcode+message from user input in a priority chain: (1) session state (A2A), (2) JSON `{"empcode":"...","message":"..."}`, (3) comma-separated single-line `empcode:XX, message:YY`, (4) newline-separated `empcode: XX\nmessage: YY`. This chain exists in **two places**: the first-turn parser and the follow-up history parser. When adding a new format or changing parsing logic, both locations must be updated identically or one path will silently fail. Consider extracting a shared `_parse_empcode_message(text)` helper to avoid drift.

### Redshift MCP parallel tool calls cause "Session is not available" errors

When an `LlmAgent` (especially `project_validate_agent`) fires multiple `execute_query` calls in parallel, 2 out of 3 often fail with `ValidationException: Session is not available`. The MCP Redshift server uses a single session and can't handle concurrent statements. The LLM retries the failed calls, but by then the context is inconsistent — leading to non-deterministic results (e.g., zone "สยาม" sometimes resolves to "สยาม- วิทยุ - พระราม4" and sometimes returns `not_found`). **Mitigation**: (1) Instruct agents in their prompts to query one dimension at a time sequentially with explicit retry on "Session is not available". (2) Include a concrete example of correct order in the prompt (e.g., "validate brand Aspire → wait → validate brand Life → wait → validate zone อโศก → wait"). Vague instructions like "do not fire in parallel" are insufficient — the LLM needs the explicit sequential pattern spelled out.

### LLM sub-agents store raw user input instead of DB-resolved values — post-process deterministically
The `project_validate_agent` prompt says to put DB-resolved zone names (e.g., "อโศก - พระราม9") in `scope_filters.zones`, but the LLM frequently stores the user's raw input ("อโศก") instead. This causes downstream `text_to_sql` to generate `LIKE '%พระราม 4%'` which doesn't match "พระราม4" (no space) in the data. **Pattern**: For any value that the LLM resolves from a DB lookup and passes downstream, add a deterministic post-processing step in the orchestrator that validates/corrects the value. See `_resolve_zone_names_in_scope_filters()` — it checks if `scope_filters.zones` values look like raw input (short, no separator) and attempts to replace them with resolved values from the `projects[]` array or `message` field. Apply this pattern to any future dimension where raw-vs-resolved mismatch could cause query failures.

### text_to_sql LLM invents filter clauses not in scope_filters — add explicit prohibitions
When `scope_filters` has incomplete data (e.g., only 1 of 2 zones resolved), the `text_to_sql` LLM compensates by adding filters not specified in scope_filters — like `bgno IN ('3')` — which massively broadens the query scope and returns wrong results. **Rule**: The `TEXT_TO_SQL_INSTRUCTION` must explicitly prohibit adding filter dimensions that aren't in scope_filters. For example: "NEVER add bgno to WHERE unless access_level is bg_filter or scope_filters.bgs is not empty." Simply listing what filters to use is not enough — the LLM needs explicit "do NOT add X" instructions for dimensions it might invent.

### Model sizing per sub-agent: match model capability to prompt complexity, not pipeline position
Not all sub-agents need the same model size. In `agent_factory.py`, agents are assigned either `model` (full-size) or `model_mini` based on task complexity:
- **Full model** (`gpt-5.4`): `project_validate_agent` (complex multi-step tool calling with sequential constraints, access control branching, zone resolution), `faq_match_agent` (reliable tool calling + intent matching across 123 FAQ entries), `text_to_sql_agent` (complex SQL generation with access filters).
- **Mini model** (`gpt-5.4-mini`): `emp_validate_agent` (mechanical query-and-parse), `query_context_agent` (pure JSON extraction, no tools), `sql_executor_agent` (run pre-built SQL, format results).
**Rule**: When adding a new sub-agent, assign the model based on prompt complexity and tool-calling reliability requirements — not just cost. Agents with conditional branching in prompts, sequential tool-call constraints, or complex output structures need the full model. Simple extract/format/execute agents work fine on mini. If an agent shows non-deterministic failures (skipped tool calls, ignored instructions), upgrading to the full model is the first thing to try before adding more prompt engineering.

### project_filter access: projectcode_list is the ultimate boundary, not brand/zone
- **Decision**: For `access_level = "project_filter"` users, `project_validate_agent` must populate `selected_projects` with the specific projects from `projectcode_list` that match the requested brand/zone/bg. `text_to_sql_agent` must always include `WHERE projectno IN (<projectcode_list>)` even when brand/zone filters are present.
- **Rationale**: Without this, a project_filter user asking "ยอด lead ของ Centro" would get data for ALL Centro projects (~30+), not just their allowed subset (e.g., 5). Brand/zone/bg filters narrow within `projectcode_list`, they never bypass it.
- **Where enforced**: Two places — (1) `PROJECT_VALIDATE_INSTRUCTION` populates `selected_projects` for project_filter users, (2) `TEXT_TO_SQL_INSTRUCTION` adds `projectno IN (...)` to every query. Both must be kept in sync. If either is missing, data leaks.
When an `LlmAgent` (especially `project_validate_agent`) fires multiple `execute_query` calls in parallel, 2 out of 3 often fail with `ValidationException: Session is not available`. The MCP Redshift server uses a single session and can't handle concurrent statements. The LLM retries the failed calls, but by then the context is inconsistent — leading to non-deterministic results (e.g., zone "สยาม" sometimes resolves to "สยาม- วิทยุ - พระราม4" and sometimes returns `not_found`). **Mitigation**: Instruct agents in their prompts to query one dimension at a time sequentially, or combine lookups into a single query. This is a recurring issue for any agent that uses the Redshift MCP toolset with multiple filter dimensions.

### Zone fuzzy matching is non-deterministic across LLM calls
User input "สยาม" must match DB value "สยาม- วิทยุ - พระราม4". The `project_validate_agent` uses `LIKE '%สยาม%'` which works at the SQL level, but the LLM sometimes returns `status: "not_found"` for the zone even when the query returned data — especially when it's recovering from failed parallel calls. For critical filter dimensions like zones, consider pre-resolving fuzzy matches deterministically in the orchestrator (Python) before passing to the LLM agent, rather than relying on the LLM to interpret query results correctly every time.

### FAQ table (`analytics_ai.faq_sql`) structure and known gaps
- Column names: `business_question_synonyms` (comma-separated Thai/English phrasings for matching) and `sql_stetment` (note: the typo is the actual column name — do NOT "fix" it in queries).
- All 121 existing FAQ entries cover **aggregate metrics by time period only** (e.g., "จำนวน lead ของเดือนนี้"). There are **no FAQ entries for dimension breakdowns** such as `type_of_lead_new`, `sub_type_of_lead`, `leadstatus`, brand-level, or zone-level splits.
- When adding new FAQ entries for dimension-based questions, the SQL must `GROUP BY` the dimension column (e.g., `type_of_lead_new`) and `business_question_synonyms` should include multiple phrasings covering Thai, English, formal, and casual variants.
- The `faq_match_agent` loads all `business_question_synonyms` first (no SQL), matches by intent, then fetches `sql_stetment` for the matched row using an exact `WHERE` clause. New synonyms must be unique enough to avoid ambiguous matches.

### "Previous period" date filters must use dim_date lookup, not arithmetic on current period
The `TEXT_TO_SQL_INSTRUCTION` provides date filter patterns for "this month" (`ap_m = SPLIT_PART(...)`) and "this year" (`ap_y = SPLIT_PART(...)`), but has no explicit pattern for "เดือนที่แล้ว" (previous month). Without it, the LLM non-deterministically either (a) copies the current-month filter from FAQ reference SQL verbatim, or (b) invents `ap_m - 1` which breaks in January (returns 0 instead of 12 with year rollback). The correct pattern uses `dim_date`: `WHERE (ap_y||LPAD(ap_m,2,'0'))::INT = (SELECT DISTINCT prev_ap_m FROM analytics_ai.dim_date WHERE calendar_date = CURRENT_DATE - 1)::INT`. **Rule**: Every relative time period ("เดือนที่แล้ว", "สัปดาห์ที่แล้ว", "ไตรมาสที่แล้ว") must have an explicit SQL pattern in the prompt using `dim_date` lookup columns. Never rely on arithmetic (`ap_m - 1`, `ap_w - 1`) because period boundaries don't wrap correctly. The FAQ SQL in `analytics_ai.faq_sql` already uses these patterns — copy them into the prompt as canonical examples.

### ADK prompt templates: use InstructionProvider functions, not raw strings with double braces
- **Decision**: All prompts that reference session state (`{empcode}`, `{query_context}`, etc.) use async `InstructionProvider` functions with `instructions_utils.inject_session_state()` instead of raw string constants.
- **Rationale**: ADK's `{key}` interpolation replaces valid identifiers from session state. But non-f-string prompts with `{{double_braces}}` for JSON examples send literal `{{` to the LLM, confusing it about expected output format. F-strings solve the state variable side but require `{{` for literal braces, creating a different confusion. InstructionProvider functions cleanly separate concerns: f-string for computed values (dates), `inject_session_state` for state keys, and plain `{` for JSON examples.
- **Pattern**: Define `async def my_instruction(context: ReadonlyContext) -> str`, use `r"""` raw strings for templates without computed values or `f"""` when mixing computed values + state keys, call `inject_session_state(template, context)`, and assign the function to the constant name: `MY_INSTRUCTION = my_instruction`.
- **Where**: `app/agents/prompts.py` — all 5 InstructionProvider functions follow this pattern.

### Store cross-turn pipeline metadata in top-level session state, not inside sub-agent output JSON
- **Decision**: `_original_query` (the user's question before confirmation) is stored as `ctx.session.state["_original_query"]`, not embedded inside `project_validation_result` JSON.
- **Rationale**: When the LLM re-runs `project_validate.run_async()` during confirmation, it overwrites `project_validation_result` via `output_key`. Any metadata stored inside that JSON is lost. Top-level state keys survive sub-agent re-runs because only the sub-agent's `output_key` is overwritten.
- **Rule**: Never store orchestrator-level metadata (original queries, flow phase markers, clarification context) inside a sub-agent's `output_key` JSON. Use separate top-level state keys prefixed with `_` (e.g., `_original_query`, `_awaiting_metric_clarification`, `_metric_clarification_qc`). Add them to both the state initialization block and `_clear_pipeline_state` stale keys list.

---

## Notes

- Keep entries concise and actionable
- Remove patterns that are no longer relevant
- Update patterns as the project evolves
- Focus on what's unique to this project
