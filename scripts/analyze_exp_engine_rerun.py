"""Compare the corrected-feedback results before and after redoing the reruns with the EXPERIMENTAL engine (0.2.0b1).

Inputs : data/blind (original sealed runs), data/blind_fix (corrected rerun, applied with the RELEASED engine, 0.2.0b2),
         data/exp_engine_rerun/trajectories_{sealed,dev}.jsonl (this rerun, applied with 0.2.0b1),
         data/loop2*, loop4* (original development runs), data/dev_fix (corrected development rerun, released engine).
Method : same as the paper. Sealed: task-level bootstrap, 5,000 resamples, seed 20261113 (scripts/analyze_blind.py); development: seed 20261112
         with the call order of scripts/analyze_dev_fix.py. Exact two-sided McNemar test on the discordant tasks.
Output : results/analysis/exp_engine_rerun_summary.json, results/analysis/exp_engine_rerun_per_task.csv
"""
import csv, json, math, os, random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AN = os.path.join(ROOT, "results", "analysis")
M20, M120 = "gpt-oss-20b", "gpt-oss-120b"


def load(d, name="trajectories.jsonl", need_models=True):
    p = os.path.join(ROOT, "data", d, name)
    return {r["iid"]: r for r in (json.loads(l) for l in open(p, encoding="utf-8")) if (not need_models or "models" in r)}


def mcnemar(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return round(min(1.0, 2 * sum(math.comb(n, j) for j in range(k + 1)) / 2 ** n), 4)


def boot_sealed(v, B=5000, seed=20261113):
    r = random.Random(seed)
    n = len(v)
    xs = sorted(sum(v[r.randrange(n)] for _ in range(n)) / n for _ in range(B))
    return round(100 * xs[int(.025 * B)], 1), round(100 * xs[int(.975 * B)], 1)


# --------------------------------------------------------------------------------------------- sealed set
orig = load("blind")
old_fix = load("blind_fix")
new_exp = load("exp_engine_rerun", "trajectories_sealed.jsonl")
IDS = sorted(i for i, r in orig.items() if r["gold"]["resolved"])
summary = {"sealed": {}, "dev": {}}
rows_csv = []


def arm_of(src, i, m, a):
    return src[i]["models"].get(m, {}).get(a) if i in src else None


def merged(m, base, fix):
    """F arm per task: the rerun where present, otherwise the original run (feedback unchanged there)."""
    out = {}
    for i in IDS:
        x = arm_of(fix, i, m, "F") or arm_of(base, i, m, "F")
        out[i] = x
    return out


for m in (M20, M120):
    R = {i: int(bool(arm_of(orig, i, m, "R") and arm_of(orig, i, m, "R")["solved"])) for i in IDS}
    variants = {"original_uncorrected": merged(m, orig, {}), "corrected_released_engine": merged(m, orig, old_fix), "corrected_experimental_engine": merged(m, orig, new_exp)}
    res = {}
    for name, F in variants.items():
        f = {i: int(bool(F[i] and F[i]["solved"])) for i in IDS}
        d = [f[i] - R[i] for i in IDS]
        b = sum(1 for i in IDS if f[i] and not R[i])
        c = sum(1 for i in IDS if R[i] and not f[i])
        cost = sum((F[i] or {}).get("cost_usd", 0) for i in IDS)
        res[name] = dict(n=len(IDS), R=sum(R.values()), F=sum(f.values()), diff_pts=round(100 * sum(d) / len(IDS), 1), ci95=boot_sealed(d),
                         F_only=b, R_only=c, mcnemar_p=mcnemar(b, c), F_cost_usd=round(cost, 4),
                         F_cost_per_solve_usd=round(cost / max(1, sum(f.values())), 5))
        res[name]["_solved"] = f
    res["R_cost_usd"] = round(sum((arm_of(orig, i, m, "R") or {}).get("cost_usd", 0) for i in IDS), 4)
    res["R_cost_per_solve_usd"] = round(res["R_cost_usd"] / max(1, sum(R.values())), 5)
    # tasks whose outcome changed between the old corrected rerun (released engine) and the new one (experimental engine)
    a, b2 = res["corrected_released_engine"]["_solved"], res["corrected_experimental_engine"]["_solved"]
    res["changed_vs_old_corrected"] = sorted(i for i in IDS if a[i] != b2[i])
    res["changed_vs_old_corrected_detail"] = {i: dict(old=a[i], new=b2[i]) for i in res["changed_vs_old_corrected"]}
    for v in variants:
        res[v].pop("_solved")
    summary["sealed"][m] = res
    for i in sorted(new_exp):
        if m.split("/")[-1] in new_exp[i]["models"]:
            o = arm_of(old_fix, i, m, "F")
            n_ = arm_of(new_exp, i, m, "F")
            rows_csv.append(dict(set="sealed", iid=i, model=m, arm="F", old_stop=o and o["stop"], old_solved=o and int(o["solved"]), old_n=o and o["n"],
                                 new_stop=n_ and n_["stop"], new_solved=n_ and int(n_["solved"]), new_n=n_ and n_["n"],
                                 changed=int(bool(o and n_ and (o["solved"] != n_["solved"] or o["stop"] != n_["stop"] or o["n"] != n_["n"])))))

# 20B loop against 120B loop (the paper's "smaller model with the loop" comparison), per variant
for name in ("original_uncorrected", "corrected_released_engine", "corrected_experimental_engine"):
    pass
cmp = {}
for name, fixsrc in (("original_uncorrected", {}), ("corrected_released_engine", old_fix), ("corrected_experimental_engine", new_exp)):
    f20, f120 = merged(M20, orig, fixsrc), merged(M120, orig, fixsrc)
    a = {i: int(bool(f20[i] and f20[i]["solved"])) for i in IDS}
    b = {i: int(bool(f120[i] and f120[i]["solved"])) for i in IDS}
    d = [a[i] - b[i] for i in IDS]
    cost20 = sum((f20[i] or {}).get("cost_usd", 0) for i in IDS)
    cost120 = sum((f120[i] or {}).get("cost_usd", 0) for i in IDS)
    cmp[name] = dict(F20=sum(a.values()), F120=sum(b.values()), diff_pts=round(100 * sum(d) / len(IDS), 1), ci95=boot_sealed(d),
                     cost_per_task_20=round(cost20 / len(IDS), 5), cost_per_task_120=round(cost120 / len(IDS), 5),
                     cost_ratio=round(cost20 / cost120, 3))
summary["sealed"]["loop_20b_vs_120b"] = cmp

# --------------------------------------------------------------------------------------------- development set
DMODELS = {M120: ("loop2", "loop4"), M20: ("loop2_20b", "loop4_20b")}
dev_old_fix = load("dev_fix")
dev_new = load("exp_engine_rerun", "trajectories_dev.jsonl")


def run_dev(fix, seed=20261112):
    rng = random.Random(seed)

    def boot(a, b, ids, reps=5000):
        n = len(ids)
        d = [a[i] - b[i] for i in ids]
        vals = [sum(d[rng.randrange(n)] for _ in range(n)) / n * 100 for _ in range(reps)]
        vals.sort()
        return round(sum(d) / n * 100, 1), round(vals[int(.025 * reps)], 1), round(vals[int(.975 * reps)], 1)

    out = {}
    for model, (dF, dP) in DMODELS.items():
        old_f, old_p = load(dF, need_models=False), load(dP, need_models=False)
        ids = sorted(old_f)
        R = {i: int(old_f[i]["R"]["solved"]) for i in ids}
        F_old = {i: int(old_f[i]["F"]["solved"]) for i in ids}
        P_old = {i: int(old_p[i]["P"]["solved"]) for i in ids}
        F_new, P_new = dict(F_old), dict(P_old)
        for i, r in fix.items():
            m = model.split("/")[-1]
            if i in F_new and m in r["models"]:
                F_new[i] = int(r["models"][m]["F"]["solved"])
                P_new[i] = int(r["models"][m]["P"]["solved"])
        out[model] = dict(n=len(ids), R=sum(R.values()), F_orig=sum(F_old.values()), F=sum(F_new.values()), P_orig=sum(P_old.values()), P=sum(P_new.values()),
                          F_minus_R=boot(F_new, R, ids), P_minus_F=boot(P_new, F_new, ids), P_minus_R=boot(P_new, R, ids),
                          F_only=sum(1 for i in ids if F_new[i] and not R[i]), R_only=sum(1 for i in ids if R[i] and not F_new[i]),
                          _F=F_new, _P=P_new)
    return out


dev_released = run_dev(dev_old_fix)
dev_exp = run_dev(dev_new)
for m in dev_exp:
    for tag, src in (("corrected_released_engine", dev_released), ("corrected_experimental_engine", dev_exp)):
        pass
    ch = {}
    for arm in ("F", "P"):
        a, b = dev_released[m]["_" + arm], dev_exp[m]["_" + arm]
        ch[arm] = sorted(i for i in a if a[i] != b[i])
    summary["dev"][m] = dict(corrected_released_engine={k: v for k, v in dev_released[m].items() if not k.startswith("_")},
                             corrected_experimental_engine={k: v for k, v in dev_exp[m].items() if not k.startswith("_")},
                             changed_vs_old_corrected=ch)
for i in sorted(dev_new):
    for m in (M20, M120):
        mm = m.split("/")[-1]
        for a in ("F", "P"):
            o = dev_old_fix.get(i, {}).get("models", {}).get(mm, {}).get(a)
            n_ = dev_new[i]["models"].get(mm, {}).get(a)
            if o and n_:
                rows_csv.append(dict(set="dev", iid=i, model=m, arm=a, old_stop=o["stop"], old_solved=int(o["solved"]), old_n=o["n"], new_stop=n_["stop"],
                                     new_solved=int(n_["solved"]), new_n=n_["n"],
                                     changed=int(o["solved"] != n_["solved"] or o["stop"] != n_["stop"] or o["n"] != n_["n"])))

summary["notes"] = ["Sealed 'corrected_released_engine' is the earlier rerun in data/blind_fix; 'corrected_experimental_engine' replays the same chains with 0.2.0b1.",
                    "Tasks outside the rerun scope keep their original F result (their feedback text never changed).",
                    "Costs use list prices on stored token counts; Redraw cost is from the original runs."]
json.dump(summary, open(os.path.join(AN, "exp_engine_rerun_summary.json"), "w"), indent=1)
with open(os.path.join(AN, "exp_engine_rerun_per_task.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows_csv[0].keys()))
    w.writeheader()
    w.writerows(rows_csv)
print(json.dumps(summary, indent=1))
print("changed chains:", sum(r["changed"] for r in rows_csv), "of", len(rows_csv))
