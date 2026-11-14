# Argus claim-status table (draft, 2026-11-14)

Evidence: official swebench Docker harness, file-given setting, prompt p1, Argus v0.2.0b1 (467b720). Numbers are tasks solved per 100; CIs are 95% task-bootstrap.
Status key: SUPPORTED / WEAKENED / NOT SUPPORTED / UNTESTED / TO RE-CHECK (carried from earlier reports, not re-verified in this round).

| # | Claim | Status | Evidence | Limits |
|---|-------|--------|----------|--------|
| 1 | Apply-layer gain depends on how often the model's plain edits fail to apply | SUPPORTED | Gain: gpt-oss-20b +5.7, Gemma 26B +6.0 (25.6 to 31.6), gpt-oss-120b ~+2, Gemini ~+1, Qwen3.8-27B +0.3 (18% not applied). Cross-family Spearman 0.71 | n=8 models; families and sizes confounded |
| 2 | The apply layer is a general improvement | NOT SUPPORTED | Near-zero gain where edits already apply | Reframe as conditional recovery |
| 3 | gpt-oss failures are mostly indentation / edit-format | SUPPORTED | Earlier failure taxonomy | gpt-oss only |
| 4 | Extra attempts give most of the recovery lift | SUPPORTED | 3 attempts, re-draw: Qwen3.8 26.3 to 41.0, Gemma 31.6 to 44.4 | Test-gated stop uses the verifier; not a no-oracle number |
| 5 | Showing the failing test beats plain re-draw | NOT SUPPORTED | F-R: Qwen3.8 +0.0 (-7 to +7), Gemma -1.0 (-6 to +4); earlier 20B +8, 120B -2 | CIs span zero; n=100; API errors hit F harder (15 / 7 tasks) |
| 6 | The first-F2P-pass stop rule gives correct patches | WEAKENED | Accepted-but-regressed: 6 Qwen3.8, 9 Gemma tasks. E3 review of 265 unique resolved patches: about 18% wrong or fragile, 8% partial (reviewer-judged, unexecuted) | Verifier false-accept is a result in itself |
| 6b | Apply layer rescues real fixes, not wrong patches that happen to pass | SUPPORTED | Rescued patches non-clean 8/38 (21%) vs 61/227 (27%) for non-rescued (reports/E3_RESCUED_PATCH_REVIEW.md) | One non-blind reviewer; rescued subset only; 'fragile' not executed |
| 7 | Qwen3.5 -> Qwen3.8 shows a size ladder | NOT SUPPORTED | Series and size confounded | Report 3.8 as a separate data point |
| 8 | A router/cascade beats the best single model | WEAKENED | Re-baseline (Report 4, T=1, 3 draws, 99 tasks): perfect-knowledge oracle 51.0 (49.3 smoothed) at $0.113-0.124; test-gated 20B->120B cascade 51.0 at $0.222; 120B alone 47.0 at $0.154; observable-only cascade 39.7 at $0.156, dominated by 120B alone. Every task 20B ever solves, 120B also solves on some draw | gpt-oss pair only; oracle needs knowledge a real router lacks (half its spend is skipping hopeless tasks) |
| 9 | 20B vs 120B cost per solved task at parity | SUPPORTED (recorded) | Report 4: 20B $0.00321 vs 120B $0.00328 per solve; Report 3: 20B loops took 46% of its spend at T=0, 18% at T=1 | Groq price card; one pair |
| 10 | Routing principles generalise from algorithmic tasks to repo-level SWE | UNTESTED | No algorithmic-task data in this round | Do not claim without it |
| 11 | Headline number on unseen tasks | UNTESTED | Blind 200 tasks sealed (tag blind200-prereg), not run | Held until go-ahead |
| 12 | Older reports 13 / 14 / 17 claims | MAPPED, see section below | 2026-11-10 adversarial audit (audit_reports/ARGUS_ADVERSARIAL_AUDIT.md) | I did not reopen the .docx files; statuses rest on that audit |

## Pre-registered predictions (Rev 14 / 15)

| Prediction | Result |
|---|---|
| Qwen3.8 plain not-applied 8-20% | Held (18.3%) |
| Qwen3.8 Argus gain <= +3 | Held (+0.3) |
| Qwen3.8 plain >= 25 solved/100 | Held (26.0) |
| Qwen3.8 F-R in -4..+4 | Held (0.0) |
| Gemma F-R in +2..+10 | Failed (-1.0; 0.0 without API-error tasks) |

## Known weaknesses to state up front
- Loop comparisons are underpowered: every F-R interval spans zero.
- API errors (Groq 7,000 input-tokens/min, Gemma connection closes) cut F runs short; reported with and without.
- R replay treats a patch with no stored grade as not accepted; count not yet checked.
- django-13406 skipped for Gemma (2 draws missing).

## Older reports (13 / 14 / 17): claim-by-claim

Source: audit_reports/ARGUS_ADVERSARIAL_AUDIT.md (2026-11-10). It recomputed counts from stored per-task files and re-checked six of the biggest claims by hand; the rest rests on six reviewer agents. I have not reopened the .docx reports or re-run any of these experiments, so treat "DROP" as "do not present", not as a proof of error in every case.

| Old claim | Status | Reason (from the audit) | Use in the new story |
|---|---|---|---|
| SWE-bench Verified 26 -> 50 of 500 ("doubled") | QUALIFIED | Counts recompute, but the strict arm is a replay classification of the same frozen candidates; candidates are SEARCH/REPLACE blocks, so "git apply" is a straw man. An Aider-style applier ties Argus Tiers 1-3 (E1); only 2 of 50 solves needed Tier 3 | Replace with the pilot-50 apply-layer gain (+5.7 for 20B, CI 2.7 to 9.1, T=1, official harness) |
| Tier 4 (boundary anchors) contributed +10 solves (53 -> 63) | REFUTED | Tier 4 was disabled in code | Drop; Tier 4 is off in the v0.2.0b1 baseline |
| 63/500 "closed loop" | Count verified, mechanism REFUTED | Loop gives apply-error feedback, not test feedback; it is a 20B -> 120B cascade; tuned on the same 500, single run | Cite only as engineering history |
| 76/500 "Cohort B + AST beam" | INVALID | Task set filtered with the gold patch; generator falls back to the gold file | Drop |
| "Frontier-grade at under 1.3 cents per bug" | REFUTED | 12.6% vs published 53-61% for gpt-oss-20b, different scaffold | Drop "frontier-grade"; cost per solve is still a fair metric |
| ~$0.0125 per solved bug | QUALIFIED | Same tokens cost $0.29-$0.86 under the project's four price cards | Use one price card, stated |
| 50-task token audit: -26.6% tokens, 100% thinking eliminated | REFUTED | Best of three runs (+53%, -10%, -26.6%); nothing scored for resolution | Drop |
| 30-task pilot "strictly dominates" | QUALIFIED | No p-value survives Holm correction | Drop |
| 120-task confirmatory study | VERIFIED as a null | Best arm 7/60 repo tasks, adjusted p = 0.5 | Report as null |
| "Zero incorrect applications" | QUALIFIED | True only on the synthetic 500-case corpus; Tier 3 accepted `<` vs `<=` at 0.997 | Scope to the corpus; Tier 3 is a known risk (audit C1) |
| HumanEval/MBPP repair gain (88-90.5%) | REFUTED as held-out | Failing scoring assertions were pasted into the next prompt; 26 of 28 rescues were MBPP | Drop, or report as oracle-assisted only |
| Few-shot lifts 72 -> 78.5% | REFUTED | All exemplars come from the benchmark's own tasks (60/60 retrieval of the task itself) | Drop |
| 72/77% zero-shot baselines reflect capability | REFUTED | max_tokens=512 truncated 22% of attempts | Drop |
| 20B loop ~3.9x cheaper than 120B | REFUTED | Flat per-token prices the code applied; at listed Groq prices costs are about equal | Matches the pilot-50 parity finding (row 9) |
| Best-of-3 = 83%, best-of-5 = 87% | REFUTED | Raw 78.0% / 79.0% (best-of-4); best-of-5 never run | Drop |
| "Function spec" arm best (91.5%) | REFUTED | Arm duplicates always_repair; gap is noise | Drop |
| Learned planner 92% / 184 of 200 | REFUTED | 92/100 doubled; label leakage (AUC 0.97) | Drop |
| Group 1B results ("VERIFIED") | INVALID | Script never calls the engine; flags are synthetic | Retract |
| Adaptive routing (AGENTS.md framing) | NOT SUPPORTED | Routing is a keyword regex over one model in the default config | Say "recovery runtime with a test-gated retry loop", not adaptive routing |
| Closed-loop test-feedback rescued tasks on SWE-bench | REFUTED | Loop used apply-error feedback | Replaced by the pilot-50 F vs R experiment (row 5) |

Still open after this mapping: E3 for the other 295 resolved patches (45 touch lines the gold patch does not), E2 (oracle-free vs oracle-assisted loop), the blind run, and the algorithmic-task half of the research question.
