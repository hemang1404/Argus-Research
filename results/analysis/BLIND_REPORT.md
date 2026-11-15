# Blind test report (200 sealed SWE-bench Verified tasks, 198 analysed)

Source: `python -X utf8 scripts/analyze_blind.py` on the full set; data in `results/analysis/blind_report_data.json`.
Task-clustered bootstrap, 5,000 resamples, seed 20261113. Two tasks excluded because the gold-patch control failed (psf__requests-1724, psf__requests-1921).
Disclosure: the script was debugged on a partial snapshot (about 119 tasks) of this data before the run finished. No setting of the run was changed because of it.

## Results (solved within 3 attempts, percent of tasks)

| Model | R (re-draw) | F (test feedback) | F-R | 95% CI | F-only / R-only |
|---|---|---|---|---|---|
| gpt-oss-20b | 49.0 | 55.6 | +6.6 | (1.5, 11.6) | 20 / 7 |
| gpt-oss-120b | 54.5 | 59.1 | +4.5 | (0.0, 9.1) | 15 / 6 |
| gemma-4-26b (exploratory) | 40.4 | 41.4 | +1.0 | (-3.5, 5.6) | 11 / 9 |

Gemma had 19 F-arm and 8 R-arm api_error tasks (counted unsolved). Excluding tasks with infrastructure failures: F-R +1.1, CI (-3.4, 6.2), so the conclusion does not change.

## Pre-registered hypotheses

- H1 (confirmatory, 20B F > R): CONFIRMED. +6.6, CI (1.5, 11.6). The design estimate was +8, so the effect is slightly smaller than expected but clearly above 0.
- H2 (120B F-R upper bound <= 5): DOES NOT HOLD. +4.5, CI (0.0, 9.1). The point estimate is under 5, but the upper bound is 9.1. The design set suggested about 0. The honest reading is that feedback helps 120B a little, possibly as much as it helps 20B.
- H3 (cascade of 20B F then 120B R vs 120B R alone, spend ratio <= 1.2): SUPPORTED. 59.6 vs 54.5 (+5.1, CI 1.0 to 9.1) at 1.10 times the spend.
  Caveat: this is an offline replay using stored attempts, not a live cascade. The cascade's gain is mostly the 20B feedback loop's gain over 120B re-draws.
- H4 (apply-layer gain larger for 20B than 120B): HOLDS. +13.1 pp for 20B vs +5.6 pp for 120B (Gemma +17.6 pp).

## What it changes

1. The main finding stands: test-failure feedback beats blind re-draws for the weakest gpt-oss model, on tasks nobody tuned on.
2. The belief "feedback does not help the strong model" is not supported. The effect on 120B is smaller but plausibly positive. We should stop saying it does nothing.
3. Gemma gets almost nothing from feedback. The apply layer helps it most (+17.6 pp), so for Gemma the gain is in applying edits, not in feedback.
4. Cost per solve is lowest for 20B with F ($0.0045), below 120B ($0.0056 to $0.0058). Feedback loops with the small model are the cheapest route.
5. The cascade result supports the allocation framing: a cheap model with feedback first, and a larger model only for what is left.

## Limits

- Single sealed set, one seed per arm. Per-repo splits are underpowered, and repo-clustered intervals are degenerate for single-repo subsets.
- Order of tasks was not randomised during the run, which does not bias the paired comparison.
- Revision 18 (Gemini, arm P, replicates, greedy) is running separately and is not part of this report.
