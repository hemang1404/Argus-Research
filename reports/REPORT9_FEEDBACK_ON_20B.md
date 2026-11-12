# Report 9. Feedback vs independent re-draws on gpt-oss-20b (Revision 9, tag `pilot100-20b-loop-prereg`)

Date 2026-11-12. Same design as Reports 7 and 8 (100 tasks, medium effort, T=1.0, cap 8000, whole file, Argus apply layer, at most 3 attempts, stop at the first patch passing all FAIL_TO_PASS tests, solved iff resolved in the full Docker harness) with gpt-oss-20b ($0.075 / $0.30 per 1M). Arms: R independent re-draws, F test/apply feedback without the previous answer, P multi-turn with the model's previous answer. All arms were run fresh. Runners `scripts/run_loop2.py` and `run_loop3.py` with `--model`, analysis `scripts/analyze_loop2.py _20b` and `analyze_loop3.py _20b`, data `data/loop2_20b/`, `data/loop3_20b/`. Discovery run on the design tasks, file-given, Groq list prices.

## Result: tasks solved of 100
| Within | F (feedback) | R (re-draw) | P (history + feedback) | F minus R (95% CI) | P minus R (95% CI) | P minus F (95% CI) |
|---|---|---|---|---|---|---|
| 2 attempts | 49 | 43 | 46 | **+6 (+1 to +12)** | +3 (-2 to +8) | -3 (-9 to +3) |
| 3 attempts (primary) | 55 | 47 | 52 | **+8 (+2 to +14)** | +5 (-2 to +12) | -3 (-11 to +5) |

For the 20B, feedback beat independent re-draws: the pre-registered primary comparison excludes zero (+8, CI +2 to +14) at about the same spend ($0.269 vs $0.279; $0.0049 vs $0.0059 per solve). For the 120B the same comparison was -2 (CI -8 to +3, Report 7). Showing the previous answer (P) did not add to feedback alone (-3 vs F). P lost 6 tasks to the free-tier 8,000 tokens-per-minute limit (counted unsolved; leaving them out: P minus R +6, CI 0 to +13).

## Where the 20B's gain comes from
- Resolve rate among the 59 tasks that failed attempt 1: attempt 2, F 18.6% vs R 8.5%; attempt 3, F 13.0% vs R 7.7%.
- Truncation: at attempt 2, R's identical re-draw ran out of tokens without an answer on 9 of 59 tasks, F's on 3 of 59. F's prompt includes (from Revision 5) one sentence telling the model that its previous answer was cut off and to keep reasoning short. So part of F's gain may be that instruction, not information from the tests. 14 F attempts received that sentence (1 then resolved).
- Feedback type and next outcome in F (attempts 2 and 3): after a failing test with its traceback, 13 of 59 next attempts resolved (22%); after Argus's apply-failure message 3 of 27 (11%); after the cut-off sentence 1 of 14; after a formatting error 0 of 4. A fresh re-draw resolves about 8% per attempt in this arm, so the traceback case is the clearest sign that information helped the 20B.
- Accepted-but-regressed patches: F 4, R 8.

## Reading
1. Feedback helps the 20B and did not help the 120B. This fits the idea that a weaker model has more recoverable errors (apply failures, cut-off outputs, wrong first fixes) and a stronger one has fewer. It is one task set and one pre-registered comparison: treat it as a hypothesis worth a fresh-task confirmation.
2. Not isolated: how much of the gain is the truncation instruction and how much is test information. A re-draw arm that also receives the short-reasoning sentence after a cut-off would separate them.
3. In dollars the feedback loop with the 20B (55 solved, $0.27) is cheaper than 120B re-drawn up to three times (59 solved, $0.32) only by cost per solve ($0.0049 vs $0.0054), not by total solves; the 120B still solves more.

## Caveats
Same tasks as all design; whole file at every attempt; file-given; Groq list prices (undated docs); 20B truncates more often at medium effort (15 of 100 first attempts hit the cap in R); P shows the same free-tier request-size limit as in Report 8; the bootstrap interval is task-clustered (5,000 resamples); several comparisons were made across Reports 7 to 9, each pre-registered separately.
