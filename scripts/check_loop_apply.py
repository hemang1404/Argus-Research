"""Self-test: harness.argus_apply must reproduce the stored Revision 4 Argus-arm diffs exactly."""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from harness.argus_apply import apply_output

full = {}
for l in open(r"C:\coding\Argus-research-archive\data\swe_bench_verified_tasks.jsonl", encoding="utf-8"):
    d = json.loads(l); full[d["instance_id"]] = d
stored = {}
for tag in ("gpt-oss-20b", "gpt-oss-120b"):
    for l in open(os.path.join(ROOT, "data", "phase2_t1", f"argus_apply_{tag}.jsonl"), encoding="utf-8"):
        r = json.loads(l); stored[(r["iid"], r["model"], r["sample"])] = r
n = bad = 0
for l in open(os.path.join(ROOT, "data", "raw", "phase2_t1_clean.jsonl"), encoding="utf-8"):
    g = json.loads(l)
    t = full[g["iid"]]
    new = apply_output(t["repo"], t["base_commit"], g["target_file"], g.get("content"), g.get("finish"))
    old = stored[(g["iid"], g["model"], g["sample"])]
    n += 1
    if new["status"] != old["status"] or new.get("diff") != old.get("diff"):
        bad += 1
        print("MISMATCH", g["iid"], g["model"], g["sample"], old["status"], new["status"])
print(f"{n} outputs replayed, {bad} mismatches")
