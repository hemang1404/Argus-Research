"""Design-set recovery arms before and after the corrected-feedback rerun (data/dev_fix).
Merges: arm R from the original runs (unaffected), arms F and P from the original runs except for the tasks rerun in data/dev_fix.
Prints counts, paired differences with 95% bootstrap intervals (seed 20261112, 5000 resamples) and the recovery-by-failure-type table.
Writes results/analysis/dev_fix_summary.json."""
import json
import os
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(d):
    p = os.path.join(ROOT, "data", d, "trajectories.jsonl")
    return {json.loads(l)["iid"]: json.loads(l) for l in open(p, encoding="utf-8")}


MODELS = {"gpt-oss-120b": ("loop2", "loop4", "loop3"), "gpt-oss-20b": ("loop2_20b", "loop4_20b", "loop3_20b")}
fix = load("dev_fix")
out = {}
rng = random.Random(20261112)


def boot(a, b, ids, reps=5000):
    n = len(ids)
    d = [a[i] - b[i] for i in ids]
    vals = []
    for _ in range(reps):
        vals.append(sum(d[rng.randrange(n)] for _ in range(n)) / n * 100)
    vals.sort()
    return round(sum(d) / n * 100, 1), round(vals[int(.025 * reps)], 1), round(vals[int(.975 * reps)], 1)


def classify(rows_R):
    t = rows_R["attempts"][0]
    if t.get("finish") == "length" or t.get("apply_status") in ("truncated_no_output", "empty_output"):
        return "truncated"
    if t.get("apply_status") == "applied":
        return "applied_failing"
    return "not_applied"


for model, (dF, dP, dP3) in MODELS.items():
    old_f, old_p = load(dF), load(dP)
    ids = sorted(old_f)
    R = {i: int(old_f[i]["R"]["solved"]) for i in ids}
    F_old = {i: int(old_f[i]["F"]["solved"]) for i in ids}
    P_old = {i: int(old_p[i]["P"]["solved"]) for i in ids}
    F_new, P_new = dict(F_old), dict(P_old)
    F_arm, P_arm = {i: old_f[i]["F"] for i in ids}, {i: old_p[i]["P"] for i in ids}
    changed = 0
    for i, r in fix.items():
        if i in F_new and model in r["models"]:
            F_new[i] = int(r["models"][model]["F"]["solved"]); P_new[i] = int(r["models"][model]["P"]["solved"])
            F_arm[i] = r["models"][model]["F"]; P_arm[i] = r["models"][model]["P"]
            changed += (F_new[i] != F_old[i]) + (P_new[i] != P_old[i])
    res = dict(n=len(ids), R=sum(R.values()), F_old=sum(F_old.values()), F_new=sum(F_new.values()), P_old=sum(P_old.values()), P_new=sum(P_new.values()),
               outcome_changes_in_rerun=changed,
               F_minus_R_old=boot(F_old, R, ids), F_minus_R_new=boot(F_new, R, ids),
               P_minus_F_old=boot(P_old, F_old, ids), P_minus_F_new=boot(P_new, F_new, ids),
               P_minus_R_new=boot(P_new, R, ids))
    # discordant counts for F vs R
    res["F_only_new"] = sum(1 for i in ids if F_new[i] and not R[i]); res["R_only_vs_F_new"] = sum(1 for i in ids if R[i] and not F_new[i])
    # recovery by attempt-1 failure type (tasks whose first attempt was not accepted)
    cats = {}
    for i in ids:
        a1 = old_f[i]["R"]["attempts"][0]
        if a1["state"] != "continue":
            continue
        c = classify(old_f[i]["R"])
        d = cats.setdefault(c, dict(n=0, R=0, F_old=0, F_new=0, P_old=0, P_new=0))
        d["n"] += 1; d["R"] += R[i]; d["F_old"] += F_old[i]; d["F_new"] += F_new[i]; d["P_old"] += P_old[i]; d["P_new"] += P_new[i]
    res["by_failure_type"] = cats
    BAD = "scikit-learn__scikit-learn-14710"  # grading exceeded the 1,800 s limit in the rerun: infrastructure failure, counted unsolved above
    ids2 = [i for i in ids if i != BAD]
    res["excluding_14710"] = dict(n=len(ids2), R=sum(R[i] for i in ids2), F_new=sum(F_new[i] for i in ids2), P_new=sum(P_new[i] for i in ids2),
                                  F_minus_R=boot(F_new, R, ids2), P_minus_F=boot(P_new, F_new, ids2), P_minus_R=boot(P_new, R, ids2))
    # 20B: drop tasks on which the 20B model hit the output limit (repetition loop) in the temperature-0 run (results/analysis/records.jsonl)
    t0 = [json.loads(l) for l in open(os.path.join(ROOT, "results", "analysis", "records.jsonl"), encoding="utf-8")]
    loop_tasks = {r["iid"] for r in t0 if r["model"] == "gpt-oss-20b" and r["argus"] == "F1_budget_truncation"}
    ids3 = [i for i in ids if i not in loop_tasks]
    res["without_t0_loop_tasks"] = dict(n_removed=len(set(ids) & loop_tasks), n=len(ids3), F_minus_R_old=boot(F_old, R, ids3), F_minus_R_new=boot(F_new, R, ids3),
                                        P_minus_R_old=boot(P_old, R, ids3), P_minus_R_new=boot(P_new, R, ids3))
    # 20B: drop tasks whose first attempt was cut off by a repetition loop
    nt = [i for i in ids if old_f[i]["R"]["attempts"][0].get("finish") != "length"]
    res["without_truncated_first_attempt"] = dict(n=len(nt), F_minus_R=boot(F_new, R, nt), P_minus_R=boot(P_new, R, nt))
    # identical attempt-2 patch, and attempt-2 resolved share
    def ident(arm):
        n_ = k = 0
        for i in ids:
            a = arm[i]["attempts"]
            if len(a) >= 2 and a[0].get("patch_hash") and a[1].get("patch_hash"):
                n_ += 1; k += a[0]["patch_hash"] == a[1]["patch_hash"]
        return "%d/%d" % (k, n_)
    def att2_resolved(arm):
        n_ = k = 0
        for i in ids:
            a = arm[i]["attempts"]
            if len(a) >= 2:
                n_ += 1; k += bool((a[1].get("grade") or {}).get("resolved"))
        return "%d/%d" % (k, n_)
    R_arm = {i: old_f[i]["R"] for i in ids}
    res["identical_attempt2_patch"] = dict(R=ident(R_arm), F_old=ident({i: old_f[i]["F"] for i in ids}), F_new=ident(F_arm), P_old=ident({i: old_p[i]["P"] for i in ids}), P_new=ident(P_arm))
    res["attempt2_resolved"] = dict(R=att2_resolved(R_arm), F_old=att2_resolved({i: old_f[i]["F"] for i in ids}), F_new=att2_resolved(F_arm))
    out[model] = res
    print(model, json.dumps(res, indent=1))
json.dump(out, open(os.path.join(ROOT, "results", "analysis", "dev_fix_summary.json"), "w"), indent=1)
