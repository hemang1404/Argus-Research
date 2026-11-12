"""Kaggle smoke test: can this notebook load a Hugging Face model and answer one prompt? No keys needed (open weights).

Paste into a Kaggle notebook cell (Settings: Accelerator = GPU T4 x2, Internet = On). Set MODEL_ID to the exact Hugging Face repo id.
Prints GPUs, load time, one short answer, tokens/second and GPU memory. Run once per model (2B first).
"""
import subprocess, sys
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "transformers", "accelerate"], check=False)

import time, torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_ID = "Qwen/Qwen3.5-2B"   # <- set to the exact repo id from huggingface.co/Qwen
DTYPE = torch.float16          # T4 has no bf16

print("torch", torch.__version__, "cuda", torch.cuda.is_available(), "gpus", torch.cuda.device_count())
for i in range(torch.cuda.device_count()):
    p = torch.cuda.get_device_properties(i)
    print(" gpu", i, p.name, round(p.total_memory / 2**30, 1), "GiB")

t0 = time.time()
tok = AutoTokenizer.from_pretrained(MODEL_ID)
try:
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, torch_dtype=DTYPE, device_map="auto")
except Exception as e:  # these Qwen3.5 checkpoints are listed as image-text-to-text
    print("AutoModelForCausalLM failed:", repr(e)[:300], "-> trying AutoModelForImageTextToText")
    from transformers import AutoModelForImageTextToText
    model = AutoModelForImageTextToText.from_pretrained(MODEL_ID, torch_dtype=DTYPE, device_map="auto")
print("loaded in", round(time.time() - t0, 1), "s; transformers", __import__("transformers").__version__)

messages = [{"role": "user", "content": "Write a Python function add(a, b) that returns a + b. Reply with only the code."}]
try:
    text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
except TypeError:
    text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
inputs = tok(text, return_tensors="pt").to(model.device)
t0 = time.time()
out = model.generate(**inputs, max_new_tokens=80, do_sample=True, temperature=1.0)
dt = time.time() - t0
new = out[0][inputs["input_ids"].shape[1]:]
print("ANSWER:\n", tok.decode(new, skip_special_tokens=True))
print("new tokens", len(new), "seconds", round(dt, 1), "tok/s", round(len(new) / dt, 1))
for i in range(torch.cuda.device_count()):
    print(" gpu", i, "memory used GiB", round(torch.cuda.memory_allocated(i) / 2**30, 2))
