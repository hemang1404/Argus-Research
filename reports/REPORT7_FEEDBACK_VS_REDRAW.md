# Report 7. Does test feedback help beyond drawing again? (Revision 7, pre-registered tag `pilot100-loop2-prereg`)

Date 2026-11-12. 100 tasks (Revision 6 set), gpt-oss-120b, medium effort, temperature 1.0, cap 8000, prompt p1 + whole target file, Argus apply layer, at most 3 attempts per task and arm, stop at the first patch that passes all FAIL_TO_PASS tests, solved only if that patch resolves in the full Docker harness. Runner `scripts/run_loop2.py`, analysis `scripts/analyze_loop2.py` -> `results/analysis/loop2_summary.json`, raw trajectories `data/loop2/`. Free Groq keys, about $0.50 of list-price tokens for both arms (the shared first attempt counted once). Discovery run on the same tasks used for all design; none of it is a claim. File-given setting, not a leaderboard score.

Arm R: independent re-draws, no information from earlier attempts. Arm F: attempt 1 is R's draw 0 (shared); attempts 2 and 3 add the Revision 5 feedback block (first failing target test, name plus up to 2,000 characters of its failure text; or Argus's apply error). The previous patch is **not** shown to the model.

## Result
| Within | F (feedback) | R (re-draw) | F minus R (paired, task-clustered 95% CI) | Spend F / R |
|---|---|---|---|---|
| 1 attempt | 42 | 42 | 0 (shared draw) | $0.156 / $0.156 |
| 2 attempts | 52 | 56 | **-4 (-10 to +2)** | $0.253 / $0.251 |
| 3 attempts (primary) | 57 | 59 | **-2 (-8 to +3)** | $0.330 / $0.320 |

Feedback did not beat drawing again. The interval is wide: a benefit larger than about +3 tasks is unlikely, a harm of up to 8 tasks cannot be excluded, and (as pre-registered) effects under about 5 tasks cannot be told apart from zero. The cap problem of Revision 5 is gone: **0 of 188 attempts after attempt 1 were truncated** (95 in F, 93 in R); every attempt returned an answer.

Replication check: R's 59 solved at a $0.32 spend matches the Revision 4/6 replay of 120B x3 under the same stop rule (59.3 solved, $0.30) with draws taken in an earlier session, so the backend and the baseline are stable.

## Where the arms differ
54 tasks failed attempt 1, identical in both arms. After that:
- Attempt 2, among those 54: **F resolved 10 (18.5%), R resolved 14 (25.9%)**.
- Attempt 3, among 41 (F) and 39 (R) still open: F 5 (12.2%), R 3 (7.7%).
- Solved later: F 15 of 54, R 17 of 54.
- Only-F solves: django-14534, django-16877, scikit-learn-14983. Only-R solves: django-14434, django-14771, pytest-7521, sympy-15875, sympy-24443. These sets are the size expected from sampling noise at temperature 1.0.
- Accepted but regressed (target test passes, another test breaks): F 7, R 6. A loop that stops at the first passing test ships these in both arms.
- Cost per solve: F $0.0058, R $0.0054.

## What the feedback contained
Of 95 feedback-bearing attempts in F: 61 showed a failing target test with its traceback (12 then resolved, 19.7%), 26 showed Argus's apply-failure message (3 resolved), 5 asked for blocks after a formatting error (0), 3 other. A resolve rate of about 20% after a test traceback is within the range of a fresh draw at the same stage (R: 25.9% at attempt 2, 7.7% at attempt 3), so the traceback did not visibly raise the chance of a fix.

## Reading
1. In this setting test feedback adds no measurable value beyond resampling, and the earlier null (Revision 5, 53 vs 54.9) was not just the token cap: with the cap removed the result is the same sign.
2. This is a narrow test of what feedback does. The model sees the failing test and its traceback but **not its own previous patch**, so a retry cannot tell what it already tried; each retry is close to a fresh draw with an extra block of text. A loop that also shows the previous patch is a different design and has not been tested here. The real Argus controller's prompt for later turns was not replicated (it uses 25/45-line windows).
3. Combined with Report 6's replay (re-drawing 120B beats cross-model cascades per dollar) the working picture is: **in this file-given setting, the value of a test-gated loop comes from the verifier plus extra draws (pass@3 is 13 solves above pass@1 for the 120B), not from feedback content or from model escalation.**
4. The false-accept rate matters: 6 to 7 of 100 tasks end accepted-but-regressed in either arm.

## Caveats
Same tasks as all design; whole target file at every attempt; Groq list prices of undated docs; cosmetic quirk shared with Revision 5: the ANSI-stripping regex in `failure_excerpt` removes "[c" from pytest parameter ids, so the title line of a failure block can read `test_separableompound_model6-result6]` (traceback body intact); 100 tasks give low power, intervals above are task-clustered bootstrap with 5,000 resamples.
