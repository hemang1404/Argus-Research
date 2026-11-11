"""Revision 6 analysis (pre-registered in PILOT50_PROTOCOL.md): four models x 100 tasks x 3 draws, plain vs Argus apply.

Models: gpt-oss-20b, gpt-oss-120b (Revision 4 draws, replacement task from phase2_t1_repl), gemini-3.1-flash-lite, gemini-3.5-flash-lite.
Task set: data/gemini_sweep/task_ids_full.json (99 valid + astropy__astropy-13579).

  python -X utf8 scripts/analyze_sweep.py [--allow-partial]   -> results/analysis/sweep_summary.json

(1) resolve rate per draw and mean, task-clustered bootstrap CI; (2) Argus effect (paired), rescued draws and pass rate;
(3) failure funnel; (4) per-task success probability, pass@3, Gemini-only vs gpt-oss-only tasks;
(5) cost per solve, oracle router and verifier cascade (replays; Docker result is a perfect verifier, so upper bounds).
"""
import argparse, collections, hashlib, json, os, random, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument("--allow-partial", action="store_true", help="treat ungraded applied patches as unresolved (smoke test only)")
ap.add_argument("--boot", type=int, default=5000)
args = ap.parse_args()

IDS = json.load(open(os.path.join(ROOT, "data", "gemini_sweep", "task_ids_full.json")))["ids"]
IDSET = set(IDS)
MODELS = ["gpt-oss-20b", "gpt-oss-120b", "gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]
GPT, GEM = MODELS[:2], MODELS[2:]
PRICE = {"gpt-oss-20b": (0.075, 0.30), "gpt-oss-120b": (0.15, 0.60), "gemini-3.1-flash-lite": (0.25, 1.50), "gemini-3.5-flash-lite": (0.30, 2.50)}
K = 3


def load(path):
    return [json.loads(l) for l in open(path, encoding="utf-8")] if os.path.exists(path) else []


def sha(s):
    return hashlib.sha1(s.encode()).hexdigest()[:10]


# ---- grades: (iid, patch hash) -> resolved
res = {}
for f in ("state_t1.jsonl", "state.jsonl", "state_new.jsonl"):
    for r in load(os.path.join(ROOT, "results", "grading", f)):
        if r.get("hash") and r.get("resolved") is not None:
            res[(r["iid"], r["hash"])] = r["resolved"]
for f in (os.path.join(ROOT, "data", "probe_gemini", "grading.jsonl"), os.path.join(ROOT, "data", "gemini_sweep", "grading.jsonl")):
    for r in load(f):
        if r.get("h") and r.get("resolved") is not None:
            res[(r["iid"], r["h"])] = r["resolved"]

# ---- draws: D[model][(iid, k)] = dict(plain, argus, cost, finish)
D = {m: {} for m in MODELS}
for m in GPT:
    sources = [(os.path.join(ROOT, "data", "raw", "phase2_t1_clean.jsonl"), os.path.join(ROOT, "data", "phase2_t1")),
               (os.path.join(ROOT, "data", "raw", "phase2_t1_repl.jsonl"), os.path.join(ROOT, "data", "phase2_t1_repl"))]
    for raw, ad in sources:
        pl = {(r["iid"], r["sample"]): r for r in load(os.path.join(ad, f"plain_apply_{m}.jsonl"))}
        ar = {(r["iid"], r["sample"]): r for r in load(os.path.join(ad, f"argus_apply_{m}.jsonl"))}
        for g in load(raw):
            if g["model"].endswith(m) and g["iid"] in IDSET and g.get("http") == 200:
                k = (g["iid"], g["sample"])
                pin, pout = PRICE[m]
                cost = ((g.get("prompt_tokens") or 0) * pin + (g.get("completion_tokens") or 0) * pout) / 1e6
                D[m][k] = dict(plain=pl[k], argus=ar[k], cost=cost, finish=g.get("finish"), content=g.get("content"))
for m in GEM:
    pl = {(r["iid"], r["sample"]): r for r in load(os.path.join(ROOT, "data", "gemini_sweep", "apply", f"plain_apply_{m}.jsonl"))}
    ar = {(r["iid"], r["sample"]): r for r in load(os.path.join(ROOT, "data", "gemini_sweep", "apply", f"argus_apply_{m}.jsonl"))}
    for g in load(os.path.join(ROOT, "data", "gemini_sweep", "raw.jsonl")):
        if g["model"].endswith(m) and g.get("http") == 200:
            k = (g["iid"], g["sample"])
            u = g["usage_raw"]; pin, pout = PRICE[m]
            cost = (u["prompt_tokens"] * pin + (u["total_tokens"] - u["prompt_tokens"]) * pout) / 1e6
            D[m][k] = dict(plain=pl[k], argus=ar[k], cost=cost, finish=g.get("finish"), content=g.get("content"))
for m in MODELS:
    missing = [(i, k) for i in IDS for k in range(K) if (i, k) not in D[m]]
    assert not missing, (m, "missing draws", missing[:5], len(missing))

ungraded = set()


def solved(rec):
    if rec["status"] != "applied":
        return 0
    key = (rec["iid"], sha(rec["diff"]))
    if key not in res:
        ungraded.add(key)
        return 0
    return 1 if res[key] else 0


S = {m: {a: {(i, k): solved(D[m][(i, k)][a]) for i in IDS for k in range(K)} for a in ("plain", "argus")} for m in MODELS}
if ungraded and not args.allow_partial:
    sys.exit(f"{len(ungraded)} applied patches are not graded yet; finish grading or use --allow-partial")


def count(m, a, tasks=IDS):
    return [sum(S[m][a][(i, k)] for i in tasks) for k in range(K)]


def mean_solves(m, a, tasks):  # mean over draws of #resolved tasks
    return sum(S[m][a][(i, k)] for i in tasks for k in range(K)) / K


rng = random.Random(20261112)
BOOT = [[rng.choice(IDS) for _ in IDS] for _ in range(args.boot)]


def ci(fn):
    vals = sorted(fn(b) for b in BOOT)
    return round(vals[int(0.025 * len(vals))], 2), round(vals[int(0.975 * len(vals)) - 1], 2)


out = dict(n_tasks=len(IDS), draws=K, ungraded_applied_patches=len(ungraded), bootstrap=dict(n=args.boot, seed=20261112, unit="task"))

# (1) resolve rate and (2) Argus effect
out["resolved"] = {}
for m in MODELS:
    e = {}
    for a in ("plain", "argus"):
        e[a] = dict(per_draw=count(m, a), mean=round(mean_solves(m, a, IDS), 2), ci95=ci(lambda b, m=m, a=a: mean_solves(m, a, b)))
    e["argus_minus_plain"] = dict(mean=round(mean_solves(m, "argus", IDS) - mean_solves(m, "plain", IDS), 2),
                                  ci95=ci(lambda b, m=m: mean_solves(m, "argus", b) - mean_solves(m, "plain", b)))
    resc = [(i, k) for i in IDS for k in range(K) if D[m][(i, k)]["plain"]["status"] != "applied" and D[m][(i, k)]["argus"]["status"] == "applied"]
    lost = [(i, k) for i in IDS for k in range(K) if D[m][(i, k)]["plain"]["status"] == "applied" and D[m][(i, k)]["argus"]["status"] != "applied"]
    e["rescued_draws"] = len(resc)
    e["rescued_resolved"] = sum(S[m]["argus"][x] for x in resc)
    e["rescued_pass_rate"] = round(e["rescued_resolved"] / len(resc), 3) if resc else None
    e["lost_to_refusal"] = len(lost)
    e["lost_resolved"] = sum(S[m]["plain"][x] for x in lost)
    ap_ = [x for x in S[m]["argus"] if D[m][x]["argus"]["status"] == "applied"]
    e["argus_pass_given_applied"] = round(sum(S[m]["argus"][x] for x in ap_) / len(ap_), 3) if ap_ else None
    out["resolved"][m] = e

# (3) failure funnel (per arm, over all 300 draws)
out["funnel"] = {}
for m in MODELS:
    out["funnel"][m] = {}
    for a in ("plain", "argus"):
        c = collections.Counter()
        for i in IDS:
            for k in range(K):
                r = D[m][(i, k)][a]
                if r["status"] == "applied":
                    c["resolved" if S[m][a][(i, k)] else "applied_but_wrong"] += 1
                elif r["status"] in ("empty_output", "truncated_no_output"):
                    c["empty_or_truncated"] += 1
                elif r["status"] == "no_blocks":
                    c["no_blocks"] += 1
                else:
                    c["edit_not_applied:" + r["status"]] += 1
        out["funnel"][m][a] = dict(c)

# (4) per-task success probability, pass@3 (Argus arm), Gemini-only vs gpt-oss-only tasks
p = {m: {i: sum(S[m]["argus"][(i, k)] for k in range(K)) / K for i in IDS} for m in MODELS}
out["per_task"] = {}
for m in MODELS:
    v = [p[m][i] for i in IDS]
    out["per_task"][m] = dict(pass_at_3=sum(1 for x in v if x > 0), always=sum(1 for x in v if x == 1), sometimes=sum(1 for x in v if 0 < x < 1),
                              never=sum(1 for x in v if x == 0))
any_g = {i for i in IDS if any(p[m][i] > 0 for m in GEM)}
any_o = {i for i in IDS if any(p[m][i] > 0 for m in GPT)}
out["tasks_gemini_only"] = sorted(any_g - any_o)
out["tasks_gptoss_only"] = sorted(any_o - any_g)
out["tasks_both"] = len(any_g & any_o)
out["tasks_neither"] = len(set(IDS) - any_g - any_o)
out["pairwise_only"] = {f"{a}_not_{b}": sum(1 for i in IDS if p[a][i] > 0 and p[b][i] == 0) for a in MODELS for b in MODELS if a != b}

# (5) cost per solve, oracle router, verifier cascade (Argus arm; per draw index k, then mean over k)
mean_cost = {m: sum(D[m][(i, k)]["cost"] for i in IDS for k in range(K)) / K for m in MODELS}  # $ per full 100-task pass
out["cost"] = {m: dict(usd_per_100_task_pass=round(mean_cost[m], 4), mean_solves=out["resolved"][m]["argus"]["mean"],
                       usd_per_solve=round(mean_cost[m] / out["resolved"][m]["argus"]["mean"], 5) if out["resolved"][m]["argus"]["mean"] else None,
                       mean_truncated_draws=round(sum(1 for i in IDS for k in range(K) if D[m][(i, k)]["finish"] == "length") / K, 1)) for m in MODELS}
order = sorted(MODELS, key=lambda m: mean_cost[m])
routers = []
for k in range(K):
    # oracle: cheapest model whose draw k resolved; unsolved tasks cost nothing (perfect knowledge)
    n = c = 0
    for i in IDS:
        ok = [m for m in MODELS if S[m]["argus"][(i, k)]]
        if ok:
            m = min(ok, key=lambda x: D[x][(i, k)]["cost"]); n += 1; c += D[m][(i, k)]["cost"]
    # cascade: cheapest-first order by mean cost, stop at first resolved (Docker = perfect verifier); pay for every attempt
    n2 = c2 = 0
    for i in IDS:
        for m in order:
            c2 += D[m][(i, k)]["cost"]
            if S[m]["argus"][(i, k)]:
                n2 += 1; break
    # 120B-only reference and best-single reference
    routers.append(dict(oracle_solved=n, oracle_usd=c, cascade_solved=n2, cascade_usd=c2))
out["routing_replay"] = dict(cascade_order=order, per_draw=routers,
                             mean=dict((key, round(sum(r[key] for r in routers) / K, 4)) for key in routers[0]),
                             note="Docker result as perfect verifier; oracle skips tasks no model solves; upper bounds, not deployable policies")
# POST HOC (not pre-registered): cascades over every subset of models, cheapest-first by mean cost, draw index k, mean over k
import itertools
sub = {}
for r in range(1, len(MODELS) + 1):
    for combo in itertools.combinations(order, r):
        ns, cs = [], []
        for k in range(K):
            n3 = c3 = 0
            for i in IDS:
                for m in combo:
                    c3 += D[m][(i, k)]["cost"]
                    if S[m]["argus"][(i, k)]:
                        n3 += 1; break
            ns.append(n3); cs.append(c3)
        sub["->".join(combo)] = dict(solved=round(sum(ns) / K, 2), usd=round(sum(cs) / K, 4))
out["cascade_subsets_post_hoc"] = sub
# 3-draw budget baseline: best single model with all 3 draws, pass@3 cost
out["best_of_3_single_model"] = {m: dict(solved_any_of_3=out["per_task"][m]["pass_at_3"], usd=round(mean_cost[m] * K, 4)) for m in MODELS}

os.makedirs(os.path.join(ROOT, "results", "analysis"), exist_ok=True)
json.dump(out, open(os.path.join(ROOT, "results", "analysis", "sweep_summary.json"), "w", encoding="utf-8"), indent=1)
print(json.dumps(out, indent=1))
