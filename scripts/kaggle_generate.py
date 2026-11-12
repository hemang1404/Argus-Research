"""Kaggle generation for the Qwen size-ladder probe (Revision 10). Reads prompts_remaining.jsonl from the attached dataset, answers each prompt ONCE per model,
one prompt at a time, appends to /kaggle/working/outputs_<tag>.jsonl. Run with Save & Run All (Commit) so the outputs are kept.
Settings: temperature 1.0, top_p 1.0, top_k 0, thinking OFF, max_new_tokens 4000, fp16 on T4. QUANT nf4 = 4-bit (quantization check only).
Memory handling (added after the first 9B attempt ran out of memory on prompts of 6k tokens with device_map="auto"): weights are split evenly
over both GPUs (device_map="balanced"); a prompt that still runs out of memory is retried once with chunked prefill (1,024 tokens per chunk) and
the record notes prefill_chunk; records that failed are not treated as done.
"""
import os
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
import subprocess, sys
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "transformers", "accelerate", "flash-linear-attention", "bitsandbytes"], check=False)

import gc, glob, json, time, torch
import transformers
from transformers import AutoModelForCausalLM, AutoTokenizer

RUNS = [("Qwen/Qwen3.5-2B", "none"), ("Qwen/Qwen3.5-4B", "none"), ("Qwen/Qwen3.5-9B", "none")]   # Revision 11: remaining 70 tasks, one draw each
MAX_NEW = 4000
cands = glob.glob("/kaggle/input/**/prompts_remaining.jsonl", recursive=True) + glob.glob("prompts_remaining.jsonl") + glob.glob("/kaggle/working/prompts_remaining.jsonl")
assert cands, "prompts_remaining.jsonl not found: attach it as a Kaggle dataset or put it in /kaggle/working"
PROMPTS = [json.loads(l) for l in open(cands[0], encoding="utf-8")]


def run_model(MODEL_ID, QUANT):
    TAG = MODEL_ID.split("/")[-1] + ("-nf4" if QUANT == "nf4" else "")
    OUT = f"/kaggle/working/outputs_{TAG}.jsonl"
    done = set()
    if os.path.exists(OUT):
        for l in open(OUT, encoding="utf-8"):
            r = json.loads(l)
            if r.get("content") is not None:
                done.add(r["iid"])
    tok = AutoTokenizer.from_pretrained(MODEL_ID)
    kw = dict(device_map="balanced")
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
    print("model", MODEL_ID, "quant", QUANT, "transformers", transformers.__version__, "torch", torch.__version__, "todo", len(PROMPTS) - len(done),
          "gpu mem GiB", [round(torch.cuda.memory_allocated(i) / 2**30, 1) for i in range(torch.cuda.device_count())], flush=True)

    def gen(inp, **extra):
        with torch.no_grad():
            return model.generate(**inp, max_new_tokens=MAX_NEW, do_sample=True, temperature=1.0, top_p=1.0, top_k=0, **extra)

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
                   target_file=p["target_file"], ctx=p["ctx"], prompt_tokens=int(inp["input_ids"].shape[1]), max_new_tokens=MAX_NEW, prefill_chunk=None)
        out = None
        try:
            out = gen(inp)
        except torch.cuda.OutOfMemoryError:
            gc.collect(); torch.cuda.empty_cache()
            try:
                out = gen(inp, prefill_chunk_size=1024)
                rec["prefill_chunk"] = 1024
            except Exception as e:
                rec.update(error="OOM_after_chunked_prefill: " + repr(e)[:200])
                gc.collect(); torch.cuda.empty_cache()
        if out is not None:
            new = out[0][inp["input_ids"].shape[1]:]
            rec.update(content=tok.decode(new, skip_special_tokens=True), new_tokens=int(len(new)), finish="length" if len(new) >= MAX_NEW else "stop")
        else:
            rec.update(content=None)
        rec["seconds"] = round(time.time() - t0, 1)
        open(OUT, "a", encoding="utf-8").write(json.dumps(rec) + "\n")
        print(f"[{TAG} {k + 1}/{len(PROMPTS)}] {p['iid']} prompt={rec['prompt_tokens']} new={rec.get('new_tokens')} {rec['seconds']}s "
              f"{rec.get('finish') or rec.get('error')} chunk={rec['prefill_chunk']}", flush=True)
    del model, tok
    gc.collect(); torch.cuda.empty_cache()
    return OUT


outs = [run_model(m, q) for m, q in RUNS]
print("done ->", outs)
print("files in /kaggle/working:", os.listdir("/kaggle/working"))
