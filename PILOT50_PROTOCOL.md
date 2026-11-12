# Pilot-50 (now Pilot-100): where small models fail, and how much Argus closes the gap

## Revision 2 (2026-11-10), decisions made with the owner. These override anything below that conflicts.

- **Size and scope:** 100 tasks (not 50), restricted to **single-file** tasks: the gold source patch touches exactly one non-test `.py` file (429 of 500 Verified tasks qualify). Multi-file tasks (71) are deferred to a later phase, not dropped from the roadmap.
- **Models:** `openai/gpt-oss-20b` (small, under test) and `openai/gpt-oss-120b` (reference), on Groq free keys. Qwen later.
- **Phase order:** (1) plain one-shot, no Argus: generate once per model, grade in Docker, label every failure and identify why the small model fails. (2) Argus ladder on the same outputs (apply layer, then retry, then test feedback) and see what it recovers. (3) From the failure evidence, write down what Argus should change; test those changes later on tasks not used to design them.
- **Context budget (8k prompt tokens on free keys):** no task is dropped after seeing results. Every task is run; for each we record offline whether the gold edit region was inside the prompt ("context coverage"). Failures with no coverage are labelled context-insufficient, not model failures. A diagnostic arm with the gold file in context separates "budget" from "capability". The prompt-size rule is decided before any call.
- **Sampling:** proportional by repo from the eligible pool, fixed seed, manifest hash recorded before any model call (`manifests/pilot100_manifest.json`). Reserve tasks replace only harness defects (class F0), in order, and every replacement is logged.
- **Django cap (owner decision):** Django is capped at 30 of 100; the other 70 slots are proportional among the remaining repos (sympy 21, sphinx 11, matplotlib 9, scikit-learn 9, astropy 6, xarray 5, pytest 5, requests 3, pylint 1; seaborn and flask get none). Results are still clustered by repo; report per-repo and repo-clustered intervals. The sample over-represents non-Django repos relative to the full benchmark, so do not quote a pilot rate as a benchmark rate.
- **Pilot is exploratory.** At n=100, expect roughly 10 to 25 solves per model. Report rates and failure shares; make no significance claims. Design changes found here are tested on a separate sealed set.


Status: DRAFT for review and pre-registration. Nothing here has been run.
Models (revised): **`openai/gpt-oss-20b` is the small model under test; `openai/gpt-oss-120b` is the larger reference that defines "the gap".** Both through Groq (17 free keys, verified available). Qwen3.8-27B (available on Groq as `qwen/qwen3.8-27b`) is deferred to a later phase.

Free-tier constraints (probed 2026-11-10): about 1,000 requests/day and 8,000 tokens/minute per key. Every request must fit prompt + reasoning + answer in roughly 8k tokens, so all arms run under one fixed context budget (localized snippet, not whole files). This is a stated condition of the study, applied to both models.

## 0. The one rule that protects the whole project

The plan "run a pilot, find the failures, improve Argus, then show Argus helps" is valid **only if the improvement is not measured on the tasks it was tuned on.** That is exactly what went wrong in the earlier work: v4 hyperparameters were tuned on the same 500 tasks they were reported on.

So there are two phases and two task sets:

| Phase | Tasks | Purpose | May we change Argus after seeing results? | What we may claim |
|---|---|---|---|---|
| **Discovery** (this pilot, 50 tasks) | Set D | Find failure modes, estimate variance and acceptance rate, develop improvements | Yes, in numbered, tagged rounds | Descriptive only: failure distribution, hypotheses |
| **Confirmatory** | Set C: new tasks, never looked at | Test the frozen Argus | No. Freeze a tagged version first | The headline results |

Set C stays sealed until Argus vN is frozen. Run it once. Report D and C separately, and say which is which in the paper.

## 1. Questions

- **Q1 (failure anatomy).** For each model, at which stage does a task fail: budget, format, localization, patch synthesis ("reasoning"), application, or verification? What share of failures falls in each?
- **Q2 (what Argus recovers).** Which failure classes does each Argus layer fix, and by how much?
- **Q3 (the gap).** How much of the gap between a small model and a larger reference is closed by Argus, per stage?
- **Q4 (cost).** What is the all-in cost per resolved task, and the cascade acceptance rate `s` against the price ratio `r` (savings ≈ s − r)?
- **Q5 (safety).** Of the patches Argus accepts, how many are wrong anyway (tests pass, fix incorrect)?

## 2. Tasks

- Source for Set D: SWE-bench Verified, stratified random sample of 50 with a fixed seed across repositories, **not outcome-conditioned** (do not choose tasks after seeing results). Exclude only tasks whose base tests already pass (harness defect, as with the 10 sympy tasks previously).
- Record for every task: number of files in the gold patch, gold patch size, F2P and P2P counts, repo. Do **not** restrict to single-file tasks. Argus is single-file today, so multi-file tasks become a named failure class ("out of scope"), which is itself a result.
- Freeze the manifest and commit its SHA-256 to git **before** any model call, tagged `pilot50-manifest`.
- Caveat: Verified is public and old; Qwen3.8 (Aug 2026) is likely to have seen it. Use it for discovery only. Set C should be post-cutoff tasks (SWE-bench-Live or equivalent), created after the newest model's release.
- Disk: 23 GB free means pull, run, grade, then delete each task's image before the next. Never keep more than a couple of images. Log image digests, not `:latest`.

## 3. Arms (per model, same tasks)

| Arm | What it is | Isolates |
|---|---|---|
| A0 | Single shot, exact-match apply only | Floor |
| A1 | A0 + Argus apply layer: annotation stripping, tolerant matching with ambiguity guard, bare-hunk repair for diffs, AST gate | Format and apply failures |
| A2 | A1 + retry on apply or syntax error (no tests) | Syntax and format recovery |
| A3 | A2 + visible failing-test feedback (regime R1, §4) | Assertion-level recovery |
| A4 | Best-of-N at the same token budget as A3, selected with the same verifier | Control: is it Argus, or just more samples? |
| Ref | `gpt-oss-120b`, single shot (A1 conditions), same prompt and applier | Defines the gap |
| Ref+ | `gpt-oss-120b` through the same A3 loop | Is the Argus effect model-size dependent? (the arm never run in the earlier study) |

Docker plan: generate all candidates through the API first, then evaluate task by task. For each task, pull the image once, grade every candidate (all arms, both models), then remove the image. Images are 3.6 to 7.6 GB each in the local cache, so never keep more than one task's image at a time.

Fix the generation settings and write them down: reasoning effort (gpt-oss low/medium/high; Qwen thinking on/off), temperature, **max output tokens high enough that reasoning is never truncated** (the 512-token cap was the dominant artifact in the earlier benchmark), and seeds. Log provider-billed tokens including reasoning.

## 4. Feedback regimes (the leakage guard)

- **R0:** no tests. Pure model plus apply and syntax checks.
- **R1:** the developer-visible failing test only. For SWE-bench that is the first F2P test, with its name and error shown. This matches the real product input ("here's my failing test"). Grading always uses the full official F2P and P2P suites.
- Never show the model the full hidden test patch, the gold patch, `hints_text`, or the gold file.
- R1 can overfit to that one test, so every resolved patch goes into the passing-but-wrong audit (§6).

## 5. Failure taxonomy (mechanically assignable, in order)

For each (task, model, arm), label the earliest stage that failed:

| # | Class | Detection |
|---|---|---|
| F0 | Environment or harness defect | Base tests pass, build fails, image error. **Exclude and report the count.** |
| F1 | Budget: no output or truncated | Empty or `finish_reason=length` |
| F2 | Format: no parseable edit | Parser yields zero blocks |
| F3 | Path or localization: edited the wrong file | Edit file ∉ gold files |
| F4 | Apply: SEARCH text not found or ambiguous | Engine refusal reason |
| F5 | Syntax: applied but does not parse | AST gate |
| F6 | Out of scope: gold needs several files | Gold file count > 1 |
| F7 | Wrong fix: right file, tests fail | Hidden F2P fails |
| F8 | Regression: fix works, P2P breaks | P2P fails |
| F9 | Passing but wrong | Tests pass, audit says the fix is incorrect |

F7 gets a second pass: a two-annotator blind review of a sample (target 40 failures per model), each tagged as incomplete fix, wrong root cause, misread issue, wrong API or semantics, or other. Report Cohen's kappa. An LLM judge may pre-label but never replaces the human labels.

## 6. Answering "reasoning, syntax, or something else"

Counting failure labels shows where models fail. To show what would close the gap, use **oracle interventions that are diagnostic only** and are never reported as performance:

| Intervention | Question it answers |
|---|---|
| Give the gold file (and function) in context | How much of the gap is localization? |
| Give the same model a higher reasoning budget or effort | How much is thinking budget? |
| Replace the model's edit text with a fixed-format rewrite by a larger model, keeping the model's intent | How much is formatting vs ideas? (needs a pre-registered rubric) |
| Run the reference model on the same prompt | How much is raw capability that no scaffold fixes? |

The gap is decomposed as: gap closed by each Argus layer + gap closed by each oracle + remaining gap. The remainder is the part only a bigger model can fix, and the paper should say so openly.

Passing-but-wrong audit (E3): for each resolved patch, differential tests against the gold patch where feasible, plus blind human review of a stratified sample. This feeds Q5 and the `s` estimate (accepted-and-correct share).

## 7. Metrics and analysis

- Primary: resolve rate per arm per model on the official F2P+P2P; paired exact tests on discordant pairs; Wilson intervals; clustered by repo where repos repeat.
- Cost: provider-billed tokens × one frozen price table; **all** attempts, failed ones and escalations counted; sensitivity at several price ratios; the break-even formula `s > r`.
- Acceptance rate `s` of the cheap tier, with the verifier-precision caveat from the audit.
- At n = 50, differences under about 15 points will not be detectable. The pilot is for rates, variance, failure shares and hypotheses, **not significance claims**. Use its variance to size Set C (likely 200–300 tasks).

## 8. Improving Argus from the pilot, without fooling ourselves

Candidate changes, each mapped to a failure class so we test a mechanism and not a hunch:

| Failure class | Candidate Argus change |
|---|---|
| F2 format | Port the bare-`@@` hunk repair into the v0.2 parser; accept more wrappers; line-annotation stripping (already in) |
| F3 path | File-name fallback for hallucinated paths (production v3 had it, v0.2 does not) |
| F4 apply | "Closest match" feedback to the model instead of a bare refusal (Aider-style retry); ambiguity-aware disambiguation using surrounding lines |
| F5 syntax | Retry with the parse error and line shown |
| F7 wrong fix | Test-failure summarization; multi-sample plus test-based selection |
| F6 scope | Multi-file transactions (currently refused) |
| F8 regression | Run P2P subset before accepting |
| Cascade | Escalate to the larger model when the verifier fails twice |

Rules: each round is a git tag with a one-line hypothesis written **before** the run; at most three rounds on Set D; every round re-runs all arms; keep a ledger of every variant tried, including failures, so the final result discloses how many knobs were turned. Then freeze (tag `argus-frozen`), seal-open Set C, run once.

Fix the two known defects first (Tier 3 silent wrong applications; forgeable approval gate), because both change what "Argus accepts" means.

## 9. Decisions I need from you

1. ~~Reference model~~ Settled: `gpt-oss-120b`. A frontier-API reference (a few dollars on the same 50 tasks) is optional and would make the cascade-vs-frontier question testable.
2. ~~Qwen reasoning mode~~ Deferred with Qwen. Check how its thinking toggle works on Groq before that phase.
3. ~~Local or API~~ Settled: Groq API, free keys. Free keys are unmetered, so dollar cost is computed from tokens at a frozen price table (taken from Groq's console on the run date), not from billing.
4. **Reasoning effort for gpt-oss** (low/medium/high): pick one for the primary run and record the others as side arms. It changes both accuracy and tokens.
5. **Annotators:** who does the blind F7 and F9 review? Two people, not the author alone.

## 10. Paper

Working title: *Where Small Models Fail at Repository Repair, and What Verified Recovery Buys: A Stage-Decomposed, Cost-Accounted Study*.

Contributions the evidence could support (each only if the confirmatory run backs it):
1. A stage-decomposed failure taxonomy for small open models on repo-level repair, with oracle interventions that separate localization, formatting and reasoning.
2. A cost-and-quality Pareto for verifier-gated cascades with all-in accounting, including the break-even condition `s > r` and sensitivity to price ratios.
3. Measured wrong-location and passing-but-wrong rates for tolerant patch application (a gap I found no study of).
4. A reproducibility section: how leakage (test feedback, few-shot overlap, token caps, price tables) can inflate small-model results, replicated from this project's own earlier numbers. This is useful to others and honest.

Outline: Intro and RQs → Related work (Aider and apply formats, self-repair and Olausson et al., routing and cascades, SWE-bench validity) → Method (tasks, arms, regimes, taxonomy, oracles) → Results D then C → Failure anatomy → Gap decomposition → Cost → Safety audit → Threats to validity → Reproducibility package (manifests, hashes, price table, prompts, all variants tried).

Report negative results as results. If Argus's loop doesn't beat matched-compute best-of-N, say so; that finding is publishable. Venues to consider: an agent or LLM-for-SE workshop, a benchmarks or evaluation track, or an empirical-SE venue. Choose after Set C results, not before.

## 11. Order of work

1. Fix Tier 3 and the approval gate; port bare-hunk repair; freeze `argus-v0.3-pilot`.
2. Freeze the manifest and price table; commit and tag.
3. Smoke test on 3 tasks (tokens, disk, no truncation).
4. Pilot-50, all arms; label failures; blind review.
5. Up to three improvement rounds on D.
6. Freeze; build and seal Set C; power analysis from D.
7. Run C once; audit; write.


## Revision 3 (2026-11-10): no-oracle localization run (pre-registered before any localization or generation)

**Question.** The Pilot-100 prompts name the target file, taken from the gold patch (an oracle). How much of the resolve rate survives when the file must be found from the issue text alone?

**Localizers (neither sees the gold patch; gold is used only afterwards to score recall):**
- L-A: Argus `DeterministicLocalizer` as published (commit 467b720): traceback frame, explicit file paths in the issue, symbol extraction + `git grep`, its default `EXCLUDED_DIRS`. Run on a snapshot of the repo at the task's `base_commit` (GitHub tarball), `git init` + `git add` so `git grep` works.
- L-B: file-level BM25 over all non-test `.py` files of the same snapshot, query = issue text. (Matches the BM25 stage of the earlier project.)
- Primary pipeline file = L-A top-1; if L-A returns no candidate, L-B top-1. Reported separately: recall@1/3/5 for L-A, L-B and the primary.

**Generation.** Same prompt p1, same context builder, same models, effort medium, temperature 0, seed 1000, cap 8000, but the target file is the primary localizer's top-1. When the chosen file equals the oracle file the prompt is byte-identical to the oracle run and that output is reused (prompt hash checked). Apply: plain and stock Argus (v0.2.0b1, no prototype fixes). Docker grading: every patch for tasks where the chosen file is the oracle file reuses the existing grade. Patches for wrong-file tasks are graded on a pre-declared random sample (seed 7, up to 20 distinct patches); the rest are counted unresolved and flagged as extrapolated.

**Analysis fixed in advance.** Primary metrics: localization recall@1 (primary), resolve rate (plain, Argus) per model with the oracle run beside it, and the share of the oracle-to-no-oracle drop explained by wrong-file selection. Exploratory only; no tuning of localizers on these tasks.

### Revision 3 amendment (2026-11-11)
Generation and Docker grading for the issue-only run are DROPPED (owner decision; wrong-file edits almost never resolve, so the spend would confirm the obvious). Only localization recall is reported. Results: `data/loc/candidates.jsonl`, `data/loc/recall_summary.json`, `scripts/localize.py`, `scripts/loc_recall.py`. Gold file used only for scoring. The target-map output of `loc_recall.py` is not used for generation.


## Revision 4 (2026-11-11): temperature-1.0, 3-draw re-baseline (pre-registered before any call)

**Why.** The Pilot-100 primary runs used temperature 0, which is not the vendor-recommended setting for gpt-oss and is a known trigger for repetition loops. This run re-measures both models at temperature 1.0 so that (a) the loop finding is not a decoding artifact, (b) per-task success probabilities can be estimated from several draws, (c) the oracle router and stop-rule analyses stop depending on one lucky or unlucky sample.

**Design (fixed now).** Same 100 manifest tasks, same prompt p1 and context builder (target file GIVEN, as in Pilot-100; this is the "file-given" setting), models gpt-oss-20b and gpt-oss-120b on Groq, reasoning_effort=medium, temperature 1.0, top_p default, max_completion_tokens 8000, seeds 1000, 1001, 1002 (three draws per task and model). Output: `data/raw/phase2_t1_v1.jsonl`. The prompt hash must equal the Pilot-100 hash per task (checked after generation). Apply: plain exact line-match arm and stock Argus v0.2.0b1 (commit 467b720), no prototype fixes. Grading: official swebench harness in Docker, one image at a time, every distinct patch graded; gold-patch result reused from Pilot-100 (`results/grading/state.jsonl`).

**Analysis fixed in advance.** (1) Per-model resolve rate per draw and mean over draws with task-clustered bootstrap CI; (2) loop/truncation rate at temperature 1.0 versus 0; (3) per-task success probability from 3 draws, and the share of "solved by neither" tasks at temperature 0 that are solved by some draw; (4) the oracle router recomputed in three parts (model-choice only, must-attempt-all, and skip-hopeless), with and without the multi-draw smoothing; (5) offline stop-rule replays (stop after loop, after first failed attempt, after apply failure) reporting spend recovered and solves lost. All hypotheses exploratory; thresholds for rules are chosen on draws 1 and 2 and evaluated on draw 3 so no rule is scored on the data that tuned it.

## Revision 5 (2026-11-11, tag pilot100-loop-prereg): Argus-loop discovery run on the 99 valid tasks

**Status.** Discovery experiment. It uses the same 99 tasks as every earlier analysis, so its numbers are hypotheses for design, never claims. A separate confirmatory pre-registration (Revision 6) will be written after the loop design is frozen and a sealed task set is hashed. Nothing here is a SWE-bench score: the test-given arm shows test output to the model and is a different task setting from the leaderboard.

**Question.** Does feedback-driven repair (the Argus loop) solve more tasks than independent re-drawing at the same spend, and which failure classes does it repair?

**Fixed design.**
- Prompt p1 and the whole-file context builder as in Pilot-100 and Revision 4, plus one feedback block from turn 2 onward. Ladder, following `argus/runtime/controller.py`: turn 1 gpt-oss-20b, medium effort; turn 2 gpt-oss-20b, high effort; turns 3 and 4 gpt-oss-120b, high effort. Temperature 1.0, max_completion_tokens 8000, seed 2000 + turn. Up to 4 turns. Deviation from the real controller (stated, not hidden): the 25/45-line context radius is not replicated; the whole target file is given at every turn, as in the baselines. The real RecoveryController is used only in the confirmatory run.
- Apply: stock Argus apply engine (commit 467b720), no prototype fixes.
- **Arm L-B (test-given).** After a failed turn the model receives: for an apply or format failure, Argus's own error message; for a patch that applied, the output of the first failing FAIL_TO_PASS test only (name plus traceback/assertion text, truncated to 2,000 characters), not the test source, not the gold patch, not the other tests. Stop rule: stop when all FAIL_TO_PASS tests pass in the harness. Final status = official harness resolved (FAIL_TO_PASS and PASS_TO_PASS). Cases that stop on pass but fail PASS_TO_PASS are reported separately as "stopped but regressed".
- **Arm L-A (observable only).** Feedback is limited to what needs no test: format, apply, syntax errors. Stop rule: stop at the first patch that applies and parses. No test output is ever shown or used.
- **Baselines, no new generation.** (a) Independent re-draws on the same ladder (draws 1-2 of the 20B, then draws 1-2 of the 120B from Revision 4, test-gated stop, averaged over draw orders); (b) the 120B alone, up to 4 turns, from re-draws.
- Docker: one task image at a time; the image is kept for the task's turns and removed afterwards.

**Primary comparison (fixed in advance).** Resolved rate of L-B minus independent re-draws at matched cumulative dollar spend (Groq list prices), paired by task, task-clustered bootstrap 95% CI (2,000 resamples), reported as a curve over spend and as the difference at 1, 2, 3 and 4 turns.

**Secondary (exploratory).** Which failure class each solved turn repaired (loop, format, apply, wrong fix, regression); loop rate after feedback; L-A vs L-B (value of test feedback); stop-but-regressed count; cost per solve; per-turn token use; edit-location check (does the repaired patch overlap the gold region).

**What would count as evidence.** If the L-B minus re-draw CI excludes zero in favour of L-B at matched spend, feedback adds something beyond resampling in this setting. If it includes zero, the loop is spending tokens, not adding information. Either result goes into Report 5 with the discovery caveat.

**Not done here.** No tuning of the feedback format after seeing results. If a change is wanted it is a new revision and a rerun.

## Revision 6 (2026-11-12): Gemini Flash-Lite sweep, 3 draws, 100 tasks (discovery; pre-registered before the sweep)

**Status.** Discovery experiment on the same task set used for all design so far, so nothing here is a claim. Task set: the 99 valid tasks plus one replacement for the excluded `psf__requests-1766`. The first candidate, `psf__requests-2317` (the only requests reserve), was rejected before any Gemini call because its own gold patch fails the harness (target test `test_requests_history_is_saved` and four other tests fail with the correct fix applied; same kind of problem as 1766; its gpt-oss draws are kept in `data/raw/rejected_replacement_requests2317.jsonl` and unused). The replacement is therefore the next reserve entry in manifest order, `astropy__astropy-13579`, used only if its gold patch resolves in the official harness. gpt-oss-20b and gpt-oss-120b results on the 99 tasks are Revision 4; the replacement task was generated with identical settings (prompt hash 56e5b02fa8ed, 3 draws each, `data/raw/phase2_t1_repl.jsonl`).

**Exploratory probe already run (disclosed).** A 30-task, one-draw screen of `gemini-3.1-flash-lite`, `gemini-3.5-flash-lite` (medium effort) and `gemini-3.8-flash` (low effort), plus an issue-only contamination screen, was run before this revision (scripts `probe_gemini*.py`, `probe_contam.py`, data in `data/probe_gemini/`). Its numbers (3.1: 9, 3.5: 16, 3.8: 12 plain / 14 Argus of 30) informed the model choice and the price estimate. The probe's draw for the two Flash-Lite models is reused as draw 0 on those 30 tasks (identical settings); all other draws are new.

**Design (fixed now).**
- Models: `gemini-3.1-flash-lite` and `gemini-3.5-flash-lite` through Google's OpenAI-compatible endpoint. `gemini-3.8-flash` is excluded for cost and output cut-offs. `gemini-2.5-flash-lite` is not available to new users.
- Settings: prompt p1 and the 6,000-token context builder, target file GIVEN (the gold file, as in every earlier run, so this is the file-given setting, not a leaderboard setting); reasoning_effort medium, temperature 1.0, max_completion_tokens 16,000, no seed (not set through this endpoint), 3 draws per task and model.
- Apply: plain exact line-match arm and stock Argus v0.2.0b1 (commit 467b720), no prototype fixes, applied to the same frozen outputs. Grading: official swebench harness in Docker, one image at a time, every distinct patch graded; identical patches already graded are reused by (task, patch hash).
- Cost: tokens x list price on 2026-11-11 (3.1 Flash-Lite $0.25 / $1.50, 3.5 Flash-Lite $0.30 / $2.50 per 1M input / output; the 3.1 row was read from a page summary). Output tokens are total minus prompt tokens, because Gemini bills thinking tokens but leaves them out of the reported completion count. Hard cap: $5.00 of new spend; draws run in order (all draw 0, then draw 1, then draw 2) so a stop leaves complete draws.

**Analysis fixed in advance.** (1) Per model and arm (plain, Argus): resolve rate per draw and mean over draws with task-clustered bootstrap 95% CI. (2) Argus effect per model as the paired difference in resolved draws, with CI, and the numbers of rescued draws (plain fails to apply, Argus applies) and their pass rate; the same for the two gpt-oss models for comparison. (3) Failure funnel per model (truncated or empty, no blocks, edit not applied, applied but wrong, resolved). (4) Per-task success probability from 3 draws and pass-at-3; tasks solved by some Gemini draw but by no gpt-oss draw and the reverse. (5) Cost per solve for every model using the stated price book, and the oracle router and verifier-driven cascade across the four models (replays of recorded draws, Docker result as a perfect verifier, so upper bounds). All hypotheses are exploratory.

**Not done here.** No prompt or setting changes after seeing results; no use of the loop. Contamination: the issue-only screen found no sign of patch recall but could not rule out contamination, so absolute pass rates for the newer models may be inflated.

## Revision 7 (2026-11-12): clean test of test feedback vs independent re-draws (discovery; pre-registered before any call)

**Why.** Revision 5's loop did not beat re-drawing (53 vs 54.9 resolved), but its turns 2 to 4 ran at high effort and 56 to 91% of them spent the whole 8,000-token cap and returned no answer, so feedback was acted on in only about 10 turns. Revision 6's replay (`scripts/analyze_policies.py`, exploratory) found that sequentially re-drawing gpt-oss-120b (3 attempts, stop at first pass) beat every cross-model cascade per dollar. This revision asks one question with the cap problem removed: **does showing the model the failing test output help beyond simply drawing again?**

**Design (fixed now).**
- Task set: the 100 tasks of Revision 6 (`data/gemini_sweep/task_ids_full.json`). Same 99 tasks used for all design so far plus `astropy__astropy-13579`; discovery only, no claim.
- Model and settings, every attempt: gpt-oss-120b on Groq, reasoning_effort medium, temperature 1.0, max_completion_tokens 8000 (the Revision 4 setting, under which 120B truncated 0.3 of 100 draws), prompt p1 and the 6,000-token whole-file context, target file GIVEN, Argus v0.2.0b1 apply layer (commit 467b720, as in `harness/argus_apply.py`). Same model at every turn, so model and effort never change between attempts.
- Maximum 3 attempts per task and arm. Stop rule, identical for both arms: stop at the first patch that passes all FAIL_TO_PASS tests (what a test-gated loop can see). The task counts as solved only if that patch also resolves in the full official harness; a patch that passes the target tests but breaks others ends the task unsolved ("accepted but regressed").
- Arm R (independent re-draws): attempt d = 0, 1, 2 are separate calls with the same prompt, seed 5000 + d, no information from earlier attempts.
- Arm F (feedback): attempt 1 is arm R's draw 0 (identical request; shared). From attempt 2 the prompt is the same plus one feedback block, built exactly as in Revision 5 (`feedback_for`: apply or format failure, Argus's own message; applied patch whose target test fails, the first failing FAIL_TO_PASS test name and up to 2,000 characters of its failure text; never the test source or the gold patch; the previous patch itself is NOT shown). Seeds 6000 + attempt.
- Grading: official swebench harness in Docker, one task image at a time, distinct patches graded once, known grades reused by (task, patch hash).
- Cost: tokens x Groq list price (gpt-oss-120b $0.15 / $0.60 per 1M input / output, undated docs). No paid services.

**Analysis fixed in advance.**
- Primary: tasks solved within at most 3 attempts, F minus R, paired by task, task-clustered bootstrap 95% CI (5,000 resamples, seed 20261112), with the difference in total spend. If the CI excludes zero in F's favour, feedback adds something beyond resampling in this setting; if it includes zero, there is no evidence it does. Both outcomes are reported.
- Also reported: the same at at most 2 attempts; per-attempt resolve probability among tasks that reach attempt 2 and 3 (F vs R); how often the model returned an answer after feedback; share of F's attempts 2 and 3 that were apply failures vs test failures; accepted-but-regressed counts per arm; cost per solve; whether F-only solves edit the gold region.
- Power: with about 50 tasks failing attempt 1 and two more attempts each, an effect smaller than roughly 5 solved tasks cannot be distinguished from zero. A null is therefore "no effect larger than about 5 tasks", not "no effect".
- Reference only (not a comparison arm): the Revision 4/6 replay of 120B x3 under the same target-test stop rule (59.3 solved, $0.30).

**Not done / limits.** Whole target file at every attempt (the product controller uses 25/45-line windows); same tasks as all earlier design; file-given setting, not a leaderboard score; Groq prices are list prices of undated docs; backends can vary over time, which is why arm R is drawn fresh in the same session instead of reusing Revision 4 draws.

## Revision 8 (2026-11-12): repair loop that shows the model its own previous answer (discovery; pre-registered before any call)

**Why.** Revision 7 found that test feedback (failing test name and traceback) did not beat independent re-draws (57 vs 59 solved within 3 attempts, difference -2, CI -8 to +3). In that design the model did not see its own previous patch, so a retry could not know what it had already tried; a real chat or coding agent keeps that history. This revision tests that realistic variant.

**Design (fixed now).** Identical to Revision 7 (100 tasks of `task_ids_full.json`, gpt-oss-120b, medium effort, temperature 1.0, cap 8000, prompt p1 + whole target file, Argus v0.2.0b1 apply layer, at most 3 attempts, same stop rule: first patch that passes all FAIL_TO_PASS tests; solved iff that patch resolves in the full harness) except for the prompt of attempts 2 and 3. Arm P (previous answer + result): a multi-turn conversation: the original system and user messages, then for every earlier attempt an assistant message containing that attempt's full final answer (its SEARCH/REPLACE blocks and any text, truncated at 4,000 characters; hidden reasoning is not included) followed by a user message with the result block built exactly as in Revision 7 (first failing FAIL_TO_PASS test, name plus up to 2,000 characters of failure text; or Argus's apply error) and the same closing instruction to write corrected SEARCH/REPLACE blocks against the original file. Attempt 1 is identical to Revision 7's draw 0 (seed 5000, shared); attempts 2 and 3 use seeds 7000 + attempt.
- Comparators are the Revision 7 arms, not re-run: R (independent re-draws, seeds 5000 + d) and F (feedback without the previous answer). They were generated hours earlier on the same backend with identical settings.
- Cost: tokens x Groq list price as before; no paid services.

**Analysis fixed in advance.** Primary: tasks solved within at most 3 attempts, P minus R, paired by task, task-clustered bootstrap 95% CI (5,000 resamples, seed 20261112), with the spend difference. Secondary: P minus F; the same at at most 2 attempts; per-attempt resolve rate among tasks reaching attempts 2 and 3; accepted-but-regressed counts; cost per solve; feedback type and next outcome; whether P repeats its previous patch (identical patch hash to an earlier attempt of the same task). Effects under about 5 tasks cannot be distinguished from zero; a null is reported as such.

**Limits.** Same tasks as all design; whole file at every attempt; file-given setting; Groq list prices of undated docs; the hidden reasoning of earlier attempts is not shown (the API does not return it for re-use here).

## Revision 9 (2026-11-12): feedback vs independent re-draws on gpt-oss-20b (discovery; pre-registered before any call)

**Why.** Revisions 7 and 8 tested feedback only on gpt-oss-120b, chosen because it is the most cost-efficient model. The 20B fails to apply 23% of its edits and loses 6% of draws to empty output, so apply-failure messages and test output may matter more for it. This repeats Revisions 7 and 8 unchanged except for the model.

**Design (fixed now).** Identical to Revisions 7 and 8 (100 tasks of `task_ids_full.json`; reasoning_effort medium, temperature 1.0, max_completion_tokens 8000, prompt p1 + whole target file, Argus apply layer, at most 3 attempts, stop at the first patch passing all FAIL_TO_PASS tests, solved iff resolved in the full harness; seeds 5000 + d for re-draws, 6000 + attempt for feedback, 7000 + attempt for the multi-turn arm) with the model gpt-oss-20b (Groq list price $0.075 / $0.30 per 1M). Arms: R independent re-draws; F result block only; P multi-turn with the model's previous answer (attempt 1 shared with R draw 0). All three are run fresh in this revision. Truncated or empty outputs are ordinary failed attempts and receive the existing one-sentence message ("cut off... keep reasoning short") from Revision 5; no other message is added.

**Analysis fixed in advance.** Primary: tasks solved within at most 3 attempts, F minus R, paired by task, task-clustered bootstrap 95% CI (5,000 resamples, seed 20261112), with spend. Secondary: P minus R and P minus F; at most 2 attempts; per-attempt resolve rate among tasks reaching attempt 2 and 3; effect by feedback type (apply failure vs test failure vs truncated); accepted-but-regressed counts; cost per solve. Tasks that could not complete an attempt (token-per-minute limit, image pull failure) are counted unsolved and also reported left out. Effects under about 5 tasks cannot be distinguished from zero.

**Limits.** Same tasks as all design; whole file; file-given; Groq list prices; the 20B truncates more often at medium effort, which changes what a retry can do.
