# Report 3. Follow-ups: truncation loops, apply-layer prototype, and cost (Pilot-100, discovery set)

Date 2026-11-10. All designs here were made after reading the 99 discovery tasks. These are discovery numbers, not claims about Argus; a claim needs a frozen design run once on tasks not used here.

## 1. The 21 truncations are repetition loops, not long thinking

- All 21 truncated 20B reasoning traces are highly repetitive: compression ratio 0.03 to 0.15 (finished runs: median 0.28). Many repeat one line 20 to over 200 times (`django-14771`: "They are stored in `sys.argv`? No." repeated).
- So "generate another 8k" would extend the loop. Pilot ran at temperature 0, a known loop trigger; 120B never looped.
- Simple compression-window detector (3,000 chars, ratio threshold 0.18) flags 19 of 22 length-capped runs at a median of ~3,200 reasoning tokens, with 2 false positives among 77 normal runs (one of them a passing run). Not safe to ship as is.

## 2. Temperature-1.0 rerun of the 22 length-capped tasks (20B, identical prompts, hash-checked)

Selection by an observable trigger (`finish=length`), not by any Docker result.

| Outcome | n |
|---|---|
| Finished with an answer | 16 |
| ... resolved in Docker | **3** (django-15315, django-16485, sympy-19346) |
| ... applied but wrong | 8 |
| ... not applied (no match, etc.) | 5 |
| Still hit the 8,000 cap | 6 |

Loops mostly break, but the tasks that were looping are hard: 3 of 22 solved (14%), consistent with 120B solving 2 of 21 of the same tasks.

## 3. Apply-layer prototype (`scripts/apply_proto.py`, research folder only)

Four fixes replayed on the 200 frozen outputs: empty-replacement parsing, `...` wildcard in SEARCH, collapse duplicated SEARCH lines, refuse a new `def f(self, …)` outside a class. 6 outputs change.

| Task (model) | Change | Docker |
|---|---|---|
| pydata__xarray-4356 (20B) | parser accepts empty REPLACE | PASS |
| sympy__sympy-11618 (20B) | `...` wildcard | PASS |
| django__django-11141 (20B) | parsed (was "no blocks") | fail: target tests pass, 1 previously-passing test breaks |
| django__django-14238 (20B) | duplicated line collapsed | fail: suite did not produce results |
| scikit-learn__scikit-learn-14983 (120B) | scope gate refuses | was a wrong patch |
| sympy__sympy-22914 (20B) | scope gate refuses | was a wrong patch |

Net: +2 solves for the 20B, and two wrong patches become clean refusals. Both fixes are small and general (the empty-REPLACE case is a genuine parser bug in the current Argus). Not yet ported to the Argus repo.

## 4. 20B tally with everything (discovery numbers, 99 tasks)

| Stage | 20B resolved |
|---|---|
| Plain one-shot | 31 |
| Stock Argus apply layer | 38 |
| + prototype apply fixes | 40 |
| + temperature-1.0 retry on length-capped tasks | 43 |
| 120B with stock Argus (for reference) | 46 |

Overlap check: the prototype tasks and the rerun tasks are disjoint.

## 5. Cost at Groq list prices (docs pages, undated; confirm before external use)

20B $0.075 in / $0.30 out per 1M tokens; 120B $0.15 / $0.60. Real token counts from the runs.

| | Cost per solved task |
|---|---|
| 120B plain (44) | $0.00349 |
| 120B + Argus (46) | $0.00334 |
| 20B plain (31) | $0.00414 |
| 20B + stock Argus (38) | $0.00338 |
| 20B all-in with rerun (43; rerun cost $0.043) | $0.00398 |
| same, if first-pass loops had been cut at ~3.3k tokens (estimate) | ~$0.00326 |

- 46% of the 20B's first-pass spend ($0.059 of $0.128) went to the 21 loops.
- Price ratio is 0.5 per token, but the 20B writes 2.3 times more tokens, so the per-task cost ratio is 0.83.
- A cascade (20B first, 120B when no patch applies) costs $0.0040 per solve with Argus, worse than 120B alone.
- Excludes Docker compute, retries beyond these, and free-tier effects.

## 6. Reading

At this model pair the cost story is parity at best: a 2x price gap is eaten by the small model's verbosity and loops, and the small model resolves fewer tasks. The apply-layer fixes and gates are worthwhile for correctness and safety independent of cost. A cost-saving claim needs a pair with a much larger price gap (or a frontier model as the reference), and a no-oracle run (file chosen by retrieval, not given) to measure the localization cost.
