# Report 5. Argus-loop discovery run (Revision 5, pre-registered tag `pilot100-loop-prereg`)

Date 2026-11-12. 99 valid tasks (same set as every earlier analysis), so everything here is a discovery number, not a claim. Runner `scripts/run_loop.py`, analysis `scripts/analyze_loop.py` -> `results/analysis/loop_summary.json`, trajectories `data/loop/trajectories.jsonl`. The test-given arm shows test output to the model and is not a SWE-bench score.

## Design as run
Ladder from `argus/runtime/controller.py`: turn 1 gpt-oss-20b medium, turn 2 gpt-oss-20b high, turns 3 and 4 gpt-oss-120b high, up to 4 turns, temperature 1.0, **max_completion_tokens 8,000**, whole target file given, first failing FAIL_TO_PASS test's failure text as feedback, stock Argus apply. Arm L-A (observable only) is read off the same trajectory (stop at the first applied patch). Baselines come from Revision 4 draws at **medium** effort: independent re-draws on the same ladder (stop when all FAIL_TO_PASS pass, averaged over draw orders), 120B x3 and 20B x3.

Deviations: the 25/45-line context windows of the real controller are not replicated (whole file at every turn); one added feedback sentence for a turn that produced no answer (not specified in the protocol); the baselines use medium effort while the loop's turns 2 to 4 use high effort. **This last difference confounds the primary comparison**: loop versus re-draw differs in feedback and in reasoning effort.

## Headline
| | Resolved (of 99) | Total spend | $ per solve |
|---|---|---|---|
| L-B, test-given loop | 53 | $0.758 | 0.0143 |
| L-A, observable only | 45 | $0.415 | 0.0092 |
| Independent re-draws, same ladder | 54.9 (mean over draw orders) | $0.340 | 0.0062 |
| 120B re-drawn x3 | 58.3 | $0.299 | 0.0051 |
| 20B re-drawn x3 | 47.5 | not computed here | |

Stops (L-B): 53 resolved, 39 used all 4 turns, 7 stopped with the target test passing but another test broken ("stopped but regressed").

## Primary comparison (L-B minus re-draw ladder, paired by task, task-clustered bootstrap)
- After turn 4: -2.0 pp (95% CI -10.4 to +6.8). No evidence that the loop beats re-drawing.
- At matched per-task spend the loop is **below** re-drawing at mid budgets: -9.0 pp (CI -16.7 to -1.8) at $0.004 and -14.8 pp (CI -23.0 to -7.1) at $0.006 per task. It is above only at one low budget ($0.0012: +6.4 pp, CI -0.3 to +13.1, not significant).
- L-B costs 2.2 times the re-draw ladder for the same number of solves. L-A (no test feedback) solves 45; test feedback is worth +8 solves for +$0.34.
- Resolved by turn: 38, 38, 46, 53. The 20B's high-effort turn 2 adds **0**; the gain comes from the 120B turns 3 and 4 (+8, +7). The loop's gain here is escalation, not feedback.

## Why the loop was weak: the token cap at high effort
| Turn | Model, effort | Hit the 8,000 cap with no answer |
|---|---|---|
| 1 | 20B medium | 11/99 (11.1%) |
| 2 | 20B high | **49/54 (90.7%)** |
| 3 | 120B high | 30/54 (55.6%) |
| 4 | 120B high | 30/46 (65.2%) |

Turn 2 averages 7,834 completion tokens against the cap of 8,000. At high effort most turns spend the whole cap on reasoning and return nothing. These are not all repetition loops (the earlier finding was about temperature-0 repetition); many are probably long legitimate reasoning that the cap cuts off. The pre-registered ladder therefore mostly tested the cap, not the feedback. The same effort setting may hurt the real Argus controller if its own output limit is similar; that needs checking in the Argus code and is not verified here.

## What feedback did when the model answered (exploratory, small numbers)
Previous turn applied but the test still failed (44 next turns): 34 next turns hit the cap, 6 gave another wrong fix, **4 resolved**. So among the 10 turns that returned an answer after test feedback, 4 resolved (40%). This is selected (the turns that answered are the ones that reasoned briefly) and n is tiny; it is a hypothesis for a cleaner run, not a result. After a no-answer turn: 11 of 90 next turns resolved (12.2%). After an apply failure or no edit: 0 of 20.

## Other findings
- **Visible-test pass is not correctness.** 7 of the 60 patches that made all FAIL_TO_PASS tests pass (11.7%) broke other tests. A loop that stops at the first passing test would ship these.
- Of the 15 patches resolved at turn 2 or later, 12 overlap the gold region (edit in the right place) and 3 are elsewhere.
- The loop solved 6 tasks no Revision 4 draw solved (django-14017, django-15315, pytest-6197, scikit-learn-14983, sphinx-9658, sympy-17139); 13 tasks solved by some Revision 4 draw were not solved by the loop.
- 11 of 99 turn-1 runs (medium effort, seed 2000) hit the cap, consistent with Revision 4.

## Reading
1. In this configuration the Argus loop does not beat independent re-drawing and costs about twice as much per solved task.
2. That result is not a clean test of feedback, because the loop's turns 2 to 4 ran at high effort and mostly exhausted the 8,000-token cap. The feedback mechanism was exercised on only about 10 answered turns after a wrong fix.
3. The cleanest next test holds effort at medium for every turn so the only difference from re-drawing is the feedback (and/or raises the cap). That is a new revision and a new run, with its own pre-registration; its result would again be a discovery number.
4. The stop-at-first-passing-test regression rate (about 12%) matters for the product claim regardless of the above.

## Caveats
Same 99 tasks used for design. Baselines are simulated from Revision 4 draws (medium effort), not run in the same session. Prices are Groq list prices from undated docs. Docker is the grader for both feedback and final status, so feedback uses benchmark test output (a real-use setting, not a leaderboard one).
