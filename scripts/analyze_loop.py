"""Revision 5 analysis (Argus-loop discovery run), exactly the items fixed in PILOT50_PROTOCOL.md Revision 5.

Loop arms: L-B (test-given, the full trajectory) and L-A (observable only: stop at the first applied patch; read off the same trajectory).
Baselines from Revision 4 draws (stock Argus apply, medium effort): independent re-draws on the same ladder (20B draws then 120B draws, stop
when all FAIL_TO_PASS pass, averaged over all draw orders) and the 120B alone (3 draws, the most Revision 4 has).
Matched spend: per-task budget B; a turn counts only if the cumulative spend after it is <= B.
Output: results/analysis/loop_summary.json
"""
import collections, hashlib, itertools, json, math, os, random, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "results", "analysis")
PRICE = {"gpt-oss-20b": (0.075, 0.30), "gpt-oss-120b": (0.15, 0.60)}
rng = random.Random(20261112)
B = 2000

man = json.load(open(os.path.join(ROOT, "manifests", "pilot100_manifest.json"), encoding="utf-8"))
gold = {}
for l in open(os.path.join(ROOT, "results", "grading", "state.jsonl"), encoding="utf-8"):
    r = json.loads(l)
    if "gold" in (r.get("labels") or []):
        gold[r["iid"]] = r
valid = [t["instance_id"] for t in man["primary"] if gold.get(t["instance_id"], {}).get("resolved") is True]
full = {}
for l in open(r"C:\coding\Argus-research-archive\data\swe_bench_verified_tasks.jsonl", encoding="utf-8"):
    d = json.loads(l); full[d["instance_id"]] = d

traj = {}
for l in open(os.path.join(ROOT, "data", "loop", "trajectories.jsonl"), encoding="utf-8"):
    r = json.loads(l); traj[r["iid"]] = r
assert set(traj) == set(valid), (len(traj), len(valid))

# ---- Revision 4 draws (Argus arm) -> per (task, model, draw): cost, stop flag (all F2P pass), resolved
sha = lambda d: hashlib.sha1(d.encode()).hexdigest()[:10]
st = {}
for l in open(os.path.join(ROOT, "results", "grading", "state_t1.jsonl"), encoding="utf-8"):
    r = json.loads(l); st[(r["iid"], r["hash"])] = r
gen = {}
for l in open(os.path.join(ROOT, "data", "raw", "phase2_t1_clean.jsonl"), encoding="utf-8"):
    r = json.loads(l); gen[(r["iid"], r["model"].split("/")[-1], r["sample"])] = r
cell = {}
for m in PRICE:
    for l in open(os.path.join(ROOT, "data", "phase2_t1", f"argus_apply_{m}.jsonl"), encoding="utf-8"):
        a = json.loads(l)
        if a["iid"] not in valid:
            continue
        g = gen[(a["iid"], m, a["sample"])]
        cost = (g["prompt_tokens"] * PRICE[m][0] + g["completion_tokens"] * PRICE[m][1]) / 1e6
        stop = res = False
        if a["status"] == "applied":
            s = st[(a["iid"], sha(a["diff"]))]
            res = bool(s["resolved"])
            stop = bool(s.get("applied")) and s.get("f2p_fail") == 0 and (s.get("f2p_pass") or 0) > 0
        cell[(a["iid"], m, a["sample"])] = dict(cost=cost, stop=stop, resolved=res)


def run_seq(iid, seq, K):
    """seq of (model, draw); returns cum_cost[1..K], solved[1..K]"""
    cc, sv, cum, solved, stopped = [], [], 0.0, 0, False
    for k in range(K):
        if not stopped:
            c = cell[(iid, seq[k][0], seq[k][1])]
            cum += c["cost"]
            if c["stop"]:
                stopped = True; solved = int(c["resolved"])
        cc.append(cum); sv.append(solved if stopped else 0)
    return cc, sv


def baseline_ladder(iid):
    out = []
    for p20 in itertools.permutations((0, 1, 2), 2):
        for p120 in itertools.permutations((0, 1, 2), 2):
            seq = [("gpt-oss-20b", p20[0]), ("gpt-oss-20b", p20[1]), ("gpt-oss-120b", p120[0]), ("gpt-oss-120b", p120[1])]
            out.append(run_seq(iid, seq, 4))
    return out


def baseline_120(iid):
    return [run_seq(iid, [("gpt-oss-120b", d) for d in p], 3) for p in itertools.permutations((0, 1, 2), 3)]


def baseline_20(iid):
    return [run_seq(iid, [("gpt-oss-20b", d) for d in p], 3) for p in itertools.permutations((0, 1, 2), 3)]


def loop_arrays(t, arm):
    """cum_cost[1..4], solved[1..4] for L-B (full) or L-A (stop at first applied patch)"""
    turns = t["turns"]
    cc, sv, cum, solved, stopped = [], [], 0.0, 0, False
    for k in range(4):
        if k < len(turns) and not stopped:
            tr = turns[k]
            cum += tr.get("cost_usd", 0.0)
            g = tr.get("grade") or {}
            if arm == "B":
                if t["stop"] == "resolved" and k == len(turns) - 1:
                    stopped = True; solved = 1
                elif t["stop"] == "stopped_f2p_pass_regressed" and k == len(turns) - 1:
                    stopped = True; solved = 0
            else:
                if tr.get("apply_status") == "applied":
                    stopped = True; solved = int(bool(g.get("resolved")))
        cc.append(cum); sv.append(solved if stopped else 0)
    return cc, sv


def at_budget(cc, sv, b):
    k = -1
    for i, c in enumerate(cc):
        if c <= b and c > 0:
            k = i
    return sv[k] if k >= 0 else 0


def boot_mean(vals, reps=B):
    n = len(vals); ms = []
    for _ in range(reps):
        ms.append(sum(vals[rng.randrange(n)] for _ in range(n)) / n)
    ms.sort()
    return [round(100 * ms[int(.025 * reps)], 1), round(100 * ms[int(.975 * reps) - 1], 1)]


S = dict(n_tasks=len(valid))
LB = {i: loop_arrays(traj[i], "B") for i in valid}
LA = {i: loop_arrays(traj[i], "A") for i in valid}
BL = {i: baseline_ladder(i) for i in valid}
B120 = {i: baseline_120(i) for i in valid}
B20 = {i: baseline_20(i) for i in valid}

# ---- headline and by-turn
S["headline"] = dict(L_B_resolved=sum(traj[i]["resolved"] for i in valid), L_B_stop_counts=dict(collections.Counter(traj[i]["stop"] for i in valid)),
                     L_A_resolved=sum(LA[i][1][3] for i in valid),
                     redraw_ladder_resolved_mean=round(sum(sum(s[1][3] for s in BL[i]) / len(BL[i]) for i in valid), 1),
                     redraw_120B_x3_resolved_mean=round(sum(sum(s[1][2] for s in B120[i]) / len(B120[i]) for i in valid), 1),
                     redraw_20B_x3_resolved_mean=round(sum(sum(s[1][2] for s in B20[i]) / len(B20[i]) for i in valid), 1))
S["by_turn"] = {}
for k in range(4):
    row = dict(turn=k + 1,
               L_B_solved=sum(LB[i][1][k] for i in valid), L_B_mean_cum_spend=round(sum(LB[i][0][k] for i in valid) / len(valid), 5),
               L_A_solved=sum(LA[i][1][k] for i in valid), L_A_mean_cum_spend=round(sum(LA[i][0][k] for i in valid) / len(valid), 5),
               redraw_ladder_solved=round(sum(sum(s[1][k] for s in BL[i]) / len(BL[i]) for i in valid), 1),
               redraw_ladder_mean_cum_spend=round(sum(sum(s[0][k] for s in BL[i]) / len(BL[i]) for i in valid) / len(valid), 5))
    d = [LB[i][1][k] - sum(s[1][k] for s in BL[i]) / len(BL[i]) for i in valid]
    row["L_B_minus_redraw_ladder_pp"] = round(100 * sum(d) / len(d), 1); row["ci95_pp"] = boot_mean(d)
    S["by_turn"][k + 1] = row

# ---- matched spend curve (per-task budget)
grid = [0.0003, 0.0005, 0.0008, 0.0012, 0.0018, 0.0026, 0.004, 0.006, 0.009, 0.013, 0.02]
S["matched_spend"] = []
for b in grid:
    d = [at_budget(*LB[i], b) - sum(at_budget(*s, b) for s in BL[i]) / len(BL[i]) for i in valid]
    dA = [at_budget(*LA[i], b) - sum(at_budget(*s, b) for s in BL[i]) / len(BL[i]) for i in valid]
    d120 = [at_budget(*LB[i], b) - sum(at_budget(*s, b) for s in B120[i]) / len(B120[i]) for i in valid]
    S["matched_spend"].append(dict(budget=b, L_B_solved=sum(at_budget(*LB[i], b) for i in valid), L_A_solved=sum(at_budget(*LA[i], b) for i in valid),
                                   redraw_ladder_solved=round(sum(sum(at_budget(*s, b) for s in BL[i]) / len(BL[i]) for i in valid), 1),
                                   redraw_120B_solved=round(sum(sum(at_budget(*s, b) for s in B120[i]) / len(B120[i]) for i in valid), 1),
                                   L_B_minus_ladder_pp=round(100 * sum(d) / len(d), 1), ci95_pp=boot_mean(d),
                                   L_A_minus_ladder_pp=round(100 * sum(dA) / len(dA), 1), ci95_A_pp=boot_mean(dA),
                                   L_B_minus_120B_pp=round(100 * sum(d120) / len(d120), 1), ci95_120_pp=boot_mean(d120)))

# ---- cost per solve
tot_B = sum(traj[i]["total_cost_usd"] for i in valid)
S["cost"] = dict(L_B_total=round(tot_B, 4), L_B_per_solve=round(tot_B / max(1, S["headline"]["L_B_resolved"]), 5),
                 L_A_total=round(sum(LA[i][0][3] for i in valid), 4),
                 L_A_per_solve=round(sum(LA[i][0][3] for i in valid) / max(1, S["headline"]["L_A_resolved"]), 5),
                 redraw_ladder_total=round(sum(sum(s[0][3] for s in BL[i]) / len(BL[i]) for i in valid), 4),
                 redraw_120B_x3_total=round(sum(sum(s[0][2] for s in B120[i]) / len(B120[i]) for i in valid), 4))
S["cost"]["redraw_ladder_per_solve"] = round(S["cost"]["redraw_ladder_total"] / S["headline"]["redraw_ladder_resolved_mean"], 5)
S["cost"]["redraw_120B_x3_per_solve"] = round(S["cost"]["redraw_120B_x3_total"] / S["headline"]["redraw_120B_x3_resolved_mean"], 5)


# ---- failure class per turn and what the next turn repaired
def turn_class(tr):
    s = tr.get("apply_status"); g = tr.get("grade") or {}
    if s in ("truncated_no_output",) or (tr.get("finish") == "length" and s != "applied"):
        return "loop"
    if s in ("no_blocks", "empty_output"):
        return "no_edit"
    if s in ("refused", "path_refused", "no_change"):
        return "apply_fail"
    if s == "applied":
        if g.get("resolved"):
            return "resolved"
        if g.get("applied") is False:
            return "patch_rejected_or_crash"
        if g.get("f2p_fail") == 0 and (g.get("f2p_pass") or 0) > 0:
            return "stopped_regressed"
        return "wrong_fix"
    return "other"


trans = collections.defaultdict(lambda: collections.Counter())
loops = collections.defaultdict(lambda: [0, 0])
for i in valid:
    turns = traj[i]["turns"]
    for k, tr in enumerate(turns):
        c = turn_class(tr)
        loops[(k + 1, tr["model"].split("/")[-1], tr["effort"])][1] += 1
        loops[(k + 1, tr["model"].split("/")[-1], tr["effort"])][0] += int(c == "loop")
        if k > 0:
            trans[turn_class(turns[k - 1])][c] += 1
S["turn_class_transitions"] = {p: dict(c) for p, c in trans.items()}
S["loop_rate_by_turn"] = {f"turn{k}_{m}_{e}": dict(loops=v[0], n=v[1], pct=round(100 * v[0] / v[1], 1)) for (k, m, e), v in sorted(loops.items())}
S["turn1_class"] = dict(collections.Counter(turn_class(traj[i]["turns"][0]) for i in valid))
# solved at turn k by previous failure class
rescued = collections.Counter(); attempted = collections.Counter()
for i in valid:
    turns = traj[i]["turns"]
    for k in range(1, len(turns)):
        prev = turn_class(turns[k - 1]); attempted[prev] += 1
        if turn_class(turns[k]) == "resolved":
            rescued[prev] += 1
S["repair_by_previous_failure"] = {p: dict(turns_attempted=attempted[p], resolved_next=rescued[p], pct=round(100 * rescued[p] / attempted[p], 1)) for p in attempted}

# ---- loop vs one-shot: tasks gained and lost relative to turn 1
S["tasks_resolved_after_turn1"] = sum(LB[i][1][0] for i in valid)
S["tasks_resolved_at_each_turn"] = [sum(LB[i][1][k] for i in valid) for k in range(4)]
S["stopped_but_regressed"] = [i for i in valid if traj[i]["stop"] == "stopped_f2p_pass_regressed"]
S["tasks_never_resolved_by_loop"] = len([i for i in valid if not traj[i]["resolved"]])
# solved by loop but by no draw in Revision 4 (any model) / solved by none at all
rev4_any = {i: any(cell[(i, m, d)]["resolved"] for m in PRICE for d in range(3)) for i in valid}
S["loop_resolved_not_in_any_rev4_draw"] = sorted(i for i in valid if traj[i]["resolved"] and not rev4_any[i])
S["rev4_any_draw_resolved_not_by_loop"] = sorted(i for i in valid if rev4_any[i] and not traj[i]["resolved"])


# ---- edit location of patches resolved at turn >= 2 (overlap with the gold region)
def hunks_old(diff):
    out = []
    for m in re.finditer(r"^@@ -(\d+)(?:,(\d+))? ", diff, re.M):
        a = int(m.group(1)); b = int(m.group(2) or 1)
        out.append((a, a + max(b, 1) - 1))
    return out


def overlap(d1, d2, pad=5):
    return any(a1 - pad <= b2 and a2 - pad <= b1 for a1, b1 in hunks_old(d1) for a2, b2 in hunks_old(d2))


def get_diff(iid, h):
    for base in ("loop_grading", "grading"):
        p = os.path.join(ROOT, "results", base, "logs", "run_evaluation", f"p100_{iid}_{h}", f"c{h}", iid, "patch.diff")
        if os.path.exists(p):
            return open(p, encoding="utf-8", errors="replace").read()
    return None


loc = collections.Counter()
for i in valid:
    turns = traj[i]["turns"]
    for k, tr in enumerate(turns):
        if tr.get("patch_hash") and (tr.get("grade") or {}).get("resolved") and k >= 1:
            d = get_diff(i, tr["patch_hash"])
            loc["resolved_turn>=2_overlaps_gold" if d and overlap(d, full[i]["gold_patch"]) else ("resolved_turn>=2_elsewhere" if d else "no_diff_found")] += 1
S["edit_location_of_rescued_patches"] = dict(loc)

# ---- tokens per turn
S["tokens_per_turn"] = {}
for k in range(4):
    x = [tr for i in valid for kk, tr in enumerate(traj[i]["turns"]) if kk == k and tr.get("completion_tokens") is not None]
    if x:
        S["tokens_per_turn"][k + 1] = dict(n=len(x), mean_prompt=round(sum(t["prompt_tokens"] for t in x) / len(x)), mean_completion=round(sum(t["completion_tokens"] for t in x) / len(x)),
                                            mean_cost=round(sum(t["cost_usd"] for t in x) / len(x), 5))

json.dump(S, open(os.path.join(OUT, "loop_summary.json"), "w"), indent=1)
print(json.dumps(S, indent=1))
