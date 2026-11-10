"""Revision 4 analysis (temperature 1.0, 3 draws, 2 models), exactly the five items fixed in PILOT50_PROTOCOL.md.

Inputs : data/raw/phase2_t1_clean.jsonl (generation), data/phase2_t1/{plain,argus}_apply_*.jsonl,
         results/grading/state_t1.jsonl (Docker grades, keyed by task + sha1(diff)[:10]),
         results/grading/state.jsonl (gold control), results/analysis/records.jsonl (temperature-0 pilot outcomes).
Output : results/analysis/t1_summary.json and a printed report.
All figures are exploratory. Verifier used in retry simulations = the Docker result (a perfect, hidden-test verifier), which is an
upper bound for any real failing-test verifier; observable-only rules never read the Docker result.
"""
import collections, hashlib, itertools, json, os, random, statistics
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "results", "analysis")
MODELS = ("gpt-oss-20b", "gpt-oss-120b")
PRICE = {"gpt-oss-20b": (0.075, 0.30), "gpt-oss-120b": (0.15, 0.60)}  # $/1M tokens (in, out), Groq docs, undated
DRAWS = (0, 1, 2)
B = 2000
rng = random.Random(20261111)


def sha(d):
    return hashlib.sha1(d.encode()).hexdigest()[:10]


man = json.load(open(os.path.join(ROOT, "manifests", "pilot100_manifest.json"), encoding="utf-8"))
ids = [t["instance_id"] for t in man["primary"]]
gold = {}
for l in open(os.path.join(ROOT, "results", "grading", "state.jsonl"), encoding="utf-8"):
    r = json.loads(l)
    if "gold" in (r.get("labels") or []):
        gold[r["iid"]] = r
valid = [i for i in ids if gold.get(i, {}).get("resolved") is True]
excluded = [i for i in ids if i not in valid]

state = {}
for l in open(os.path.join(ROOT, "results", "grading", "state_t1.jsonl"), encoding="utf-8"):
    r = json.loads(l); state[(r["iid"], r["hash"])] = r

gen = {}
for l in open(os.path.join(ROOT, "data", "raw", "phase2_t1_clean.jsonl"), encoding="utf-8"):
    r = json.loads(l)
    assert r["http"] == 200
    gen[(r["iid"], r["model"].split("/")[-1], r["sample"])] = r
app = {}
for kind in ("plain", "argus"):
    for m in MODELS:
        for l in open(os.path.join(ROOT, "data", "phase2_t1", f"{kind}_apply_{m}.jsonl"), encoding="utf-8"):
            r = json.loads(l); app[(kind, r["iid"], m, r["sample"])] = r

# ---- per (arm, task, model, draw) outcome table
cell = {}
missing = 0
for kind in ("plain", "argus"):
    for i in valid:
        for m in MODELS:
            for d in DRAWS:
                g = gen[(i, m, d)]; a = app[(kind, i, m, d)]
                res = False
                if a["status"] == "applied":
                    s = state.get((i, sha(a["diff"])))
                    if s is None or s.get("resolved") is None:
                        missing += 1
                    else:
                        res = bool(s["resolved"])
                c = (g["prompt_tokens"] * PRICE[m][0] + g["completion_tokens"] * PRICE[m][1]) / 1e6
                cell[(kind, i, m, d)] = dict(resolved=res, status=a["status"], applied=a["status"] == "applied", loop=g["finish"] == "length",
                                             cost=c, ptok=g["prompt_tokens"], ctok=g["completion_tokens"])
assert missing == 0, f"{missing} applied patches without a grade"

S = dict(n_valid=len(valid), excluded=excluded)

# ---- (1) resolve rate per draw and mean, task-clustered bootstrap
def boot(stat_fn, tasks, reps=B):
    vals = []
    for _ in range(reps):
        samp = [tasks[rng.randrange(len(tasks))] for _ in range(len(tasks))]
        vals.append(stat_fn(samp))
    vals.sort()
    return [round(100 * vals[int(0.025 * reps)], 1), round(100 * vals[int(0.975 * reps) - 1], 1)]


def mean_rate(kind, m):
    return lambda samp: sum(cell[(kind, i, m, d)]["resolved"] for i in samp for d in DRAWS) / (len(samp) * len(DRAWS))


S["resolve"] = {}
for kind in ("plain", "argus"):
    for m in MODELS:
        per = [sum(cell[(kind, i, m, d)]["resolved"] for i in valid) for d in DRAWS]
        mean = mean_rate(kind, m)(valid)
        S["resolve"][f"{kind}:{m}"] = dict(per_draw=per, per_draw_pct=[round(100 * x / len(valid), 1) for x in per],
                                           mean_pct=round(100 * mean, 1), ci95=boot(mean_rate(kind, m), valid))
# Argus minus plain, paired by task
for m in MODELS:
    f = lambda samp, m=m: (mean_rate("argus", m)(samp) - mean_rate("plain", m)(samp))
    S["resolve"][f"argus_minus_plain:{m}"] = dict(mean_pp=round(100 * f(valid), 2), ci95_pp=boot(f, valid))
f = lambda samp: mean_rate("argus", "gpt-oss-120b")(samp) - mean_rate("argus", "gpt-oss-20b")(samp)
S["resolve"]["argus:120b_minus_20b"] = dict(mean_pp=round(100 * f(valid), 2), ci95_pp=boot(f, valid))

# temperature-0 reference (pilot records)
t0 = {}
for l in open(os.path.join(OUT, "records.jsonl"), encoding="utf-8"):
    r = json.loads(l); t0[(r["iid"], r["model"])] = r
S["t0_reference"] = {m: dict(plain=sum(t0[(i, m)]["plain"] == "PASS" for i in valid), argus=sum(t0[(i, m)]["argus"] == "PASS" for i in valid),
                             n=len(valid)) for m in MODELS}

# ---- (2) loop rate
S["loop"] = {}
for m in MODELS:
    n1 = sum(cell[("argus", i, m, d)]["loop"] for i in valid for d in DRAWS)
    n0 = sum(t0[(i, m)]["finish"] == "length" for i in valid)
    S["loop"][m] = dict(t1_loops=n1, t1_runs=len(valid) * 3, t1_pct=round(100 * n1 / (len(valid) * 3), 1),
                        t0_loops=n0, t0_runs=len(valid), t0_pct=round(100 * n0 / len(valid), 1),
                        t1_loop_tokens_share_of_spend_pct=round(100 * sum(cell[("argus", i, m, d)]["cost"] for i in valid for d in DRAWS if cell[("argus", i, m, d)]["loop"]) /
                                                              sum(cell[("argus", i, m, d)]["cost"] for i in valid for d in DRAWS), 1))
    lp = [i for i in valid if any(cell[("argus", i, m, d)]["loop"] for d in DRAWS)]
    S["loop"][m]["tasks_with_any_loop"] = len(lp)
    S["loop"][m]["tasks_looping_all_3_draws"] = sum(all(cell[("argus", i, m, d)]["loop"] for d in DRAWS) for i in valid)
    # were looping tasks the T0 loopers?
    S["loop"][m]["t0_loopers_that_loop_again_at_t1_any_draw"] = sum(1 for i in valid if t0[(i, m)]["finish"] == "length" and i in lp)
    S["loop"][m]["t0_loopers_n"] = n0

# ---- (3) per-task success probability (Argus arm)
S["per_task"] = {}
pt = {}
for m in MODELS:
    for i in valid:
        pt[(i, m)] = sum(cell[("argus", i, m, d)]["resolved"] for d in DRAWS) / 3
    c = collections.Counter(round(pt[(i, m)] * 3) for i in valid)
    S["per_task"][m] = dict(hist_k_of_3={k: c.get(k, 0) for k in range(4)},
                            always=c.get(3, 0), sometimes=c.get(1, 0) + c.get(2, 0), never=c.get(0, 0),
                            never_at_t0=sum(t0[(i, m)]["argus"] != "PASS" for i in valid),
                            t0_failed_solved_by_some_draw=sum(1 for i in valid if t0[(i, m)]["argus"] != "PASS" and pt[(i, m)] > 0),
                            t0_passed_not_solved_by_any_draw=sum(1 for i in valid if t0[(i, m)]["argus"] == "PASS" and pt[(i, m)] == 0))
neither_t0 = [i for i in valid if all(t0[(i, m)]["argus"] != "PASS" for m in MODELS)]
rec = [i for i in neither_t0 if any(pt[(i, m)] > 0 for m in MODELS)]
S["per_task"]["solved_by_neither_at_t0"] = dict(n=len(neither_t0), solved_by_some_t1_draw_any_model=len(rec), tasks=rec,
                                                 by_20b=sum(pt[(i, "gpt-oss-20b")] > 0 for i in neither_t0), by_120b=sum(pt[(i, "gpt-oss-120b")] > 0 for i in neither_t0))
union_any = [i for i in valid if any(pt[(i, m)] > 0 for m in MODELS)]
S["per_task"]["solvable_by_any_model_any_draw_t1"] = len(union_any)
S["per_task"]["solved_by_20b_not_by_120b_any_draw"] = sum(pt[(i, "gpt-oss-20b")] > 0 and pt[(i, "gpt-oss-120b")] == 0 for i in valid)
S["per_task"]["solved_by_120b_not_by_20b_any_draw"] = sum(pt[(i, "gpt-oss-120b")] > 0 and pt[(i, "gpt-oss-20b")] == 0 for i in valid)
# draw-to-draw agreement (is a failure a property of the task or of the draw?)
agree = {}
for m in MODELS:
    n_pairs = n_same = 0
    for i in valid:
        for d1, d2 in itertools.combinations(DRAWS, 2):
            n_pairs += 1; n_same += cell[("argus", i, m, d1)]["resolved"] == cell[("argus", i, m, d2)]["resolved"]
    agree[m] = round(100 * n_same / n_pairs, 1)
S["per_task"]["draw_pair_agreement_pct"] = agree


# ---- (4) oracle router in three parts, with and without multi-draw smoothing
def avg_cost(m):
    return {i: statistics.mean(cell[("argus", i, m, d)]["cost"] for d in DRAWS) for i in valid}


C = {m: avg_cost(m) for m in MODELS}
cheap, big = MODELS
order = sorted(MODELS, key=lambda m: sum(C[m].values()))  # cheapest first
S["oracle"] = {}


def one_draw_policies(d):
    """per-draw outcomes of fixed and oracle policies; solves and dollars"""
    out = {}
    for m in MODELS:
        out[f"always_{m}"] = (sum(cell[("argus", i, m, d)]["resolved"] for i in valid), sum(cell[("argus", i, m, d)]["cost"] for i in valid))
    # O1 model-choice only: one attempt per task, picks a solving model (cheapest solver); hopeless tasks still pay the cheapest model
    sv = sp = 0.0
    for i in valid:
        solvers = [m for m in MODELS if cell[("argus", i, m, d)]["resolved"]]
        if solvers:
            m = min(solvers, key=lambda m: cell[("argus", i, m, d)]["cost"]); sv += 1; sp += cell[("argus", i, m, d)]["cost"]
        else:
            m = min(MODELS, key=lambda m: cell[("argus", i, m, d)]["cost"]); sp += cell[("argus", i, m, d)]["cost"]
    out["O1_model_choice_only"] = (sv, sp)
    # O3 + skip-hopeless: hopeless tasks cost 0
    sv = sp = 0.0
    for i in valid:
        solvers = [m for m in MODELS if cell[("argus", i, m, d)]["resolved"]]
        if solvers:
            m = min(solvers, key=lambda m: cell[("argus", i, m, d)]["cost"]); sv += 1; sp += cell[("argus", i, m, d)]["cost"]
    out["O3_skip_hopeless"] = (sv, sp)
    # realizable: verifier-gated cascade cheap -> big (test as verifier), and observable-only cascade (escalate only if no patch applied)
    sv = sp = 0.0
    for i in valid:
        a = cell[("argus", i, cheap, d)]; sp += a["cost"]
        if a["resolved"]:
            sv += 1; continue
        b = cell[("argus", i, big, d)]; sp += b["cost"]; sv += b["resolved"]
    out["cascade_test_gated"] = (sv, sp)
    sv = sp = 0.0
    for i in valid:
        a = cell[("argus", i, cheap, d)]; sp += a["cost"]
        if a["applied"]:
            sv += a["resolved"]; continue
        b = cell[("argus", i, big, d)]; sp += b["cost"]; sv += b["resolved"]
    out["cascade_observable_only"] = (sv, sp)
    return out


per_draw = [one_draw_policies(d) for d in DRAWS]
S["oracle"]["single_draw_each"] = {}
for k in per_draw[0]:
    sv = [pd[k][0] for pd in per_draw]; sp = [pd[k][1] for pd in per_draw]
    S["oracle"]["single_draw_each"][k] = dict(solves_per_draw=sv, mean_solves=round(statistics.mean(sv), 1), mean_spend=round(statistics.mean(sp), 4),
                                              usd_per_solve=round(statistics.mean(sp) / statistics.mean(sv), 5))
# smoothed (expected-value) oracle: uses per-task success probability over the 3 draws, no lucky-draw picking
sm = {}
ev_sv = ev_sp = 0.0; ev3_sv = ev3_sp = 0.0
for i in valid:
    p = {m: pt[(i, m)] for m in MODELS}
    best = max(p.values())
    if best > 0:
        cands = [m for m in MODELS if p[m] == best]
        m = min(cands, key=lambda m: C[m][i])
        ev3_sv += best; ev3_sp += C[m][i]
    # O1 smoothed: hopeless tasks still pay cheapest model
    m1 = min([m for m in MODELS if p[m] == best], key=lambda m: C[m][i]) if best > 0 else min(MODELS, key=lambda m: C[m][i])
    ev_sv += best; ev_sp += C[m1][i]
sm["O1_model_choice_only_smoothed"] = dict(expected_solves=round(ev_sv, 1), spend=round(ev_sp, 4), usd_per_solve=round(ev_sp / ev_sv, 5))
sm["O3_skip_hopeless_smoothed"] = dict(expected_solves=round(ev3_sv, 1), spend=round(ev3_sp, 4), usd_per_solve=round(ev3_sp / ev3_sv, 5))
# O2 must-attempt-all with several attempts: the oracle may spend more than one attempt on a task. Expected solves when each task gets
# its best model; "all attempts paid": cost of one attempt per draw (3 attempts) on the best model for a task and 3 on each hopeless task
S["oracle"]["smoothed"] = sm
S["oracle"]["fixed_smoothed"] = {m: dict(expected_solves=round(sum(pt[(i, m)] for i in valid), 1), spend=round(sum(C[m].values()), 4),
                                         usd_per_solve=round(sum(C[m].values()) / sum(pt[(i, m)] for i in valid), 5)) for m in MODELS}
# oracle gap decomposition on the single-draw numbers: how much of the oracle's saving comes from (a) choosing the model, (b) skipping hopeless
sd = S["oracle"]["single_draw_each"]
S["oracle"]["decomposition_note"] = "O1 = pick the model per task but every task still gets one attempt; O3 = O1 plus skipping tasks nobody solves. O3 - O1 spend is the part of the oracle that is pure knowledge of hopelessness."
S["oracle"]["spend_O1_minus_O3"] = round(sd["O1_model_choice_only"]["mean_spend"] - sd["O3_skip_hopeless"]["mean_spend"], 4)

# ---- (5) stop-rule replays: sequential attempts on one model (draw order averaged over all 6 permutations), test-gated, K<=3 attempts
def sim(kind_fn, m, tasks, perms):
    """returns mean solves and mean spend; kind_fn(attempt, n_failed_so_far) -> True to continue after this FAILED attempt"""
    sv = sp = 0.0; n = 0
    for i in tasks:
        for p in perms:
            solved = False
            for k, d in enumerate(p):
                c = cell[("argus", i, m, d)]; sp += c["cost"]
                if c["resolved"]:
                    solved = True; break
                if not kind_fn(c, k + 1):
                    break
            sv += solved; n += 1
    return sv / len(perms), sp / len(perms), n


perms = list(itertools.permutations(DRAWS))
RULES = {
    "no_retry (K=1)": lambda c, k: False,
    "retry to K=2": lambda c, k: k < 2,
    "retry to K=3 (baseline)": lambda c, k: True,
    "stop_after_loop": lambda c, k: not c["loop"],
    "stop_after_no_patch (loop or apply failure)": lambda c, k: c["applied"],
    "stop_after_apply_failure (not loop)": lambda c, k: c["loop"] or c["applied"],
    "stop_after_patch_applied_but_failed": lambda c, k: not c["applied"],
}
S["stop_rules"] = {}
for m in MODELS:
    S["stop_rules"][m] = {}
    base_sv, base_sp, _ = sim(RULES["retry to K=3 (baseline)"], m, valid, perms)
    for name, fn in RULES.items():
        sv, sp, _ = sim(fn, m, valid, perms)
        S["stop_rules"][m][name] = dict(solves=round(sv, 2), spend=round(sp, 4),
                                        solves_lost_vs_K3=round(base_sv - sv, 2), spend_saved_vs_K3=round(base_sp - sp, 4),
                                        usd_per_solve=round(sp / sv, 5) if sv else None)

# cascades with retries (cheap first then big), observable and test-gated
def cascade(k_cheap, k_big, tasks, perms, gate):
    """expected solves and spend, averaged over draw orders. test gate: stop at first resolved attempt. observable gate: accept the first
    applied patch (no verifier) and escalate to the big model only if no cheap attempt produced an applied patch."""
    sv = sp = 0.0
    for i in tasks:
        for p in perms:
            solved = False
            for m, kmax in ((cheap, k_cheap), (big, k_big)):
                accepted = False
                for k in range(kmax):
                    c = cell[("argus", i, m, p[k])]; sp += c["cost"]
                    if gate == "test":
                        if c["resolved"]:
                            solved = True; break
                    elif c["applied"]:
                        solved = c["resolved"]; accepted = True; break
                if solved or accepted:
                    break
            sv += solved
    return sv / len(perms), sp / len(perms)


S["cascades"] = {}
for name, (kc, kb, gate) in {"20B x1 -> 120B x1 (test-gated)": (1, 1, "test"), "20B x3 -> 120B x1 (test-gated)": (3, 1, "test"),
                             "20B x3 -> 120B x3 (test-gated)": (3, 3, "test"), "20B x1 -> 120B x1 (observable-only: accept first applied patch)": (1, 1, "obs"),
                             "20B x3 -> 120B x3 (observable-only: accept first applied patch)": (3, 3, "obs")}.items():
    sv, sp = cascade(kc, kb, valid, perms, gate)
    S["cascades"][name] = dict(solves=round(sv, 2), spend=round(sp, 4), usd_per_solve=round(sp / sv, 5))

# early-abort token cap: threshold chosen on draws 0 and 1 (zero resolved runs lost), scored on draw 2
S["early_abort"] = {}
for m in MODELS:
    tune = [cell[("argus", i, m, d)] for i in valid for d in (0, 1)]
    mx_res = max((c["ctok"] for c in tune if c["resolved"]), default=0)
    grid = [2000, 3000, 4000, 5000, 6000, 7000, 8000]
    T = next((t for t in grid if t >= mx_res), 8000)
    ev = [cell[("argus", i, m, 2)] for i in valid]
    lost = sum(1 for c in ev if c["resolved"] and c["ctok"] > T)
    base_cost = sum(c["cost"] for c in ev)
    capped_cost = sum(((c["ptok"] * PRICE[m][0] + min(c["ctok"], T) * PRICE[m][1]) / 1e6) for c in ev)
    n_abort = sum(1 for c in ev if c["ctok"] > T)
    S["early_abort"][m] = dict(tuned_max_tokens_of_resolved_runs_draws01=mx_res, chosen_cap=T, draw3_runs_aborted=n_abort,
                               draw3_resolved_lost=lost, draw3_resolved=sum(c["resolved"] for c in ev), spend_before=round(base_cost, 4),
                               spend_after=round(capped_cost, 4), saved_pct=round(100 * (base_cost - capped_cost) / base_cost, 1),
                               aborted_runs_that_were_loops=sum(1 for c in ev if c["ctok"] > T and c["loop"]))
    # for reference: token distribution of resolved runs
    rt = sorted(c["ctok"] for c in (cell[("argus", i, m, d)] for i in valid for d in DRAWS) if c["resolved"])
    S["early_abort"][m]["resolved_tokens_p50_p90_p99_max"] = [rt[len(rt) // 2], rt[int(len(rt) * .9)], rt[int(len(rt) * .99)], rt[-1]]

# ---- plain vs argus apply layer at T1: where did the 52+ draws matter
S["apply_layer"] = {}
for m in MODELS:
    g = [(i, d) for i in valid for d in DRAWS if cell[("argus", i, m, d)]["resolved"] and not cell[("plain", i, m, d)]["resolved"]]
    l = [(i, d) for i in valid for d in DRAWS if cell[("plain", i, m, d)]["resolved"] and not cell[("argus", i, m, d)]["resolved"]]
    ao = [(i, d) for i in valid for d in DRAWS if cell[("argus", i, m, d)]["applied"] and not cell[("plain", i, m, d)]["applied"]]
    S["apply_layer"][m] = dict(draws_argus_gained_resolve=len(g), draws_argus_lost_resolve=len(l), argus_only_applied_draws=len(ao),
                               argus_only_applied_and_resolved=sum(cell[("argus", i, m, d)]["resolved"] for i, d in ao),
                               tasks_gained=sorted({i for i, _ in g}))
# conditional pass rate given applied
S["conditional_pass_given_applied"] = {m: round(100 * sum(cell[("argus", i, m, d)]["resolved"] for i in valid for d in DRAWS) /
                                              max(1, sum(cell[("argus", i, m, d)]["applied"] for i in valid for d in DRAWS)), 1) for m in MODELS}
S["apply_rate_pct"] = {m: round(100 * sum(cell[("argus", i, m, d)]["applied"] for i in valid for d in DRAWS) / (len(valid) * 3), 1) for m in MODELS}
S["spend_total_usd"] = {m: round(sum(cell[("argus", i, m, d)]["cost"] for i in valid for d in DRAWS), 4) for m in MODELS}

json.dump(S, open(os.path.join(OUT, "t1_summary.json"), "w"), indent=1)
print(json.dumps(S, indent=1))
