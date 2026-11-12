"""Build the prompt file for the Qwen size-ladder probe: same 30 tasks as the Gemini probe, same prompt p1, same 6,000-token context budget,
target file GIVEN. Output data/qwen_probe/prompts.jsonl (public issue text and public source only; safe to upload to a notebook).

  python -X utf8 scripts/build_qwen_prompts.py
"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from harness.context import fetch_source, build_file_context, ntok
from harness.prompts import SYSTEM, build_messages, prompt_hash, PROMPT_VERSION

TASKS = r"C:\coding\Argus-research-archive\data\swe_bench_verified_tasks.jsonl"
PROMPT_BUDGET = 6000
ids = json.load(open(os.path.join(ROOT, "data", "probe_gemini", "task_ids.json")))["ids"]
man = json.load(open(os.path.join(ROOT, "manifests", "pilot100_manifest.json"), encoding="utf-8"))
meta = {t["instance_id"]: t for t in man["primary"] + man["reserve"]}
full = {}
for l in open(TASKS, encoding="utf-8"):
    d = json.loads(l); full[d["instance_id"]] = d
out = open(os.path.join(ROOT, "data", "qwen_probe", "prompts.jsonl"), "w", encoding="utf-8")
for iid in ids:
    t = full[iid]; path = meta[iid]["gold_file"]
    src = fetch_source(t["repo"], t["base_commit"], path)
    code_budget = max(500, PROMPT_BUDGET - ntok(SYSTEM) - ntok(t["problem_statement"][:6000]) - 250)
    code, spans, info = build_file_context(t, src, code_budget)
    out.write(json.dumps(dict(iid=iid, target_file=path, messages=build_messages(t, path, code), ctx=info, prompt_hash=prompt_hash(), prompt_version=PROMPT_VERSION)) + "\n")
out.close()
print(len(ids), "prompts; prompt_hash", prompt_hash())
