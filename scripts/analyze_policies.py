"""Exploratory (not pre-registered): fair baselines for allocation policies, and verifier false accepts.

Replays recorded draws (Argus apply arm, 100 tasks x 3 draws x 4 models) under sequential policies "try model A, then B, ..., stop when the
verifier accepts". Same-model re-draw policies (A, A, A) use distinct recorded draws; the expectation is taken over all assignments of draw
indices (3 choose ordered per model), per task, so policies are not tied to a lucky draw order.

Verifier modes
  perfect : accept iff the full harness resolves the patch (upper bound, no false accepts)
  target  : accept iff every FAIL_TO_PASS test passes (what a loop that stops at the first passing test sees); the task counts as solved
            only if that accepted patch is actually resolved, so false accepts cost both money and correctness.

Part 1: false-accept rate of the target-test verifier per model.  Part 2: policy table with task-clustered bootstrap for named contrasts.

  python -X utf8 scripts/analyze_policies.py   -> results/analysis/policies_summary.json
"""
import collections, hashlib, itertools, json, os, random, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDS = json.load(open(os.path.join(ROOT, "data", "gemini_sweep", "task_ids_full.json")))["ids"]
IDSET = set(IDS)
MODELS = ["gpt-oss-20b", "gpt-oss-120b", "gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]
SHORT = {"gpt-oss-20b": "20B", "gpt-oss-120b": "120B", "gemini-3.1-flash-lite": "G3.1", "gemini-3.5-flash-lite": "G3.5"}
PRICE = {"gpt-oss-20b": (0.075, 0.30), "gpt-oss-120b": (0.15, 0.60), "gemini-3.1-flash-lite": (0.25, 1.50), "gemini-3.5-flash-lite": (0.30, 2.50)}
K = 3


def load(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")] if os.path.exists(p) else []


def sha(s):
    return hashlib.sha1(s.encode()).hexdigest()[:10]


# grades: (iid, hash) -> (resolved, f2p_ok)
G = {}
for f in ("state_t1.jsonl", "state.jsonl", "state_new.jsonl"):
    for r in load(os.path.join(ROOT, "results", "grading", f)):
        if r.get("hash") and r.get("resolved") is not None:
            G[(r["iid"], r["hash"])] = (bool(r["resolved"]), bool(r.get("applied")) and r.get("f2p_fail") == 0 and (r.get("f2p_pass") or 0) > 0, r.get("p2p_fail"))
for f in (os.path.join(ROOT, "data", "probe_gemini", "grading.jsonl"), os.path.join(ROOT, "data", "gemini_sweep", "grading.jsonl")):
    for r in load(f):
        if r.get("h") and r.get("resolved") is not None:
            G[(r["iid"], r["h"])] = (bool(r["resolved"]), bool(r.get("applied")) and r.get("f2p_fail") == 0 and (r.get("f2p_pass") or 0) > 0, r.get("p2p_fail"))

# draws: X[m][(iid,k)] = dict(res, acc, cost)
X = {m: {} for m in MODELS}


def add(m, k, arec, cost):
    if arec["status"] == "applied":
        res, acc, _ = G[(k[0], sha(arec["diff"]))]
    else:
        res = acc = False
    X[m][k] = dict(res=res, acc=acc, cost=cost, applied=arec["status"] == "applied")


for m in MODELS[:2]:
    for raw, ad in ((os.path.join(ROOT, "data", "raw", "phase2_t1_clean.jsonl"), os.path.join(ROOT, "data", "phase2_t1")),
                    (os.path.join(ROOT, "data", "raw", "phase2_t1_repl.jsonl"), os.path.join(ROOT, "data", "phase2_t1_repl"))):
        ar = {(r["iid"], r["sample"]): r for r in load(os.path.join(ad, f"argus_apply_{m}.jsonl"))}
        for g in load(raw):
            if g["model"].endswith(m) and g["iid"] in IDSET and g.get("http") == 200:
                k = (g["iid"], g["sample"]); pin, pout = PRICE[m]
                add(m, k, ar[k], ((g.get("prompt_tokens") or 0) * pin + (g.get("completion_tokens") or 0) * pout) / 1e6)
for m in MODELS[2:]:
    ar = {(r["iid"], r["sample"]): r for r in load(os.path.join(ROOT, "data", "gemini_sweep", "apply", f"argus_apply_{m}.jsonl"))}
    for g in load(os.path.join(ROOT, "data", "gemini_sweep", "raw.jsonl")):
        if g["model"].endswith(m) and g.get("http") == 200:
            k = (g["iid"], g["sample"]); u = g["usage_raw"]; pin, pout = PRICE[m]
            add(m, k, ar[k], (u["prompt_tokens"] * pin + (u["total_tokens"] - u["prompt_tokens"]) * pout) / 1e6)
for m in MODELS:
    assert all((i, k) in X[m] for i in IDS for k in range(K)), m

out = {}
# ---------------- Part 1: false accepts of a target-test-only verifier
fa = {}
for m in MODELS:
    acc = [d for d in X[m].values() if d["acc"]]
    false = [d for d in acc if not d["res"]]
    appl = [d for d in X[m].values() if d["applied"]]
    fa[m] = dict(applied=len(appl), target_test_pass=len(acc), resolved=sum(d["res"] for d in acc), false_accepts=len(false),
                 false_accept_rate=round(len(false) / len(acc), 3) if acc else None,
                 target_pass_rate_given_applied=round(len(acc) / len(appl), 3), resolved_rate_given_applied=round(sum(d["res"] for d in appl) / len(appl), 3))
out["part1_false_accepts"] = fa

# ---------------- Part 2: sequential policies
def assignments(policy):
    """all ways to give each position a draw index; same-model positions get distinct indices"""
    by = collections.defaultdict(list)
    for pos, m in enumerate(policy):
        by[m].append(pos)
    per_model = []
    for m, poss in by.items():
        per_model.append([(poss, perm) for perm in itertools.permutations(range(K), len(poss))])
    for combo in itertools.product(*per_model):
        idx = [None] * len(policy)
        for poss, perm in combo:
            for p, k in zip(poss, perm):
                idx[p] = k
        yield idx


def per_task(policy, mode):
    """-> (solved[task], cost[task]) expectations over draw-index assignments"""
    asg = list(assignments(policy))
    sol, cst = [], []
    for i in IDS:
        s_acc = c_acc = 0.0
        for idx in asg:
            c = 0.0; ok = 0
            for m, k in zip(policy, idx):
                d = X[m][(i, k)]
                c += d["cost"]
                if (d["res"] if mode == "perfect" else d["acc"]):
                    ok = 1 if d["res"] else 0
                    break
            s_acc += ok; c_acc += c
        sol.append(s_acc / len(asg)); cst.append(c_acc / len(asg))
    return sol, cst


rng = random.Random(20261112)
BOOT = [[rng.randrange(len(IDS)) for _ in IDS] for _ in range(4000)]


def summ(sol, cst):
    return dict(solved=round(sum(sol), 2), usd=round(sum(cst), 4))


def diff_ci(a, b):
    """paired task-clustered bootstrap of (a - b) in solved and usd; a,b = (sol,cst)"""
    ds = sorted(sum(a[0][j] - b[0][j] for j in bs) for bs in BOOT)
    dc = sorted(sum(a[1][j] - b[1][j] for j in bs) for bs in BOOT)
    n = len(BOOT)
    return dict(solved=round(sum(a[0]) - sum(b[0]), 2), solved_ci95=[round(ds[int(.025 * n)], 2), round(ds[int(.975 * n) - 1], 2)],
                usd=round(sum(a[1]) - sum(b[1]), 4), usd_ci95=[round(dc[int(.025 * n)], 4), round(dc[int(.975 * n) - 1], 4)])


order = ["gpt-oss-20b", "gpt-oss-120b", "gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]
policies = {}
for m in MODELS:
    for n in (1, 2, 3):
        policies[f"{SHORT[m]}x{n}"] = [m] * n
for r in (2, 3, 4):
    for combo in itertools.combinations(order, r):
        policies["->".join(SHORT[x] for x in combo)] = list(combo)
policies["120Bx2->G3.1"] = ["gpt-oss-120b", "gpt-oss-120b", "gemini-3.1-flash-lite"]
policies["20B->120Bx2"] = ["gpt-oss-20b", "gpt-oss-120b", "gpt-oss-120b"]
policies["20Bx2->120B"] = ["gpt-oss-20b", "gpt-oss-20b", "gpt-oss-120b"]
policies["G3.1x2->120B"] = ["gemini-3.1-flash-lite", "gemini-3.1-flash-lite", "gpt-oss-120b"]

cache, table = {}, {}
for mode in ("perfect", "target"):
    table[mode] = {}
    for name, pol in policies.items():
        cache[(mode, name)] = per_task(pol, mode)
        table[mode][name] = dict(attempts_max=len(pol), **summ(*cache[(mode, name)]))
out["part2_policies"] = table

contrasts = [("20B->120B->G3.1", "120Bx3"), ("20B->120B->G3.1", "120Bx2->G3.1"), ("120B->G3.1", "120Bx2"), ("20B->120B", "120Bx2"),
             ("20B->120B->G3.1->G3.5", "120Bx3"), ("120B->G3.1->G3.5", "120Bx3"), ("G3.1->G3.5", "G3.1x2"), ("120B->G3.5", "120Bx2"),
             ("20B->120B->G3.1", "G3.1x3")]
out["part2_contrasts_a_minus_b"] = {mode: {f"{a} vs {b}": diff_ci(cache[(mode, a)], cache[(mode, b)]) for a, b in contrasts} for mode in ("perfect", "target")}
json.dump(out, open(os.path.join(ROOT, "results", "analysis", "policies_summary.json"), "w", encoding="utf-8"), indent=1)
print(json.dumps(out["part1_false_accepts"], indent=1))
for mode in ("perfect", "target"):
    print("\n==", mode)
    for n, v in sorted(table[mode].items(), key=lambda x: x[1]["usd"]):
        print(f"{n:28s} attempts<={v['attempts_max']} solved {v['solved']:6.2f} usd {v['usd']:.4f}")
    for k, v in out["part2_contrasts_a_minus_b"][mode].items():
        print(k, v)
