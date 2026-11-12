"""Revision 8 analysis (pre-registered in PILOT50_PROTOCOL.md): arm P (previous answer + test result, multi-turn) vs Revision 7 arms R and F.

  python -X utf8 scripts/analyze_loop3.py   -> results/analysis/loop3_summary.json
Tasks where an attempt could not be made (request over the free-tier 8,000 tokens/minute limit, image pull failure) are counted unsolved
in the pre-registered primary numbers and also reported with those tasks left out.
"""
import collections, json, os, random, sys
SUF = sys.argv[1] if len(sys.argv) > 1 else ""
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDS = json.load(open(os.path.join(ROOT, "data", "gemini_sweep", "task_ids_full.json")))["ids"]


def load(p):
    d = {}
    for l in open(os.path.join(ROOT, p), encoding="utf-8"):
        r = json.loads(l); d[r["iid"]] = r
    return d


T2, T3 = load("data/loop2" + SUF + "/trajectories.jsonl"), load("data/loop3" + SUF + "/trajectories.jsonl")
assert sorted(T3) == sorted(IDS) and sorted(T2) == sorted(IDS)
arms = {"P": {i: T3[i]["P"] for i in IDS}, "F": {i: T2[i]["F"] for i in IDS}, "R": {i: T2[i]["R"] for i in IDS}}
infra = {i for i in IDS if any(a["state"] in ("api_error", "image_pull_failed", "grade_error") for a in arms["P"][i]["attempts"])}
rng = random.Random(20261112)
BOOT = [[rng.randrange(len(IDS)) for _ in IDS] for _ in range(5000)]
IDX = {i: k for k, i in enumerate(IDS)}


def solved(arm, n):
    return {i: any(a["state"] == "accepted_resolved" for a in arms[arm][i]["attempts"][:n]) for i in IDS}


def cost(arm, n):
    return {i: sum(a.get("cost_usd", 0) for a in arms[arm][i]["attempts"][:n]) for i in IDS}


def paired(a, b, keep):
    d = [int(a[i]) - int(b[i]) if i in keep else 0 for i in IDS]
    s = sorted(sum(d[j] for j in bs) for bs in BOOT)
    return dict(diff=sum(d), ci95=[s[int(.025 * len(s))], s[int(.975 * len(s)) - 1]])


out = dict(infra_tasks_in_P=sorted(infra), infra_reasons={i: [a["state"] for a in arms["P"][i]["attempts"] if a["state"] in ("api_error", "image_pull_failed", "grade_error")] for i in infra})
ALL, KEEP = set(IDS), set(IDS) - infra
for n in (2, 3):
    row = {}
    S = {a: solved(a, n) for a in arms}; C = {a: cost(a, n) for a in arms}
    for a in arms:
        row[a] = dict(solved=sum(S[a].values()), usd=round(sum(C[a].values()), 4),
                      solved_excluding_infra_tasks=sum(S[a][i] for i in KEEP), usd_excluding_infra_tasks=round(sum(C[a][i] for i in KEEP), 4))
    row["P_minus_R"] = paired(S["P"], S["R"], ALL); row["P_minus_R_excl_infra"] = paired(S["P"], S["R"], KEEP)
    row["P_minus_F"] = paired(S["P"], S["F"], ALL); row["P_minus_F_excl_infra"] = paired(S["P"], S["F"], KEEP)
    row["P_only_vs_R"] = sorted(i for i in IDS if S["P"][i] and not S["R"][i]); row["R_only_vs_P"] = sorted(i for i in IDS if S["R"][i] and not S["P"][i])
    out[f"within_{n}_attempts"] = row
per = {}
for a in (2, 3):
    row = {}
    for arm in ("P", "F", "R"):
        at = [arms[arm][i]["attempts"][a - 1] for i in IDS if len(arms[arm][i]["attempts"]) >= a and arms[arm][i]["attempts"][a - 1]["state"] != "api_error"]
        row[arm] = dict(tasks_reaching=len(at), accepted_resolved=sum(x["state"] == "accepted_resolved" for x in at), accepted_regressed=sum(x["state"] == "accepted_regressed" for x in at),
                        resolve_rate=round(sum(x["state"] == "accepted_resolved" for x in at) / len(at), 3) if at else None,
                        applied=sum(x.get("apply_status") == "applied" for x in at), truncated=sum(x.get("finish") == "length" for x in at))
    per[f"attempt_{a}"] = row
out["per_attempt"] = per
# does P repeat itself?
rep = tot = 0
for i in IDS:
    seen = []
    for a in arms["P"][i]["attempts"]:
        h = a.get("patch_hash")
        if h:
            tot += 1; rep += h in seen; seen.append(h)
out["P_repeated_identical_patch"] = dict(patches=tot, repeats=rep)
ft = collections.defaultdict(collections.Counter)
for i in IDS:
    for a in arms["P"][i]["attempts"][1:]:
        t = a.get("feedback_in") or ""
        k = "test_failure_output" if t.startswith("The edit was applied but the failing test") else ("apply_refused" if t.startswith("Patch application failed") else "other")
        ft[k]["n"] += 1; ft[k][a["state"]] += 1
out["P_feedback_types_and_next_outcome"] = {k: dict(v) for k, v in ft.items()}
for arm in arms:
    out[f"{arm}_total"] = dict(solved=sum(arms[arm][i]["solved"] for i in IDS), accepted_regressed=sum(arms[arm][i]["stop"] == "accepted_regressed" for i in IDS),
                               usd=round(sum(arms[arm][i]["cost_usd"] for i in IDS), 4))
    out[f"{arm}_total"]["usd_per_solve"] = round(out[f"{arm}_total"]["usd"] / max(1, out[f"{arm}_total"]["solved"]), 5)
json.dump(out, open(os.path.join(ROOT, "results", "analysis", "loop3" + SUF + "_summary.json"), "w", encoding="utf-8"), indent=1)
print(json.dumps(out, indent=1))
