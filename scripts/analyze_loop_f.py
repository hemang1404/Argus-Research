"""F (test feedback) vs R (re-draw) loops, <=3 attempts; paired task bootstrap. Plus single-shot plain/Argus."""
import hashlib, json, os, random, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L = lambda p: [json.loads(l) for l in open(os.path.join(ROOT, p), encoding="utf-8")] if os.path.exists(os.path.join(ROOT, p)) else []
IDS = json.load(open(os.path.join(ROOT, "data/gemini_sweep/task_ids_full.json")))["ids"]
sha = lambda s: hashlib.sha1(s.encode()).hexdigest()[:10]
G = {}
for f in ("results/grading/state_t1/state/state_new.jsonl", "results/grading/state_t1.jsonl", "results/grading/state.jsonl", "results/grading/state_new.jsonl",
          "data/probe_gemini/grading.jsonl", "data/gemini_sweep/grading.jsonl", "data/new_runs_grading.jsonl"):
    for r in L(f):
        h = r.get("hash") or r.get("h")
        if h and r.get("resolved") is not None:
            G[(r["iid"], h)] = r
def grade(iid, diff):
    return G.get((iid, sha(diff)))
def acc(g): return g is not None and g.get("f2p_fail", 1) == 0 and g.get("f2p_pass", 0) > 0 or (g is not None and g["resolved"])
def boot(v, B=5000, seed=0):
    r = random.Random(seed); n = len(v)
    xs = sorted(sum(v[r.randrange(n)] for _ in range(n)) / n for _ in range(B))
    return round(100 * xs[int(.025 * B)], 1), round(100 * xs[int(.975 * B)], 1)
def draws(path, arm, tag):
    per = collections.defaultdict(dict)
    for r in L(f"{path}/{arm}_apply_{tag}.jsonl"):
        per[r["iid"]][r["sample"]] = r
    return per
CFG = {"qwen38": ("data/qwen38/apply_qwen38", "qwen3.8-27b"), "gemma26": ("data/gemma_sweep/apply_gemma26", "gemma-4-26b-a4b-it")}
for m, (path, tag) in CFG.items():
    P, A = draws(path, "plain", tag), draws(path, "argus", tag)
    T = {r["iid"]: r for r in L(f"data/loop_f_{m}/trajectories.jsonl")}
    ids = [i for i in IDS if i in T]
    def ok(arm, i, s):
        r = arm[i].get(s); return bool(r and r["status"] == "applied" and (g := grade(i, r["diff"])) and g["resolved"])
    out = collections.OrderedDict()
    rows = []
    for i in ids:
        # R: first accepted of draws 0..2 (Argus apply), solved iff that patch resolved
        rsolved, rn = False, 0
        for s in range(3):
            r = A[i].get(s)
            if not r: continue
            rn += 1
            g = grade(i, r["diff"]) if r["status"] == "applied" else None
            if g and g.get("f2p_fail", 1) == 0 and g.get("applied", True):
                rsolved = bool(g["resolved"]); break
        F = T[i]["F"]
        rows.append(dict(i=i, p0=ok(P, i, 0), a0=ok(A, i, 0), plain3=sum(ok(P, i, s) for s in range(3)) / 3, arg3=sum(ok(A, i, s) for s in range(3)) / 3,
                         R=rsolved, F=bool(F["solved"]), stop=F["stop"], n=F["n"], apierr=any(a.get("state") == "api_error" for a in F["attempts"])))
    def agg(rs, k): return 100 * sum(float(r[k]) for r in rs) / len(rs)
    for label, rs in (("all", rows), ("excl api_error tasks", [r for r in rows if not r["apierr"]])):
        n = len(rs)
        print(f"\n=== {m} [{label}] tasks={n}")
        for k, nm in (("plain3", "plain single-shot (mean of 3 draws)"), ("arg3", "Argus-apply single-shot (mean of 3)"), ("R", "R loop <=3"), ("F", "F loop <=3")):
            print(f"  {nm:40s} {agg(rs,k):5.1f}/100  CI{boot([float(r[k]) for r in rs])}")
        d = [float(r["F"]) - float(r["R"]) for r in rs]
        print(f"  F-R = {100*sum(d)/n:+.1f}  CI{boot(d)}   F-only {sum(x>0 for x in d)}  R-only {sum(x<0 for x in d)}")
    print("  F stop states:", dict(collections.Counter(r["stop"] for r in rows)))
    resc = collections.Counter()
    for i in ids:
        at = T[i]["F"]["attempts"]
        if T[i]["F"]["solved"] and len(at) > 1: resc[len(at)] += 1
    print("  F solved at attempt:", {1: sum(1 for i in ids if T[i]["F"]["solved"] and len(T[i]["F"]["attempts"]) == 1), **dict(resc)})
