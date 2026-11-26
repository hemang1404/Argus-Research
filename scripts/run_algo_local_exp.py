"""Experiment 1 + Experiment 3 runner on EvalPlus (HumanEval+ / MBPP+) for local/open-weight models.

Zero Docker: grades candidate Python solutions in milliseconds in a scrubbed subprocess.
Built-in leakage-free test split (matching scripts/run_algo.py):
  - base tests (visible): used in-loop by Experiment 3 (`feedback_loop`)
  - plus tests (hidden):  EvalPlus extra edge-case suite, NEVER shown to the model;
                          grades true non-regressive solve rate (`accepted_resolved` vs `accepted_regressed`)

Arms:
  - baseline:        1-shot generation (no loop detector, no retry)
  - loop_kill:       streaming RepetitionLoopDetector aborts repetition loops early
  - loop_kill_retry: loop_kill + trap-aware retry (temperature >= 0.7) on loop_aborted
  - feedback_loop:   Experiment 3: up to --max-turns with loop_guard + base-test failure feedback
                     (graded against hidden `plus` tests to catch overfit/regressive patches)

Examples:
  # Colab Ollama (Experiment 1 + Experiment 3 on 60 tasks = 30 HE+ / 30 MBPP+):
  python -X utf8 scripts/run_algo_local_exp.py \
      --argus-repo /content/Argus \
      --backend openai --base-url http://127.0.0.1:11434/v1 \
      --model qwen2.5-coder:7b --sample 60 \
      --arms baseline loop_kill loop_kill_retry feedback_loop
"""

from __future__ import annotations

import argparse
import ast
import gc
import json
import math
import os
import random
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


SYSTEM = (
    "You are an expert Python programmer. Reply with ONE complete Python code block "
    "containing the full solution (the function definition plus any imports it needs). No explanation."
)

TRAP_RETRY_NOTE = (
    "\n\n## Note on Previous Attempt (aborted)\n"
    "Repetition loop detected: your previous response repeated itself and was aborted early. "
    "Reply directly with ONE concise, complete ```python code block and no commentary."
)

SAFE_ENV_KEYS = {
    "PATH",
    "HOME",
    "TMPDIR",
    "TEMP",
    "TMP",
    "SYSTEMROOT",
    "COMSPEC",
    "PATHEXT",
    "WINDIR",
    "APPDATA",
    "LOCALAPPDATA",
    "USERPROFILE",
    "HOMEDRIVE",
    "HOMEPATH",
    "PYTHONIOENCODING",
}


def _setup_argus_imports(argus_repo: Optional[str]) -> None:
    if argus_repo:
        p = os.path.abspath(argus_repo)
        if p not in sys.path:
            sys.path.insert(0, p)
    else:
        sibling = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Argus"))
        if os.path.isdir(os.path.join(sibling, "argus")) and sibling not in sys.path:
            sys.path.insert(0, sibling)


class AlgoBank:
    """Loads HumanEval+ / MBPP+ tasks and grades them against base (visible) and plus (hidden) suites."""

    def __init__(self, root: Path) -> None:
        algo_dir = root / "data" / "algo"
        self.he = {
            "humaneval/" + r["task_id"].split("/")[1]: r
            for r in self._load_jsonl(algo_dir / "he_plus.jsonl")
        }
        self.mb = {
            "mbpp/" + str(r["task_id"]): r
            for r in self._load_jsonl(algo_dir / "mbpp_plus.jsonl")
        }
        self.base_he = {
            "humaneval/" + r["task_id"].split("/")[1]: r
            for r in self._load_jsonl(algo_dir / "he_base.jsonl")
        }
        excluded = set(json.loads((algo_dir / "excluded.json").read_text(encoding="utf-8")))
        for x in excluded:
            self.he.pop(x, None)
            self.mb.pop(x, None)
        self.tasks: Dict[str, Dict[str, Any]] = {**self.he, **self.mb}
        self.safe_env = {k: v for k, v in os.environ.items() if k.upper() in SAFE_ENV_KEYS}

    @staticmethod
    def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
        return [
            json.loads(ln)
            for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]

    @staticmethod
    def _tests_of(t: Dict[str, Any]) -> List[str]:
        v = t["test_list"]
        return ast.literal_eval(v) if isinstance(v, str) else v

    @staticmethod
    def _imports_of(t: Dict[str, Any]) -> str:
        v = t.get("test_imports") or "[]"
        return "\n".join(ast.literal_eval(v) if isinstance(v, str) else v)

    def select_ids(self, *, sample: int, seed: int, explicit_ids: List[str]) -> List[str]:
        if explicit_ids:
            return [i for i in explicit_ids if i in self.tasks]
        if sample > 0:
            rng = random.Random(seed)
            n_he = min(len(self.he), sample // 2)
            n_mb = min(len(self.mb), sample - n_he)
            return sorted(rng.sample(sorted(self.he), n_he)) + sorted(rng.sample(sorted(self.mb), n_mb))
        return sorted(self.tasks)

    def user_prompt(self, iid: str) -> str:
        t = self.tasks[iid]
        if iid in self.he:
            return "Complete the following function.\n\n```python\n" + t["prompt"] + "\n```"
        return (
            t["prompt"].strip()
            + "\n\nYour code must pass this example test (the function name and signature must match it):\n```python\n"
            + self._tests_of(t)[0]
            + "\n```"
        )

    def build_base(self, iid: str, code: str) -> str:
        t = self.tasks[iid]
        if iid in self.he:
            return t["prompt"] + "\n\n" + code + "\n\n" + self.base_he[iid]["test"] + f"\n\ncheck({t['entry_point']})\n"
        lines = ["import sys", self._imports_of(t), code, "_fails = []"]
        for a in self._tests_of(t):
            lines.append(
                f"try:\n    exec({a!r})\nexcept BaseException as _e:\n"
                f"    _fails.append(({a!r}, type(_e).__name__ + ': ' + str(_e)[:200]))"
            )
        lines.append(
            "if _fails:\n    for a, e in _fails[:3]:\n        print('FAILED: ' + a + '  ->  ' + e)\n    sys.exit(1)"
        )
        return "\n".join(lines) + "\n"

    def build_plus(self, iid: str, code: str) -> str:
        t = self.tasks[iid]
        if iid in self.he:
            return t["prompt"] + "\n\n" + code + "\n\n" + t["test"] + f"\n\ncheck({t['entry_point']})\n"
        return self._imports_of(t) + "\n" + code + "\n\n" + t["test"] + "\n"

    def _run_py(self, code: str, timeout: int) -> Tuple[bool, str]:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.py"
            p.write_text(code, encoding="utf-8")
            try:
                r = subprocess.run(
                    [sys.executable, "-X", "utf8", str(p)],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=d,
                    env=self.safe_env,
                    stdin=subprocess.DEVNULL,
                    errors="replace",
                )
                return r.returncode == 0, (r.stdout + r.stderr)[-4000:]
            except subprocess.TimeoutExpired:
                return False, "TimeoutError: the solution did not finish within the time limit"

    @staticmethod
    def extract_code(text: str) -> Optional[str]:
        blocks = re.findall(r"```(?:python|py)?[ \t]*\r?\n(.*?)```", text or "", re.DOTALL)
        return blocks[-1] if blocks else None

    def verify(self, iid: str, code: str) -> Tuple[bool, Optional[bool], str]:
        """Return (base_pass, plus_pass_or_None, base_failure_feedback)."""
        try:
            ast.parse(code)
        except SyntaxError as exc:
            return False, None, f"SyntaxError: {exc.msg} (line {exc.lineno})"
        ok_base, out = self._run_py(self.build_base(iid, code), timeout=20)
        if not ok_base:
            return False, None, "The solution fails the example tests:\n" + out.strip()[-1800:]
        ok_plus, _ = self._run_py(self.build_plus(iid, code), timeout=60)
        return True, ok_plus, ""


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
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens

    def preflight_check(self) -> None:
        import urllib.error
        import urllib.request

        url = f"{self.base_url}/models"
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status >= 400:
                    raise RuntimeError(f"Model server health check returned HTTP {resp.status} at {url}")
        except urllib.error.HTTPError as exc:
            if exc.code >= 500:
                raise RuntimeError(f"Model server returned HTTP {exc.code} at {url}") from exc
        except Exception as exc:
            raise RuntimeError(
                f"Cannot reach OpenAI-compatible server at {url}: {exc}. "
                "Start Ollama (11434) or llama-server (8000) first."
            ) from exc

    def generate(self, messages: List[Dict[str, str]], *, temperature: float, loop_guard: bool) -> Dict[str, Any]:
        resp = self.adapter.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=self.max_tokens,
            model=self.model,
            loop_guard=loop_guard,
        )
        reason = resp.raw_response.get("loop_guard_reason") if isinstance(resp.raw_response, dict) else None
        return {
            "content": resp.content or "",
            "finish": resp.finish_reason or "stop",
            "prompt_tokens": int(resp.prompt_tokens or 0),
            "completion_tokens": int(resp.completion_tokens or 0),
            "duration_s": round(float(resp.duration_ms) / 1000.0, 2),
            "loop_guard_reason": reason,
        }


class _HFRunner:
    def __init__(self, *, model_id: str, quant: str, max_tokens: int, enable_thinking: bool) -> None:
        os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.torch = torch
        self.model_id = model_id
        self.max_tokens = max_tokens
        self.enable_thinking = enable_thinking
        self.tok = AutoTokenizer.from_pretrained(model_id)
        kw: Dict[str, Any] = {"device_map": "balanced" if torch.cuda.device_count() > 1 else "auto"}
        if quant == "nf4":
            from transformers import BitsAndBytesConfig

            kw["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.float16
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
                messages, tokenize=False, add_generation_prompt=True, enable_thinking=self.enable_thinking
            )
        except TypeError:
            return self.tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

    def generate(self, messages: List[Dict[str, str]], *, temperature: float, loop_guard: bool) -> Dict[str, Any]:
        from transformers import StoppingCriteria, StoppingCriteriaList, TextIteratorStreamer
        from argus.providers.loop_guard import RepetitionLoopDetector

        torch = self.torch
        inp = self.tok(self._format_chat(messages), return_tensors="pt").to(self.model.device)
        prompt_tokens = int(inp["input_ids"].shape[1])
        gen_kw: Dict[str, Any] = {"max_new_tokens": self.max_tokens, "do_sample": temperature > 0.0}
        if temperature > 0.0:
            gen_kw.update(temperature=temperature, top_p=1.0)
        t0 = time.perf_counter()
        if not loop_guard:
            try:
                with torch.no_grad():
                    out = self.model.generate(**inp, **gen_kw)
            except torch.cuda.OutOfMemoryError:
                gc.collect()
                torch.cuda.empty_cache()
                with torch.no_grad():
                    out = self.model.generate(**inp, prefill_chunk_size=1024, **gen_kw)
            new_ids = out[0][prompt_tokens:]
            n_new = int(len(new_ids))
            return {
                "content": self.tok.decode(new_ids, skip_special_tokens=True),
                "finish": "length" if n_new >= self.max_tokens else "stop",
                "prompt_tokens": prompt_tokens,
                "completion_tokens": n_new,
                "duration_s": round(time.perf_counter() - t0, 2),
                "loop_guard_reason": None,
            }

        detector = RepetitionLoopDetector()
        stop_event = threading.Event()
        streamer = TextIteratorStreamer(self.tok, skip_prompt=True, skip_special_tokens=True)

        class _EventStop(StoppingCriteria):
            def __call__(self, input_ids, scores, **kwargs) -> bool:
                return stop_event.is_set()

        gen_kw["streamer"] = streamer
        gen_kw["stopping_criteria"] = StoppingCriteriaList([_EventStop()])
        holder: Dict[str, Any] = {}

        def _worker() -> None:
            try:
                with torch.no_grad():
                    holder["out"] = self.model.generate(**inp, **gen_kw)
            except Exception as exc:
                holder["err"] = exc

        th = threading.Thread(target=_worker, daemon=True)
        th.start()
        parts: List[str] = []
        loop_reason: Optional[str] = None
        for ch in streamer:
            if ch:
                parts.append(ch)
                reason = detector.feed(ch)
                if reason is not None and loop_reason is None:
                    loop_reason = reason
                    stop_event.set()
        th.join()
        if "err" in holder:
            raise holder["err"]
        n_new = int(holder["out"][0][prompt_tokens:].shape[0])
        return {
            "content": "".join(parts),
            "finish": "loop_aborted" if loop_reason else ("length" if n_new >= self.max_tokens else "stop"),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": n_new,
            "duration_s": round(time.perf_counter() - t0, 2),
            "loop_guard_reason": loop_reason,
        }


def run_task_arm(
    runner: Any,
    bank: AlgoBank,
    iid: str,
    *,
    arm: str,
    model_name: str,
    temperature: float,
    retry_temp: float,
    max_turns: int,
) -> Dict[str, Any]:
    use_guard = arm != "baseline"
    base_user = bank.user_prompt(iid)
    attempts: List[Dict[str, Any]] = []
    aborted_contents: List[Dict[str, Any]] = []

    turns_budget = 1 if arm in ("baseline", "loop_kill") else (2 if arm == "loop_kill_retry" else max_turns)
    next_user = base_user
    next_temp = temperature
    last_gen: Optional[Dict[str, Any]] = None

    for turn in range(1, turns_budget + 1):
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": next_user}]
        gen = runner.generate(msgs, temperature=next_temp, loop_guard=use_guard)
        last_gen = gen
        if gen["finish"] == "loop_aborted":
            aborted_contents.append({"attempt": turn, "reason": gen["loop_guard_reason"], "content": gen["content"]})

        code = bank.extract_code(gen["content"])
        if code is None:
            base_ok, plus_ok = False, None
            fb = (
                TRAP_RETRY_NOTE.strip()
                if gen["finish"] == "loop_aborted"
                else (
                    "Your previous answer was cut off before containing a code block. Keep reasoning short and output ONE ```python block."
                    if gen["finish"] == "length"
                    else "Formatting error: reply with ONE complete ```python code block."
                )
            )
        else:
            base_ok, plus_ok, fb = bank.verify(iid, code)

        state = ("accepted_resolved" if plus_ok else "accepted_regressed") if base_ok else "failed"
        attempts.append(
            {
                "attempt": turn,
                "temperature": next_temp,
                "finish": gen["finish"],
                "prompt_tokens": gen["prompt_tokens"],
                "completion_tokens": gen["completion_tokens"],
                "duration_s": gen["duration_s"],
                "loop_guard_reason": gen["loop_guard_reason"],
                "has_code": code is not None,
                "base_pass": base_ok,
                "plus_pass": plus_ok,
                "state": state,
            }
        )

        if base_ok:
            break
        if arm == "loop_kill_retry":
            if gen["finish"] != "loop_aborted":
                break
            next_temp = max(temperature, retry_temp)
            next_user = base_user + TRAP_RETRY_NOTE
        elif arm == "feedback_loop" and turn < turns_budget:
            if gen["finish"] == "loop_aborted":
                next_temp = max(temperature, retry_temp)
                next_user = base_user + TRAP_RETRY_NOTE
            else:
                next_temp = temperature
                next_user = base_user + f"\n\n## Result of Previous Attempt\n{fb}\n\nWrite a corrected, complete ```python solution."

    final = attempts[-1]
    assert last_gen is not None
    return {
        "iid": iid,
        "source": "HumanEval+" if iid in bank.he else "MBPP+",
        "model": model_name,
        "arm": arm,
        "http": 200,
        "finish": final["finish"],
        "content": last_gen["content"],
        "base_pass": bool(final["base_pass"]),
        "plus_pass": bool(final["plus_pass"]),
        "state": final["state"],
        "accepted_resolved": final["state"] == "accepted_resolved",
        "accepted_regressed": final["state"] == "accepted_regressed",
        "prompt_tokens": sum(a["prompt_tokens"] for a in attempts),
        "completion_tokens": sum(a["completion_tokens"] for a in attempts),
        "duration_s": round(sum(a["duration_s"] for a in attempts), 2),
        "loop_aborts": sum(1 for a in attempts if a["finish"] == "loop_aborted"),
        "aborted_contents": aborted_contents,
        "attempts": len(attempts),
        "attempt_history": attempts,
    }


def _bootstrap_ci(diffs: List[float], *, scale: float = 1.0, n_resamples: int = 5000, seed: int = 42) -> Tuple[float, float, float]:
    n = len(diffs)
    if n == 0:
        return 0.0, 0.0, 0.0
    mean = scale * sum(diffs) / n
    rng = random.Random(seed)
    boots = sorted(scale * sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(n_resamples))
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
    b_res = [1 if base[k].get("accepted_resolved") else 0 for k in common]
    t_res = [1 if treat[k].get("accepted_resolved") else 0 for k in common]
    only_t = sum(1 for a, b in zip(t_res, b_res) if a == 1 and b == 0)
    only_b = sum(1 for a, b in zip(t_res, b_res) if a == 0 and b == 1)
    disc = only_t + only_b
    mcnemar_p = (
        1.0
        if disc == 0
        else min(1.0, 2.0 * sum(math.comb(disc, j) for j in range(min(only_t, only_b) + 1)) / (2 ** disc))
    )
    diff_pp, pp_lo, pp_hi = _bootstrap_ci([float(a - b) for a, b in zip(t_res, b_res)], scale=100.0)

    b_comp = [float(base[k].get("completion_tokens", 0)) for k in common]
    t_comp = [float(treat[k].get("completion_tokens", 0)) for k in common]
    tok_mean, tok_lo, tok_hi = _bootstrap_ci([b - t for b, t in zip(b_comp, t_comp)])
    sec_mean, sec_lo, sec_hi = _bootstrap_ci(
        [float(base[k].get("duration_s", 0.0)) - float(treat[k].get("duration_s", 0.0)) for k in common]
    )
    b_tot, t_tot = sum(b_comp), sum(t_comp)
    b_sec = sum(float(base[k].get("duration_s", 0.0)) for k in common)
    t_sec = sum(float(treat[k].get("duration_s", 0.0)) for k in common)

    return {
        "n_paired": n,
        "baseline_base_pass": sum(1 for k in common if base[k].get("base_pass")),
        "treatment_base_pass": sum(1 for k in common if treat[k].get("base_pass")),
        "baseline_resolved_plus": sum(b_res),
        "treatment_resolved_plus": sum(t_res),
        "baseline_regressed": sum(1 for k in common if base[k].get("accepted_regressed")),
        "treatment_regressed": sum(1 for k in common if treat[k].get("accepted_regressed")),
        "resolve_diff_pp": diff_pp,
        "resolve_diff_95_ci": [pp_lo, pp_hi],
        "mcnemar_p": round(mcnemar_p, 5),
        "only_treatment_solved": only_t,
        "only_baseline_solved": only_b,
        "treatment_loop_aborts": sum(int(treat[k].get("loop_aborts", 0)) for k in common),
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


def _load_completed_ids(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    done: set[str] = set()
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not ln.strip():
            continue
        try:
            r = json.loads(ln)
            if r.get("iid") and r.get("http") == 200 and r.get("content") is not None:
                done.add(str(r["iid"]))
        except json.JSONDecodeError:
            continue
    return done


def main() -> None:
    ap = argparse.ArgumentParser(description="Experiment 1 + 3 runner on HumanEval+ / MBPP+ (no Docker).")
    ap.add_argument("--argus-repo", help="Path to cloned hemang1404/Argus repo.")
    ap.add_argument("--backend", choices=["openai", "hf"], default="openai")
    ap.add_argument("--base-url", default="http://127.0.0.1:11434/v1")
    ap.add_argument("--api-key-env", default="")
    ap.add_argument("--model", default="qwen2.5-coder:7b")
    ap.add_argument("--quant", choices=["none", "nf4"], default="none")
    ap.add_argument("--enable-thinking", action="store_true")
    ap.add_argument("--reasoning-effort", default=None)
    ap.add_argument(
        "--arms",
        nargs="+",
        choices=["baseline", "loop_kill", "loop_kill_retry", "feedback_loop"],
        default=["baseline", "loop_kill", "loop_kill_retry", "feedback_loop"],
    )
    ap.add_argument("--sample", type=int, default=60, help="Total tasks (half HE+, half MBPP+; 0 = all 542).")
    ap.add_argument("--seed", type=int, default=20261126)
    ap.add_argument("--ids", nargs="*", default=[])
    ap.add_argument("--out-dir", default="data/algo_local_exp")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--retry-temp", type=float, default=0.7)
    ap.add_argument("--max-turns", type=int, default=3)
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--selftest", action="store_true", help="Verify sandbox grading on gold and broken code.")
    ap.add_argument("--summarize", nargs=2, metavar=("BASELINE_JSONL", "TREATMENT_JSONL"))
    args = ap.parse_args()

    _setup_argus_imports(args.argus_repo)
    if args.summarize:
        print(json.dumps(summarize_paired(Path(args.summarize[0]), Path(args.summarize[1])), indent=2))
        return

    root = Path(__file__).resolve().parent.parent
    bank = AlgoBank(root)
    ids = bank.select_ids(sample=args.sample, seed=args.seed, explicit_ids=args.ids)

    if args.selftest:
        ok = bad = 0
        for iid in ids:
            t = bank.tasks[iid]
            gold = (t["prompt"] + t["canonical_solution"]) if iid in bank.he else t["code"]
            b, pl, _ = bank.verify(iid, gold)
            broken = f"def {t.get('entry_point') or 'zzz'}(*a, **k):\n    return None\n"
            b2, _, _ = bank.verify(iid, broken)
            if b and pl and not b2:
                ok += 1
            else:
                bad += 1
                print("SELFTEST FAIL", iid, b, pl, b2)
        print(f"selftest: {ok}/{len(ids)} ok, {bad} failed")
        return

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
        runner.preflight_check()
    else:
        runner = _HFRunner(
            model_id=args.model, quant=args.quant, max_tokens=args.max_tokens, enable_thinking=args.enable_thinking
        )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = args.model.split("/")[-1].replace(":", "_")
    arm_paths: Dict[str, Path] = {}

    for arm in args.arms:
        out_path = out_dir / f"algo_{arm}_{tag}.jsonl"
        arm_paths[arm] = out_path
        done = _load_completed_ids(out_path)
        print(f"=== arm={arm} model={args.model} tasks={len(ids)} already_done={len(done)} -> {out_path} ===", flush=True)
        with out_path.open("a", encoding="utf-8") as fh:
            for idx, iid in enumerate(ids, 1):
                if iid in done:
                    continue
                try:
                    rec = run_task_arm(
                        runner,
                        bank,
                        iid,
                        arm=arm,
                        model_name=args.model,
                        temperature=args.temperature,
                        retry_temp=args.retry_temp,
                        max_turns=args.max_turns,
                    )
                except Exception as exc:
                    rec = {"iid": iid, "model": args.model, "arm": arm, "http": -1, "error": str(exc)[:300], "content": None}
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                if rec.get("http") == 200:
                    print(
                        f"  [{arm} {idx}/{len(ids)}] {iid:16s} state={rec['state']:18s} "
                        f"tok={rec['completion_tokens']} aborts={rec['loop_aborts']} tries={rec['attempts']} {rec['duration_s']}s",
                        flush=True,
                    )
                else:
                    print(f"  [{arm} {idx}/{len(ids)}] {iid:16s} ERROR={rec.get('error')}", flush=True)

    if "baseline" in arm_paths:
        for arm in args.arms:
            if arm != "baseline":
                print(f"\n=== PAIRED SUMMARY: baseline vs {arm} ===", flush=True)
                print(json.dumps(summarize_paired(arm_paths["baseline"], arm_paths[arm]), indent=2), flush=True)


if __name__ == "__main__":
    main()
