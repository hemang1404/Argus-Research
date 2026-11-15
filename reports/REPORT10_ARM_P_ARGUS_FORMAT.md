# Report 10: arm P in the deployed Argus prompt format (Revision 19) and why feedback helps or not

Data: `data/loop4` (120B), `data/loop4_20b`, `data/loop4_gemma26`. Scripts: `scripts/analyze_rev19.py`, `scripts/analyze_why19.py`. Results: `results/analysis/rev19_results.json`.
Design set, 100 tasks, up to 3 attempts, attempt 1 shared across arms. Paired task bootstrap, 5,000 resamples, seed 20261113. Infrastructure losses count as unsolved.
Reference arms: R and F from Revision 7 (120B) and Revision 9 (20B); Gemma F from Revision 15/16. No matched Gemma R arm.

## Results (solved within 3 attempts)

| Model | n | P | F | R | P-F (95% CI) | P-R (95% CI) | Prediction check |
|---|---|---|---|---|---|---|---|
| gpt-oss-120b | 100 | 56 | 57 | 59 | -1.0 (-5, +3) | -3.0 (-9, +3) | P-F and P-R inside the pre-registered ranges |
| gpt-oss-20b | 100 | 53 | 55 | 47 | -2.0 (-10, +6) | +6.0 (-1, +13) | inside |
| Gemma 26B | 99 | 49 | 43 | none | +6.1 (0, +12) | n/a | MISS (predicted -5 to +5) |

- 20B F-R is +8.0 (CI +2, +14), consistent with the blind run (+6.6).
- Cost per solve: 20B F $0.0049, 20B P $0.0050, 120B R $0.0054, 120B F $0.0058, 120B P $0.0061 (Gemma has no list cost here).
- Losses: 20B had 1 P grade_error and 1 F api_error; Gemma had 4 P and 7 F api_error. Without them the differences change by less than 1 point (Gemma P-F +6.7, CI 0 to 13.5). The 120B pass logged one grade_error (`sympy__sympy-18698`) that is stored as stop "continue", so the sensitivity filter does not exclude it (one task).
- Gemma caveats: `django__django-13406` has no Gemma P record (99 of 100), so it is not in the comparison. The Gemma F arm is from an earlier run with its own draws; attempts 2 and 3 are not matched, so P-F mixes the prompt effect with draw noise. Treat +6.1 as a lead.

Reading: showing the previous patch does not beat feedback alone on either gpt-oss model. Only Gemma shows a hint of a P advantage, with the weakest comparison.

## Why: three offline checks on stored attempts (exploratory, nothing re-run)

1. Anchoring on the old patch. Share of attempt-2 patches identical to attempt 1: 120B P 2%, F 0%, R 0%; 20B P 0%, F 0%, R 3%. P does not repeat its earlier answer, so the anchoring explanation is not supported. Attempt 2 applies about equally often in P and F (120B 72% vs 72%; 20B 64% vs 58%).
2. Recovery by why attempt 1 failed (tasks eventually solved, P / F / R):

| Attempt-1 failure | 120B | 20B |
|---|---|---|
| Applied, F2P still failing | 11 / 12 / 13 of 37 | 12 / 15 / 8 of 37 |
| Not applied | 3 / 3 / 4 of 17 | 2 / 1 / 1 of 11 |
| Not applied, hit output limit | none | 1 / 1 / 0 of 11 |

   The recovery that exists is in tasks where the patch applied but tests still failed, and the 20B feedback gain is concentrated there. Edit-not-applied failures are rarely recovered under any arm, so apply-error feedback alone does little.
3. Loop/truncation. About 13% of 20B R attempts and 10% of F attempts hit the output limit (120B: 0%). Removing the 21 tasks with any truncated run leaves 20B F-R at +7.6 (CI +1.3, +15.2) and P-R at +5.1 (CI -2.5, +12.7), so the feedback gain is not a loop-breaking artifact. On the 21 truncated-run tasks alone F-R is +9.5 (CI 0, +23.8).

Interpretation (hypothesis, not tested): most remaining failures are semantic, with the patch applied and the model's theory of the bug wrong. Feedback helps the weaker 20B model there; 120B gets as much from a fresh draw. Whether the failing-test text is too uninformative to guide a fix was not tested.

## Limits
Single design set, one seed per arm, F and R reference arms come from earlier revisions with different draw histories than P's attempts 2 and 3. The three "why" checks were not pre-registered and are exploratory.
