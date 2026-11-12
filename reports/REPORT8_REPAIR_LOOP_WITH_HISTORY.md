# Report 8. Repair loop that shows the model its own previous answer (Revision 8, tag `pilot100-loop3-prereg`)

Date 2026-11-12. Same setup as Report 7 (100 tasks, gpt-oss-120b, medium effort, T=1.0, cap 8000, whole file, Argus apply layer, at most 3 attempts, stop at the first patch passing all FAIL_TO_PASS tests, solved iff resolved in the full Docker harness). Arm P: attempts 2 and 3 are a multi-turn chat (the model's earlier answer, then the failing test and traceback or Argus's apply error). Comparators are Report 7's arms R (independent re-draws) and F (test feedback without the previous answer). Runner `scripts/run_loop3.py`, analysis `scripts/analyze_loop3.py` -> `results/analysis/loop3_summary.json`, data `data/loop3/`. Discovery run on the design tasks, file-given, Groq list prices.

## Result: tasks solved of 100
| Within | P (history + result) | F (result only) | R (re-draw) | P minus R (95% CI) | P minus F (95% CI) |
|---|---|---|---|---|---|
| 2 attempts | 53 | 52 | 56 | -3 (-10 to +4) | +1 (-5 to +7) |
| 3 attempts | 57 | 57 | 59 | -2 (-10 to +6) | 0 (-6 to +6) |

Seeing its own previous answer did not help: P equals F and sits 2 below R, with intervals far wider than the differences. Resolve rate among tasks reaching attempt 2 (54 tasks): P 20.4%, F 18.5%, R 25.9%. P repeated an identical patch only 3 times in 133 patches, so it does try something new.

## Infrastructure losses (disclosed)
6 tasks could not complete all attempts in P: 5 hit Groq's free-tier limit (a request of about 8,100 tokens against an 8,000 tokens-per-minute cap, because earlier answers lengthen the chat) and 1 more (matplotlib-24570) the same limit after a rerun; 3 image-pull failures were rerun and 2 then completed. These tasks are counted as unsolved in the pre-registered numbers above. Leaving the 6 out of every arm: P 57, F 55, R 56 within 3 attempts (P minus R +1, CI -6 to +8; P minus F +2, CI -3 to +8). The conclusion does not depend on them, but the multi-turn design is partly constrained by the free tier.

## Reading
Across Reports 7 and 8, no form of test feedback tried (traceback only, or traceback plus the model's previous answer) beat independent re-draws, and none was measurably worse; all three arms solve 57 to 59 within 3 attempts at about $0.32. With 100 tasks, differences under about 5 tasks cannot be detected. The gain in every arm comes from the verifier plus extra draws (pass@3 above pass@1), not from feedback content. Not tested: other feedback (e.g. stack-frame or diff-of-expected output beyond 2,000 characters), reasoning shown from earlier attempts, a stronger model for repair, and tasks outside the file-given setting.
