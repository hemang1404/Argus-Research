"""Revision 21 analysis (LiveCodeBench test6, 175 post-cutoff problems): one-shot, R, F, P per model; paired task bootstrap (5,000, seed 20261113); predictions from PILOT50_PROTOCOL.md.
  python -X utf8 scripts/analyze_lcb.py     (works on partial data: reports n tasks recorded per model)
Infrastructure losses (api_error attempts) count as unsolved; a without-losses sensitivity drops tasks with an api_error in either compared arm."""
import json, os, random, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = {"gpt-oss-20b": "lcb_20b", "gpt-oss-120b": "lcb_120b", "gemma-26b": "lcb_gemma26"}
PRED_ONE = {"gpt-oss-20b": (35, 70), "gpt-oss-120b": (35, 70), "gemma-26b": (20, 55)}
PRED_FR = {"gpt-oss-20b": (-3, 10), "gpt-oss-120b": (-3, 8)}
PRED_PF = {"gpt-oss-20b": (-6, 6), "gpt-oss-120b": (-6, 6), "gemma-26b": (-6, 6)}


def boot(v, B=5000, seed=20261113):
    r = random.Random(seed)
    n = len(v)
    xs = sorted(sum(v[r.randrange(n)] for _ in range(n)) / n for _ in range(B))
    return round(100 * xs[int(.025 * B)], 1), round(100 * xs[int(.975 * B)], 1)


def load(d):
    p = os.path.join(ROOT, "data", d, "trajectories.jsonl")
    out = {}
    if os.path.exists(p):
        for l in open(p, encoding="utf-8"):
            r = json.loads(l)
            out[r["iid"]] = r
    return out


OUT = {}
for m, d in MODELS.items():
    rows = load(d)
    if not rows:
        print(f"\n=== {m}: no data")
        continue
    ids = sorted(rows)
    n = len(ids)
    print(f"\n=== {m}: {n} of 175 tasks recorded")
    one = [float(rows[i]["ONE"]["solved"]) for i in ids]
    lo, hi = PRED_ONE[m]
    mu = 100 * sum(one) / n
    print(f"  one-shot solved {sum(one):.0f}/{n} = {mu:.1f}%  prediction [{lo},{hi}] -> {'inside' if lo <= mu <= hi else 'MISS'}")
    res = {"n": n, "one_shot": round(mu, 1)}
    for a in "RFP":
        k = sum(rows[i][a]["solved"] for i in ids)
        c = sum(rows[i][a]["cost_usd"] for i in ids)
        print(f"  {a}: solved {k}/{n} = {100*k/n:.1f}%  cost ${c:.3f}" + (f"  per solve ${c/k:.4f}" if k and c else ""))
        res[a] = round(100 * k / n, 1)
    bad = lambda i, a: any(t["state"] == "api_error" for t in rows[i][a]["attempts"])
    for lab, x, y, pr in (("F-R", "F", "R", PRED_FR.get(m)), ("P-R", "P", "R", None), ("P-F", "P", "F", PRED_PF[m])):
        d_ = [float(rows[i][x]["solved"]) - float(rows[i][y]["solved"]) for i in ids]
        mu = round(100 * sum(d_) / n, 1)
        keep = [i for i in ids if not bad(i, x) and not bad(i, y)]
        d2 = [float(rows[i][x]["solved"]) - float(rows[i][y]["solved"]) for i in keep]
        tag = f"  prediction [{pr[0]},{pr[1]}] -> {'inside' if pr[0] <= mu <= pr[1] else 'MISS'}" if pr else ""
        print(f"  {lab}: {mu:+.1f}  95% CI {boot(d_)}  ({sum(v > 0 for v in d_)} vs {sum(v < 0 for v in d_)} tasks){tag}  | without api-error tasks n={len(keep)}: {round(100*sum(d2)/len(d2),1):+.1f} CI {boot(d2)}")
        res[lab] = dict(diff=mu, ci=boot(d_), without_losses=round(100 * sum(d2) / len(d2), 1))
    # recovery after a failed attempt 1 and by difficulty
    fail1 = [i for i in ids if rows[i]["R"]["n"] >= 2 or rows[i]["ONE"]["state"] != "accepted_resolved"]
    f1 = [i for i in ids if not rows[i]["ONE"]["solved"]]
    print(f"  tasks where attempt 1 did not solve: {len(f1)}; solved later  R {sum(rows[i]['R']['solved'] for i in f1)}  F {sum(rows[i]['F']['solved'] for i in f1)}  P {sum(rows[i]['P']['solved'] for i in f1)}")
    for diff in ("easy", "medium", "hard"):
        s = [i for i in ids if rows[i]["difficulty"] == diff]
        if s:
            print(f"  {diff:6s} n={len(s):3d}  one-shot {sum(rows[i]['ONE']['solved'] for i in s):3d}  R {sum(rows[i]['R']['solved'] for i in s):3d}  F {sum(rows[i]['F']['solved'] for i in s):3d}  P {sum(rows[i]['P']['solved'] for i in s):3d}")
    # stops, truncation, accepted_regressed, why attempt-1 failed
    first = [rows[i]["R"]["attempts"][0] for i in ids]
    trunc = sum(t.get("finish") == "length" for t in first)
    nocode = sum(bool(t.get("no_code")) for t in first)
    reg = sum(t["state"] == "accepted_regressed" for t in first)
    print(f"  attempt 1: hit output limit {trunc} ({100*trunc/n:.1f}%), no code {nocode}, public-pass-private-fail {reg}, api_error {sum(t['state']=='api_error' for t in first)}")
    st = {a: dict(collections.Counter(rows[i][a]["stop"] for i in ids)) for a in "RFP"}
    print("  stops:", st)
    OUT[m] = res
json.dump(OUT, open(os.path.join(ROOT, "results", "analysis", "lcb_results.json"), "w"), indent=1)
