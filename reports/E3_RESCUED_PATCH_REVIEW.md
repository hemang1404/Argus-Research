# E3 (partial): manual review of apply-layer-rescued resolved patches

Date 2026-11-14. Reviewer: one model reviewer (not blind, not independent of the analysis). Method: read each candidate diff against the gold patch. Nothing was re-run.

Scope: every Argus-arm patch that passed the official harness (all F2P and P2P) where the plain arm's patch for the same task, model and draw did NOT apply, i.e. resolved only because of the apply layer. Models: gpt-oss-20b and gpt-oss-120b (T=1, 99 tasks, 3 draws), Gemma 26B (3 draws). 47 draw-level rows, 38 unique patches, 26 tasks. Scripts: scripts/e3_collect.py, e3_triage.py, e3_show.py; data results/analysis/e3_resolved.json (all 342 resolved Argus-arm patches).

Max tier of the rescued rows: Tier 1: 2, Tier 2: 25, Tier 3: 20.

## Result (38 unique rescued patches)

| Verdict | n | What it means |
|---|---|---|
| Correct (same edit as gold, or an equivalent edit) | 29 | 4 identical to gold; 25 same behaviour with different code, comments, or omitted docstring changes |
| Partial | 5 | Fixes the tested case, narrower than gold |
| Fragile | 3 | Fixes the tested case but looks likely to break another real case (not executed) |
| Equivalent by luck | 1 | Garbled output that nets out to the gold behaviour |

None of the 38 was clearly wrong in the sense of fixing nothing or fixing the wrong thing. 9 of 38 (24%) are not clean fixes.

## The 9 that are not clean

- Partial (5): astropy-8872 (gpt-oss-20b; skips the Quantity-input path, still upcasts bool); matplotlib-24970 (gpt-oss-20b; casts unsigned ints early instead of suppressing the cast warning, narrower); sympy-14531 (gpt-oss-20b and Gemma, 2 draws; fix _print for Limit/Relational/Piecewise-style cases, gold fixes about a dozen printers).
- Fragile (3, confirmed by execution): sphinx-11445 (gpt-oss-120b, Gemma x2). The fix replaces the docinfo regex with one that needs whitespace after the second colon (`:\w+:\s`, `:\w+: .*`). A docinfo field with no value (e.g. `:orphan:`) would no longer match, so a prolog would be inserted above it. Inferred from the regex, not executed.
- Equivalent by luck (1): pytest-5262 (Gemma). The patch contains repeated `__init__` blocks, a `# ... (lines omitted) ...` comment, and a stray `__getattr__`. The later definitions in the class override the junk, so the final behaviour matches gold.

Other notes: three Gemma patches contain duplicated dead code (django-11964, matplotlib-25311, sympy-11618) that Python's later-definition-wins rule makes harmless; matplotlib-20488 (gpt-oss-20b) adds unrequested vmax clamping on top of the correct fix.

## What this does and does not show

- Supports: the apply layer does not turn wrong patches into passes by lowering the bar. Most rescued passes are real fixes. Tier 3 produced the junk and the duplicated code, which fits the audit's C1 concern about Tier 3.
- Does not show: this is the rescued subset only (47 rows). The other 295 resolved rows were only triaged automatically (40 identical to gold; 210 overlap but differ; 45 touch lines the gold patch does not), not read. The "fragile" calls are reasoning from the diff, not execution. One reviewer, not blind.
- Suggested follow-up: execute the three sphinx-11445 candidates on a `:orphan:`-style input, and read the 45 no-overlap rows from the non-rescued set.

---
# E3 (full): review of the other resolved patches (added 2026-11-14)

Scope: all 342 resolved Argus-arm rows (gpt-oss-20b, gpt-oss-120b at T=1; Gemma 26B) = 265 unique (task, patch) pairs. Rescued 38 (above, my own reading). Not-rescued 227: 11 identical to gold (counted correct), 216 read by five parallel reviewer agents (44/44/44/44/40 per chunk), each told to compare behaviour to gold, be skeptical, and not run anything. Verdicts: results/analysis/e3_all_verdicts.json.

| Verdict | Rescued (38) | Not rescued (227) | All (265) |
|---|---|---|---|
| Correct (incl. 15 identical to gold) | 29 | 165 | 194 (73%) |
| Partial | 5 | 15 | 20 (8%) |
| Wrong or fragile | 3 | 46 | 49 (18%) |
| Junk but equivalent | 1 | 1 | 2 (1%) |

- Non-clean (partial + wrong/fragile): rescued 8/38 = 21%; not rescued 61/227 = 27%. The apply layer's extra passes are about as good as ordinary passes, so it does not inflate the score disproportionately.
- By model (wrong/fragile among reviewed not-rescued): gpt-oss-120b 22/113, gpt-oss-20b 18/66, Gemma 26B 6/37. Small cells; repeated draws of the same task are counted separately.
- By task: 18 of the 59 reviewed not-rescued tasks have at least one flagged patch. Heavy repeats: django-12209 (7 patches), matplotlib-25311 (5), django-13933 (4), xarray-4356 (4), sphinx-10466 (4).
- Confidence: only 15 of the 46 wrong/fragile calls are marked high confidence by the reviewers.

Typical findings (reviewer claims, unexecuted): a pk-default fix that turns the new single-INSERT optimisation off (django-12209, no wrong data, extra query); int32 downcast that wraps large values (matplotlib-24970); pickling fix that drops the canvas on unpickle (matplotlib-25311); a changed default error message (django-13933); `cv=None` raising TypeError (scikit-learn-25973); a swallowed exception that stops a version check from raising (sphinx-9711); regex fix needing trailing whitespace (sphinx-11445).

Limits: all verdicts are by reading; the 216-patch pass is model-reviewed, not human-reviewed or executed; reviewers saw only diffs (some read source); severity varies from "wrong output" to "lost optimisation / untested edge case". Treat 18% as a plausible estimate of how much "resolved" overstates correctness for these small models, with a wide margin.

## Execution check of the three sphinx-11445 "fragile" patches (2026-11-14)

Ran in the official swebench image for sphinx-11445 (script results/analysis/t11445.py), calling `prepend_prolog` on three inputs. Unpatched code keeps `:orphan:` first and puts the prolog after it (correct). All three candidates (gpt-oss-120b s0, Gemma s0, Gemma s2) insert the prolog BEFORE a bare `:orphan:` line, a regression, while fixing the `:mod:` heading case. `:author: Me` still works. So the reading-based "fragile" call is confirmed by execution for these three. The existing test suite did not catch it.
