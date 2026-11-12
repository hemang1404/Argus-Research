"""Kaggle speed test (run after kaggle_smoke.py works): warm-up, then time a realistic prompt at batch 1 and batch 4.
Paste into a Kaggle notebook cell (GPU T4 x2, Internet on). Set MODEL_ID. No keys needed.
"""
import subprocess, sys
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "transformers", "accelerate", "flash-linear-attention"], check=False)

import time, torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_ID = "Qwen/Qwen3.5-2B"   # change for 4B / 9B
DTYPE = torch.float16
NEW_TOKENS = 300

tok = AutoTokenizer.from_pretrained(MODEL_ID)
tok.padding_side = "left"
try:
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, dtype=DTYPE, device_map="auto")
except Exception as e:
    print("AutoModelForCausalLM failed:", repr(e)[:300])
    from transformers import AutoModelForImageTextToText
    model = AutoModelForImageTextToText.from_pretrained(MODEL_ID, dtype=DTYPE, device_map="auto")


def prompt_text(n_filler):
    code = "\n".join(f"def helper_{i}(x):\n    return x + {i}\n" for i in range(n_filler))
    msg = [{"role": "user", "content": "Here is a Python file:\n```python\n" + code + "\n```\nRewrite helper_3 so it returns x * 3. "
            "Answer with a SEARCH/REPLACE block only."}]
    try:
        return tok.apply_chat_template(msg, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    except TypeError:
        return tok.apply_chat_template(msg, tokenize=False, add_generation_prompt=True)


def run(batch, n_filler, new_tokens):
    texts = [prompt_text(n_filler)] * batch
    inp = tok(texts, return_tensors="pt", padding=True).to(model.device)
    torch.cuda.synchronize(); t0 = time.time()
    out = model.generate(**inp, max_new_tokens=new_tokens, min_new_tokens=new_tokens, do_sample=True, temperature=1.0)
    torch.cuda.synchronize(); dt = time.time() - t0
    return inp["input_ids"].shape[1], dt, batch * new_tokens / dt


run(1, 10, 8)  # warm-up
for batch in (1, 4):
    plen, dt, tps = run(batch, 450, NEW_TOKENS)
    print(f"batch {batch}: prompt {plen} tokens, {NEW_TOKENS} new tokens each, {dt:.1f} s, {tps:.1f} tokens/s total")
for i in range(torch.cuda.device_count()):
    print(" gpu", i, "peak GiB", round(torch.cuda.max_memory_allocated(i) / 2**30, 2))
