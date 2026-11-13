"""Analysis of Qwen 2B/4B/9B (1 draw, 100 tasks) and Gemma 26B (3 draws, 100 tasks): resolved rate plain vs Argus, bootstrap CIs over tasks."""
import hashlib, json, os, random, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L = lambda p: [json.loads(l) for l in open(os.path.join(ROOT, p), encoding="utf-8")] if os.path.exists(os.path.join(ROOT, p)) else []
IDS = json.load(open(os.path.join(ROOT, "data/gemini_sweep/task_ids_full.json")))["ids"]
sha = lambda s: hashlib.sha1(s.encode()).hexdigest()[:10]
G = {}
for f in ("results/grading/state_t1.jsonl", "results/grading/state.jsonl", "results/grading/state_new.jsonl"):
    for r in L(f):
        if r.get("hash") and r.get("resolved") is not None: G[(r["iid"], r["hash"])] = r["resolved"]
for f in ("data/probe_gemini/grading.jsonl", "data/gemini_sweep/grading.jsonl", "data/new_runs_grading.jsonl"):
    for r in L(f):
        if r.get("h") and r.get("resolved") is not None: G[(r["iid"], r["h"])] = r["resolved"]
def res(r):  # draw resolved?
    return r["status"] == "applied" and G.get((r["iid"], sha(r["diff"])), None) is True
def table(d, tag, arm):
    rows = L(f"{d}/{arm}_apply_{tag}.jsonl")
    ids = set(IDS); rows = [r for r in rows if r["iid"] in ids]
    per = {i: [] for i in IDS}
    for r in rows: per[r["iid"]].append(r)
    return per
def boot(vals, B=4000, seed=0):
    rnd = random.Random(seed); n = len(vals)
    xs = sorted(sum(vals[rnd.randrange(n)] for _ in range(n)) / n for _ in range(B))
    return xs[int(.025 * B)], xs[int(.975 * B)]
out = {}
for name, d, tags in (("qwen", "data/qwen_probe/apply_qwen", ["Qwen3.5-2B", "Qwen3.5-4B", "Qwen3.5-9B"]), ("gemma26", "data/gemma_sweep/apply_gemma26", ["gemma-4-26b-a4b-it"])):
    for tag in tags:
        P, A = table(d, tag, "plain"), table(d, tag, "argus")
        pt, at, dt, nap, naa, ndraw = [], [], [], 0, 0, 0
        for i in IDS:
            pr, ar = P[i], A[i]
            if not pr and not ar: continue
            pv = sum(res(r) for r in pr) / max(len(pr), 1); av = sum(res(r) for r in ar) / max(len(ar), 1)
            pt.append(pv); at.append(av); dt.append(av - pv)
            nap += sum(r["status"] == "applied" for r in pr); naa += sum(r["status"] == "applied" for r in ar); ndraw += len(pr)
        n = len(pt)
        o = dict(tasks=n, draws=ndraw, plain_applied_pct=round(100 * nap / ndraw, 1), argus_applied_pct=round(100 * naa / ndraw, 1),
                 plain_resolved_per100=round(100 * sum(pt) / n, 1), plain_ci=[round(100 * x, 1) for x in boot(pt)],
                 argus_resolved_per100=round(100 * sum(at) / n, 1), argus_ci=[round(100 * x, 1) for x in boot(at)],
                 delta_per100=round(100 * sum(dt) / n, 1), delta_ci=[round(100 * x, 1) for x in boot(dt)],
                 any_draw_plain=sum(1 for i in IDS if any(res(r) for r in P[i])), any_draw_argus=sum(1 for i in IDS if any(res(r) for r in A[i])))
        out[tag] = o; print(tag, json.dumps(o))
os.makedirs(os.path.join(ROOT, "results/analysis"), exist_ok=True)
json.dump(out, open(os.path.join(ROOT, "results/analysis/new_runs_summary.json"), "w"), indent=1)
