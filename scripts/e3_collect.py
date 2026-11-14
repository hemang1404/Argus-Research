import hashlib, json, os, collections
ROOT = r"C:\coding\Argus-pilot50"
L = lambda p: [json.loads(l) for l in open(os.path.join(ROOT, p), encoding="utf-8")] if os.path.exists(os.path.join(ROOT, p)) else []
sha = lambda s: hashlib.sha1(s.encode()).hexdigest()[:10]
G = {}
for f in ("results/grading/state_t1/state/state_new.jsonl","results/grading/state_t1.jsonl","results/grading/state.jsonl","results/grading/state_new.jsonl","data/probe_gemini/grading.jsonl","data/gemini_sweep/grading.jsonl","data/new_runs_grading.jsonl"):
    for r in L(f):
        h = r.get("hash") or r.get("h")
        if h and r.get("resolved") is not None: G[(r["iid"], h)] = r
gold = {}
for l in open(r"C:\coding\Argus-research-archive\data\swe_bench_verified_tasks.jsonl", encoding="utf-8"):
    r = json.loads(l); gold[r["instance_id"]] = r["gold_patch"]
SRCS = {"gpt-oss-20b": "data/phase2_t1/{a}_apply_gpt-oss-20b.jsonl", "gpt-oss-120b": "data/phase2_t1/{a}_apply_gpt-oss-120b.jsonl",
        "gemma26": "data/gemma_sweep/apply_gemma26/{a}_apply_gemma-4-26b-a4b-it.jsonl"}
out = []
for m, tpl in SRCS.items():
    P = {(r["iid"], r.get("sample", 0)): r for r in L(tpl.format(a="plain"))}
    A = L(tpl.format(a="argus"))
    for r in A:
        if r["status"] != "applied": continue
        g = G.get((r["iid"], sha(r["diff"])))
        if not g or not g["resolved"]: continue
        p = P.get((r["iid"], r.get("sample", 0)))
        out.append(dict(model=m, iid=r["iid"], sample=r.get("sample", 0), max_tier=r.get("max_tier"), rescued=not (p and p["status"] == "applied"),
                        same_as_plain=bool(p and p["status"]=="applied" and p["diff"]==r["diff"]), diff=r["diff"], gold=gold[r["iid"]]))
print(len(out), collections.Counter((o["model"], o["rescued"]) for o in out))
print(len({(o["model"], o["iid"]) for o in out}), "unique model-task")
print(collections.Counter(o["max_tier"] for o in out if o["rescued"]))
json.dump(out, open(os.path.join(ROOT, "results/analysis/e3_resolved.json"), "w"))
