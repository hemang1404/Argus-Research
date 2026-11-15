# Argus code audit and change list

Subject: `C:\coding\Argus`, commit `467b720` (v0.2.0b1, 2026-11-09), main branch, working tree clean apart from untracked `audit_reports/` and zip/jsonl artifacts. Date of audit: 2026-11-16.
Read-only: nothing under `C:\coding\Argus` was edited. All executions were done on a copy of `argus/`, `tests/`, `pyproject.toml` placed in the session scratchpad (so no `.argus/`, `__pycache__` or pytest cache was written into the repo). No model API, Docker, network, or `.env` access.

Conventions. Confidence tags: [V-exec] verified by running code; [V-read] verified by reading the cited lines; [INF] inference, not verified; [NOT-RETESTED] carried over from the earlier audit, not re-checked by me. File:line cites are into `C:\coding\Argus` unless stated.

---

## 0. What I actually ran

| Command (summarised) | Result |
|---|---|
| `pytest --collect-only` on the copy | 506 tests collected (62 test files). |
| Full offline suite on the copy, `--ignore=tests/test_real_host_integration.py` | **470 passed, 27 skipped, 8 failed** in 166 s. 5 failures are `test_packaging_and_wrapper.py` + `test_update.py::test_detect_install_method_source`, caused by my copy lacking `package.json`, `packages/` and `.git` (copy artefact, not a defect). The other two, `test_e2e_desktop.py::test_end_to_end_desktop_workflow` and `test_recovery_stream.py::test_recovery_dispatch_and_stream`, are **flaky**: re-running the pair twice, one failed and the other passed each time (`StopIteration` / `assert 2 >= 3` on SSE event count). [V-exec] Likely a race in the SSE stream endpoint (`argus/api/recovery.py:222`) [INF]. |
| 7 patch-engine probes (`python probe1.py` in scratchpad) | See B2, B3, B10. |
| 5 config/budget probes (`probe2.py`) | See B1, B7. |
| Import probe of every `src.*` module | See A.7. |
| `argus recover --help`, `argus mcp serve --help`, click command walk | See C-section README items. |

Coverage was not measured by me (the earlier audit reports 74% overall, `hybrid_localizer.py` 0%; I did not reproduce it).

---

## A. What Argus is today

### A.1 One-paragraph truth

Argus is a **local, single-file, test-gated recovery runtime for Python**. Given a failing test command it copies the project to an isolated workspace, asks an LLM for SEARCH/REPLACE edits to one target file, applies them through a tiered tolerant patch engine plus `ast.parse`, re-runs the test command, and on success stores a hash-pinned candidate that a human (or an agent via MCP) approves and applies atomically. Up to 3 attempts; attempts 1-2 use a "small" model, attempt 3 a "large" model. This is a **fixed cascade with failure-text feedback**, not an adaptive/learned router. [V-read: `argus/runtime/controller.py:1077-1131, 1765-1768`]

### A.2 Component map

| Component | Where | Status | Evidence |
|---|---|---|---|
| CLI (`run`/`recover`, `apply`, `approve`, `candidates`, `diff`, `provider`, `mcp`, `gateway`, `serve`, `tui`, `doctor`, `exec`, `update`, `init`, `setup`) | `argus/cli.py` (1390 lines) | Runs. 30+ commands load. `recover` is an alias of `run` (`cli.py:1226`). | [V-exec] click walk |
| Recovery loop | `argus/runtime/controller.py:744-1780` (`RecoveryController.run`) | **Core of the product; works end-to-end with mock adapters** (tests `test_recovery_engine_e2e`, `test_toy_repo_e2e`, `test_auto_localization_and_escalation`, budget/429/timeout tests). Live-provider path not run by me (no network); live tests are opt-in markers. | [V-exec] suite |
| "Routing" | (a) `argus/routing/difficulty.py`: keyword/size heuristic returning an effort string. (b) hard-coded attempt-index ladder `controller.py:1109-1130`. (c) gateway tier map `argus/gateway/router.py:60-120` using the same classifier. | Exists, but it is a **heuristic effort label + fixed ladder**. No latency, reliability, cost, or outcome input; no fallback ordering; no persisted outcomes; no learned planner anywhere in `argus/` (grep for learned/planner/sklearn: zero hits). | [V-read]+[V-exec] grep |
| Escalation ladder | `controller.py:1109-1130` | attempt 1: small, effort low/medium; attempt 2: small, effort high; attempt 3+: large, effort high, context radius 45. Hard-capped at 3 attempts in CLI (`cli.py:386`) and MCP (`mcp/server.py:180`); the config allows up to 10 (`config.py:317`). | [V-read] |
| Difficulty classifier | `routing/difficulty.py`, called `controller.py:1061-1070` | Called with `prompt=f"Fix failing test: {exec_test_cmd}"`, so the architectural/multi-file/"simple question" regexes see only the test command. Its output only affects attempt-1 effort (`low` vs `medium`, `controller.py:1118`) and the `effort_used` label. | [V-read] |
| Patch engine | `argus/patch/fuzzy_engine.py` (424), `parser.py`, `paths.py`, `ast_checker.py` | Works. T1 exact (unique), T2 per-line strip match with first-line indent delta, T3 SequenceMatcher window (0.82, margin 0.10, ±1 line), T4 anchors (opt-in, default off), T5 refusal. Python-only: non-`.py` targets are refused (`fuzzy_engine.py:130-142`). Single target file only: cross-file/rename/create/delete patches refused (`paths.py:83-113`). | [V-read]+[V-exec] |
| AST gate | `patch/ast_checker.py`, applied in engine `fuzzy_engine.py:144-156`, again in controller `1622-1664` and in the applier | Works; syntax only. | [V-read] |
| Localization | `controller.py:608-742` (traceback frames, test-file imports, then `HybridLocalizer` BM25+AST, then `DeterministicLocalizer`), `runtime/frame_slicer.py`, `controller.py:103-310` (`extract_context_frame`, ±25 lines; ±45 on attempt 3) | Works for the product's input (a failing test with a traceback). Research issue-only recall@1 is 21-27% (your finding 7); that situation is **not the product's main input** [INF]. Context-window failure returns `LOCALIZATION_FAILED` mid-loop (`controller.py:1158-1168`). | [V-read] |
| Workspace isolation | `runtime/workspace.py` (copy mode or `git worktree`) | Works; stale-workspace GC with PID start-time identity. | [V-read]+suite |
| Test runner | `runtime/runner.py` | `shell=False`, allow-list of executables, shell-operator rejection, bounded 4 MB output, process-tree kill. Traceback feedback = lines from `=== FAILURES ===` capped at 60 lines (`runner.py:473-496`). | [V-read] |
| Container evaluator | `runtime/container.py` | Docker `--network=none`, memory/pids limits. Only used when `use_container_runner` is set (research runner), not by CLI/MCP default. | [V-read] |
| Budget | `runtime/budget.py` | Per-task reservation/settle/quarantine + process-global ceiling. Works as designed under tests, with the defects in B7. | [V-read]+[V-exec] |
| Candidate store + applier | `runtime/candidate.py` | Per-run `.argus/runs/<id>/` artifacts, SHA-256 baseline/candidate hashes, `os.replace` with TOCTOU re-hash, symlink refusal. Approval is a boolean in `metadata.json`. | [V-read] |
| Providers/adapters | `providers/adapter.py` (OpenAI-compatible), `providers/antigravity.py` (host CLI), `providers/storage.py` (keyring + fallback file), `providers/models.py` presets | Works. Groq prohibited in 4 places (`config.py:158`, `controller.py:448`, `mcp/server.py`, gateway router). | [V-read] |
| MCP server | `argus/mcp/server.py` (4 tools) | Works; `argus_recover` takes `test_command`, `budget`, `provider`, `model` from the calling agent. | [V-read] |
| Gateway (OpenAI/Anthropic-style proxy) | `argus/gateway/*` (server.py 1874 lines) | Present, excluded from `[all]` and described as experimental in `pyproject.toml:56`, but headlined in README. Not re-audited in depth (B12). | [V-read] |
| Local API (`argus serve`) | `argus/api/*` | Present; needs `fastapi` which is only in the `gateway` extra (`pyproject.toml:57-60`) [INF: a plain `pip install argus-recovery` cannot run `serve`; I did not run it without fastapi]. | [V-read] |
| TUI | `argus/tui/*` (Textual) | Present; tests pass (`test_tui_app`, `test_tui_hardening`). Not audited. | suite |
| Research runner | `argus/research/runner.py` (**shipped in the wheel**, `packages.find include=["argus*"]`) | Runs SWE-bench-style tasks through the real controller with `attempts.jsonl`/`outcomes.jsonl`. Has serious limits (B8). | [V-read] |
| Legacy research code | `src/` (66 files: `strategies/learned.py`, `swebench/patch_builder.py`, `actions/*`, 22 experiment scripts) | **Untracked and gitignored** (`.gitignore:120 /src/`; `git ls-files src` = 0 files). Not in the wheel. Largely **not importable** (A.7). | [V-exec] |

### A.3 What runs end-to-end (as far as I could check offline)

`argus recover -t "pytest ..." [-f file]` -> workspace copy -> baseline test -> (optional auto-localize) -> loop (prompt, model, parse, validate single-file, apply T1-T3, AST, test) -> `RecoveryOutcome` -> `.argus/runs/<id>` artifact -> `argus approve` -> `argus apply`. All steps have passing mock-adapter tests. Live model quality is not something I could test.

### A.4 What the shipped runtime already does relative to your findings

- **It already uses feedback format F, not P.** Each failed attempt calls `ws.reset_target_file()` (`controller.py:1767`), so the next prompt shows pristine code plus "Primary Test Failure (Root Bug)" and "Feedback / Diagnostic from Attempt N-1" (`controller.py:1878-1897`). The previous patch/answer is **not** in the prompt (`last_error` is the test traceback or the apply-failure message only: `1615, 1661, 1766`). The P format (previous answer shown, `Previous Attempt (FAILED)`, `previous_patch[:3000]`) exists only in the untracked `src/swebench/patch_builder.py:171-235`, which cannot even be imported (it needs the missing `src.groq_client`). So the task statement's premise "deployed Argus = arm P" is **not accurate for `argus/`**. [V-read, V-exec] Caveat: the product's feedback block differs from the protocol's F block (below, C3), so the F result transfers by analogy, not exactly.
- **Apply-failure feedback exists** (`1615`: `"Patch application failed: <engine details>"`), but the message for the common failure is generic: `"No matching region found for search block (checked Tiers 1-4)."` (`fuzzy_engine.py:119`), with no nearest-match hint. Your finding 2 says this kind of feedback rarely recovers anyway.
- **A per-task dollar cap already exists** (default `budget_limit_usd=0.030` in `config.py:135`; CLI/MCP/API default 0.05), with pre-dispatch worst-case reservation, settle, and quarantine (`controller.py:1181-1215, 1264`). It is a hard stop. What is missing is in B7.
- **Per-attempt cost/tokens exist in memory** (`AttemptRecord`, `controller.py:42-66`), but are **not persisted** by CLI/MCP: the artifact stores only the aggregate and the *last* attempt's prompt/raw response (`candidate.py:166-225`; `controller.py:890-910`). Only `research/runner.py` writes `attempts.jsonl`, with a reduced field set (no patch hash, no prompt hash, no finish reason, no escalation tier).
- **No loop/truncation detection anywhere.** `grep finish_reason|truncat|degenerate` over `argus/` (excluding TUI/gateway streaming) returns nothing in providers or controller. A truncated or looping answer simply has no closing `>>>>>>> REPLACE`, parses to zero blocks, and becomes `"Formatting error: Please output exact SEARCH/REPLACE blocks."` (`controller.py:1504`), identical to a genuine format mistake. [V-read]

### A.5 Documentation-only or unsupported in the shipped package

| Claim | Reality |
|---|---|
| "adaptive inference routing" (AGENTS.md; spec line 4; `ArgusConfig.adaptive_routing`) | A keyword heuristic that picks a reasoning-effort label (A.2). No model-selection, fallback, learned planner, or outcome feedback in `argus/`. |
| "learned planner / Argus Full Adaptive Policy 92%" (spec) | Exists only as untracked `src/strategies/learned.py` + `src/analysis/train_learned_planner.py`, loading a pickle from `models/learned_planner.pkl`. Refuted by the earlier audit (label leakage). Not used by the product. |
| Multi-language recovery | Not implemented (`fuzzy_engine.py:130-142` refuses non-Python). Website says "roadmap" (honest). |
| Gateway "dual-protocol translation" | README overstates; earlier audit found one-direction, text-only translation; I did not retest. |

### A.6 Test status and coverage of critical paths

Counts disagree across docs: README says 489 passed/15 skipped (`README.md:344`), CHANGELOG and website say 471 (`CHANGELOG.md:40`), my collect shows 506 (my run: 470 passed/27 skipped/8 failed, 5 of the failures being copy artefacts; the earlier audit: 485/21/1). Treat every published count as stale.

| Critical path | Tested? | Gap |
|---|---|---|
| Escalation ladder per attempt (model/effort/context) | Yes, `test_auto_localization_and_escalation.py:130` (uses explicit `small_model`/`large_model`) | No test that `--model` is honoured (B1). |
| 429 retry, backoff ceiling, post-dispatch timeout quarantine, pre-dispatch refusal, global cap | Yes, `test_budget_and_provider_milestone.py` | No tests for NaN budget, cap-after-first-instance, 5xx retry, word-count token fallback. |
| Patch tiers | Yes, `test_patch_engine.py`, 500-case synthetic corpus | Corpus has no operator/negation/variable-swap drift (B2); no deletion-block test (B3); no CRLF round-trip through the applier. |
| Feedback prompt content | Only indirectly (`test_frame_localization.py`) | No test that the previous patch is *absent* and the failure text is present/trimmed; no truncation/empty-output test. |
| Approval gate | Yes, but only that the flag is honoured | No test against a forged `metadata.json` (B9). |
| Gateway | Many tests, run under a test-mode auth bypass | Earlier audit: happy-path coverage. |
| Research runner | `test_unified_research_runner.py` | Does not test the `max_tokens=256`/placeholder-file/`F2P[:2]` behaviours (B8). |
| SSE stream | 2 tests | Flaky (section 0). |

### A.7 Legacy `src/`

- `git ls-files src` returns 0 files; `.gitignore:120` ignores `/src/`. A fresh clone does not have it; `tests/test_confirmatory_remediations.py` skips with "Historical research ... module not present" (verified: 7 passed, 10 skipped in my copy). [V-exec]
- Import probe (run from the repo root, read-only): OK: `src`, `src.strategies.{fixed,heuristic,learned}`, `src.state_builder`, `src.calculator`, `src.antigravity_client`. **FAIL (ModuleNotFoundError)**: `src.execution_harness` (needs `src.evaluator`), `src.swebench.patch_builder` and `src.swebench.harness_swe` (need `src.groq_client`), `src.actions.repair` and `src.pre_interventions` (need `src.prompt_builder`), plus `retrieval`, `task_loader`, `quality_analyzer`, `generate_synopsis`. The task's suspicion is confirmed: `src/execution_harness.py:14,16` imports the missing `src.evaluator` and `src.prompt_builder`. Stale `.pyc` for those modules sit in `src/__pycache__` (so they once existed). [V-exec]
- The spec (`ARGUS_END_TO_END_..._SPECIFICATION.md`, itself gitignored at `.gitignore:104`) links into `src/` as if it were part of the product.

---

## B. Defects and risks (ranked)

Severity is for the stated use (research validity first, then product safety).

### High

**B1. The user's `--model` is silently overridden by hard-coded tier models.** [V-exec] `ArgusConfig.__post_init__` fills `small_model`/`large_model` from the provider *name* (`config.py:196-226`) and the controller dispatches `tier_model` on every attempt (`controller.py:1116-1131, 1247-1252`); CLI/MCP never set them (`cli.py:388-397`, `mcp/server.py:229-234`). Probe results: provider `openai`, model `gpt-5` -> small `gpt-4o-mini`, large `gpt-4o`; `ollama` + `llama3:70b` -> `qwen2.5-coder:7b` for all attempts; `antigravity` + `gemini-3.8-flash-high` -> `gemini-2.5-flash`/`gemini-2.5-pro`; `deepseek` + `deepseek-reasoner` -> `deepseek-flash`/`deepseek-chat`. For unknown provider names (e.g. `openrouter`) small = large = the user's model, so **no escalation happens**. This violates AGENTS.md ("must not silently select an unsuitable model"), contaminates any experiment that uses the CLI/MCP, and means the gpt-oss 20B->120B cascade can only be expressed via `argus.yaml` or constructing `ArgusConfig` directly (the research runner does the latter, `research/runner.py:301-303`).

**B2. Tier 3 still applies semantically wrong edits (earlier audit C1, unfixed).** [V-exec] SEARCH `if a <= b:` against source `if a < b:` -> applied at Tier 3, confidence 0.984, AST valid. SEARCH `if x.ok:` against source `if not x.ok:` -> applied at Tier 3 (0.957). Mechanism: ratio-only match over character windows with no token/operator check (`fuzzy_engine.py:256-372`); the interior check only triggers when both boundary lines match and the block has at least 3 non-blank lines (`:314-359`). Your data says Tier 3 added about 1 solve and 2/50 resolved candidates needed it (finding 3), so the benefit is small relative to this risk; the test gate catches many (not all) of these, which is why it is "High" and not "Critical" for the product [INF]. Related Tier 2 weakness [V-exec]: Tier 2 compares stripped lines only, so a SEARCH with flattened indentation matches a block nested deeper and the replacement is re-indented by the *first-line* delta only; probe: inserting `z()` between `a()` and `b()` landed inside an `if` it did not intend; and a tab-indented SEARCH against space-indented source produced mixed indentation `'   \tdef f(self):'` (valid Python by luck, corrupt style) (`fuzzy_engine.py:195-236`). This is the "gpt-oss fails on indentation" case, so it is exactly where this tier is exercised.

**B9. Approval gate is forgeable and the launcher has `shell=True` (earlier audit H1/H2, unfixed).** [V-read] `set_approval` just rewrites `metadata.json` (`candidate.py:331-360`); `grep hmac` finds only token comparisons in API/gateway auth, no signing of candidate metadata. An agent with `argus_recover(test_command="python -c ...")` plus file write can mint a verified, approved candidate (earlier audit reproduced it; I did not re-run it). `argus/launcher.py:122` still has `subprocess.Popen(cmd_str, shell=True)` with `workspace_path` interpolated (Windows conhost fallback). [NOT-RETESTED: G-H1 gateway command injection via `.cmd` shim; the `antigravity.py` call itself uses `shell=False` list args, `:384-391`.]

### Medium-high

**B3. Pure-deletion SEARCH/REPLACE blocks cannot be parsed.** [V-exec] `parse` of `<<<<<<< SEARCH\nx = 1\ny = 2\n=======\n>>>>>>> REPLACE` returns 0 blocks; with a blank line in the replace section it returns 1. Cause: the regex requires `\n` after `=======` *and* `\n` before `>>>>>>>` (`parser.py:25-27`). A correct fix that deletes lines becomes "Formatting error", burns an attempt and spend, and is indistinguishable from truncation.

**B4. No truncation / loop / empty-output handling; defaults likely truncate reasoning models.** [V-read] `adapter.py:224-260` ignores `finish_reason` and reasoning tokens; `_call_model` returns only content and token counts (`controller.py:1823`). Defaults: `max_tokens=2500` (`config.py:130`) and `temperature=0.0` (`config.py:133`), whereas your protocol found 10-13% of 20B attempts hit the output limit at cap 8000 and records temperature 0 as a repetition-loop trigger (`PILOT50_PROTOCOL.md` Rev 4, line 183). `research/runner.py:312` hard-codes `max_tokens=256`, which is far below any reasoning budget (B8). Truncated output is reported to the model as a format error (`controller.py:1504`), and the protocol's own one-sentence "cut off ... keep reasoning short" message is missing.

**B5. Transient provider errors consume an attempt and quarantine worst-case spend; feedback is overwritten.** [V-read] Any non-429, non-4xx error (500/502/503/504, timeout, connection drop) goes to the `else`/`except Exception` branches (`controller.py:1372-1448`): reservation quarantined in full (`1375, 1415`), `attempt_idx += 1`, **no retry**, and `last_error = "Inference timeout: ..."` replaces the test failure that was to be shown next (`1405, 1446`). With the default of 3 attempts, one 503 costs a third of the run, and the quarantined amount stays against the task cap and the global cap. 429 handling itself is sound (bounded by `rate_limit_backoff_max_seconds=60`, does not consume an attempt, re-reserves).

**B7. Budget and cost-accounting defects.** 
- NaN budget fails open [V-exec]: `ArgusConfig(budget_limit_usd=nan).validate()` reports no issue (`config.py:319` uses `<= 0`), and `TaskConditionBudget(nan).check_and_reserve(10**9, 10**9, ...)` returns `True` (`budget.py` `projected > limit + 1e-9` is False for NaN). `argus.yaml` `budget_limit_usd` is a float() parse (`config.py:265-266`), and MCP `budget` is client-supplied (`mcp/server.py:130`).
- `GlobalExperimentBudget.get_instance(cap)` ignores `cap` after the first call [V-exec] (`budget.py:185-190`), and the singleton is process-wide and never reset outside tests: a long-lived MCP/API process accumulates toward the $5 default (`config.py:136`) across unrelated runs, after which every run is refused with `GLOBAL_BUDGET_EXCEEDED` [INF on the long-lived-process consequence; the accumulation mechanism is V-read].
- Token fallback undercounts [V-read]: if the provider returns 0/0 usage, tokens become whitespace word counts (`adapter.py:243-246`), which understate real token counts, so settled cost is understated; the record does not flag the estimate.
- Unknown models are priced at $0.50/$0.50 per 1M (`config.py:285`); the Antigravity models are priced $0 (`config.py:49-59`), so the cap never binds for them (unmetered subscription spend, correctly flagged in docs but not in `RecoveryOutcome`).
- Tier-3 budget downgrade silently swaps the model [V-read] (`controller.py:1189-1201`): if the large model does not fit, the small model is used while `tier_used` stays 3. `model_used` is correct, so telemetry can detect it, but nothing surfaces it as an event/status.
- Reservation estimate uses the gpt-oss tokenizer for all models (`budget.py:29-42`), and `tiktoken` is only in the `research` extra, so the default install uses the bytes/2 fallback (`budget.py:104-121`): conservative, over-reserves [V-read].

**B8. The shipped research runner can produce false negatives and inflated difficulty.** [V-read]
- `max_tokens=256` hard-coded (`research/runner.py:312`).
- If `data/repos/<owner__repo>` is missing it silently seeds the target with `"# Target file initial state\ndef solve(): pass\n"` (`:248-263`); the model then repairs a fake file and the failure is classified `MODEL_REPAIR_FAILURE`, not infrastructure.
- Test command is `pytest <first two FAIL_TO_PASS ids> -q` (`:178`): P2P tests are never run and tasks with more than two F2P tests are "verified" on a subset (same class of flaw the earlier audit found in the pilot30 script). IDs containing spaces break the split.
- Target file comes from the gold patch and multi-file tasks are dropped (`:171, :171-173`), i.e. an oracle-localization setting; correct for a file-given experiment, misleading as a product claim (your finding 7).
- Conditions are only `direct`/`self_repair`/`escalate` with attempts 1/2/3 (`:299`), so the 20B x2 -> 120B x2 cascade, F-vs-R arms and seeds are not expressible; `attempts.jsonl` lacks patch hash/prompt hash/finish reason.

**B6. Telemetry is incomplete and one field is overloaded.** [V-read] `AttemptRecord.tier_used` means the *escalation tier* in provider-error records (`controller.py:1346`) and in refusal paths `tier_idx` (`1213`), but the *patch-engine tier* in apply/test records (`1582, 1636, 1722`). `duration_ms` mixes model latency, patch, and test time; provider `duration_ms`, `thinking_tokens`, `finish_reason` and a prompt hash are available or trivially computable but dropped (`controller.py:1823`). No seed is sent (`grep seed argus/` returns nothing, except TUI). Per-attempt history is not persisted by the CLI/MCP path (A.4). Consequence: offline replay of a Argus run (your item 9) is impossible without the research runner or stdout `--json-events`, which carries no patch/prompt hash either.

### Medium

**B10. Encoding/line-ending corruption on apply.** [V-exec for the engine, V-read for I/O] The engine normalises `\r\n` to `\n` and returns LF-only text (`fuzzy_engine.py:88`; probe: `'a = 1\r\nb = 2\r\n'` -> `'a = 1\nb = 3\n'`). The workspace reads with `errors="replace"` (`workspace.py:399, 445, 498, 513`), so non-UTF-8 bytes become U+FFFD, and `write_text` uses the platform newline (`:505, 517, 525`). The earlier audit's approval-diff mismatch still applies [NOT-RETESTED].

**B11. Swallowed failures.** [V-read] `_finalize` catches every exception when persisting the artifact and continues (`controller.py:911-912`), so a `SUCCESS`/`verified=True` outcome can be returned with no artifact on disk and `apply` later fails with "not found". `_get_adapter` swallows storage errors (`:487-488, 553-554`); `config.py:246, 254, 259` swallows malformed `argus.yaml`/`pyproject.toml` silently (a typo'd policy file is ignored without warning). `close()` swallows (`:433`), acceptable.

**B12. Test acceptance accepts F2P-only passes.** [V-read] "verified" means the one `test_command` passed on the candidate (`controller.py:1711-1713, 1747`) plus AST. There is no regression command, so your finding 6 (accepted_regressed 4-11%) applies unmitigated; the outcome says `verified=True` with no "plausible, not proven" qualifier, and README says "guarantees that candidate repairs pass your test suite" (README.md:37), which is true only for the command given.

**B13. Gateway (not re-audited).** Spot checks only. [V-read] Reservations still have no TTL (`gateway/budget.py:106-125`); `argus/auto` is the same keyword classifier mapped to tiers (`gateway/router.py:60-95`), no fallback; the `/v1/chat` cost estimate prices `MODEL_REGISTRY.get(target_model, $2.50/$10)` where `target_model` may be the alias (`server.py:479-481`); tool handling exists now (`server.py:1168, 1224`) so the earlier G-H2 may be partly addressed. [NOT-RETESTED] G-H1..G-H6, config-trust (`key_env`), redaction gaps.

### Low

- Tier 5 message says "checked Tiers 1-4" even when Tier 4 is disabled (`fuzzy_engine.py:119`).
- Tier 3 runs `SequenceMatcher` over every window for three window sizes with no time bound (`:269-277`): quadratic-ish on large files [INF].
- `strip_line_annotations` strips any `^\s*\d+\s*\|` line prefix in the whole SEARCH/REPLACE text if any line matches (`parser.py:38-45`), which can damage code lines such as a continuation `    1 | FLAG`.
- `maybe_load_dotenv` is opt-in (good); fallback key file uses `chmod 600` which has no effect on Windows (`providers/storage.py:152-156`) [INF].
- Version/doc drift: three different test counts (above).

### Earlier-audit items: status now

| Earlier item | Now |
|---|---|
| C1 Tier 3 wrong-location/semantic drift | **Still present** [V-exec] |
| H1 forgeable approval | **Still present** [V-read] |
| H2 launcher `shell=True` | **Still present** [V-read] (`launcher.py:122`) |
| G-H1..G-H6 gateway | Not re-tested; tool handling partially changed |
| CRLF/UTF-8 corruption | **Still present** [V-exec engine] |
| `GlobalExperimentBudget` cap ignored; NaN fails open | **Still present** [V-exec] |
| Routing = keyword regex, no fallback | **Unchanged** (and `AGENTS.md` still says adaptive) |
| README gateway vs `pyproject` mismatch | **Still present** (`README.md:45, 253` vs `pyproject.toml:56`) |
| Tier definitions inconsistent between README/CHANGELOG/spec | README and CHANGELOG now agree with the code; the (gitignored) spec still uses a different tier scheme (CRLF/indent-delta/SequenceMatcher/anchor) |
| Test-count drift | **Worse**: three numbers (489, 471, my 506 collected) |
| Refuted headline numbers | Removed from tracked README/website/docs (`git grep` finds none), **still in the spec** and in `CONTEXT_HANDOVER.md` (both gitignored) |
| Website research page | Calibrated and honest ("maintainer-reported ... not independently replicated") |

---

## C. Doc/claim mismatches, most misleading first

1. **README "Local Gateway Proxy" + "Dynamic tier-based model routing" lines (`README.md:42, 45, 253-266`).** Presents routing across T1/T2/T3 models and a dual-protocol gateway as core features while `pyproject.toml:56` calls the gateway deferred/experimental and excludes it from `[all]`; routing is a keyword heuristic with a fixed ladder; model names (`claude-3-7-sonnet`, `claude-3-opus`) are not what the code selects (B1). Given your findings, the honest description is: "fixed cheap-first cascade with test-failure feedback, hard budget caps".
2. **README "guarantees that candidate repairs pass your test suite" / "Verified ... zero incorrect applications" (`README.md:37, 39`; CHANGELOG:42; website research table).** The corpus is synthetic and does not contain operator/negation drift (B2); acceptance is F2P-only (B12). Scope the claim to "the supplied command" and to the synthetic corpus.
3. **README Quickstart is wrong in three places** [V-exec]: `argus recover "pytest tests/..."` (`README.md:60, 118`): `recover` takes `-t/--test` as a required option, no positional; MCP config `args: ["mcp","serve"]` (`README.md:243-247`): there is no `serve` subcommand (`Error: No such command 'serve'`; the command is `argus mcp run`); Python SDK snippet (`README.md:144-155`): `RecoveryController(config=..., workspace_root=...)` and `controller.recover_async(...)` do not exist (`__init__` takes `config, adapter, container_evaluator`; the method is `run`/`execute_recovery`, `controller.py:398, 744, 1927`). New users hit these first.
4. **Spec headline results** (gitignored, but it is the document most likely to be pasted into papers/slides): 92%/184 of 200, "Beats 120B ... at 44% lower cost", "doubling 26 -> 63", "48% of discarded patches", Cohort B 76/500 at $0.27, "-26.6% tokens/100% thinking eliminated". All refuted or qualified by the earlier audit and not supported by your findings (item 7). It also contradicts itself on tier numbering.
5. **README "Tested Model Providers: ... Anthropic Claude (claude-3-5-haiku, ...), OpenAI (gpt-4o ...)" and "Platform Matrix: Verified" for Linux/macOS** (`README.md:309-314`). I found no evidence in the repo of live tests against those providers or on Linux/macOS (live markers are opt-in; the earlier audit mentions WSL2 only for process-group tests). [INF] unsupported as "Verified".
6. **README "Zero cloud telemetry ... zero prompt tracking" vs code.** Prompts and raw responses are persisted unencrypted in `.argus/runs/<id>/prompt.txt|raw_response.txt` (`candidate.py:211-215`, scrubbed for secrets only). Local only, so "zero cloud telemetry" is true, but "persisting prompts" is a listed AGENTS.md security concern; state it.
7. **AGENTS.md "Argus is an adaptive inference routing system ... factors such as latency, reliability, cost, observed outcomes".** None of latency, reliability or observed outcomes feeds any decision in `argus/`. Either build it (section D) or reword; since your cascade result says oracle routing gives no extra solves, reword.
8. **PRODUCT.md / CHANGELOG** are calibrated except the count (471) and "0 incorrect applications".
9. **Website** is the best-calibrated artefact (research page explicitly separates guaranteed from experimental). I did not read all 40 pages.

---

## D. Recommendations

Effort: S < 0.5 day, M ~ 1-3 days, L > 3 days. Mapping to your findings is `F#`.

### D.1 CHANGE (existing behaviour)

| # | What / where | Why | Effort / risk | How to test |
|---|---|---|---|---|
| CH1 | **Honour the configured model.** `config.py:196-226` and `controller.py:1116-1131`: if `model` was set explicitly and no explicit `small_model`/`large_model` was given, use `model` for all tiers (or require an explicit policy). Never derive tier models from a provider name. | B1; reproducibility; AGENTS.md routing rule. | S / low (behaviour change for people relying on the implicit ladder; call it out in CHANGELOG). | Parametrised test over providers asserting `adapter.call_history[*].model`; reuse `MockAdapterWithEscalationTracking`. |
| CH2 | **Keep feedback format F; do not port P.** Keep `reset_target_file()` and previous-answer-hidden prompts. Add a test asserting the prompt contains the failure text and does **not** contain the prior SEARCH/REPLACE text. Trim the feedback block to the validated shape: first failing test + up to ~2,000 chars, and stop duplicating "Primary Test Failure" when it equals the latest feedback (`controller.py:1880-1897`, `runner.py:473-496`: today up to 60 lines of the FAILURES section). | F1: F >= P (P-F -1/-2), previous-patch repetition not a cause. Matching the validated block keeps the +6.6..+8 (20B) transferable [INF]. | S / low-medium (prompt change shifts behaviour; replay offline first). | Prompt snapshot test; offline replay of the 20B feedback arm with the new trimming. |
| CH3 | **Default cascade as an explicit policy** (see AD1): attempts 1-2 small with feedback, then large; allow up to 4 attempts (2+2) as an opt-in (today hard-capped at 3 at `cli.py:386`, `mcp/server.py:180`; the replayed best cascade was 20B x2 then 120B x2 re-draws). For the large tier use re-draws or feedback as a policy flag (F4: 120B feedback effect is small/uncertain, -2 design / +4.5 blind CI 0 to 9.1), default to the validated re-draw. | F4 (59.6 vs 54.5 at 1.10x; offline replay only, not a live run). Today attempt 3 is a single large attempt *with* feedback (`controller.py:1126-1130`), which is not the replayed cascade. | M / medium (policy code; keep old behaviour behind `policy=legacy3`). | Decision-boundary unit tests (AD1); a live pilot of the cascade is still needed because the 59.6 figure is a replay [INF]. |
| CH4 | **Generation defaults** for reasoning models: `max_tokens` 2500 -> policy value >= 8000 for gpt-oss-class models; `temperature` 0.0 -> provider-recommended (1.0 for gpt-oss) when a seed is recorded; make `research/runner.py:312` use config (`256` is a bug). Reserve budget on the real cap (`budget.py` worst case scales with it; 8,000 x $0.60/M = $0.0048 for 120B, fine under $0.03). | F5 (10-13% of 20B attempts truncate; loop trigger). | S / medium (cost per attempt rises; temperature change loses determinism, so record seed + hash). | Mock adapter returning truncated content; assert classification (AD3). |
| CH5 | **Make truncation a first-class attempt outcome** distinct from format error: carry `finish_reason`, reasoning tokens and a repetition flag from `adapter.py:224-260` through `_call_model` (`controller.py:1823`); on truncation send the protocol's one-line "cut off, keep reasoning short" feedback instead of `controller.py:1504`'s message. | F5. | M / low. | Unit tests with `finish_reason="length"` and a repeated-n-gram response. |
| CH6 | **Transient errors**: retry 5xx/timeouts once *inside* the attempt (bounded, with the existing deadline), and do not overwrite the failure text with "Inference failure" (`controller.py:1368, 1405, 1446`). Keep quarantine on genuinely unresolved dispatches. | B5; AGENTS.md retry-correctness. | S-M / medium (risk of double-billing: only retry when the error is conclusively pre-compute, else keep quarantining). | Extend `test_post_dispatch_timeout_quarantines_uncertain_spend` with a 503-then-200 adapter. |
| CH7 | **Tier 3 policy.** Given F3 (T3 ~1 solve, ~2/50 resolved needed it) and B2: either (a) default Tier 3 off, opt-in like Tier 4 (`--enable-tier3`), or (b) keep it and add a token/operator-level equality check on the matched window plus record `patch_confidence` and `matched_search_block` in the artifact. Tiers 1-2 (the bulk of the +13.1/+5.6 pp) stay default. Fix Tier 2 so relative indentation is compared (not just stripped lines) and tab/space mixes are normalised before computing the delta (`fuzzy_engine.py:195-236`). | F3, B2. | M / medium (may lose ~1 solve in 50; the test gate remains). | Add operator/negation/variable-swap/omitted-security-line cases to the corpus; report false-apply rate with a CI (the E6 study is the open research gap). |
| CH8 | **Parser**: accept empty replacement (deletion) blocks (`parser.py:25-27`: allow `=======\n(.*?)>>>>>>>`). | B3. | S / low. | Add the probe as a test; run the adversarial corpus. |
| CH9 | **Acceptance qualifier + optional regression command**: add `--regression-test <cmd>` (run after the F2P command on the candidate) and report `verified_scope` ("supplied command only" vs "plus regression command"); until then, README wording per C2. | F6 (18% judged wrong/fragile; accepted_regressed 4-11%). | M / low. | Toy repo where the fix breaks a sibling test; assert candidate not verified when the regression command fails. |
| CH10 | **Disambiguate `tier_used`** into `escalation_tier` and `patch_tier` in `AttemptRecord`/events/artifact (`controller.py:42-66`, usages at 1213, 1346, 1582, 1636, 1722). | B6. | S / low (event schema change; add a version field). | Event-schema test. |
| CH11 | **Budget hardening**: `math.isfinite` + `>0` in `validate()` and `TaskConditionBudget.__post_init__`; make `get_instance` raise or re-create on a different cap; scope the global budget to the controller/process-run (or reset per MCP call) and expose `reset`; flag `usage_estimated` when the word-count fallback is used (`adapter.py:243-246`); surface the tier-3 downgrade as an event/status. | B7. | S / low. | Unit tests mirroring `probe2.py`. |
| CH12 | **Security fixes carried from the earlier audit**: HMAC the candidate metadata with a key held outside the workspace (or require out-of-band confirmation); remove `shell=True` in `launcher.py:122` (pass a list); preserve CRLF and bytes when applying (read/write bytes, keep original newline, fail on non-UTF-8 instead of `errors="replace"`, `workspace.py:399-525`). | B9, B10. | M / medium (HMAC needs key management; keyring is already a dependency). | Forged-metadata test must fail; CRLF round-trip test; non-UTF-8 refusal test. |
| CH13 | **Research runner**: fail loudly (infrastructure failure) when the repo checkout is absent instead of seeding a placeholder (`research/runner.py:248-263`); run all F2P ids (and optionally P2P) with proper quoting (`:178`); take `max_tokens` from config (`:312`). | B8. | S / low. | Test for each of the three behaviours. |
| CH14 | **Fix README quickstart/MCP/SDK snippets** (C3) and reword routing/gateway/verification claims (C1, C2, C5, C6). | C-section. | S / none. | Doc-snippet smoke test in CI (run `argus recover --help`, `argus mcp run --help`, import snippet). |

### D.2 REMOVE

| # | What | Why | Effort / risk | How to verify |
|---|---|---|---|---|
| RM1 | **Retire the untracked `src/` tree from the product repo.** Move what is needed for reproducing the research into `Argus-pilot50` (or a tagged archive branch) and delete it from the working tree; keep nothing importable that depends on missing modules. | 66 files, ignored by git, ~half unimportable (A.7), contains the P-format builder, a Groq client dependency (policy says Groq prohibited), a pickle-loading learned planner, and 22 experiment scripts whose headline results were refuted. | S / low (history stays in git-ignored copies; archive first). | `python -c "import src..."` no longer relevant; `pytest` unchanged (research tests skip already). |
| RM2 | **Remove unsupported claims** from the spec (or delete the spec; it is gitignored but circulated), `CONTEXT_HANDOVER.md`, and any slide/report text derived from them: 184/200, 63/500 as a fix rate, 48% rescued, 76/500, "frontier-grade", "-26.6% tokens", "adaptive policy beats 120B". | Item 7 and the earlier audit. | S / none. | `git grep` plus a grep over `docs/`, reports and website for the strings. |
| RM3 | **Remove or rename "adaptive routing"** (`ArgusConfig.adaptive_routing`, `--no-adaptive`, AGENTS.md wording) unless you build AD1+AD6: today it only chooses an effort label. Alternatively rename to `effort_heuristic`. | A.5; F4 (oracle routing adds no solves, learned routers unsupported). | S / low (CLI flag deprecation). | CLI help text and tests. |
| RM4 | **Drop the `learned`/planner story** from all product docs; do not build a learned router with 100-200 tasks. | F4 (underpowered; literature says no gain over cascades). | S / none. | n/a |
| RM5 | **Drop the gateway from the README headline** until its audit items are closed, or move it to an "experimental" section matching `pyproject.toml:56`. | C1, B13. | S / none. | README review. |
| RM6 | **Remove `strip_line_annotations` over-reach or scope it** to lines in a consistent `N | ` pattern (all lines, or none). | B-low. | S / low. | Corpus plus a code line `    1 | FLAG` test. |
| RM7 | Remove dead/duplicated code paths in the controller: `_get_client` stub that always raises (`controller.py:604-606`), the three-way TypeError fallback in `_call_model` (`:1813-1820`) that masks adapter signature bugs, the legacy `"cmd"` kwarg and test-command-in-`target_file` guesses (`:762-767`). | Hidden behaviour, harder to test. | S / low. | Existing suite. |

### D.3 ADD

| # | What / where | Why | Effort / risk | How to test |
|---|---|---|---|---|
| AD1 | **One explicit `RecoveryPolicy` object** (new `argus/routing/policy.py`): ordered list of steps `[(model, effort, max_attempts, feedback_mode in {none,F}, context_radius)]`, a pure `next_step(history) -> Step | Stop(reason)` function, and escalation rules (e.g. escalate after N failed small attempts, stop after loop/truncation, stop on apply-failure streak). Replace `controller.py:1109-1130` and the duplicated gateway tier mapping (`router.py`) and `DifficultyClassifier` call. Serialise the policy into the artifact. | F4, item 9: duplicated routing logic (`controller.py`, `gateway/router.py`, `mcp/server.py` cap, `cli.py` cap, research runner conditions each re-encode attempts/tiers). | M / medium. | Table-driven unit tests: normal route, fallback after provider failure, timeout, malformed/empty response, budget-driven downgrade, attempts exhausted, truncation; same table drives the offline replay. |
| AD2 | **Per-attempt record persisted and replayable**: write `attempts.jsonl` per run (not only in the research runner) with `{run_id, attempt, state (pre-state hash), model, effort, seed, temperature, prompt_sha256, response_sha256, finish_reason, tokens (prompt/completion/reasoning/cached), usage_estimated, model_latency_ms, patch_sha256, patch_tier, apply_status, test_status, test_failure_sha256, cost_usd, reserved_usd, cumulative_cost_usd}`; fix prompt secrets by storing hashes plus an opt-in raw dump. Hook into `_finalize` and the attempt paths (`controller.py:1340-1745`). | Item 9; F4 offline replay; AGENTS.md reproducibility/telemetry. | M / low. | Golden-file test of one mock run; replay tool reproduces the run's accept/reject decisions from the log. |
| AD3 | **Early abort / loop detection**: stop reading a stream or reject a completed response on: `finish_reason=length`, repeated n-gram ratio above threshold, empty content with non-zero reasoning tokens; classify as `LOOP`/`TRUNCATED`; policy decides whether to retry at lower effort, escalate, or stop. If the provider supports streaming, abort early (saves the 46%-of-spend-with-no-output seen earlier). | F5 (10-13% of 20B attempts; 21% of earlier runs / 46% of spend). | M / medium (streaming path is new). | Synthetic degenerate response fixtures; assert zero spend growth after abort when streaming mock supports it. |
| AD4 | **Budget as policy input**: per-task cap that accounts for *expected remaining cascade cost* (refuse to start an attempt that cannot be followed by the policy's next step, or choose the cheaper step explicitly), expose `remaining_budget` to the policy, and add a hard per-task attempt-count and token ceiling (not only dollars; Antigravity is $0 so dollars never bind). | Item 9; B7. | S-M / low. | Boundary tests: cap exactly equal to reservation; NaN; $0-priced model with token ceiling. |
| AD5 | **Deterministic config capture**: record `argus_version`, git commit of the target workspace, policy hash, prompt-template hash, model id as returned by the provider (`CompletionResponse.model`, currently ignored), seed/temperature, and tool versions in the artifact; pass a `seed` to providers that support it. | Item 9; AGENTS.md reproducibility. | S / low. | Same-input run twice with a deterministic mock gives byte-identical artifact metadata. |
| AD6 | **Optional learned/bandit hooks only after data exists**: log enough (AD2) to evaluate a router offline against the cascade; do not ship one. | F4. | n/a | n/a |
| AD7 | **Decision-boundary tests** the AGENTS.md asks for: feedback prompt content (F, no previous patch), deletion block, operator/negation drift refusal (if CH7 chosen), CRLF round-trip, NaN/negative/zero budget, `--model` honoured, 5xx retry, truncation, empty response, malformed SEARCH block, localization failure on large file, Tier-3 downgrade event, forged `metadata.json`. | A.6 gaps. | M / low. | They are the tests. |
| AD8 | **Fix the flaky SSE tests** (`test_recovery_stream.py`, `test_e2e_desktop.py`) by awaiting the terminal event rather than counting events/sleeping [INF on cause]; add CI retry diagnostics. | Section 0. | S / low. | Run 20x in a loop. |
| AD9 | **Optional apply-failure assist** (research, not default): on `REFUSED_NO_MATCH` return the nearest window ("did you mean") in the feedback; evaluate offline against the 0-4/11-17 recovery rate first. | F2 says apply-error feedback rarely recovers even now; this may or may not move it [INF]. | S / low. | Offline replay on the stored edit-not-applied failures. |

### D.4 Priority order of work (top 10)

1. **CH1** honour `--model`/explicit models (B1). Everything else assumes the code runs the model you think it does.
2. **AD2 + AD5** persisted per-attempt records and deterministic config capture. Without them nothing below can be evaluated by replay.
3. **AD1 (+CH3)** one policy object; implement the validated cascade (small x2 with F, then large x2 re-draws) and remove the duplicated tier/attempt logic.
4. **CH4 + CH5 + AD3** generation defaults, truncation/loop detection (F5); fix `research/runner.py:312`.
5. **CH11 + AD4** budget hardening and budget-as-policy-input.
6. **CH8** deletion-block parsing (cheap, real correctness bug).
7. **CH7** Tier 3 decision (default off or guarded) plus the Tier 2 indentation fix; add the adversarial shapes to the corpus.
8. **CH12** approval HMAC, launcher `shell=True`, CRLF/encoding preservation.
9. **CH9** regression-command option and "verified scope" qualifier (F6).
10. **CH14 + RM1/RM2/RM3** doc/claim cleanup, retire `src/`, rename "adaptive routing".
(CH6 transient-error retry and AD8 flaky tests slot in around 5-6.)

### D.5 Do NOT change (the data supports it)

- **Test-failure feedback with the previous answer hidden** (F, already implemented): +8 design / +6.6 blind for 20B, CIs exclude 0; P adds nothing.
- **Pristine-workspace reset between attempts** (`controller.py:1767`): it is what makes the format F-like.
- **Tolerant Tiers 1-2 as default** (+13.1 pp 20B / +5.6 pp 120B applied-edit rate; most of the gain). Keep AST gate and the single-target-file/path-containment refusal.
- **Cheap-first cascade** as the default shape, rather than a learned or per-task router (F4: oracle router adds no solves, only cost headroom; learned routers underpowered).
- **Tier 4 opt-in/default-off** (added 0).
- **The budget machinery's structure**: reserve-before-dispatch, settle with provider usage, quarantine uncertain spend, 429 not consuming attempts. Fix the edge cases (B7), keep the design.
- **SSRF/path/symlink/TOCTOU/bounded-output/process-tree-kill/`shell=False` runner/Groq prohibition**: earlier audit judged them sound and I saw nothing that contradicts it in the code I read.
- **Container evaluation with `--network=none`** for any research use; extend rather than weaken.

---

## E. Open questions (not resolvable from the code alone)

1. Which prompt/feedback block did the blind-set F arm use relative to the product's? The protocol F block is "first failing F2P test name + <=2,000 chars"; the product shows up to 60 lines of the FAILURES section plus the baseline failure. Whether the product's richer block is better, equal or worse than the validated F block is untested [INF].
2. Is the offline-replay cascade (59.6 vs 54.5) reproducible live with `argus/` rather than the harness? The protocol itself notes deviations (whole-file context vs 25/45-line windows, seeds, temperature 1.0) from the real controller. No live run of the real controller on the blind set was found.
3. How often does the product's apply-failure message resemble the harness's? The harness reused "Argus's own message"; if the stock message is unchanged, finding 2 transfers; I did not diff them.
4. Real-world distribution: your tasks are issue-only SWE-bench with the gold file given; the product's input is a failing test with a traceback. Whether 25-30% recovery after a failed first attempt and the small gains hold there is unknown.
5. Gateway status of G-H1..G-H6 and config trust (`key_env`): not retested; need a focused re-run with the gateway extra installed.
6. Linux/macOS behaviour and live-provider behaviour (README marks them "Verified"): I could not check without network or other OSes; also unclear whether `argus serve` runs without `fastapi` (the extra is `gateway`).
7. Whether `models/learned_planner.pkl` and `data/`, `results/` contents are intended to be kept; deleting `src/` (RM1) assumes archived copies exist elsewhere (`Argus-research-archive`, `Argus_backup_pre_remediation` are mentioned in the earlier audit but I did not inspect them).
8. The two flaky SSE tests: cause not isolated (only reproduced as intermittent).
9. Coverage numbers: not re-measured.

