# Local & Open-Weight Evaluation Protocol (`Argus-Research`)

This protocol governs Colab (`1×T4`) and Kaggle (`2×T4`) local-model experiments inside **`Argus-Research`** (`hemang1404/Argus-Research`), evaluated against the product code in **`hemang1404/Argus`**.

---

## 1. Scope & Execution Order

Run strictly in order — **do not run cascade or quantization studies until both Experiment 1 and Experiment 3 have results**:

1. **Experiment 1 — Loop Kill-Switch + Trap-Aware Retry** (`scripts/run_loop_guard_exp.py`)
2. **Experiment 3 — In-Loop Regression Gate with Hidden Grading Split** (`scripts/make_exp3_p2p_split.py`)

Deferred until both complete:
- Hybrid local -> cloud cascade
- Quantization drift vs. recovery (`Inkling 2 Mini` — Thinking Machines Lab Nov 2026 Apache-2.0 looped MoE, `26.4B` total / `3.4B–5.4B` active, HF `UD-Q4_K_M` / `UD-IQ3_XXS`)

---

## 2. Frozen Task Source (Zero Paper Overlap)

Do **not** mine fresh repos (`click`/`rich`) or build ad-hoc subsets on Colab. Use the frozen SHA-256 manifests already in this repo:

- **Discovery / Dev set:** `manifests/pilot100_manifest.json` (`100` single-file tasks from `SWE-bench_Verified`, pre-rendered at `data/qwen_probe/prompts.jsonl` + `prompts_remaining.jsonl`, `6,000`-token prompt budget).
- **Held-out set (keep sealed):** `manifests/blind200_manifest.json` (`200` tasks strictly disjoint from Pilot-100).

---

## 3. Token Limits & Server Configuration (Aligned)

All layers agree on the exact budget:
- **Prompt budget:** `6,000` tokens (frozen in `data/qwen_probe/prompts*.jsonl`)
- **Max completion tokens:** `4,096` (`--max-tokens 4096`)
- **Server context window (`num_ctx` / `--n_ctx`):** **`16,384`** (`>= 6,000 + 4,096`, preventing `HTTP 400` context-overflow errors observed at Ollama's default `4096`).

On Colab `1×T4`:
- **Option A (fastest, zero CUDA build):** Ollama with `OLLAMA_CONTEXT_LENGTH=16384`.
- **Option B (`llama-cpp-python`):** Install a CUDA wheel (`--extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124`), launch with `--n_gpu_layers -1 --n_ctx 16384`, and verify `/tmp/llama_server.log` confirms layers offloaded to CUDA (GPU is not sitting idle).

---

## 4. Experiment 1 Specification (3 Paired Arms)

Always run **all three arms** so abort and retry effects are measured separately:
1. `baseline`: no streaming loop detector, no retry.
2. `loop_kill`: streaming `argus.providers.loop_guard.RepetitionLoopDetector` (`min_line_chars=20`, `line_window=24`, `line_repeat_threshold=5`; `ngram_chars=80`, `ngram_repeat_threshold=4`; periodic tail `24–320` chars x `4` repeats).
3. `loop_kill_retry`: `loop_kill` + single trap-aware retry at `temperature >= 0.7` folded into the single user prompt with explicit target filename (to prevent system-template placeholder echoes).

### Metrics & Statistical Honesty
- **Primary metrics:** Paired **completion tokens saved** and **wall-clock seconds saved** (with 95% task-bootstrap CI).
- **Safety / non-inferiority checks:** Verify `apply` rate / solve rate does not drop vs. `baseline`.
- **Sample-size reality:** Two-sided exact McNemar at `n=30–40` requires at least `6` discordant pairs all in one direction to reach `p < 0.05`, so run all `100` Pilot-100 tasks when measuring solve differences, and never expect statistical significance on solve rate from a small subset.
- **False-abort audit:** Every `loop_aborted` trace is stored in `aborted_contents` in the output JSONL; run `--inspect-aborts <file.jsonl>` and read them to verify no repetitive-but-valid code was killed.
- **Resumability safety:** Failed/offline tasks log `http=-1` and are **retried** on resume; only `http == 200 and content is not None` marks a task done. `_OpenAIRunner.preflight_check()` fails fast if the server is down.

---

## 5. Experiment 3 Specification (No Regression Leakage)

To avoid grading on the exact regression tests shown to the model:
1. Run `python -X utf8 scripts/make_exp3_p2p_split.py` to freeze `manifests/exp3_p2p_split.json` (`seed=20261126`).
2. Each task's `PASS_TO_PASS` suite is split 50/50 into:
   - `visible_p2p`: passed into the in-loop regression gate; failures can be fed back into Attempts 2–3.
   - `heldout_p2p`: **strictly hidden** from the model during all attempts and graded only at the end alongside `FAIL_TO_PASS`.
