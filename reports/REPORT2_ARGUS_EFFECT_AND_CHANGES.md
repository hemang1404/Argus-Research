# Report 2. What Argus recovers, where it falls short, and what to change (Pilot-100)

Status: exploratory, one sample per task. Date 2026-11-10. Companion to `REPORT1_WHY_SMALL_MODELS_FAIL.md` (same tasks, same frozen model outputs, same Docker grading).

**What was run.** The *same* model outputs as Report 1 were applied a second way: through Argus v0.2.0b1 as published (repo commit `467b720`, default settings: similarity 0.82, ambiguity margin 0.10, AST gate on, Tier 4 off), using its own parser, single-target check and `ResilientPatchEngine`. No model was called again. So this measures **Argus's apply layer only**. Argus's retry and test-feedback loops were **not** exercised and are not evaluated here.
Valid tasks 99 (`psf__requests-1766` excluded: the gold patch fails a flaky test).

---

## 1. Headline

| Arm | Resolved / 99 | 95% Wilson CI |
|---|---|---|
| 20B plain | 31 | 23.0 to 41.0 |
| 20B + Argus | 38 | 29.4 to 48.2 |
| 120B plain | 44 | 35.0 to 54.3 |
| 120B + Argus | 46 | 37.0 to 56.2 |

- **20B: +7, no losses** (7 tasks gained, 0 lost; exact McNemar p = 0.016). Applied patches rose from 58 to 67.
- **120B: +2, no losses** (p = 0.5).
- **Gap to the large model:** 20B plain vs 120B plain was 13 tasks (p = 0.007). 20B + Argus vs 120B plain is 6 tasks (p = 0.24, no longer distinguishable at this n). The fairer comparison, 20B + Argus vs 120B + Argus, is 8 tasks (4 only-20B, 12 only-120B, p = 0.077).
- Argus added zero model tokens and no extra calls.
- Argus did not touch the three biggest failure buckets: 21 truncations, 28 wrong or broken fixes (20B), and the context-less tasks.

## 2. Where the 7 extra solves came from

All seven were plain "SEARCH text not found" failures that Argus's engine located:

| Task (20B) | Tier that applied | Result |
|---|---|---|
| scikit-learn-11578 | 1 exact | PASS |
| scikit-learn-13496 | 1 exact | PASS |
| matplotlib-20488 | 2 whitespace-normalized | PASS |
| sphinx-9230 | 2 | PASS |
| sphinx-9711 | 2 | PASS |
| sympy-13480 | 2 | PASS |
| pytest-5262 | 3 fuzzy (sliding window) | PASS |

Three more 20B "not found" cases were also applied (django-16642 tier 2, sympy-21596 tier 2, sympy-24539 tier 3) but the fix is wrong (section 4). For 120B: sklearn-11578 and sympy-13480 (both tier 2) pass; sklearn-14983 and sympy-21596 apply but are wrong.

## 3. How much of this is Argus, and how much is just a decent apply tool? (important)

The plain arm in Report 1 is deliberately strict: SEARCH must equal whole lines, uniquely. Real edit tools are more forgiving. Because a better plain tool and Argus put the same text in the same place when the match is exact or whitespace-only, their graded results are identical, so I can build a baseline ladder from the data without re-grading:

| Apply rule | 20B resolved | 120B resolved |
|---|---|---|
| Line-exact, unique (my plain arm) | 31 | 44 |
| + exact substring (a normal `str_replace`) | 33 | 44 |
| + whitespace/indent normalization (Aider-style) | 37 | 46 |
| + Argus Tier 3 fuzzy window (full Argus) | 38 | 46 |

Reading:

- **6 of the 7 extra solves for 20B, and both for 120B, come from tiers any competent edit tool already has** (substring match and indentation tolerance). Only **1 solve (pytest-5262) needs true fuzzy matching.** Against a reasonable baseline, Argus's distinctive apply gain is about +1 task for 20B and 0 for 120B.
- This pilot does not support attributing the gain to fuzzy matching.
- The honest framing of the result is: *"a tolerant apply layer is worth about 6 solves for a 20B model at this setting (31 to 37)"*, not *"Argus's fuzzy engine is worth 7"*. Argus's real contributions beyond that are the gates (next section), not the matching.

## 4. Safety: what the gates did (the part that is Argus-specific)

Every non-exact application (tier 2 or 3) across both models, 12 events: 7 passed, 5 were wrong fixes. Plus the refusals:

| Event | Count | Detail |
|---|---|---|
| Tier 1-2 apply, correct | 7 | see section 2 |
| Tier 2-3 apply, wrong fix | 5 | django-16642, sympy-21596, sympy-24539 (20B); sklearn-14983, sympy-21596 (120B) |
| Refused: AST syntax gate | 3 (20B) | django-14238 and sympy-17655 (tier 3 landed on code that does not parse), xarray-4356 (a stray `>>>>>>> REPLACE` marker in the replacement; plain applied it as a syntax error) |
| Refused: ambiguous exact match | 3 (20B) | matplotlib-24637, sympy-15017, sympy-16792: SEARCH occurs 2 to 4 times |
| Refused: ambiguous fuzzy match | 2 | django-16595 (20B), matplotlib-23412 (120B): top two windows within 0.10 |
| Refused: nothing close | 2 (20B), 9 (120B) | model invented text; no tier can help |

- The **AST gate did its job three times** (3 patches that would have been syntax errors were stopped, one of them a plain-arm syntax-error patch).
- The **ambiguity guards did their job**: no pass was lost to a refusal (0 plain passes turned into refusals), and the two fuzzy ties were genuinely ties.
- **One real false positive:** sympy-24539 (20B). The model, with none of the target region in its prompt, guessed a one-line SEARCH (`return expr_from_dict(self, self.ring, self.ring.symbols)`). Tier 3 matched it at similarity 0.8235 against a different method's line (`to_dense`: `return dmp_from_dict(self, self.ring.ngens-1, self.ring.domain)`) and applied it, introducing an undefined name. The AST gate accepted it (undefined names parse fine). Result: 13 other tests broke. The runner-up margin passed. This is the failure mode flagged in the audit (short single-line SEARCH blocks are easy to fuzzy-match to the wrong place) and it has now shown up once in the data.
- Tier-3 outcomes in total: 6 events, 1 correct apply, 1 wrong apply, 2 syntax refusals, 2 ambiguity refusals. Small numbers, but 1 of 2 accepted fuzzy edits was wrong and a one-liner would have prevented it (section 6, change C4).
- Caveat on "wrong fix": in this experiment nothing but the hidden tests judged the patches. Argus in production would run the user's tests as a gate; some of these 5 would be rejected there. This pilot does not measure that.

## 5. What Argus cannot fix (by design, as it exists today)

20B, after Argus, 61 failures:

| Remaining failure | n | Untouched by apply layer? |
|---|---|---|
| Budget truncation, no output | 21 | yes |
| Wrong fix / regression / startup crash | 29 (17 + 9 + 2 + 1) | yes |
| Not applied: no match 2, ambiguous 4, syntax-gate 3 | 9 | partly (could be retried) |
| Unparseable output | 2 | yes |

The 12 tasks 120B plain solves but 20B + Argus does not: 2 truncations, 5 not applied, 1 unparseable, 1 startup crash (wrong fix in effect), 3 wrong fixes. **The remaining gap is still mostly pipeline losses (8 of 12), not reasoning.** (Again descriptive; we do not know what those 8 would score if they got through.)

## 6. What Argus should change, mapped to evidence

Ordered by expected value over cost. Each says what it targets, why, and how to test it. None of these has been implemented or tested; per the protocol they must be developed on this discovery set and then confirmed once on a sealed set.

**C1. Budget-aware generation (targets 21 tasks, 21%).** Evidence: 21 of 99 20B runs end at the 8,000-token cap with a median of 7,858 reasoning tokens and no answer; 120B never does. Change: cap thinking and retry on `finish=length` with lower reasoning effort or an instruction to answer now. Expected: bounded by the fact that 120B solves only 2 of those 21, so perhaps 2 to 6 solves. Test: rerun just those 21 tasks (cheap) at `reasoning_effort=low`, and with a larger cap, to separate "budget" from "capability".

**C2. Closest-match feedback and one repair retry on apply refusal (targets 9 tasks for 20B, 12 for 120B).** Evidence: 20B has 2 no-match, 4 ambiguous, 3 syntax refusals after Argus; 120B has 9 no-match and 3 ambiguous. Change: on refusal, return the actual closest file region (or the multiple match locations) to the model and ask for a corrected block. Expected: 3 to 6 solves; the invented-text cases need the model to see the real code. Cost: one extra call on failures only.

**C3. Regression gate using the repository's existing tests (targets the F8/F78 class: 11 tasks for 20B, 14 for 120B, Argus arm).** Evidence: 11 of 20B's applied patches and 14 of 120B's break previously-passing tests. Those tests exist in the repo and can be run before accepting a patch; no hidden test is needed. Change: run the touched test files; reject or retry on new failures. Expected: converts some wrong patches into clean failures (a safety gain), and into fixes when the retry uses the failure output.

**C4. Make Tier 3 stricter (targets the sympy-24539 failure).** Evidence: 1 of 2 accepted fuzzy edits was wrong; the false match was a one-line SEARCH landing in a different method. Change: disable tier 3 for SEARCH blocks of 1 to 2 non-blank lines, or require the match to sit in the same enclosing `def`/`class` that the SEARCH's own context implies; add an undefined-name check (pyflakes-style) to the AST gate, which would have flagged `symbols`. Cost: tiny. Risk: loses short true-positive fuzzy matches. I have not checked whether pytest-5262's SEARCH block (the one correct tier-3 apply) would survive the rule; check that before shipping.

**C5. Keep Tiers 1-2 as the default and say so.** Evidence: section 3. They give essentially all of the apply-layer gain. Report which tier fired in telemetry so tier-3 claims can be audited.

**C6. Context acquisition (targets the 18% with zero coverage and part of the wrong-fix class).** Evidence: zero-coverage tasks are solved 1 in 18 times by either model; the largest wrong-fix classes are "wrong location" and "partial fix", i.e. under-exploration. Change: a bounded read step where the model asks for a function or class by name before editing (still single-file, still bounded). This is the largest structural change and the largest likely upside, and also the one that moves Argus from "a repair runtime" toward an agent. Decide deliberately.

**C7. Sample-and-select with a test gate (cost lever).** The cascade economics only works if a cheap model's answer can be accepted without calling the big model. A gate (C3) plus a second cheap sample may raise the accepted-correct rate. Not tested.

## 7. Does Argus help a small model match a bigger one? (the original question)

On this pilot, partly, at the apply layer only:

- 20B + Argus gets within 6 tasks of 120B plain (38 vs 44; not distinguishable at n=99). The gap to 120B + Argus is 8.
- Most of that closure is a tolerant edit tool, not Argus's novel parts.
- The remaining gap is mostly truncation and unrecovered apply failures, which C1 and C2 target.
- **Cost is not shown.** The 20B writes 2.3 times more tokens per task than 120B (mean completion 3,094 vs 1,360). Whether 20B is cheaper per solved task depends on the price ratio between the models: if 20B's output-token price is about 44% or more of 120B's (1 / 2.3), the 20B is *not* cheaper per task here, and it resolves fewer tasks. I have not verified current Groq prices, so I make no cost-saving claim. This must be settled before any "saves money" statement; token counts per arm are in `records.jsonl`.

## 8. Limits

- Exploratory: 99 tasks, one sample each, McNemar tests unadjusted for multiple comparisons; treat p-values as descriptive.
- Apply layer only; Argus retries, test loops and Tier 4 anchors were not run.
- The baseline ladder in section 3 is derived (identical-diff argument), not separately graded. The argument holds for tiers 1 and 2 when matches are unique; I did not re-grade a substring-exact tool end to end.
- All design changes in section 6 came from reading these same 99 tasks; their effect must be tested on tasks not used here.
- Telemetry caveat: "wrong fix" is judged only by the benchmark's hidden tests; a correct alternative fix that the tests reject would count as wrong.

## 9. Proposed next steps (need your decision)

1. Run C1 on the 21 truncated 20B tasks (about 21 calls, small): isolates budget from capability.
2. Run the Phase-2 loop (C2 repair retry, C3 regression gate) on both models' failures only, and re-grade just the changed patches.
3. Verify Groq pricing, then compute cost per resolved task with the real token counts.
4. Build C4 (stricter tier 3 plus undefined-name check) and measure it by replaying the 6 tier-3 events.
5. Second annotator for the wrong-fix categories before any paper claim; then freeze a design and run a sealed confirmatory set.

## 10. Files

`results/analysis/summary.json`, `records.jsonl`, `deep.json` (includes `baseline_ladder_*` and tier lists), `data/phase1/argus_apply_*.jsonl` (per-task Argus tier, confidence, refusal reason), `results/grading/state.jsonl`, `scripts/analyze.py`, `scripts/deep_dive.py`.
