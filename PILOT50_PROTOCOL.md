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
