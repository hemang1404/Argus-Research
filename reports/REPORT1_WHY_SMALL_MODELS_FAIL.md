# Report 1. Why does the small model fail? (Pilot-100, no Argus)

Status: exploratory, one sample per task. Date 2026-11-10.
Models: `openai/gpt-oss-20b` (small) vs `openai/gpt-oss-120b` (reference), Groq free tier, `reasoning_effort=medium`, temperature 0, seed 1000, 8,000 output-token cap, prompt version p1.
Tasks: 100 single-file SWE-bench Verified tasks (manifest sha256 `820d412d…12a5ca`, pre-registered at tag `pilot100-prereg`); Django capped at 30.
Grading: official `swebench` 5.0.2 harness in the pre-built Docker images; the gold patch was graded as a control on every task.

**Valid tasks: 99.** `psf__requests-1766` is excluded: the gold patch itself fails one pass-to-pass test (`test_mixed_case_scheme_acceptable`), so the harness cannot judge that task. It has not been replaced from the reserve list.

---

## 1. Headline

| Arm | Resolved | Rate | 95% Wilson CI |
|---|---|---|---|
| gpt-oss-20b, plain one-shot | 31 / 99 | 31.3% | 23.0 to 41.0 |
| gpt-oss-120b, plain one-shot | 44 / 99 | 44.4% | 35.0 to 54.3 |

Paired: 27 solved by both, 4 only by 20B, 17 only by 120B, 51 by neither (exact McNemar p = 0.007). The 13-task gap is real at this size.

Nothing here is a benchmark rate. The sample is Django-capped and the model is told which file to edit, which removes most of the localization problem that dominates real SWE-bench runs.

## 2. Where each task stopped (earliest failing stage)

Plain arm, 99 tasks each:

| Stage reached | 20B | 120B |
|---|---|---|
| Model produced a usable answer | 78 | 99 |
| ... answer parsed and addressed the target file | 76 | 98 |
| ... SEARCH text applied to the file (exact, line-aligned) | 58 | 82 |
| ... resolved by hidden tests | 31 | 44 |

Failure labels (plain):

| Label | 20B | 120B |
|---|---|---|
| PASS | 31 | 44 |
| F1 budget truncation (hit 8,000 tokens, no answer) | 21 | 0 |
| F2 unparseable or empty edit | 2 | 0 |
| F3 wrong file | 0 | 1 |
| F4 SEARCH text not found | 15 | 14 |
| F4 SEARCH text ambiguous (matches more than once) | 3 | 2 |
| F5 applied but syntax error | 1 | 0 |
| F6 applied, suite crashes at startup | 1 | 0 |
| F7 wrong fix (target tests fail, nothing else breaks) | 15 | 25 |
| F8 target passes, other tests break | 2 | 6 |
| F7+F8 both | 8 | 7 |

Two numbers matter most:

1. **Once a patch lands, the two models are indistinguishable.** Of patches that applied, 20B passes 31/58 (53.4%) and 120B passes 44/82 (53.7%). On the 57 tasks where *both* models got a patch applied, 20B solved 31 and 120B solved 32.
2. **The gap is mostly pipeline losses, not reasoning.** Of the 17 tasks that 120B solves and 20B does not, 14 are pipeline losses: 9 SEARCH-not-found, 2 truncations, 1 unparseable, 1 syntax, 1 startup crash; at most 3 are plain wrong fixes. (The crash is a wrong fix in effect: the patch calls `.name` on a string.)

Caution on (1) and (2): they are descriptive. We do not know whether the 24 extra tasks 120B gets applied would have passed for 20B, because the tasks where 20B lands a patch are probably the easier ones. "Equal conditional pass rate" does not prove "equal reasoning". It does show the 20B deficit is concentrated *before* the tests run.

## 3. Failure class 1: the 20B model runs out of budget thinking (21 of 99)

- 21 of 99 tasks end with `finish=length` at 8,000 tokens, no answer. Median reasoning on these: 7,858 tokens. 120B never truncated (max completion well under 8,000).
- Mean completion tokens: 20B 3,094, 120B 1,360. The smaller model *writes 2.3 times more* while being worse. Same prompt size on average (4,911 tokens).
- **These are the hard tasks, not random bad luck.** 120B solves only 2 of those 21 (9.5%), against 42 of the other 78 (53.8%). 120B also reasons about twice as long on them (median 1,405 vs 711 tokens).
- Only 8 of the 21 have the gold edit region inside the prompt, so for 13 the model could not have succeeded from the provided context either (see section 6). Truncation and missing context are overlapping causes, not alternatives.
- Truncated tasks are spread across repos (Django 6, matplotlib 4, sympy 4, pytest 3, others 1 each).

Answer to the earlier worry ("the 8k budget may be stopping a solvable task"): for most of these, probably not. A bigger budget would have rescued perhaps the few that 120B also solves. We did not run the 20B with a larger cap, so this is an inference and the proper test is Phase 2 (retry with a lower reasoning effort, or a larger cap on just these tasks).

Excluding the 21 truncated tasks, 20B plain is 31/78 = 39.7%, and 120B plain on the same 78 is 42/78 = 53.8%.

## 4. Failure class 2: the edit does not land (18 of 76 attempts for 20B; 16 of 98 for 120B)

When the model writes a SEARCH/REPLACE edit, the SEARCH text must be found in the file. Plain exact matching fails often, and the *kind* of mismatch matters for the Argus report:

- 15 (20B) and 14 (120B) "not found" cases. In the cases Argus later recovered, the SEARCH text was a correct copy of the code with a trivial difference. Checked on five of them: the model dropped the leading indentation on the first line of the SEARCH (sklearn-11578, sklearn-13496: exact substring present, but not line-aligned), or drifted indentation inside the block (sympy-13480, matplotlib-20488, sphinx-9230: identical after stripping whitespace).
- The remaining "not found" cases include ones where the model wrote a plausible line that does not exist (for example sympy-24539, where the prompt had none of the target region). No whitespace tolerance can fix that. I did not inspect every remaining case.
- 3 (20B) and 2 (120B) "ambiguous" cases: the SEARCH text appears more than once in the file. The model chose too little context to be unique.

**This is a tool-strictness effect as much as a model effect.** My plain arm requires line-exact, unique matches. A normal `str_replace` tool matches substrings, and Aider-style tools also tolerate indentation drift. Section 3 of Report 2 shows what happens against fairer baselines. Do not read the apply-failure numbers as "20B cannot copy code".

## 5. Failure class 3: wrong fix (the real reasoning failures)

25 of 20B's applied patches are wrong (15 target-test-fail, 2 regression, 8 both) and 38 of 120B's (25, 6, 7). Applied patches overlap the gold edit region (within 5 lines) 16 of 25 times for 20B and 25 of 38 for 120B; the rest edit somewhere else. Patches that overlap the gold region pass 28 of 44 times (20B) and 41 of 66 (120B); patches that edit elsewhere pass 3 of 12 and 3 of 16.

I read all 28 of 20B's wrong or broken applied patches (the 25 plain plus 3 more that only apply under Argus) next to the gold patch and the issue text. Single annotator, not blind, based on the diffs and the test counts (I did not run the patches by hand). Categories overlap in a few cases; I assigned the dominant one.

| Type | n | Example | What it looks like |
|---|---|---|---|
| Partial fix: right place, not all of it | 8 | django-12039, sphinx-10435, sphinx-10614, astropy-14182, django-14534, sympy-13798, sympy-24066, sphinx-8459 | Edits one of the three spots the gold edits, or handles the headline case (`exp`) only. |
| Wrong location or wrong mechanism | 8 | astropy-12907, django-14017, django-11087, sphinx-9258, sphinx-9658, sympy-22914, sklearn-14983, sympy-15875 | Treats the symptom with a new function or a large rewrite. Gold is often a one-line change somewhere else. |
| Over-broad or invented change that breaks other tests | 5 | sklearn-14710, sklearn-25973 (67 other tests break), psf-2931, django-12774, sympy-13551 | Uses an attribute that does not exist, or loosens a check so other behaviour changes. |
| Near-miss on a fact | 5 | django-16642 (`x-compress` for `compress`), django-16877 (`escape` for `conditional_escape`), django-13551 (hard-coded `email` rather than the declared email field), django-15161 (13 decorators where 6 are right), astropy-13033 | Correct idea, one wrong name, spelling or message. |
| Logic inversion | 1 | sympy-21596 (`-=` replaced by `&=`) | Wrong set operation. |
| Fuzzy edit applied in the wrong function | 1 | sympy-24539 | Not a model reasoning failure alone; see Report 2. |

Takeaways, as hypotheses:

- The dominant wrong-fix pattern is **"patches the symptom the issue describes rather than the cause"** and **"fixes one of several sites"**. Both are under-exploration of the code, not syntax or format.
- Five wrong fixes are single-token factual errors in an otherwise correct patch. Test feedback (a failing test names the bad token) is the natural fix; this is what Phase 2's test-feedback loop should address.
- Where the issue text spells out a fix (sympy-22914 asked for `_print_Min`/`_print_Max` methods), the model followed it literally and the hidden tests still failed. I did not trace why; it deserves a look.
- 120B's wrong fixes look similar by size but are larger (median 11.5 changed lines vs 5 for 20B, gold median 6.5). I did not categorize them.

## 6. Context coverage (what the model was shown)

Coverage = fraction of the gold patch's changed old lines that were inside the prompt. Measured from the gold patch, never shown to the model. 38 tasks were given the whole file; 61 got BM25-selected chunks.

Among the 78 tasks where 20B produced an answer:

| Coverage | n | 20B plain pass | 20B Argus pass |
|---|---|---|---|
| Whole gold region in prompt | 62 | 26 (42%) | 31 (50%) |
| Partial | 8 | 4 | 5 |
| Zero | 8 | 1 | 2 |

For 120B (99 tasks): full coverage 70 tasks, 37 pass (53%); partial 11, 6 pass; zero 18, 1 pass.

- **18 of 99 tasks (18%) give the model zero coverage.** Neither model solves more than 1 of them. These are context failures, not model failures, and are a floor on what any one-shot arm can do here. This is a harness limit (the free-tier 8k prompt budget with BM25 retrieval), not an Argus property.
- Whole-file context helps 120B a lot (20 of 38 solve = 53%, versus 24 of 61 = 39% for chunked context) and 20B much less (10/38 vs 21/61). Both are confounded by file size.

## 7. Difficulty and repo effects

- Fix size (gold changed lines 0-3 / 4-6 / 7-12 / 13+; n = 29 / 28 / 22 / 20): 20B truncations 8 / 4 / 4 / 5; 20B Argus passes 10 / 12 / 8 / 8; 120B Argus passes 13 / 16 / 10 / 7. No clear trend for 20B; 120B does worse on the largest fixes. Too few per bucket to say more.
- By repo (20B plain / 120B plain, pass of n): Django 9/12 of 30; sympy 5/9 of 21; sphinx 3/5 of 11; matplotlib 3/4 of 9; scikit-learn 3/5 of 9; astropy 3/2 of 6; xarray 3/4 of 5; pytest 1/2 of 5; requests 0/0 of 2. Clustering by repo is real; per-repo counts are too small for conclusions.

## 8. What this tells us about "why small models fail"

1. **Budget and verbosity** (21%): the 20B model over-thinks on hard tasks and never answers. This is a configuration problem as much as a capability one, and a cheap one to attack (lower reasoning effort, early stop, retry).
2. **Edit mechanics** (about 18% of attempts): copy errors in SEARCH text. Largely recoverable, and shared with the large model (14 not-found for 120B).
3. **Context** (18% of tasks have none of the gold region in the prompt): a ceiling for any approach until localization improves.
4. **Genuine reasoning** (25 of 78 answered tasks for 20B end as wrong fixes, 32%): symptom-patching and partial fixes. Real, but smaller than the 31% vs 44% headline suggests.

What we cannot say: that the 20B is "as good as 120B" when the pipeline works. The data are consistent with that on the subset where both apply, but that subset is selected, and the run is one sample per task at n=99.

## 9. Threats to validity

- One sample per task, temperature 0, seed fixed. Run-to-run variance is not measured; a paired re-run on 20 tasks would bound it.
- Wrong-fix categories are a single unblinded reading. Treat the counts as indicative. Second-annotator labelling is planned before any paper claim.
- Prompt p1 only, file-level scope, target file given. Results do not transfer to multi-file or agentic settings.
- Repo mix is Django-capped and not benchmark-proportional.
- Free-tier constraint (8k prompt budget, BM25 chunks) is in force for both models; a better retriever would change the coverage numbers.
- The plain arm is deliberately strict; see Report 2 for the effect.
- The gold-patch control passed on 99 of 100 tasks; the one failure is a real flaky or environment-dependent test.

## 10. Files

`results/analysis/summary.json`, `results/analysis/records.jsonl` (one row per task and model), `results/analysis/deep.json` (breakdowns above), `results/analysis/wrongfix_20b_dump.txt` (the 28 gold-vs-model diffs read for section 5), `results/grading/state.jsonl` (251 graded patches), `scripts/analyze.py`, `scripts/deep_dive.py`.
