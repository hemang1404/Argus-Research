"""Experiment 1 (Loop Kill-Switch + Trap-Aware Retry) runner for Argus-Research.

Evaluates three paired arms on the frozen Pilot-100 prompts (or any prompt JSONL):
  - baseline:        normal generation (no loop detector, no retry)
  - loop_kill:       streaming RepetitionLoopDetector aborts repetition loops early
  - loop_kill_retry: loop_kill + trap-aware retry (temperature >= 0.7, concise prompt)

Supports both:
  1. --backend openai  (Colab / local llama-server, Ollama, vLLM, or any OpenAI API)
  2. --backend hf      (Kaggle 2xT4 / Hugging Face transformers with streaming StoppingCriteria)

Outputs resumable JSONL compatible with scripts/apply_argus.py and swebench Docker grading.

Examples:
  # Colab (OpenAI-compatible server on 127.0.0.1:8000):
  python -X utf8 scripts/run_loop_guard_exp.py \
      --backend openai --base-url http://127.0.0.1:8000/v1 \
      --model qwen2.5-coder-7b-instruct \
      --arms baseline loop_kill loop_kill_retry \
      --temperature 0.0 --non-django --limit 30 \
      --argus-repo /content/Argus

  # Kaggle 2xT4 (Hugging Face open weights):
  python -X utf8 scripts/run_loop_guard_exp.py \
      --backend hf --model Qwen/Qwen2.5-Coder-7B-Instruct \
      --arms baseline loop_kill loop_kill_retry \
      --temperature 0.0 --argus-repo /kaggle/working/Argus

  # Paired summary:
  python -X utf8 scripts/run_loop_guard_exp.py \
      --summarize data/loop_guard_exp/outputs_baseline_qwen2.5-coder-7b-instruct.jsonl \
                  data/loop_guard_exp/outputs_loop_kill_retry_qwen2.5-coder-7b-instruct.jsonl
"""

from __future__ import annotations

import argparse
import gc
import glob
import json
import math
import os
import random
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


TRAP_RETRY_TEMPLATE = (
    "\n\n## Note on Previous Attempt (aborted)\n"
    "Repetition loop detected: your previous response repeated itself and was aborted early. "
    "Output ONE concise SEARCH/REPLACE block for `{target_file}` copying exact lines from the code shown above "
    "and no commentary. Do not echo placeholder text like <path>."
)


def _setup_argus_imports(argus_repo: Optional[str]) -> None:
    if argus_repo:
        p = os.path.abspath(argus_repo)
        if p not in sys.path:
            sys.path.insert(0, p)
    else:
        sibling = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Argus"))
        if os.path.isdir(os.path.join(sibling, "argus")) and sibling not in sys.path:
            sys.path.insert(0, sibling)


def _discover_prompts(root: Path, prompt_paths: List[str]) -> List[Dict[str, Any]]:
    files: List[Path] = []
    if prompt_paths:
        files = [Path(p) for p in prompt_paths]
    else:
        local_pair = [
            root / "data" / "qwen_probe" / "prompts.jsonl",
            root / "data" / "qwen_probe" / "prompts_remaining.jsonl",
        ]
        if all(p.is_file() for p in local_pair):
            files = local_pair
        else:
            cands = (
                sorted(glob.glob("/kaggle/input/**/prompts*.jsonl", recursive=True))
                + sorted(glob.glob("/kaggle/working/prompts*.jsonl"))
                + sorted(glob.glob("prompts*.jsonl"))
            )
            files = [Path(p) for p in cands]

    if not files:
        raise FileNotFoundError(
            "No prompt JSONL files found. Pass --prompts or ensure data/qwen_probe/prompts*.jsonl exists."
        )

    rows: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for fp in files:
        with fp.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                iid = obj["iid"]
                if iid not in seen:
                    seen.add(iid)
                    rows.append(obj)
    return rows


def _load_completed_ids(out_path: Path) -> set[str]:
    if not out_path.is_file():
        return set()
    done: set[str] = set()
    with out_path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("iid") and rec.get("http") == 200 and rec.get("content") is not None:
                done.add(str(rec["iid"]))
    return done


def _parse_search_replace_count(text: str) -> int:
    from argus.patch.parser import PatchParser

    placeholders = (
        "<exact lines copied",
        "<the replacement lines>",
        "[exact lines from file",
        "[new replacement lines]",
    )
    blocks = PatchParser.parse(text or "")
    real = [
        b
        for b in blocks
        if (b.file_path or "").strip() != "<path>"
        and not any(ph in (b.search_text or "") or ph in (b.replace_text or "") for ph in placeholders)
    ]
    return len(real)


class _OpenAIRunner:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str,
        max_tokens: int,
        timeout_s: float,
        reasoning_effort: Optional[str],
    ) -> None:
        from argus.providers.adapter import OpenAICompatibleAdapter
        from argus.providers.models import ProviderConfig

        cfg = ProviderConfig(
            name="custom",
            base_url=base_url,
            model=model,
            api_key=api_key or None,
            temperature=0.0,
            max_tokens=max_tokens,
            timeout_seconds=timeout_s,
            reasoning_effort=reasoning_effort,
        )
        self.adapter = OpenAICompatibleAdapter(cfg)
        self.model = model
        self.max_tokens = max_tokens

    def generate(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float,
        loop_guard: bool,
    ) -> Dict[str, Any]:
        resp = self.adapter.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=self.max_tokens,
            model=self.model,
            loop_guard=loop_guard,
        )
        reason = None
        if isinstance(resp.raw_response, dict):
            reason = resp.raw_response.get("loop_guard_reason")
        return {
            "content": resp.content or "",
            "finish": resp.finish_reason or "stop",
            "prompt_tokens": int(resp.prompt_tokens or 0),
            "completion_tokens": int(resp.completion_tokens or 0),
            "duration_s": round(float(resp.duration_ms) / 1000.0, 2),
            "loop_guard_reason": reason,
            "served_model": resp.model,
        }


class _HFRunner:
    def __init__(
        self,
        *,
        model_id: str,
        quant: str,
        max_tokens: int,
        enable_thinking: bool,
    ) -> None:
        os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.torch = torch
        self.model_id = model_id
        self.quant = quant
        self.max_tokens = max_tokens
        self.enable_thinking = enable_thinking
        self.tok = AutoTokenizer.from_pretrained(model_id)

        kw: Dict[str, Any] = {"device_map": "balanced" if torch.cuda.device_count() > 1 else "auto"}
        if quant == "nf4":
            from transformers import BitsAndBytesConfig

            kw["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
            )
        else:
            kw["torch_dtype"] = torch.float16

        try:
            self.model = AutoModelForCausalLM.from_pretrained(model_id, **kw)
        except Exception:
            from transformers import AutoModelForImageTextToText

            self.model = AutoModelForImageTextToText.from_pretrained(model_id, **kw)

    def _format_chat(self, messages: List[Dict[str, str]]) -> str:
        try:
            return self.tok.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=self.enable_thinking,
            )
        except TypeError:
            return self.tok.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )

    def generate(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float,
        loop_guard: bool,
    ) -> Dict[str, Any]:
        from transformers import StoppingCriteria, StoppingCriteriaList, TextIteratorStreamer
        from argus.providers.loop_guard import RepetitionLoopDetector

        torch = self.torch
        prompt_text = self._format_chat(messages)
        inp = self.tok(prompt_text, return_tensors="pt").to(self.model.device)
        prompt_tokens = int(inp["input_ids"].shape[1])

        gen_kw: Dict[str, Any] = {
            "max_new_tokens": self.max_tokens,
            "do_sample": temperature > 0.0,
        }
        if temperature > 0.0:
            gen_kw["temperature"] = temperature
            gen_kw["top_p"] = 1.0

        t0 = time.perf_counter()
        if not loop_guard:
            out = None
            try:
                with torch.no_grad():
                    out = self.model.generate(**inp, **gen_kw)
            except torch.cuda.OutOfMemoryError:
                gc.collect()
                torch.cuda.empty_cache()
                with torch.no_grad():
                    out = self.model.generate(**inp, prefill_chunk_size=1024, **gen_kw)
            new_ids = out[0][prompt_tokens:]
            content = self.tok.decode(new_ids, skip_special_tokens=True)
            n_new = int(len(new_ids))
            return {
                "content": content,
                "finish": "length" if n_new >= self.max_tokens else "stop",
                "prompt_tokens": prompt_tokens,
                "completion_tokens": n_new,
                "duration_s": round(time.perf_counter() - t0, 2),
                "loop_guard_reason": None,
                "served_model": self.model_id,
            }

        detector = RepetitionLoopDetector()
        stop_event = threading.Event()
        streamer = TextIteratorStreamer(self.tok, skip_prompt=True, skip_special_tokens=True)

        class _EventStop(StoppingCriteria):
            def __call__(self, input_ids, scores, **kwargs) -> bool:
                return stop_event.is_set()

        gen_kw["streamer"] = streamer
        gen_kw["stopping_criteria"] = StoppingCriteriaList([_EventStop()])

        out_holder: Dict[str, Any] = {}

        def _worker() -> None:
            try:
                with torch.no_grad():
                    out_holder["out"] = self.model.generate(**inp, **gen_kw)
            except torch.cuda.OutOfMemoryError:
                gc.collect()
                torch.cuda.empty_cache()
                try:
                    with torch.no_grad():
                        out_holder["out"] = self.model.generate(**inp, prefill_chunk_size=1024, **gen_kw)
                except Exception as exc:
                    out_holder["err"] = exc
            except Exception as exc:
                out_holder["err"] = exc

        th = threading.Thread(target=_worker, daemon=True)
        th.start()
        parts: List[str] = []
        loop_reason: Optional[str] = None
        for chunk in streamer:
            if chunk:
                parts.append(chunk)
                reason = detector.feed(chunk)
                if reason is not None and loop_reason is None:
                    loop_reason = reason
                    stop_event.set()
        th.join()
        if "err" in out_holder:
            raise out_holder["err"]

        out = out_holder["out"]
        n_new = int(out[0][prompt_tokens:].shape[0])
        content = "".join(parts)
        finish = "loop_aborted" if loop_reason else ("length" if n_new >= self.max_tokens else "stop")
        return {
            "content": content,
            "finish": finish,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": n_new,
            "duration_s": round(time.perf_counter() - t0, 2),
            "loop_guard_reason": loop_reason,
            "served_model": self.model_id,
        }


def run_task_arm(
    runner: Any,
    task: Dict[str, Any],
    *,
    arm: str,
    model_name: str,
    temperature: float,
    retry_temp: float,
) -> Dict[str, Any]:
    use_guard = arm in ("loop_kill", "loop_kill_retry")
    messages = list(task["messages"])

    r1 = runner.generate(messages, temperature=temperature, loop_guard=use_guard)
    attempts = [
        {
            "attempt": 1,
            "temperature": temperature,
            "finish": r1["finish"],
            "prompt_tokens": r1["prompt_tokens"],
            "completion_tokens": r1["completion_tokens"],
            "duration_s": r1["duration_s"],
            "loop_guard_reason": r1["loop_guard_reason"],
            "n_blocks": _parse_search_replace_count(r1["content"]),
        }
    ]

    final = r1
    retry_used = False
    if arm == "loop_kill_retry" and r1["finish"] == "loop_aborted":
        retry_used = True
        eff_temp = max(temperature, retry_temp)
        note = TRAP_RETRY_TEMPLATE.format(target_file=task.get("target_file") or "the target file")
        if messages and messages[-1].get("role") == "user":
            retry_messages = messages[:-1] + [
                {"role": "user", "content": messages[-1]["content"] + note}
            ]
        else:
            retry_messages = messages + [{"role": "user", "content": note.strip()}]
        r2 = runner.generate(retry_messages, temperature=eff_temp, loop_guard=True)
        attempts.append(
            {
                "attempt": 2,
                "temperature": eff_temp,
                "finish": r2["finish"],
                "prompt_tokens": r2["prompt_tokens"],
                "completion_tokens": r2["completion_tokens"],
                "duration_s": r2["duration_s"],
                "loop_guard_reason": r2["loop_guard_reason"],
                "n_blocks": _parse_search_replace_count(r2["content"]),
            }
        )
        final = r2

    loop_aborts = sum(1 for a in attempts if a["finish"] == "loop_aborted")
    total_prompt = sum(a["prompt_tokens"] for a in attempts)
    total_comp = sum(a["completion_tokens"] for a in attempts)
    total_secs = round(sum(a["duration_s"] for a in attempts), 2)
    final_blocks = attempts[-1]["n_blocks"]

    return {
        "iid": task["iid"],
        "model": model_name,
        "arm": arm,
        "sample": 0,
        "http": 200,
        "target_file": task.get("target_file"),
        "prompt_hash": task.get("prompt_hash"),
        "finish": final["finish"],
        "content": final["content"],
        "prompt_tokens": total_prompt,
        "completion_tokens": total_comp,
        "duration_s": total_secs,
        "loop_aborts": loop_aborts,
        "loop_guard_reason": final["loop_guard_reason"],
        "attempts": len(attempts),
        "retry_used": retry_used,
        "retry_rescued_blocks": bool(retry_used and final_blocks > 0),
        "n_blocks": final_blocks,
        "attempt_history": attempts,
    }


def _bootstrap_mean_ci(diffs: List[float], n_resamples: int = 5000, seed: int = 42) -> Tuple[float, float, float]:
    n = len(diffs)
    if n == 0:
        return 0.0, 0.0, 0.0
    mean = sum(diffs) / n
    rng = random.Random(seed)
    boots = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(n_resamples))
    return (
        round(mean, 2),
        round(boots[int(0.025 * n_resamples)], 2),
        round(boots[min(n_resamples - 1, int(0.975 * n_resamples))], 2),
    )


def summarize_paired(base_path: Path, treat_path: Path) -> Dict[str, Any]:
    base = {
        r["iid"]: r
        for ln in base_path.read_text(encoding="utf-8").splitlines()
        if ln.strip()
        for r in [json.loads(ln)]
        if r.get("http") == 200
    }
    treat = {
        r["iid"]: r
        for ln in treat_path.read_text(encoding="utf-8").splitlines()
        if ln.strip()
        for r in [json.loads(ln)]
        if r.get("http") == 200
    }
    common = sorted(set(base) & set(treat))
    n = len(common)
    base_comp = [float(base[k].get("completion_tokens", 0)) for k in common]
    treat_comp = [float(treat[k].get("completion_tokens", 0)) for k in common]
    tok_saved = [b - t for b, t in zip(base_comp, treat_comp)]
    sec_saved = [float(base[k].get("duration_s", 0.0)) - float(treat[k].get("duration_s", 0.0)) for k in common]

    tok_mean, tok_lo, tok_hi = _bootstrap_mean_ci(tok_saved)
    sec_mean, sec_lo, sec_hi = _bootstrap_mean_ci(sec_saved)
    b_tot = sum(base_comp)
    t_tot = sum(treat_comp)
    b_sec = sum(float(base[k].get("duration_s", 0.0)) for k in common)
    t_sec = sum(float(treat[k].get("duration_s", 0.0)) for k in common)

    b_blocks = [1 if (base[k].get("n_blocks") or 0) > 0 else 0 for k in common]
    t_blocks = [1 if (treat[k].get("n_blocks") or 0) > 0 else 0 for k in common]
    only_t = sum(1 for a, b in zip(t_blocks, b_blocks) if a == 1 and b == 0)
    only_b = sum(1 for a, b in zip(t_blocks, b_blocks) if a == 0 and b == 1)
    disc = only_t + only_b
    mcnemar_p = (
        1.0
        if disc == 0
        else min(1.0, 2.0 * sum(math.comb(disc, j) for j in range(min(only_t, only_b) + 1)) / (2 ** disc))
    )

    return {
        "n_paired": n,
        "baseline_file": str(base_path),
        "treatment_file": str(treat_path),
        "baseline_valid_blocks": sum(b_blocks),
        "treatment_valid_blocks": sum(t_blocks),
        "blocks_mcnemar_p": round(mcnemar_p, 5),
        "baseline_length_truncations": sum(1 for k in common if base[k].get("finish") == "length"),
        "treatment_loop_aborts": sum(int(treat[k].get("loop_aborts", 0)) for k in common),
        "treatment_retries": sum(1 for k in common if treat[k].get("retry_used")),
        "treatment_retry_rescued_blocks": sum(1 for k in common if treat[k].get("retry_rescued_blocks")),
        "baseline_completion_tokens": int(b_tot),
        "treatment_completion_tokens": int(t_tot),
        "mean_tokens_saved_per_task": tok_mean,
        "tokens_saved_95_ci": [tok_lo, tok_hi],
        "tokens_saved_pct": round(100.0 * (b_tot - t_tot) / b_tot, 2) if b_tot else 0.0,
        "baseline_duration_s": round(b_sec, 2),
        "treatment_duration_s": round(t_sec, 2),
        "mean_seconds_saved_per_task": sec_mean,
        "seconds_saved_95_ci": [sec_lo, sec_hi],
        "seconds_saved_pct": round(100.0 * (b_sec - t_sec) / b_sec, 2) if b_sec else 0.0,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Experiment 1 (Loop Kill-Switch + Trap-Aware Retry) for Argus-Research.")
    ap.add_argument("--argus-repo", help="Path to cloned hemang1404/Argus repo (if argus is not pip-installed).")
    ap.add_argument("--backend", choices=["openai", "hf"], default="openai")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    ap.add_argument("--api-key-env", default="", help="Optional env var holding an API key for --backend openai.")
    ap.add_argument("--model", default="qwen2.5-coder-7b-instruct")
    ap.add_argument("--quant", choices=["none", "nf4"], default="none", help="Optional 4-bit NF4 load for --backend hf.")
    ap.add_argument("--enable-thinking", action="store_true", help="Enable model thinking template for --backend hf.")
    ap.add_argument("--reasoning-effort", default=None)
    ap.add_argument("--arms", nargs="+", choices=["baseline", "loop_kill", "loop_kill_retry"], default=["baseline", "loop_kill_retry"])
    ap.add_argument("--prompts", nargs="*", default=[], help="Explicit prompt JSONL paths (default: data/qwen_probe/prompts*.jsonl).")
    ap.add_argument("--ids-file", default="", help="Optional JSON file with {'ids': [...]} to filter task order/subset.")
    ap.add_argument("--non-django", action="store_true", help="Skip django__django tasks.")
    ap.add_argument("--limit", type=int, default=0, help="Run only the first N selected tasks (0 = all).")
    ap.add_argument("--out-dir", default="data/loop_guard_exp")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--retry-temp", type=float, default=0.7)
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--summarize", nargs=2, metavar=("BASELINE_JSONL", "TREATMENT_JSONL"))
    args = ap.parse_args()

    _setup_argus_imports(args.argus_repo)

    if args.summarize:
        print(json.dumps(summarize_paired(Path(args.summarize[0]), Path(args.summarize[1])), indent=2))
        return

    root = Path(__file__).resolve().parent.parent
    tasks = _discover_prompts(root, args.prompts)
    if args.ids_file:
        allowed = json.loads(Path(args.ids_file).read_text(encoding="utf-8"))["ids"]
        by_id = {t["iid"]: t for t in tasks}
        tasks = [by_id[i] for i in allowed if i in by_id]
    if args.non_django:
        tasks = [t for t in tasks if not t["iid"].startswith("django__")]
    if args.limit > 0:
        tasks = tasks[: args.limit]

    api_key = os.environ.get(args.api_key_env, "") if args.api_key_env else ""
    if args.backend == "openai":
        runner: Any = _OpenAIRunner(
            base_url=args.base_url,
            model=args.model,
            api_key=api_key,
            max_tokens=args.max_tokens,
            timeout_s=args.timeout,
            reasoning_effort=args.reasoning_effort,
        )
    else:
        runner = _HFRunner(
            model_id=args.model,
            quant=args.quant,
            max_tokens=args.max_tokens,
            enable_thinking=args.enable_thinking,
        )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = args.model.split("/")[-1].replace(":", "_")
    arm_paths: Dict[str, Path] = {}

    for arm in args.arms:
        out_path = out_dir / f"outputs_{arm}_{tag}.jsonl"
        arm_paths[arm] = out_path
        done = _load_completed_ids(out_path)
        print(f"=== arm={arm} model={args.model} tasks={len(tasks)} already_done={len(done)} -> {out_path} ===", flush=True)
        with out_path.open("a", encoding="utf-8") as fh:
            for idx, task in enumerate(tasks, 1):
                iid = task["iid"]
                if iid in done:
                    continue
                try:
                    rec = run_task_arm(
                        runner,
                        task,
                        arm=arm,
                        model_name=args.model,
                        temperature=args.temperature,
                        retry_temp=args.retry_temp,
                    )
                except Exception as exc:
                    rec = {
                        "iid": iid,
                        "model": args.model,
                        "arm": arm,
                        "sample": 0,
                        "http": -1,
                        "error": str(exc)[:300],
                        "content": None,
                    }
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                if rec.get("http") == 200:
                    print(
                        f"  [{arm} {idx}/{len(tasks)}] {iid} finish={rec['finish']} "
                        f"blocks={rec['n_blocks']} comp_tok={rec['completion_tokens']} "
                        f"aborts={rec['loop_aborts']} retry={rec['retry_used']} {rec['duration_s']}s",
                        flush=True,
                    )
                else:
                    print(f"  [{arm} {idx}/{len(tasks)}] {iid} ERROR={rec.get('error')}", flush=True)

    if "baseline" in arm_paths:
        for arm in args.arms:
            if arm != "baseline":
                print("\n=== PAIRED SUMMARY: baseline vs", arm, "===", flush=True)
                print(json.dumps(summarize_paired(arm_paths["baseline"], arm_paths[arm]), indent=2), flush=True)


if __name__ == "__main__":
    main()
