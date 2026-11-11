# Report 6. Gemini Flash-Lite sweep and the Argus apply layer (Revision 6, pre-registered tag `pilot100-gemini-prereg`)

Date 2026-11-12. 100 tasks (the 99 valid tasks plus `astropy__astropy-13579`, which replaced `psf__requests-1766`), 4 models, 3 draws each, plain apply vs stock Argus apply (v0.2.0b1, commit 467b720), all 2,400 patch outcomes graded in the official Docker harness (313 new distinct patches graded in this run, the rest reused by task and patch hash; 0 ungraded, 0 harness errors). Analysis `scripts/analyze_sweep.py` -> `results/analysis/sweep_summary.json`. Everything is a **discovery number on the task set used for all design so far**; none of it is a claim. Setting is **file-given** (every model receives the gold file as its target), so these are not SWE-bench leaderboard scores. Only the apply layer is used: one call per draw, no loop, no feedback.

## Headline: resolved tasks out of 100 (mean over 3 draws, task-clustered bootstrap 95% CI)
| Model | Plain apply | Argus apply | Argus minus plain | $ per 100-task pass | $ per solve (Argus) |
|---|---|---|---|---|---|
| gpt-oss-20b | 31.0 (23.7-38.7) | 36.7 (28.7-45.0) | **+5.7 (2.7 to 9.0)** | 0.116 | 0.0032 |
| gpt-oss-120b | 44.3 (36.0-53.0) | 47.7 (39.3-56.3) | **+3.3 (0.7 to 6.7)** | 0.157 | 0.0033 |
| gemini-3.1-flash-lite | 46.7 (37.7-55.7) | 47.0 (38.0-56.0) | +0.3 (0.0 to 1.0) | 0.291 | 0.0062 |
| gemini-3.5-flash-lite | 50.0 (40.7-59.0) | 51.7 (42.3-60.7) | +1.7 (0.0 to 4.0) | 1.325 | 0.0257 |

Per-draw counts (Argus arm): 20B 37/39/34, 120B 49/53/41, 3.1 FL 50/46/45, 3.5 FL 53/49/53. Draw-to-draw spread is several tasks (120B plain: 46, 50, 37; no seed is available, so this is sampling noise plus whatever else varies on the provider side).

## What the numbers say
1. **The Argus apply layer helps in proportion to how often the model's edit fails to match.** Plain "edit not applied" rates over 300 draws: 20B 68 (23%), 120B 52 (17%), 3.1 FL 36 (12%), 3.5 FL 34 (11%). The Argus gain follows the same order. The Gemini gain is near zero for 3.1 and small for 3.5.
2. **Rescue quality differs.** Draws rescued (plain does not apply, Argus does) and how many then resolve: 20B 34 rescued, 18 resolved (53%); 120B 18, 11 (61%); 3.5 FL 8, 5 (63%); 3.1 FL 9, **1 (11%)**. Gemini's other failures are mostly refused by Argus (26 draws each), not rescued. Argus lost 2 draws plain had applied for each gpt-oss model (1 resolved each time) and none for Gemini.
3. **Gemini 3.5 Flash-Lite is not clearly better than gpt-oss-120b here.** 51.7 (42.3-60.7) vs 47.7 (39.3-56.3), intervals overlap almost completely; any-of-3 solves are 59 vs 61 tasks. Gemini 3.1 Flash-Lite is level with 120B (47.0 vs 47.7). Neither beats the 120B on cost: **gpt-oss-120b costs $0.0033 per solve against $0.0062 (3.1) and $0.0257 (3.5)** at the price book below. The reason 3.5 is expensive is hidden thinking tokens (billed as output, absent from the reported completion count).
4. **Conditional on a patch applying, Gemini 3.5 passes more often** (60.8% vs 55.2% for 120B and 47.6% for 20B; 3.1 FL 51.6%). So part of Gemini's lead is fewer wrong edits, but the 120B closes most of it once the apply layer is on.
5. **The 4-model union is much bigger than any single model.** Tasks solved by at least one draw (Argus arm): 20B 50, 3.1 FL 55, 3.5 FL 59, 120B 61, any model 69; 31 tasks never. 8 tasks are solved only by a Gemini model (django-12774, django-15128, django-15315, pytest-10051, sklearn-14983, sympy-13551, sympy-13798, sympy-17139), 5 only by gpt-oss (django-15930, django-16877, matplotlib-23412, xarray-4094, sympy-19346). 56 tasks are solved by both families. Gemini-only tasks are a small, task-specific set; with the contamination caveat below I would not read them as capability.
6. **Argus's effect on larger models stays small.** This is consistent with the earlier finding (earlier reports): apply-layer gains come from models that write many non-matching edits. It does not show that Argus is irrelevant for strong models, only that the apply layer is.

## Failure funnel (all 300 draws per model, Argus arm)
| Model | resolved | applied but wrong | edit refused | no blocks | empty or truncated |
|---|---|---|---|---|---|
| gpt-oss-20b | 110 | 121 | 36 | 14 | 19 |
| gpt-oss-120b | 143 | 116 | 36 | 4 | 0 |
| gemini-3.1-flash-lite | 141 | 132 | 26 | 0 | 0 (1 no change) |
| gemini-3.5-flash-lite | 155 | 100 | 26 | 5 | 14 |

For every model the largest loss is "applied but wrong" (33-44% of draws), not apply failure. The 20B also loses 6% of draws to empty or truncated output (degenerate loops); Gemini 3.5 loses 5% to empty or truncated output.

## Routing replay (Argus arm, Docker result as a perfect verifier, upper bounds)
Pre-registered: oracle router (cheapest model that solved the task on that draw index) and cheapest-first verifier cascade over all four models, mean over the 3 draw indices.

| Policy | solved | spend per 100-task pass |
|---|---|---|
| Oracle router, 4 models | 63.3 | $0.158 |
| Cascade 20B -> 120B -> 3.1 FL -> 3.5 FL | 63.3 | $1.028 |
| 120B alone | 47.7 | $0.157 |
| 120B best of 3 draws (any-of-3, pays for 3) | 61 | $0.470 |

Post hoc (not pre-registered) cascades over subsets, same replay:
| Cascade | solved | spend |
|---|---|---|
| 20B -> 120B | 52.0 | $0.224 |
| 20B -> 120B -> 3.1 FL | 58.7 | $0.361 |
| 120B -> 3.1 FL | 56.7 | $0.307 |
| 120B -> 3.5 FL | 61.0 | $0.968 |
| 20B -> 120B -> 3.5 FL | 61.7 | $0.976 |

Reading: 3.1 Flash-Lite is a cheap, useful third rung (+6.7 solves for +$0.14 on top of 20B -> 120B); the 3.5 rung adds 3 to 6 solves for roughly +$0.6-0.7, which is poor value. The oracle needs only $0.158 for 63.3 solves because it never pays for a miss; the four-rung cascade reaches the same 63.3 solves for $1.03, and that gap is the price of not knowing which model will pass. These are replays with a perfect verifier. A real run needs a test-based verifier (which has its own false-accept rate: in an earlier analysis 11.7% of patches that passed the target test broke another test) and sequential calls whose draw index is not paired across models. 120B best-of-3 reaches 61 for $0.47 (with early stopping it is cheaper), so cross-family escalation beats repeated sampling of one cheap model only if the extra rung is priced like 3.1 FL, not 3.5 FL. The four-model cascade uses up to 4 attempts against 3 for the best-of-3, so the comparison is not budget-matched.

## Cost method and caveats
- Price book (paid tier, 2026-11-11, per 1M input / output): 3.1 FL $0.25 / $1.50 (read from a page summary, not the pricing page itself), 3.5 FL $0.30 / $2.50, gpt-oss-20b $0.075 / $0.30 and gpt-oss-120b $0.15 / $0.60 (Groq, undated). Gemini output = total minus prompt tokens, because thinking is billed but not reported as completion tokens. Prices change (3.8 Flash rises Jan 1); re-pricing is trivial because raw usage is stored. New Gemini spend for the sweep about $4.4, total Gemini spend about $6.2 including the probe.
- **Contamination is not ruled out.** The issue-only screen (30 tasks) found no patch recall, but Gemini named the right file more often than gpt-oss-120b. Absolute Gemini pass rates may be inflated.
- **File-given setting.** Localization is removed (issue-only localization recall@1 is about 21-27% in earlier work), so none of this predicts real use.
- **Same tasks as design.** All 100 tasks were used for earlier design decisions. A sealed confirmatory set has not been chosen.
- **Draw 0 of both Gemini models on 30 tasks** is the probe draw (identical settings, disclosed in Revision 6). No seed is available on this endpoint, so exact reproduction is impossible; stored outputs are the ground truth.
- **Replacement task** `astropy__astropy-13579` passed the gold control (F2P 1/1, P2P 40/40); the earlier candidate `psf__requests-2317` failed it (HTTPS test calls fail with a certificate error in the old pinned environment; my reading, not confirmed).
- Intervals are task-clustered bootstrap (5,000 resamples, seed 20261112) over 100 tasks; with CIs of about +/-9 tasks, differences between models of 3-5 tasks are not resolved. Paired Argus effects are tighter.

## Not done
No loop on Gemini; no 3.8 Flash, Carbon, Argon or Pro sweep (cost; 3.8 Flash at medium effort exhausted its 16,000-token output budget on thinking in 8 of 11 calls); no sealed confirmatory set; no bootstrap on the routing replay.
