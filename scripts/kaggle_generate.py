"""Kaggle generation for the Qwen size-ladder probe. Reads prompts.jsonl (upload it as a Kaggle dataset or into the working directory),
answers each prompt ONCE with one model, one prompt at a time, and appends to outputs_<tag>.jsonl (resumable). No keys needed.

Settings (fixed in PILOT50_PROTOCOL.md, Revision 10): temperature 1.0, top_p 1.0, top_k 0 (pure sampling, like the API runs), thinking OFF,
max_new_tokens 4000, fp16 on T4 (no bf16). QUANT = "none" or "nf4" (bitsandbytes 4-bit, used only for the quantization check).
Edit MODEL_ID and QUANT, restart the session between models, run the cell. Download outputs_<tag>.jsonl afterwards.
"""
import subprocess, sys
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "transformers", "accelerate", "flash-linear-attention", "bitsandbytes"], check=False)

import glob, json, os, time, torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_ID = "Qwen/Qwen3.5-2B"   # then Qwen/Qwen3.5-4B, Qwen/Qwen3.5-9B
QUANT = "none"                 # "none" (fp16) or "nf4" (4-bit, quantization check on the 4B only)
MAX_NEW = 4000
cands = glob.glob("/kaggle/input/**/prompts.jsonl", recursive=True) + glob.glob("prompts.jsonl") + glob.glob("/kaggle/working/prompts.jsonl")
assert cands, "prompts.jsonl not found: upload it as a Kaggle dataset or into /kaggle/working"
PROMPTS = [json.loads(l) for l in open(cands[0], encoding="utf-8")]
TAG = MODEL_ID.split("/")[-1] + ("-nf4" if QUANT == "nf4" else "")
OUT = f"/kaggle/working/outputs_{TAG}.jsonl"
done = set()
if os.path.exists(OUT):
    done = {json.loads(l)["iid"] for l in open(OUT, encoding="utf-8")}

tok = AutoTokenizer.from_pretrained(MODEL_ID)
kw = dict(device_map="auto")
if QUANT == "nf4":
    from transformers import BitsAndBytesConfig
    kw["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.float16)
else:
    kw["dtype"] = torch.float16
try:
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, **kw)
except Exception as e:
    print("AutoModelForCausalLM failed:", repr(e)[:300])
    from transformers import AutoModelForImageTextToText
    model = AutoModelForImageTextToText.from_pretrained(MODEL_ID, **kw)
import transformers
print("model", MODEL_ID, "quant", QUANT, "transformers", transformers.__version__, "torch", torch.__version__, "todo", len(PROMPTS) - len(done), flush=True)

for k, p in enumerate(PROMPTS):
    if p["iid"] in done:
        continue
    try:
        text = tok.apply_chat_template(p["messages"], tokenize=False, add_generation_prompt=True, enable_thinking=False)
    except TypeError:
        text = tok.apply_chat_template(p["messages"], tokenize=False, add_generation_prompt=True)
    inp = tok(text, return_tensors="pt").to(model.device)
    t0 = time.time()
    rec = dict(iid=p["iid"], model=MODEL_ID, quant=QUANT, temperature=1.0, top_p=1.0, top_k=0, thinking=False, prompt_hash=p["prompt_hash"],
               target_file=p["target_file"], ctx=p["ctx"], prompt_tokens=int(inp["input_ids"].shape[1]), max_new_tokens=MAX_NEW)
    try:
        with torch.no_grad():
            out = model.generate(**inp, max_new_tokens=MAX_NEW, do_sample=True, temperature=1.0, top_p=1.0, top_k=0)
        new = out[0][inp["input_ids"].shape[1]:]
        rec.update(content=tok.decode(new, skip_special_tokens=True), new_tokens=int(len(new)),
                   finish="length" if len(new) >= MAX_NEW else "stop", seconds=round(time.time() - t0, 1))
    except torch.cuda.OutOfMemoryError as e:
        rec.update(content=None, error="OOM", seconds=round(time.time() - t0, 1))
        torch.cuda.empty_cache()
    open(OUT, "a", encoding="utf-8").write(json.dumps(rec) + "\n")
    print(f"[{k + 1}/{len(PROMPTS)}] {p['iid']} prompt={rec['prompt_tokens']} new={rec.get('new_tokens')} {rec['seconds']}s {rec.get('finish') or rec.get('error')}", flush=True)
print("done ->", OUT)
