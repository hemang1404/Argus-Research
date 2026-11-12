# Report 10. Qwen3.5 size ladder: how edits fail and which Argus tier rescues them (Revision 10, tag `pilot100-qwen-prereg`)

Date 2026-11-13. Exploratory probe: 30 tasks (the Gemini probe sample), one draw per model, prompt p1 (hash 56e5b02fa8ed), 6,000-token context, target file GIVEN. Models Qwen3.5-2B, -4B, -9B (instruct checkpoints, fp16 on Kaggle 2 x T4), temperature 1.0, top_p 1.0, top_k 0, **thinking off**, max_new_tokens 4000, no seed. Generation `scripts/kaggle_generate.py`, analysis `scripts/analyze_qwen_probe.py` -> `results/analysis/qwen_probe_summary.json`, outputs `data/qwen_probe/kaggle_run1/`. Plain and stock Argus (commit 467b720) apply; **no Docker grading, no solve rates**. The predictions were written and committed before any output.

## Results (30 tasks, one draw)
| | Qwen3.5-2B | Qwen3.5-4B | Qwen3.5-9B |
|---|---|---|---|
| Plain apply succeeded | 12 (40%) | 20 (67%) | 24 (80%) |
| Argus apply succeeded | 16 (53%) | 24 (80%) | 26 (87%) |
| Plain edit failed to match | 13 (43%) | 7 (23%) | 4 (13%) |
| Draws Argus rescued | 4 | 4 | 2 |
| Failures that were indentation only | 2 | 1 | 0 |
| No SEARCH/REPLACE blocks | 2 | 2 | 2 |
| Wrong file path written | 3 | 1 | 0 |
| Hit the 4,000-token cap | 3 | 1 | 1 |

Why plain edits failed to match: changed or paraphrased lines (5 / 2 / 0 plus missing or extra lines 1 / 0 / 1), half-matching text (3 / 0 / 2), a copied `# ... (lines omitted) ...` marker from the prompt's trimmed context (2 / 3 / 1), indentation only (2 / 1 / 0), same text in several places (0 / 1 / 0). Argus also refused 5 of the 2B's 9 refusals as syntax errors.

## Predictions checked
- **P1 (capability: indentation-only failures fall with size, 2B most): not supported.** They were rare at every size (2, 1, 0 cases). For gpt-oss-20b they were 36 of 37 whitespace-type failures and 55% of all failures.
- **P2 (indentation is a gpt-oss habit): supported on this sample.** Qwen fails by changing or paraphrasing lines, as Gemini does.
- **P3 (format failures dominate the 2B): not supported.** No-blocks, wrong-file and cap hits are 8 of 30 draws for the 2B, 4 for the 4B, 3 for the 9B; edits that do not match are the main failure.
- **P4 (4-bit vs fp16 on the 4B): not run.**

## Reading
1. The **rate** of plain edit failure falls steadily with size inside Qwen (43%, 23%, 13%) and matches the other families: gpt-oss-20b 23%, gpt-oss-120b 17%, Gemini Flash-Lite about 11%. The **kind** of failure is model-family specific.
2. Argus's gain in applied edits is +13 points at 2B and 4B and +7 at 9B (4, 4, 2 rescues); it shrinks with capability, consistent with the gpt-oss and Gemini results. Counts are small.
3. Which Argus tier does the rescuing differs by family (draws plain failed, Argus applied; 300 draws per gpt-oss/Gemini model, 30 per Qwen model):

| Model | Rescued | Tier 2 (ignores indentation) | Tier 3 (fuzzy match) |
|---|---|---|---|
| gpt-oss-20b | 34 | 29 | 2 (and 3 at tier 1) |
| gpt-oss-120b | 18 | 15 | 3 |
| Gemini 3.1 Flash-Lite | 9 | 3 | 6 |
| Gemini 3.5 Flash-Lite | 8 | 0 | 8 |
| Qwen3.5-2B / 4B / 9B | 4 / 4 / 2 | 1 / 1 / 0 | 3 / 3 / 2 |

The 5-tier apply layer is therefore a robustness layer whose useful tier depends on the model's copy habits (tier 2 for gpt-oss, tier 3 for Gemini and Qwen), and its value falls as models get stronger. What it does not fix: half-matching text, copied elision markers, wrong-file headers, and edits that are valid but wrong (the largest loss in every earlier funnel).

## Caveats
- One draw on 30 tasks, so only large differences mean anything; no confidence intervals.
- Thinking is off for Qwen (gpt-oss ran at medium reasoning), so these are edit-failure signatures, not solve-rate comparisons.
- 19 of the 9B's 30 answers needed the chunked-prefill fallback (1,024-token chunks) after a full-prompt pass ran out of memory on a T4; the 2B and 4B did not. This is a small numerical difference, recorded per record as `prefill_chunk`. The first 9B attempt (`data/qwen_probe/kaggle_run_v3_oom/`) ran out of memory on 19 of 30 prompts and is excluded.
- A first interactive 2B run (lost when the session stopped) had 10 of 30 draws hit the cap, against 3 of 30 in the committed run; the committed run had the fast attention kernel installed and the first did not. The cause is unconfirmed.
- The failure classifier is rule-based; only the indentation bucket was hand-checked.
- Not done: the 4B at 4-bit, the Groq 27B, 100 tasks, Docker grading.
