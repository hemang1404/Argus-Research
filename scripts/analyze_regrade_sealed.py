"""Intervals, exact McNemar p and costs for the sealed set, with the experimental engine (0.2.0b1, as stored) and with the
released engine (0.2.0b2, re-graded lower bound).  Analysis only: no model calls, no Docker.
  python -X utf8 scripts/analyze_regrade_sealed.py

Conventions copied from scripts/analyze_blind.py: task-level bootstrap, 5,000 resamples, seed 20261113 (re-seeded for every
interval), percentile interval x[int(.025 B)], x[int(.975 B)], differences in percentage points. Exact two-sided McNemar:
p = min(1, 2 * sum_{j<=min(b,c)} C(n, j) / 2^n), n = b + c.
Cost = prompt tokens * input price + completion tokens * output price (completion tokens include reasoning tokens), summed
over the attempts actually used, at the paper's list prices. Tokens come from the stored attempt records.

Released-engine numbers are LOWER BOUNDS built from data/blind and data/blind_fix attempts plus results/analysis/
regrade_per_task_released.csv (written by scripts/regrade_released_engine.py):
  * a task not listed in the CSV keeps its stored outcome and stored attempts;
  * a listed task takes new_solved from the CSV; attempts used = the accepting turn, or all stored attempts when nothing
    was accepted. When the stop rule would have needed an attempt that was never drawn (needs_new_draw), the task counts as
    unsolved and its cost is that of the stored attempts only (a lower bound on spend).
"""
import csv
import json
import math
import os
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AN = os.path.join(ROOT, "results", "analysis")
M20, M120, MG = "gpt-oss-20b", "gpt-oss-120b", "gemma-4-26b-a4b-it"
PRICE = {M20: (0.075, 0.30), M120: (0.15, 0.60), MG: (0.09, 0.30)}  # USD per million tokens (input, output)
SEED, B = 20261113, 5000


def load(p):
    rows = {}
    for line in open(p, encoding="utf-8"):
        r = json.loads(line)
        rows[r["iid"]] = r  # last record per task wins, as in analyze_blind.py
    return rows


blind = load(os.path.join(ROOT, "data", "blind", "trajectories.jsonl"))
fix = load(os.path.join(ROOT, "data", "blind_fix", "trajectories.jsonl"))
IDS = sorted(i for i, r in blind.items() if r["gold"]["resolved"])

# re-grade rows keyed (group, model, arm, iid)
RG = {}
for r in csv.DictReader(open(os.path.join(AN, "regrade_per_task_released.csv"), encoding="utf-8")):
    RG[(r["group"], r["model"], r["arm"], r["iid"])] = r


def boot(d, B=B, seed=SEED):
    r = random.Random(seed)
    n = len(d)
    xs = sorted(sum(d[r.randrange(n)] for _ in range(n)) / n for _ in range(B))
    return round(100 * xs[int(.025 * B)], 1), round(100 * xs[int(.975 * B)], 1)


def mcnemar(b, c):
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, j) for j in range(min(b, c) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def attempt_cost(model, t):
    pt, ct = t.get("prompt_tokens"), t.get("completion_tokens")
    if pt is None or ct is None:
        return 0.0, 1
    pin, pout = PRICE[model]
    return (pt * pin + ct * pout) / 1e6, 0


def arm_record(group, model, arm, iid):
    """stored arm record used by this group (corrected: the blind_fix rerun where one exists)."""
    if group == "corrected" and iid in fix and model in fix[iid]["models"] and arm in fix[iid]["models"][model]:
        return fix[iid]["models"][model][arm]
    return blind[iid]["models"].get(model, {}).get(arm)


def solved_at_1(x):
    return bool(x and x["attempts"] and x["attempts"][0].get("state") == "accepted_resolved")


def per_task(group, model, arm, engine):
    """-> dict iid -> (solved, solved_at_attempt_1, cost, missing_token_attempts, note)"""
    out = {}
    for iid in IDS:
        x = arm_record(group, model, arm, iid)
        if not x:
            out[iid] = (False, False, 0.0, 0, "no record")
            continue
        att = x["attempts"]
        row = RG.get((group, model, arm, iid)) if engine == "released" else None
        if row is None:
            k, solved, s1, note = len(att), bool(x["solved"]), solved_at_1(x), ""
        else:
            assert (row["old_solved"] == "True") == bool(x["solved"]), (group, model, arm, iid)
            solved = row["new_solved"] == "True"
            acc = row["new_state"] in ("accepted_resolved", "accepted_regressed")
            k = int(row["turn_accepted"]) if acc and row["turn_accepted"] else len(att)
            s1 = row["new_state"] == "accepted_resolved" and row["turn_accepted"] == "1"
            note = "needs_new_draw" if row["needs_new_draw"] == "True" else ""
        cost, miss = 0.0, 0
        for t in att[:k]:
            c, m = attempt_cost(model, t)
            cost += c
            miss += m
        out[iid] = (solved, s1, cost, miss, note)
    return out


def summarize(model, tag, pt):
    n = len(IDS)
    solved = sum(v[0] for v in pt.values())
    cost = sum(v[2] for v in pt.values())
    return dict(model=model, arm=tag, n=n, solved=solved, solved_pct=round(100 * solved / n, 1), total_cost=round(cost, 4),
                cost_per_task=round(cost / n, 5), cost_per_solved=round(cost / solved, 5) if solved else None,
                attempts_missing_tokens=sum(v[3] for v in pt.values()), tasks_needing_new_draw=sum(v[4] == "needs_new_draw" for v in pt.values()))


def paired(a, b, idx=0):
    """a minus b over IDS; idx 0 = solved, 1 = solved at attempt 1"""
    va = [float(a[i][idx]) for i in IDS]
    vb = [float(b[i][idx]) for i in IDS]
    d = [x - y for x, y in zip(va, vb)]
    n = len(d)
    A = sum(x > 0 for x in d)  # solved only by a
    Bc = sum(x < 0 for x in d)
    return dict(n=n, a_solved=int(sum(va)), b_solved=int(sum(vb)), diff_pts=round(100 * sum(d) / n, 1), ci95=boot(d),
                a_only=A, b_only=Bc, mcnemar_p=round(mcnemar(A, Bc), 4))


res = dict(seed=SEED, resamples=B, prices_per_million=PRICE, n_tasks=len(IDS), cost_validation={}, arms={}, comparisons={}, notes=[
    "Intervals: task-level bootstrap, 5,000 resamples, seed 20261113 (the seed convention of scripts/analyze_blind.py).",
    "Released-engine counts are lower bounds (stored attempts only). Intervals on released counts treat the lower-bound outcomes as fixed.",
    "Feedback attempts 2 and 3 were written from feedback produced under the experimental engine; where an earlier outcome changed, the replay is approximate.",
    "Gemma list price $0.09/$0.30 per million tokens (the run itself cost $0 on a free tier)."])

ARMS = []
for model in (M20, M120, MG):
    ARMS.append(("orig", model, "R"))
    ARMS.append(("orig", model, "F"))
    if model != MG:
        ARMS.append(("corrected", model, "F"))
PT = {}
for engine in ("experimental", "released"):
    for g, m, a in ARMS:
        PT[(engine, g, m, a)] = per_task(g, m, a, engine)
        tag = f"{m} {a}" + (" corrected" if g == "corrected" else "")
        res["arms"][f"{engine}|{tag}"] = summarize(m, tag, PT[(engine, g, m, a)])


def get(engine, g, m, a):
    return PT[(engine, g, m, a)]


# validate the cost code against the paper's existing sealed cost table (experimental engine)
PAPER = {"gpt-oss-20b R": (0.5265, 0.00543), "gpt-oss-20b F": (0.4975, 0.00452), "gpt-oss-120b R": (0.6304, 0.00584),
         "gpt-oss-120b F": (0.6574, 0.00562), "gpt-oss-20b F corrected": (0.4972, 0.00460), "gpt-oss-120b F corrected": (0.6630, 0.00582),
         "gemma-4-26b-a4b-it R": (0.6889, 0.00861), "gemma-4-26b-a4b-it F": (0.6057, 0.00739)}
ok = True
for tag, (tc, cps) in PAPER.items():
    r = res["arms"]["experimental|" + tag]
    match = abs(r["total_cost"] - tc) < 0.00006 and abs(r["cost_per_solved"] - cps) < 0.000006
    ok &= match
    res["cost_validation"][tag] = dict(paper_total=tc, paper_per_solve=cps, computed_total=r["total_cost"], computed_per_solve=r["cost_per_solved"], matches=match)
res["cost_validation_all_match"] = ok

for engine in ("experimental", "released"):
    cmp_ = res["comparisons"][engine] = {}
    for m in (M20, M120, MG):
        cmp_[f"{m} F-R"] = paired(get(engine, "orig", m, "F"), get(engine, "orig", m, "R"))
        if m != MG:
            cmp_[f"{m} corrected F - R"] = paired(get(engine, "corrected", m, "F"), get(engine, "orig", m, "R"))
    cmp_["20B F loop - 120B F loop (original)"] = paired(get(engine, "orig", M20, "F"), get(engine, "orig", M120, "F"))
    cmp_["20B F loop - 120B F loop (corrected)"] = paired(get(engine, "corrected", M20, "F"), get(engine, "corrected", M120, "F"))
    cmp_["20B F loop - 120B one attempt (original)"] = {**paired(get(engine, "orig", M20, "F"), get(engine, "orig", M120, "R"), 1), "note": "b is the 120B first attempt (attempt-1 resolved)"}
    # fix: the 'a' count above is attempt-1 for both sides; recompute with the loop solved count vs attempt-1
    va = [float(get(engine, "orig", M20, "F")[i][0]) for i in IDS]
    vb = [float(get(engine, "orig", M120, "R")[i][1]) for i in IDS]
    d = [x - y for x, y in zip(va, vb)]
    cmp_["20B F loop - 120B one attempt (original)"] = dict(n=len(d), a_solved=int(sum(va)), b_solved=int(sum(vb)), diff_pts=round(100 * sum(d) / len(d), 1),
                                                           ci95=boot(d), a_only=sum(x > 0 for x in d), b_only=sum(x < 0 for x in d),
                                                           mcnemar_p=round(mcnemar(sum(x > 0 for x in d), sum(x < 0 for x in d)), 4))
    e20, e120 = res["arms"][f"{engine}|{M20} F"], res["arms"][f"{engine}|{M120} F"]
    cmp_["cost per task, 20B F vs 120B F (original)"] = dict(cost_per_task_20b=e20["cost_per_task"], cost_per_task_120b=e120["cost_per_task"],
                                                            lower_by_pct=round(100 * (1 - e20["cost_per_task"] / e120["cost_per_task"]), 1))

json.dump(res, open(os.path.join(AN, "regrade_stats_sealed.json"), "w"), indent=1)

# markdown table
L = ["# Sealed set: experimental engine against released engine (lower bound)", "",
     f"Task-level bootstrap, {B} resamples, seed {SEED}; exact two-sided McNemar. Released-engine columns are lower bounds from stored attempts.", "",
     "## Cost code check against the paper's sealed cost table (experimental engine)", "", "| arm | paper total | computed | paper per solve | computed | match |", "|:--|--:|--:|--:|--:|:--:|"]
for tag, v in res["cost_validation"].items():
    L.append(f"| {tag} | {v['paper_total']} | {v['computed_total']} | {v['paper_per_solve']} | {v['computed_per_solve']} | {'yes' if v['matches'] else 'NO'} |")
L += ["", "## Paired differences, Feedback minus Redraw (points, 95% interval, exact McNemar)", "",
      "| comparison | engine | solved (F / R) | difference | 95% interval | only-F / only-R | p |", "|:--|:--|:--:|:--:|:--:|:--:|:--:|"]
for k in (f"{M20} F-R", f"{M20} corrected F - R", f"{M120} F-R", f"{M120} corrected F - R", f"{MG} F-R",
          "20B F loop - 120B F loop (original)", "20B F loop - 120B F loop (corrected)", "20B F loop - 120B one attempt (original)"):
    for engine in ("experimental", "released"):
        v = res["comparisons"][engine][k]
        L.append(f"| {k} | {engine} | {v['a_solved']} / {v['b_solved']} | {v['diff_pts']:+.1f} | {v['ci95'][0]:+.1f} to {v['ci95'][1]:+.1f} | {v['a_only']} / {v['b_only']} | {v['mcnemar_p']} |")
L += ["", "## Cost at list prices (USD)", "", "| arm | engine | solved | total | per task | per solved | tasks needing a new draw | attempts missing tokens |", "|:--|:--|--:|--:|--:|--:|--:|--:|"]
for key, v in res["arms"].items():
    engine, tag = key.split("|")
    L.append(f"| {tag} | {engine} | {v['solved']} | {v['total_cost']} | {v['cost_per_task']} | {v['cost_per_solved']} | {v['tasks_needing_new_draw']} | {v['attempts_missing_tokens']} |")
L += ["", "Notes: " + " ".join(res["notes"])]
open(os.path.join(AN, "regrade_stats_sealed.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print("cost table reproduces:", ok)
print("\n".join(L))
