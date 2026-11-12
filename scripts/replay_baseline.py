"""Exploratory offline replays for the baseline policy (no model calls, no Docker). Not pre-registered; numbers are discovery on the design tasks.

Replay 1: "20B with test feedback first (<= k1 attempts), then independent 120B re-draws (<= k2 attempts)", built from the recorded Revision 7 and 9
trajectories (data/loop2 for the 120B, data/loop2_20b for the 20B). Two verifier modes: 'target' = stop at the first patch that passes the target
tests (a regressed patch ends the task unsolved), 'perfect' = a regressed patch does not stop the policy (upper bound).
Replay 2: choose one patch per task WITHOUT tests by majority agreement among 3 draws (identical applied Argus patch text), versus a single draw and pass@3.

  python -X utf8 scripts/replay_baseline.py   -> results/analysis/replay_baseline.json
"""
import collections, hashlib, json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDS = json.load(open(os.path.join(ROOT, "data", "gemini_sweep", "task_ids_full.json")))["ids"]


def load(p):
    return [json.loads(l) for l in open(os.path.join(ROOT, p), encoding="utf-8")] if os.path.exists(os.path.join(ROOT, p)) else []


T120 = {r["iid"]: r for r in load("data/loop2/trajectories.jsonl")}
T20 = {r["iid"]: r for r in load("data/loop2_20b/trajectories.jsonl")}
out = {}


def run_policy(i, k1, k2, mode):
    cost, used = 0.0, 0
    for stage, attempts, kmax in (("20B-F", T20[i]["F"]["attempts"], k1), ("120B-R", T120[i]["R"]["attempts"], k2)):
        for a in attempts[:kmax]:
            cost += a.get("cost_usd", 0); used += 1
            st = a["state"]
            if st == "accepted_resolved":
                return 1, cost, used
            if st == "accepted_regressed" and mode == "target":
                return 0, cost, used
    return 0, cost, used


grid = {}
for mode in ("target", "perfect"):
    rows = {}
    for k1 in (0, 1, 2, 3):
        for k2 in (0, 1, 2, 3):
            if k1 + k2 == 0:
                continue
            r = [run_policy(i, k1, k2, mode) for i in IDS]
            rows[f"20B-F<={k1} then 120B-R<={k2}"] = dict(solved=sum(x[0] for x in r), usd=round(sum(x[1] for x in r), 4), mean_attempts=round(sum(x[2] for x in r) / len(r), 2))
    grid[mode] = rows
out["replay1_20B_feedback_then_120B"] = grid

# ---------------- Replay 2: majority agreement without tests
sha = lambda s: hashlib.sha1(s.encode()).hexdigest()[:10]
G = {}
for f in ("results/grading/state_t1.jsonl", "results/grading/state.jsonl", "results/grading/state_new.jsonl"):
    for r in load(f):
        if r.get("hash") and r.get("resolved") is not None:
            G[(r["iid"], r["hash"])] = bool(r["resolved"])
for f in ("data/probe_gemini/grading.jsonl", "data/gemini_sweep/grading.jsonl"):
    for r in load(f):
        if r.get("h") and r.get("resolved") is not None:
            G[(r["iid"], r["h"])] = bool(r["resolved"])
sources = {"gpt-oss-20b": ["data/phase2_t1", "data/phase2_t1_repl"], "gpt-oss-120b": ["data/phase2_t1", "data/phase2_t1_repl"],
           "gemini-3.1-flash-lite": ["data/gemini_sweep/apply"], "gemini-3.5-flash-lite": ["data/gemini_sweep/apply"]}
maj = {}
for m, dirs in sources.items():
    recs = []
    for d in dirs:
        recs += load(f"{d}/argus_apply_{m}.jsonl")
    by = collections.defaultdict(dict)
    for r in recs:
        if r["iid"] in IDS and r["status"] == "applied":
            by[r["iid"]][r["sample"]] = sha(r["diff"])
    single = sum(G.get((i, h), False) for i in by for h in by[i].values()) / 3
    pass3 = sum(any(G.get((i, h), False) for h in by[i].values()) for i in by)
    chosen = ok = agree = agree_ok = 0
    for i in IDS:
        hs = list(by.get(i, {}).values())
        if not hs:
            continue
        cnt = collections.Counter(hs)
        top, n = max(cnt.items(), key=lambda x: (x[1], -hs.index(x[0])))  # ties -> earliest draw
        chosen += 1; ok += G.get((i, top), False)
        if n >= 2:
            agree += 1; agree_ok += G.get((i, top), False)
    maj[m] = dict(single_draw_mean_solved=round(single, 2), majority_vote_solved=int(ok), pass_at_3_oracle=int(pass3), tasks_with_applied_patch=chosen,
                  tasks_with_2_of_3_agreeing=agree, of_which_resolved=int(agree_ok))
out["replay2_majority_vote_no_tests"] = maj
json.dump(out, open(os.path.join(ROOT, "results", "analysis", "replay_baseline.json"), "w", encoding="utf-8"), indent=1)
print(json.dumps(out, indent=1))
