"""Revision 18 analysis: matched fresh-draw replicates of R/F/P (rep1, rep2) + greedy (temp 0) F vs P, Gemini 3.1/3.5 flash-lite.
Paired task bootstrap (5000, seed 20261113). Per-task score of an arm = mean solved over its replicates. Nothing here changes any run."""
import json, os, random, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def load(d):
    p = os.path.join(ROOT, "data", d, "trajectories.jsonl")
    return {r["iid"]: r for r in map(json.loads, open(p, encoding="utf-8"))} if os.path.exists(p) else {}
def boot(v, B=5000, seed=20261113):
    r = random.Random(seed); n = len(v)
    xs = sorted(sum(v[r.randrange(n)] for _ in range(n)) / n for _ in range(B))
    return round(100 * xs[int(.025 * B)], 1), round(100 * xs[int(.975 * B)], 1)
PRED = {("gemini31", "P-R"): (3, 10), ("gemini35", "P-R"): (-3, 5), ("gemini31", "P-F"): (2, 10), ("gemini35", "P-F"): (-3, 5),
        ("gemini31", "F-R"): (-4, 4), ("gemini35", "F-R"): (-4, 4), ("gemini31", "Pg-Fg"): (2, 99), ("gemini35", "Pg-Fg"): (-3, 5)}
OUT = {}
for m in ("gemini31", "gemini35"):
    A = {"R": [load(f"loop_r_rep{k}_{m}") for k in (1, 2)], "F": [load(f"loop_f_rep{k}_{m}") for k in (1, 2)],
         "P": [load(f"loop_p_rep{k}_{m}") for k in (1, 2)], "Fg": [load(f"loop_f_t0_{m}")], "Pg": [load(f"loop_p_t0_{m}")]}
    ids = sorted(set.intersection(*[set(t) for v in A.values() for t in v]))
    def sc(a, i): return sum(float(t[i]["F"]["solved"]) for t in A[a]) / len(A[a])
    def cost(a):
        return None
    print(f"\n=== {m}: {len(ids)} tasks with every arm complete")
    res = {}
    for a in A:
        v = [sc(a, i) for i in ids]; res[a] = round(100 * sum(v) / len(v), 1)
        reps = [round(100 * sum(float(t[i]["F"]["solved"]) for i in ids) / len(ids), 1) for t in A[a]]
        print(f"  {a:3s} mean {res[a]:5.1f}  per-replicate {reps}")
    for lab, x, y in (("P-R", "P", "R"), ("P-F", "P", "F"), ("F-R", "F", "R"), ("Pg-Fg", "Pg", "Fg")):
        d = [sc(x, i) - sc(y, i) for i in ids]; mu = round(100 * sum(d) / len(d), 1); ci = boot(d)
        lo, hi = PRED[(m, lab)]; inside = lo <= mu <= hi
        print(f"  {lab:6s} {mu:+5.1f}  95% CI {ci}  prediction [{lo},{hi if hi < 99 else 'inf'}] -> {'inside' if inside else 'MISS'}  {'(CI excludes 0)' if ci[0] > 0 or ci[1] < 0 else ''}")
        OUT[f"{m}:{lab}"] = dict(diff=mu, ci=ci, pred=[lo, hi], inside=inside)
    # per-replicate noise: difference between the two replicates of the same arm
    for a in ("R", "F", "P"):
        d = [float(A[a][0][i]["F"]["solved"]) - float(A[a][1][i]["F"]["solved"]) for i in ids]
        print(f"  replicate-to-replicate noise {a}: rep1-rep2 {100*sum(d)/len(d):+.1f} (tasks that flip: {sum(x != 0 for x in d)})")
    st = {a: collections.Counter(t[i]["F"]["stop"] for t in A[a] for i in ids) for a in A}
    print("  stops:", {a: dict(c) for a, c in st.items()})
json.dump(OUT, open(os.path.join(ROOT, "results", "analysis", "rev18_results.json"), "w"), indent=1)
