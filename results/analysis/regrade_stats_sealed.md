# Sealed set: experimental engine against released engine (lower bound)

Task-level bootstrap, 5000 resamples, seed 20261113; exact two-sided McNemar. Released-engine columns are lower bounds from stored attempts.

## Cost code check against the paper's sealed cost table (experimental engine)

| arm | paper total | computed | paper per solve | computed | match |
|:--|--:|--:|--:|--:|:--:|
| gpt-oss-20b R | 0.5265 | 0.5265 | 0.00543 | 0.00543 | yes |
| gpt-oss-20b F | 0.4975 | 0.4975 | 0.00452 | 0.00452 | yes |
| gpt-oss-120b R | 0.6304 | 0.6304 | 0.00584 | 0.00584 | yes |
| gpt-oss-120b F | 0.6574 | 0.6574 | 0.00562 | 0.00562 | yes |
| gpt-oss-20b F corrected | 0.4972 | 0.4972 | 0.0046 | 0.0046 | yes |
| gpt-oss-120b F corrected | 0.663 | 0.663 | 0.00582 | 0.00582 | yes |
| gemma-4-26b-a4b-it R | 0.6889 | 0.6889 | 0.00861 | 0.00861 | yes |
| gemma-4-26b-a4b-it F | 0.6057 | 0.6057 | 0.00739 | 0.00739 | yes |

## Paired differences, Feedback minus Redraw (points, 95% interval, exact McNemar)

| comparison | engine | solved (F / R) | difference | 95% interval | only-F / only-R | p |
|:--|:--|:--:|:--:|:--:|:--:|:--:|
| gpt-oss-20b F-R | experimental | 110 / 97 | +6.6 | +1.5 to +11.6 | 20 / 7 | 0.0192 |
| gpt-oss-20b F-R | released | 110 / 100 | +5.1 | +0.5 to +10.1 | 17 / 7 | 0.0639 |
| gpt-oss-20b corrected F - R | experimental | 108 / 97 | +5.6 | +0.5 to +10.6 | 19 / 8 | 0.0522 |
| gpt-oss-20b corrected F - R | released | 110 / 100 | +5.1 | +0.5 to +10.1 | 17 / 7 | 0.0639 |
| gpt-oss-120b F-R | experimental | 117 / 108 | +4.5 | +0.0 to +9.1 | 15 / 6 | 0.0784 |
| gpt-oss-120b F-R | released | 116 / 107 | +4.5 | +0.0 to +9.1 | 15 / 6 | 0.0784 |
| gpt-oss-120b corrected F - R | experimental | 114 / 108 | +3.0 | -1.5 to +7.6 | 13 / 7 | 0.2632 |
| gpt-oss-120b corrected F - R | released | 114 / 107 | +3.5 | -1.0 to +8.1 | 14 / 7 | 0.1892 |
| gemma-4-26b-a4b-it F-R | experimental | 82 / 80 | +1.0 | -3.5 to +5.6 | 11 / 9 | 0.8238 |
| gemma-4-26b-a4b-it F-R | released | 70 / 71 | -0.5 | -4.5 to +3.5 | 8 / 9 | 1.0 |
| 20B F loop - 120B F loop (original) | experimental | 110 / 117 | -3.5 | -8.6 to +2.0 | 11 / 18 | 0.2649 |
| 20B F loop - 120B F loop (original) | released | 110 / 116 | -3.0 | -8.1 to +2.0 | 10 / 16 | 0.3269 |
| 20B F loop - 120B F loop (corrected) | experimental | 108 / 114 | -3.0 | -8.6 to +2.5 | 12 / 18 | 0.3616 |
| 20B F loop - 120B F loop (corrected) | released | 110 / 114 | -2.0 | -7.1 to +3.0 | 12 / 16 | 0.5716 |
| 20B F loop - 120B one attempt (original) | experimental | 110 / 92 | +9.1 | +3.0 to +15.7 | 29 / 11 | 0.0064 |
| 20B F loop - 120B one attempt (original) | released | 110 / 90 | +10.1 | +4.5 to +16.2 | 29 / 9 | 0.0017 |

## Cost at list prices (USD)

| arm | engine | solved | total | per task | per solved | tasks needing a new draw | attempts missing tokens |
|:--|:--|--:|--:|--:|--:|--:|--:|
| gpt-oss-20b R | experimental | 97 | 0.5265 | 0.00266 | 0.00543 | 0 | 0 |
| gpt-oss-20b F | experimental | 110 | 0.4975 | 0.00251 | 0.00452 | 0 | 4 |
| gpt-oss-20b F corrected | experimental | 108 | 0.4972 | 0.00251 | 0.0046 | 0 | 3 |
| gpt-oss-120b R | experimental | 108 | 0.6304 | 0.00318 | 0.00584 | 0 | 0 |
| gpt-oss-120b F | experimental | 117 | 0.6574 | 0.00332 | 0.00562 | 0 | 0 |
| gpt-oss-120b F corrected | experimental | 114 | 0.663 | 0.00335 | 0.00582 | 0 | 0 |
| gemma-4-26b-a4b-it R | experimental | 80 | 0.6889 | 0.00348 | 0.00861 | 0 | 8 |
| gemma-4-26b-a4b-it F | experimental | 82 | 0.6057 | 0.00306 | 0.00739 | 0 | 19 |
| gpt-oss-20b R | released | 100 | 0.5262 | 0.00266 | 0.00526 | 1 | 0 |
| gpt-oss-20b F | released | 110 | 0.4953 | 0.0025 | 0.0045 | 7 | 4 |
| gpt-oss-20b F corrected | released | 110 | 0.495 | 0.0025 | 0.0045 | 5 | 3 |
| gpt-oss-120b R | released | 107 | 0.6292 | 0.00318 | 0.00588 | 2 | 0 |
| gpt-oss-120b F | released | 116 | 0.6574 | 0.00332 | 0.00567 | 2 | 0 |
| gpt-oss-120b F corrected | released | 114 | 0.663 | 0.00335 | 0.00582 | 1 | 0 |
| gemma-4-26b-a4b-it R | released | 71 | 0.6889 | 0.00348 | 0.0097 | 15 | 8 |
| gemma-4-26b-a4b-it F | released | 70 | 0.6057 | 0.00306 | 0.00865 | 31 | 19 |

Notes: Intervals: task-level bootstrap, 5,000 resamples, seed 20261113 (the seed convention of scripts/analyze_blind.py). Released-engine counts are lower bounds (stored attempts only). Intervals on released counts treat the lower-bound outcomes as fixed. Feedback attempts 2 and 3 were written from feedback produced under the experimental engine; where an earlier outcome changed, the replay is approximate. Gemma list price $0.09/$0.30 per million tokens (the run itself cost $0 on a free tier).
