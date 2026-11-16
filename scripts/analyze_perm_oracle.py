"""Perfect-router (oracle) gap versus an exchangeable-models permutation reference.
Reuses the per-(task, model, draw) outcome table of analyze_t1.py (argus apply layer, T=1.0, 3 draws, 99 valid tasks).
Gap = mean over draws of [tasks solved by at least one of the two models in that draw] - [tasks solved by the better fixed model in that draw]."""
import os, random, json, itertools, statistics
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(ROOT, "scripts", "analyze_t1.py"), encoding="utf-8").read().split("S = dict(n_valid")[0]
ns = {"__file__": os.path.join(ROOT, "scripts", "analyze_t1.py")}
exec(compile(src, "analyze_t1_head", "exec"), ns)
cell, valid, MODELS, DRAWS = ns["cell"], ns["valid"], ns["MODELS"], ns["DRAWS"]
A, B = MODELS  # 20b, 120b
Y = {m: [[int(cell[("argus", i, m, d)]["resolved"]) for d in DRAWS] for i in valid] for m in MODELS}
n = len(valid)

def gap(ya, yb, idx=None):
    idx = range(n) if idx is None else idx
    tot = []
    for d in range(3):
        sa = sum(ya[i][d] for i in idx); sb = sum(yb[i][d] for i in idx)
        un = sum(1 for i in idx if ya[i][d] or yb[i][d])
        tot.append(un - max(sa, sb))
    return statistics.mean(tot)

obs = gap(Y[A], Y[B])
rng = random.Random(20261116)
# permutation reference: swap the two models' outcome vectors per task with probability 1/2 (models exchangeable)
R = 20000; null = []
for _ in range(R):
    ya, yb = [], []
    for i in range(n):
        if rng.random() < .5: ya.append(Y[B][i]); yb.append(Y[A][i])
        else: ya.append(Y[A][i]); yb.append(Y[B][i])
    null.append(gap(ya, yb))
null.sort()
pct = sum(1 for x in null if x <= obs) / R
# bootstrap CI of observed gap over tasks
boot = []
for _ in range(5000):
    idx = [rng.randrange(n) for _ in range(n)]
    boot.append(gap(Y[A], Y[B], idx))
boot.sort()
# same-model second draw: union of two independent draws of one model minus one draw
def second_draw(ym, idx=None):
    idx = range(n) if idx is None else idx
    vals = []
    for d1, d2 in itertools.combinations(range(3), 2):
        for a, b in ((d1, d2), (d2, d1)):
            vals.append(sum(1 for i in idx if ym[i][a] or ym[i][b]) - sum(ym[i][a] for i in idx))
    return statistics.mean(vals)
sd = {m: second_draw(Y[m]) for m in MODELS}
diffs = []
for _ in range(5000):
    idx = [rng.randrange(n) for _ in range(n)]
    diffs.append(gap(Y[A], Y[B], idx) - second_draw(Y[B], idx))
diffs.sort()
res = dict(n_tasks=n,
    solves_per_model={m: statistics.mean(sum(Y[m][i][d] for i in range(n)) for d in range(3)) for m in MODELS},
    observed_gap=round(obs, 2), observed_gap_ci95=[round(boot[125], 2), round(boot[4875], 2)],
    exchangeable_null_mean=round(statistics.mean(null), 2), null_2p5_97p5=[round(null[int(.025 * R)], 2), round(null[int(.975 * R)], 2)],
    observed_percentile_in_null=round(pct, 3),
    same_model_second_draw_gain={m: round(v, 2) for m, v in sd.items()},
    cross_model_minus_second_120b_draw=round(obs - sd[B], 2), cross_minus_second_ci95=[round(diffs[125], 2), round(diffs[4875], 2)],
    tasks_solved_by_20b_not_by_120b_in_same_draw=statistics.mean(sum(1 for i in range(n) if Y[A][i][d] and not Y[B][i][d]) for d in range(3)),
    tasks_solved_by_120b_not_by_20b_in_same_draw=statistics.mean(sum(1 for i in range(n) if Y[B][i][d] and not Y[A][i][d]) for d in range(3)))
print(json.dumps(res, indent=1))
json.dump(res, open(os.path.join(ROOT, "results", "analysis", "perm_oracle_gap.json"), "w"), indent=1)
