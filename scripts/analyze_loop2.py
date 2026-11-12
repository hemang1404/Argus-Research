"""Revision 7 analysis (pre-registered in PILOT50_PROTOCOL.md): feedback arm F vs independent re-draw arm R, gpt-oss-120b, <= 3 attempts.

  python -X utf8 scripts/analyze_loop2.py   -> results/analysis/loop2_summary.json
"""
import collections, glob, json, os, random, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = {}
for l in open(os.path.join(ROOT, "data", "loop2", "trajectories.jsonl"), encoding="utf-8"):
    r = json.loads(l); T[r["iid"]] = r
IDS = json.load(open(os.path.join(ROOT, "data", "gemini_sweep", "task_ids_full.json")))["ids"]
assert sorted(T) == sorted(IDS), (len(T), len(IDS))
full = {}
for l in open(r"C:\coding\Argus-research-archive\data\swe_bench_verified_tasks.jsonl", encoding="utf-8"):
    d = json.loads(l)
    if d["instance_id"] in T:
        full[d["instance_id"]] = d


def solved_within(arm, n):
    return {i: any(a["state"] == "accepted_resolved" for a in T[i][arm]["attempts"][:n]) for i in IDS}


def cost_within(arm, n):
    return {i: sum(a.get("cost_usd", 0) for a in T[i][arm]["attempts"][:n]) for i in IDS}


rng = random.Random(20261112)
BOOT = [[rng.randrange(len(IDS)) for _ in IDS] for _ in range(5000)]


def paired(a, b):
    d = [int(a[i]) - int(b[i]) for i in IDS]
    s = sorted(sum(d[j] for j in bs) for bs in BOOT)
    return dict(diff=sum(d), ci95=[s[int(.025 * len(s))], s[int(.975 * len(s)) - 1]])


out = {}
for n in (1, 2, 3):
    F, R = solved_within("F", n), solved_within("R", n)
    cF, cR = cost_within("F", n), cost_within("R", n)
    out[f"within_{n}_attempts"] = dict(F_solved=sum(F.values()), R_solved=sum(R.values()), F_minus_R=paired(F, R), F_usd=round(sum(cF.values()), 4), R_usd=round(sum(cR.values()), 4),
                                       F_only=sorted(i for i in IDS if F[i] and not R[i]), R_only=sorted(i for i in IDS if R[i] and not F[i]))
# per-attempt behaviour among tasks that reach the attempt
per = {}
for a in (2, 3):
    row = {}
    for arm in ("F", "R"):
        at = [T[i][arm]["attempts"][a - 1] for i in IDS if len(T[i][arm]["attempts"]) >= a]
        ans = [x for x in at if x.get("apply_status") not in ("truncated_no_output", "empty_output", None)]
        row[arm] = dict(tasks_reaching=len(at), accepted_resolved=sum(x["state"] == "accepted_resolved" for x in at),
                        accepted_regressed=sum(x["state"] == "accepted_regressed" for x in at),
                        resolve_rate=round(sum(x["state"] == "accepted_resolved" for x in at) / len(at), 3) if at else None,
                        returned_an_answer=len(ans), applied=sum(x.get("apply_status") == "applied" for x in at),
                        truncated=sum(x.get("finish") == "length" for x in at))
    per[f"attempt_{a}"] = row
out["per_attempt"] = per
# feedback type for F attempts 2,3 and what happened next
def fb_type(text):
    t = text or ""
    if t.startswith("The edit was applied but the failing test"): return "test_failure_output"
    if t.startswith("The edit was applied but the tests still fail"): return "test_failure_no_name"
    if t.startswith("Patch application failed"): return "apply_refused"
    if t.startswith("Formatting error"): return "no_blocks"
    if t.startswith("Your previous answer was cut off"): return "truncated"
    if t.startswith("The edit could not be applied"): return "patch_rejected"
    if t.startswith("The edit was applied, but the test run produced no results"): return "suite_crashed"
    if t.startswith("The edit produced no change"): return "no_change"
    return "other"
ft = collections.defaultdict(lambda: collections.Counter())
for i in IDS:
    for a in T[i]["F"]["attempts"][1:]:
        k = fb_type(a.get("feedback_in")); ft[k]["n"] += 1; ft[k][a["state"]] += 1
out["F_feedback_types_and_next_outcome"] = {k: dict(v) for k, v in ft.items()}
# regressions and cost per solve
for arm in ("F", "R"):
    out[f"{arm}_total"] = dict(solved=sum(T[i][arm]["solved"] for i in IDS), accepted_regressed=sum(T[i][arm]["stop"] == "accepted_regressed" for i in IDS),
                               never_accepted=sum(T[i][arm]["stop"] == "continue" for i in IDS), usd=round(sum(T[i][arm]["cost_usd"] for i in IDS), 4),
                               usd_per_solve=round(sum(T[i][arm]["cost_usd"] for i in IDS) / max(1, sum(T[i][arm]["solved"] for i in IDS)), 5),
                               mean_attempts=round(sum(T[i][arm]["n"] for i in IDS) / len(IDS), 2))
# tasks failing attempt 1 (the only place the arms differ)
fail1 = [i for i in IDS if T[i]["F"]["attempts"][0]["state"] == "continue"]
out["tasks_failing_attempt_1"] = len(fail1)
out["of_which_solved_later"] = dict(F=sum(T[i]["F"]["solved"] for i in fail1), R=sum(T[i]["R"]["solved"] for i in fail1))
# gold-region check for tasks only one arm solved
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def touched(diff, path):
    out_, cur, old = set(), False, None
    for ln in diff.split("\n"):
        if ln.startswith("diff --git"):
            cur = ln.endswith("b/" + path); old = None; continue
        if not cur: continue
        m = HUNK.match(ln)
        if m: old = int(m.group(1)); continue
        if old is None or ln.startswith(("---", "+++")): continue
        if ln.startswith("-"): out_.add(old); old += 1
        elif ln.startswith("+"): out_.add(old); out_.add(old - 1)
        else: old += 1
    return out_


def find_patch(iid, h):
    for base in ("loop_grading", "grading"):
        for p in glob.glob(os.path.join(ROOT, "results", base, "logs", "run_evaluation", f"*{iid}_{h}", "*", iid, "patch.diff")):
            return open(p, encoding="utf-8", errors="replace").read()
    return None


gold_chk = {}
for arm in ("F", "R"):
    rows = []
    for i in IDS:
        if T[i][arm]["solved"] and not T[i]["R" if arm == "F" else "F"]["solved"]:
            h = T[i][arm]["attempts"][-1].get("patch_hash"); d = find_patch(i, h) if h else None
            if d is None: rows.append((i, "patch file not found")); continue
            tgt = d.split("diff --git a/")[1].split(" ")[0] if "diff --git a/" in d else ""
            g = touched(full[i]["gold_patch"], tgt); m = touched(d, tgt)
            rows.append((i, "touches_gold_region" if g and any(abs(x - y) <= 5 for x in m for y in g) else "elsewhere"))
    gold_chk[f"{arm}_only_solves"] = rows
out["gold_region_check"] = gold_chk
json.dump(out, open(os.path.join(ROOT, "results", "analysis", "loop2_summary.json"), "w", encoding="utf-8"), indent=1)
print(json.dumps(out, indent=1))
