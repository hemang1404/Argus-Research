# Report 4. Temperature-1.0, 3-draw re-baseline (Revision 4, pre-registered)

Date 2026-11-11. Same 99 valid tasks as Pilot-100 (psf__requests-1766 excluded: gold patch failed in the harness), same prompts (hash-identical), gpt-oss-20b and gpt-oss-120b on Groq, temperature 1.0, 3 draws per task and model, 8,000-token cap. All 447 distinct patches graded in the official Docker harness. Analysis: `scripts/analyze_t1.py` -> `results/analysis/t1_summary.json`. Everything here is exploratory. The verifier in the retry simulations is the Docker result, a perfect hidden-test verifier, so those numbers are upper bounds for any real failing-test verifier.

## 1. Resolve rate (99 tasks; task-clustered bootstrap CIs)

| Arm | Draw 1 | Draw 2 | Draw 3 | Mean | 95% CI | Pilot (T=0, 1 draw) |
|---|---|---|---|---|---|---|
| 20B plain | 29 | 33 | 28 | 30.3% | 22.9-38.0 | 31 |
| 20B Argus | 36 | 38 | 33 | 36.0% | 28.3-44.1 | 38 |
| 120B plain | 45 | 49 | 37 | 44.1% | 35.7-52.5 | 44 |
| 120B Argus | 48 | 52 | 41 | 47.5% | 39.1-55.9 | 46 |

- Temperature does not change the resolve rate: the pilot single-draw numbers fall inside the T=1 intervals.
- Argus minus plain, paired by task: **+5.7 pp (20B, CI 2.7 to 9.1)** and **+3.4 pp (120B, CI 0.7 to 6.7)**. Reproduces the pilot gain (+7, +2) with intervals that exclude zero.
- 120B minus 20B (Argus arm): +11.5 pp, CI 6.1 to 16.5.
- Draw-to-draw spread is large: the 120B resolves 41 to 52 tasks depending on the draw. A single draw can move a headline number by about 10 tasks.

## 2. Loops

| | T=0 (pilot) | T=1.0 |
|---|---|---|
| 20B length-capped runs | 22/99 (22.2%) | 22/297 (7.4%) |
| 120B | 0/99 | 1/297 (0.3%) |

- Temperature explains most of the looping, as predicted. 16 of 99 tasks loop on at least one draw; one task loops on all three. 10 of the 22 tasks that looped at T=0 loop again on some T=1 draw, so some tasks are loop-prone regardless of temperature.
- Loops are 18% of the 20B's spend at T=1 (46% at T=0).
- The "21" quoted elsewhere is the number with no output; 22 counts all runs that hit the cap (one had partial content).

## 3. Per-task success probability

| | never solved | 1 of 3 | 2 of 3 | 3 of 3 |
|---|---|---|---|---|
| 20B (Argus) | 50 | 13 | 14 | 22 |
| 120B (Argus) | 39 | 10 | 19 | 31 |

- 49 of 99 tasks were solved by neither model at T=0. **12 of those 49 are solved by some T=1 draw** (5 by the 20B, 12 by the 120B). Part of that is pass@k selection with the hidden test as the verifier.
- 60 tasks are solved by some model on some draw. **Every task the 20B ever solves, the 120B also solves on some draw** (20B-only: 0; 120B-only: 11). The cheaper model adds no coverage, only a lower price per attempt.
- Draw-pair agreement: 82% (20B), 81% (120B). Failure is mostly a property of the task, with real draw noise on about a fifth of pairs.

## 4. Oracle router in three parts (one draw each, mean over 3 draws; unsmoothed -> smoothed)

| Policy | Solves | Spend | $/solve |
|---|---|---|---|
| 20B alone | 35.7 | $0.114 | 0.00321 |
| 120B alone | 47.0 | $0.154 | 0.00328 |
| O1 model-choice only (perfect model per task, every task still attempted) | 51.0 -> 49.3 | $0.113 -> $0.124 | 0.0022 -> 0.0025 |
| O3 = O1 + skip tasks nobody solves | 51.0 -> 49.3 | $0.056 -> $0.076 | 0.0011 -> 0.0015 |
| 20B -> 120B cascade, test-gated | 51.0 | $0.222 | 0.00435 |
| 20B -> 120B cascade, observable-only (accept first applied patch) | 39.7 | $0.156 | 0.00394 |

- Smoothing (using per-task probabilities instead of picking the lucky draw) lowers oracle solves by about 1.7 (3%). The pilot's oracle ($0.115, 50 solves) is reproduced.
- Half of the oracle's spend is knowledge of hopelessness (O1 minus O3 = $0.057), not model choice. A real router has no access to that knowledge.
- The realizable cascades are far from the oracle: the test-gated cascade costs twice the O1 oracle. The observable-only cascade is **dominated by 120B alone** (39.7 solves for $0.156 vs 47.0 for $0.154), because accepting an unverified 20B patch loses solves.

## 5. Stop rules and retries (test-gated, up to 3 attempts, averaged over all 6 draw orders)

| 20B | Solves | Spend | Solves lost vs K=3 | Spend saved vs K=3 |
|---|---|---|---|---|
| K=1 | 35.7 | $0.114 | 13.3 | $0.150 |
| K=2 | 44.7 | $0.195 | 4.3 | $0.069 |
| K=3 (baseline) | 49.0 | $0.264 | 0 | 0 |
| stop after loop | 47.2 | $0.233 | 1.8 | $0.032 |
| stop after apply failure (not loop) | 45.3 | $0.218 | 3.7 | $0.047 |
| stop after patch applied but failed | 39.5 | $0.167 | 9.5 | $0.097 |

| 120B | Solves | Spend | Solves lost | Spend saved |
|---|---|---|---|---|
| K=1 | 47.0 | $0.154 | 13.0 | $0.159 |
| K=2 | 56.7 | $0.242 | 3.3 | $0.072 |
| K=3 | 60.0 | $0.313 | 0 | 0 |
| stop after loop | 60.0 | $0.311 | 0 | $0.002 |
| stop after apply failure | 56.3 | $0.264 | 3.7 | $0.050 |

- No rule saves money for free. Every rule that saves spend loses solves, at a marginal price of roughly $0.009 to $0.022 per solve lost, against an average of $0.003 to $0.005 per solve. Whether a rule is worth it depends on what a solve is worth, which is a business input, not a measurement.
- **The cascade lies below the 120B retry frontier.** 120B x2 gives 56.7 solves for $0.242. The 20B -> 120B cascade gives 51.0 for $0.222. Interpolating between 120B x1 and x2 at the cascade's spend gives about 54.5 solves. At this model pair and these prices, retrying the big model beats escalating from the small one.
- Stop-after-loop is the closest to free: 0 solves lost for the 120B (but only because it loops once) and 1.8 solves for $0.032 on the 20B.
- **Early-abort token cap (tuned on draws 1-2, scored on draw 3): null result.** The largest resolved 20B run used 7,780 of 8,000 tokens, so any cap that loses no solves on the tuning data is 8,000 and saves nothing. For the 120B the cap is 4,000 and saves 0.5%. Token count alone does not separate a long reasoning run from a loop for the 20B.

## 6. The apply layer at T=1

- Argus applied 52 draws that plain could not (34 from the 20B, 18 from the 120B). **29 of those 52 recovered patches resolve (56%)**, above the 47% to 55% conditional pass rate of all applied patches. Argus lost 1 resolve per model through its own refusals.
- Apply rate (Argus arm): 20B 76.8%, 120B 86.2%. Conditional pass rate given a patch applied: 20B 46.9%, 120B 55.1%.

## 7. Reading

1. The Argus apply-layer gain is real and reproduces at a second temperature with CIs that exclude zero, but it is a few percentage points, not a headline result.
2. With this pair at these prices the cheap model adds cost parity and no coverage, so the allocation problem collapses toward how many times to retry the big model. A cascade does not beat it.
3. Perfect knowledge would roughly halve spend, but half of that is knowing which tasks are hopeless. No observable signal tested here recovers it.
4. A wider price gap or a stronger reference model is needed before a routing claim is testable. These are still discovery numbers on the same 99 tasks used to design everything; a confirmatory set is not chosen yet.

## Caveats

- Same 99 tasks as all earlier analysis. No sealed set.
- Cost counts only the successful call of each draw (a few failed calls were retried and are not priced). Prices are Groq list prices from undated docs.
- Docker result used as the verifier in retry simulations.
- One patch (sympy-19346, 20B plain) had no harness report because the harness rejected the diff; it is recorded as an unresolved candidate with a note in the state file.
