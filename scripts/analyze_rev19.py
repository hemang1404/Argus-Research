"""Revision 19 analysis: arm P (previous attempt + result shown) vs F and R on the same tasks. Paired task bootstrap (5000, seed 20261113).
Infra losses (stop not in solved/regressed/continue/exhausted-like states) are counted unsolved; sensitivity drops tasks where P or the comparison arm had one."""
import json, os, random, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def load(d):
    p = os.path.join(ROOT, "data", d, "trajectories.jsonl")
    out = {}
    if os.path.exists(p):
        for l in open(p, encoding="utf-8"):
            r = json.loads(l); out[r["iid"]] = r  # last record wins
    return out
def boot(v, B=5000, seed=20261113):
    r = random.Random(seed); n = len(v)
    xs = sorted(sum(v[r.randrange(n)] for _ in range(n)) / n for _ in range(B))
    return round(100 * xs[int(.025 * B)], 1), round(100 * xs[int(.975 * B)], 1)
PRED = {("120b", "P-F"): (-5, 4), ("120b", "P-R"): (-4, 6), ("20b", "P-F"): (-5, 4), ("20b", "P-R"): (-2, 8), ("gemma", "P-F"): (-5, 5)}
SETS = {"120b": ("loop4", "loop2", "loop2"), "20b": ("loop4_20b", "loop2_20b", "loop2_20b"), "gemma": ("loop4_gemma26", "loop_f_gemma26", None)}
OUT = {}
for m, (pd, fd, rd) in SETS.items():
    P, F, R = load(pd), load(fd), load(rd) if rd else {}
    ids = sorted(set(P) & set(F) & (set(R) if rd else set(P)))
    print(f"\n=== {m}: {len(ids)} tasks (P {len(P)}, F {len(F)}" + (f", R {len(R)}" if rd else "") + ")")
    s = lambda D, a, i: float(D[i][a]["solved"])
    stops = {"P": collections.Counter(P[i]["P"]["stop"] for i in ids), "F": collections.Counter(F[i]["F"]["stop"] for i in ids)}
    print("  stops P:", dict(stops["P"])); print("  stops F:", dict(stops["F"]))
    bad = lambda D, a, i: D[i][a]["stop"] in ("grade_error", "api_error", "error")
    arms = [("P", P, "P"), ("F", F, "F")] + ([("R", R, "R")] if rd else [])
    for lab, D, a in arms:
        n = sum(s(D, a, i) for i in ids); c = sum((D[i][a].get("cost_usd") or 0) for i in ids)
        print(f"  {lab}: solved {int(n)}/{len(ids)} = {100*n/len(ids):.1f}%  cost ${c:.3f}" + (f"  per solve ${c/n:.4f}" if n and c else ""))
    comps = [("P-F", P, "P", F, "F")] + ([("P-R", P, "P", R, "R"), ("F-R", F, "F", R, "R")] if rd else [])
    for lab, D1, a1, D2, a2 in comps:
        d = [s(D1, a1, i) - s(D2, a2, i) for i in ids]; mu = round(100 * sum(d) / len(d), 1); ci = boot(d)
        keep = [i for i in ids if not bad(D1, a1, i) and not bad(D2, a2, i)]
        d2 = [s(D1, a1, i) - s(D2, a2, i) for i in keep]; mu2 = round(100 * sum(d2) / len(d2), 1)
        only1 = sum(x > 0 for x in d); only2 = sum(x < 0 for x in d)
        pr = PRED.get((m, lab)); tag = ""
        if pr: tag = f"  prediction [{pr[0]},{pr[1]}] -> {'inside' if pr[0] <= mu <= pr[1] else 'MISS'}"
        print(f"  {lab}: {mu:+.1f}  95% CI {ci}  ({only1} vs {only2} tasks){tag}  | without infra losses n={len(keep)}: {mu2:+.1f} CI {boot(d2)}")
        OUT[f"{m}:{lab}"] = dict(n=len(ids), diff=mu, ci=ci, only_first=only1, only_second=only2, without_losses=dict(n=len(keep), diff=mu2, ci=boot(d2)), pred=pr)
json.dump(OUT, open(os.path.join(ROOT, "results", "analysis", "rev19_results.json"), "w"), indent=1)
