"""Report 18: recompute every headline number from raw stored data (graded states, trajectories) or from the committed
analysis JSON that the re-run analysis scripts reproduce byte-for-byte, and compare with the figures quoted in the report.
Writes reports/Report18/verified_numbers.json.  No model calls, no Docker.   python -X utf8 scripts/report18_data.py"""
import json, os, re, hashlib, collections, math
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "reports", "Report18")
R = lambda p: os.path.join(ROOT, p)


def jl(p):
    out = []
    for l in open(R(p), encoding="utf-8"):
        if l.strip():
            out.append(json.loads(l))
    return out


def last_by(p, key="iid"):
    d = {}
    for r in jl(p):
        d[r[key]] = r
    return d


def J(f):
    return json.load(open(R(f), encoding="utf-8"))


sha = lambda s: hashlib.sha1(s.encode()).hexdigest()[:10]
V = {}          # values used in the report
CHK = []        # verification rows


def check(what, quoted, recomputed, source, how, tol=0.051):
    if isinstance(quoted, (int, float)) and isinstance(recomputed, (int, float)):
        ok = abs(float(quoted) - float(recomputed)) <= tol
    else:
        ok = quoted == recomputed
    CHK.append(dict(what=what, quoted=quoted, recomputed=recomputed, source=source, how=how, status="match" if ok else "MISMATCH"))
    return ok


# ---------- A. design set, T=0, plain vs Argus apply (independent join of apply outputs with Docker grades)
G = {(r["iid"], r["hash"]): r for r in jl("results/grading/state.jsonl")}
S = J("results/analysis/summary.json")
bad = set(S["excluded_gold_failed"])
A = {}
for m in ("gpt-oss-20b", "gpt-oss-120b"):
    for arm in ("plain", "argus"):
        n = res = 0
        for r in jl(f"data/phase1/{arm}_apply_{m}.jsonl"):
            if r["iid"] in bad:
                continue
            n += 1
            if r.get("status") == "applied" and r.get("diff"):
                g = G.get((r["iid"], sha(r["diff"])))
                res += bool(g and g["resolved"])
        A[(m, arm)] = (n, res)
V["design_t0"] = {f"{m}:{arm}": v[1] for (m, arm), v in A.items()}
for (m, arm), (n, res) in A.items():
    check(f"Pilot-100 T=0 {m} {arm} resolved of 99", S[m][arm]["resolved"], res, "data/phase1/*_apply_*.jsonl + results/grading/state.jsonl",
          "join on (task, sha1(diff)[:10]); scripts/report18_data.py")
V["design_summary"] = S
V["deep"] = J("results/analysis/deep.json")
PRICE = {"gpt-oss-20b": (0.075, 0.30), "gpt-oss-120b": (0.15, 0.60)}   # $ per 1M in/out, Groq list (undated docs)
rec = jl("results/analysis/records.jsonl")
cost = collections.defaultdict(float)
lp = collections.defaultdict(float)
for r in rec:
    c = (r["prompt_tokens"] * PRICE[r["model"]][0] + r["completion_tokens"] * PRICE[r["model"]][1]) / 1e6
    cost[r["model"]] += c
    if r["finish"] == "length" and r["plain"] == "F1_budget_truncation":   # the 21 runs with no output
        lp[r["model"]] += c
V["t0_cost"] = dict(cost20=cost["gpt-oss-20b"], cost120=cost["gpt-oss-120b"], loop20=lp["gpt-oss-20b"])
V["t0_cost_per_solve"] = {"120B plain": cost["gpt-oss-120b"] / 44, "120B Argus": cost["gpt-oss-120b"] / 46,
                          "20B plain": cost["gpt-oss-20b"] / 31, "20B Argus": cost["gpt-oss-20b"] / 38}
check("20B first-pass spend at T=0 in $ (Report 3: 0.128)", 0.128, round(cost["gpt-oss-20b"], 3), "results/analysis/records.jsonl", "tokens x Groq list prices", tol=0.0011)
check("20B loop share of spend at T=0 in % (Report 3: 46)", 46, round(100 * lp["gpt-oss-20b"] / cost["gpt-oss-20b"], 0), "results/analysis/records.jsonl", "the 21 no-output truncated runs / all runs (counting the 22nd length-capped run with partial content gives 48%)", tol=1.01)
for k, q in (("120B plain", 0.00349), ("120B Argus", 0.00334), ("20B plain", 0.00414), ("20B Argus", 0.00338)):
    check(f"T=0 cost per solved task, {k} ($, Report 3)", q, round(V["t0_cost_per_solve"][k], 5), "results/analysis/records.jsonl", "tokens x Groq list prices / solved", tol=0.000006)
check("20B mean completion tokens T=0 (3094)", 3094, V["deep"]["tokens_gpt-oss-20b"]["mean_completion"], "results/analysis/deep.json", "scripts/deep_dive.py", tol=1)
check("120B mean completion tokens T=0 (1360)", 1360, V["deep"]["tokens_gpt-oss-120b"]["mean_completion"], "results/analysis/deep.json", "scripts/deep_dive.py", tol=1)

# ---------- B. temperature 1.0 re-baseline (committed JSON; analyze_t1.py re-run reproduces it, git diff empty)
T1 = J("results/analysis/t1_summary.json")
V["t1"] = T1
check("T=1 20B Argus minus plain (pp)", 5.7, T1["resolve"]["argus_minus_plain:gpt-oss-20b"]["mean_pp"], "results/analysis/t1_summary.json", "python -X utf8 scripts/analyze_t1.py", tol=0.051)
check("T=1 120B Argus minus plain (pp)", 3.4, T1["resolve"]["argus_minus_plain:gpt-oss-120b"]["mean_pp"], "results/analysis/t1_summary.json", "python -X utf8 scripts/analyze_t1.py", tol=0.051)
check("T=1 oracle O1 solves", 51.0, T1["oracle"]["single_draw_each"]["O1_model_choice_only"]["mean_solves"], "results/analysis/t1_summary.json", "scripts/analyze_t1.py")
check("T=1 test-gated cascade spend ($)", 0.222, T1["oracle"]["single_draw_each"]["cascade_test_gated"]["mean_spend"], "results/analysis/t1_summary.json", "scripts/analyze_t1.py", tol=0.0006)

# ---------- C. cross-family apply layer sweep (Report 6) and other families
SW = J("results/analysis/sweep_summary.json")
V["sweep"] = SW
check("Gemini 3.5 FL Argus minus plain per 100", 1.7, SW["resolved"]["gemini-3.5-flash-lite"]["argus_minus_plain"]["mean"], "results/analysis/sweep_summary.json", "python -X utf8 scripts/analyze_sweep.py", tol=0.051)
V["new_runs"] = J("results/analysis/new_runs_summary.json")

# ---------- D. feedback loops on the design set, recomputed from trajectories (solved within 3 attempts)
def solved_count(path, arm):
    d = last_by(path)
    return sum(1 for r in d.values() if r[arm]["solved"]), len(d)


L = {}
L["120B R"] = solved_count("data/loop2/trajectories.jsonl", "R")
L["120B F"] = solved_count("data/loop2/trajectories.jsonl", "F")
L["20B R"] = solved_count("data/loop2_20b/trajectories.jsonl", "R")
L["20B F"] = solved_count("data/loop2_20b/trajectories.jsonl", "F")
L["120B P8"] = solved_count("data/loop3/trajectories.jsonl", "P")
L["20B P9"] = solved_count("data/loop3_20b/trajectories.jsonl", "P")
L["120B P19"] = solved_count("data/loop4/trajectories.jsonl", "P")
L["20B P19"] = solved_count("data/loop4_20b/trajectories.jsonl", "P")
g = last_by("data/loop4_gemma26/trajectories.jsonl")
gf = last_by("data/loop_f_gemma26/trajectories.jsonl")
L["Gemma P19"] = (sum(r["P"]["solved"] for r in g.values()), len(g))
inter = [r for r in gf.values() if r["iid"] in g]
L["Gemma F"] = (sum(r["F"]["solved"] for r in inter), len(inter))
V["loops"] = {k: v[0] for k, v in L.items()}
V["loops_n"] = {k: v[1] for k, v in L.items()}
SRC = {"120B R": "data/loop2", "120B F": "data/loop2", "20B R": "data/loop2_20b", "20B F": "data/loop2_20b", "120B P8": "data/loop3",
       "20B P9": "data/loop3_20b", "120B P19": "data/loop4", "20B P19": "data/loop4_20b", "Gemma P19": "data/loop4_gemma26", "Gemma F": "data/loop_f_gemma26"}
for k, q in (("120B R", 59), ("120B F", 57), ("20B R", 47), ("20B F", 55), ("120B P8", 57), ("20B P9", 52), ("120B P19", 56), ("20B P19", 53),
             ("Gemma P19", 49), ("Gemma F", 43)):
    check(f"Design-set loop, solved within 3 attempts: {k} (n={L[k][1]})", q, L[k][0], SRC[k] + "/trajectories.jsonl", "count solved==True per task (last record per task)")


def parse_loop_f(fn):
    txt = open(os.path.join(OUT, "verify", fn), encoding="utf-8").read()
    out = {}
    for blk in re.split(r"\n=== ", "\n" + txt):
        m = re.match(r"(\w+) \[(all|excl api_error tasks)\] tasks=(\d+)", blk)
        if not m:
            continue
        d = dict(tasks=int(m.group(3)))
        for key, pat in (("plain", r"plain single-shot.*?([\d.]+)/100"), ("argus", r"Argus-apply single-shot.*?([\d.]+)/100"),
                         ("R", r"R loop <=3\s+([\d.]+)/100"), ("F", r"F loop <=3\s+([\d.]+)/100")):
            mm = re.search(pat, blk)
            d[key] = float(mm.group(1)) if mm else None
        mm = re.search(r"F-R = ([+\-][\d.]+)\s+CI\(([\-\d.]+), ([\-\d.]+)\)\s+F-only (\d+)\s+R-only (\d+)", blk)
        if mm:
            d.update(diff=float(mm.group(1)), ci=(float(mm.group(2)), float(mm.group(3))), fonly=int(mm.group(4)), ronly=int(mm.group(5)))
        out[(m.group(1), m.group(2))] = d
    return out


LF = parse_loop_f("analyze_loop_f_F.out")
LP = parse_loop_f("analyze_loop_f_P.out")
V["loop_f"] = {f"{k[0]}|{k[1]}": v for k, v in LF.items()}
V["loop_p17"] = {f"{k[0]}|{k[1]}": v for k, v in LP.items()}
check("Rev15 Gemma F-R (all tasks)", -1.0, LF[("gemma26", "all")]["diff"], "data/loop_f_gemma26 + data/gemma_sweep", "python -X utf8 scripts/analyze_loop_f.py")
check("Rev15 Qwen3.8 F-R", 0.0, LF[("qwen38", "all")]["diff"], "data/loop_f_qwen38 + data/qwen38", "python -X utf8 scripts/analyze_loop_f.py")
check("Rev17 Gemini 3.1 P-R (first session)", 9.0, LP[("gemini31", "all")]["diff"], "data/loop_p_gemini31", "ARM=P python -X utf8 scripts/analyze_loop_f.py")
gR = LF[("gemma26", "all")]["R"]
V["gemma_R_replay"] = gR
V["gemma_P_minus_Rreplay"] = round(100 * 49 / 99 - gR, 1)

# ---------- E. Revision 18 (Gemini replicates)
R18 = J("results/analysis/rev18_results.json")
V["rev18"] = R18


def rep_solved(arm, m, reps):
    tot = []
    for rp in reps:
        d = last_by(f"data/loop_{arm}_rep{rp}_{m}/trajectories.jsonl")
        tot.append(sum(r["F"]["solved"] for r in d.values()))
    return tot


V["rev18_means"] = {f"{m}:{a}": rep_solved(a, m, (1, 2)) for m in ("gemini31", "gemini35") for a in ("r", "f", "p")}
check("Rev18 gemini35 arm P mean of replicates (63)", 63, sum(V["rev18_means"]["gemini35:p"]) / 2, "data/loop_p_rep{1,2}_gemini35", "mean of solved per replicate")
check("Rev18 gemini31 arm R mean of replicates (57.5)", 57.5, sum(V["rev18_means"]["gemini31:r"]) / 2, "data/loop_r_rep{1,2}_gemini31", "mean of solved per replicate")

# ---------- F. blind test, recomputed from trajectories
rows = last_by("data/blind/trajectories.jsonl")
ids = sorted(i for i, r in rows.items() if r["gold"]["resolved"])
V["blind_n"] = len(ids)
V["blind_gold_failed"] = sorted(i for i, r in rows.items() if not r["gold"]["resolved"])
B = {}
for m in ("gpt-oss-20b", "gpt-oss-120b", "gemma-4-26b-a4b-it"):
    for a in ("R", "F"):
        B[f"{m}:{a}"] = sum(bool(rows[i]["models"][m][a]["solved"]) for i in ids)
V["blind"] = B
V["blind_report"] = J("results/analysis/blind_report_data.json")
for k, q in (("gpt-oss-20b:R", 97), ("gpt-oss-20b:F", 110), ("gpt-oss-120b:R", 108), ("gpt-oss-120b:F", 117), ("gemma-4-26b-a4b-it:R", 80), ("gemma-4-26b-a4b-it:F", 82)):
    check(f"Blind solved of 198: {k}", q, B[k], "data/blind/trajectories.jsonl", "count solved per arm over tasks whose gold control resolved")
check("Blind tasks analysed", 198, len(ids), "data/blind/trajectories.jsonl", "gold control resolved")

# ---------- G. localization recall (issue only)
LOC = J("data/loc/recall_summary.json")["results"]
V["loc"] = LOC
check("Localization recall@1, BM25 (of 100 tasks)", 27, LOC["L-B BM25"]["recall@1"], "data/loc/recall_summary.json", "python -X utf8 scripts/loc_recall.py (re-run: identical)")
check("Localization recall@1, Argus localizer (of 100 tasks)", 21, LOC["L-A Argus"]["recall@1"], "data/loc/recall_summary.json", "python -X utf8 scripts/loc_recall.py (re-run: identical)")

# ---------- H. E3 and false accepts
e3 = J("results/analysis/e3_all_verdicts.json")
cnt = collections.Counter(x["verdict"] for x in e3)
V["e3_reviewed"] = dict(cnt)
check("E3 reviewed patches (not rescued, not identical to gold)", 216, len(e3), "results/analysis/e3_all_verdicts.json", "count rows")
check("E3 wrong or fragile among the 216", 46, cnt["WRONG_OR_FRAGILE"], "results/analysis/e3_all_verdicts.json", "count verdicts")
PO = J("results/analysis/policies_summary.json")["part1_false_accepts"]
V["false_accept"] = PO
check("False-accept rate, 20B (target test passes, other tests break)", 0.12, PO["gpt-oss-20b"]["false_accept_rate"], "results/analysis/policies_summary.json", "python -X utf8 scripts/analyze_policies.py", tol=0.0051)

# ---------- I. Spearman (plain not-applied rate vs Argus gain), 8 models as listed in Revision 13
pts = {"gemini-3.1": (12.0, 3.0), "gemini-3.5": (17.7, 2.7), "gpt-oss-120b": (19.0, 5.3), "Qwen3.5-9B": (28.0, 10.0), "Qwen3.5-4B": (32.0, 10.0),
       "gpt-oss-20b": (33.7, 10.7), "gemma-26b": (50.7, 12.3), "Qwen3.5-2B": (73.0, 7.0)}


def rank(v):
    s = sorted(v)
    return [s.index(x) + (s.count(x) + 1) / 2 for x in v]


a = [p[0] for p in pts.values()]
b = [p[1] for p in pts.values()]
ra, rb = rank(a), rank(b)
ma, mb = sum(ra) / 8, sum(rb) / 8
rho = sum((x - ma) * (y - mb) for x, y in zip(ra, rb)) / math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
d2 = sum((x - y) ** 2 for x, y in zip(ra, rb))
rho_simple = 1 - 6 * d2 / (8 * 63)
V["spearman"] = dict(points=pts, tie_corrected=round(rho, 3), simple_formula=round(rho_simple, 3))
CHK.append(dict(what="Spearman, plain not-applied rate vs Argus gain, 8 models (CLAIM_STATUS says 0.71)", quoted=0.71, recomputed=round(rho, 2),
                source="the 8 value pairs listed in PILOT50_PROTOCOL.md Revision 13 (H5)",
                how="Pearson on average ranks; the simple 1-6*sum(d^2)/(n(n^2-1)) formula gives %.2f" % rho_simple, status="DIFFERS (0.73 recomputed)"))


# ---------- K. extra quantities used in tables: applied counts, attempts and spend per arm
AP = {}
for m in ("gpt-oss-20b", "gpt-oss-120b"):
    n_app = sum(1 for r in jl(f"data/phase1/plain_apply_{m}.jsonl") if r["iid"] not in bad and r.get("status") == "applied")
    AP[m] = n_app
V["t0_plain_applied"] = AP
check("T=0 plain applied patches 20B (Report 1: 58)", 58, AP["gpt-oss-20b"], "data/phase1/plain_apply_gpt-oss-20b.jsonl", "count status==applied (99 valid tasks)")
check("T=0 plain applied patches 120B (Report 1: 82)", 82, AP["gpt-oss-120b"], "data/phase1/plain_apply_gpt-oss-120b.jsonl", "count status==applied (99 valid tasks)")


def arm_stats(path, arm):
    d = last_by(path)
    n = len(d)
    return dict(n=n, solved=sum(r[arm]["solved"] for r in d.values()), attempts=sum(r[arm]["n"] for r in d.values()) / n, usd=sum(r[arm].get("cost_usd") or 0 for r in d.values()))


V["arm_stats"] = {"120B R": arm_stats("data/loop2/trajectories.jsonl", "R"), "120B F": arm_stats("data/loop2/trajectories.jsonl", "F"),
                  "20B R": arm_stats("data/loop2_20b/trajectories.jsonl", "R"), "20B F": arm_stats("data/loop2_20b/trajectories.jsonl", "F"),
                  "120B P19": arm_stats("data/loop4/trajectories.jsonl", "P"), "20B P19": arm_stats("data/loop4_20b/trajectories.jsonl", "P"),
                  "120B P8": arm_stats("data/loop3/trajectories.jsonl", "P"), "20B P9": arm_stats("data/loop3_20b/trajectories.jsonl", "P")}
bs = {}
for m in ("gpt-oss-20b", "gpt-oss-120b", "gemma-4-26b-a4b-it"):
    for a in ("R", "F"):
        xs = [rows[i]["models"][m][a] for i in ids]
        bs[f"{m}:{a}"] = dict(n=len(xs), solved=sum(bool(x["solved"]) for x in xs), attempts=sum(len(x["attempts"]) for x in xs) / len(xs), usd=sum((x.get("cost_usd") or 0) for x in xs),
                              attempt1_solved=sum(1 for x in xs if x["attempts"] and x["attempts"][0].get("state") == "accepted_resolved"))
V["blind_stats"] = bs
check("Blind 20B F spend in $ (BLIND_REPORT: 0.498)", 0.498, round(bs["gpt-oss-20b:F"]["usd"], 3), "data/blind/trajectories.jsonl", "sum cost_usd", tol=0.0011)
check("Blind 120B R spend in $ (BLIND_REPORT: 0.630)", 0.630, round(bs["gpt-oss-120b:R"]["usd"], 3), "data/blind/trajectories.jsonl", "sum cost_usd", tol=0.0011)
check("Blind 20B attempt-1 solved (BLIND_REPORT: 75)", 75, bs["gpt-oss-20b:R"]["attempt1_solved"], "data/blind/trajectories.jsonl", "state of attempt 1", tol=0.01)
# Revision 19: infrastructure losses and Gemma tasks
r19 = {}
for nm, pth in (("120B", "data/loop4"), ("20B", "data/loop4_20b"), ("Gemma", "data/loop4_gemma26")):
    d = last_by(pth + "/trajectories.jsonl")
    r19[nm] = dict(n=len(d), stops=dict(collections.Counter(r["P"]["stop"] for r in d.values())))
V["rev19_stops"] = r19

V["rev19"] = J("results/analysis/rev19_results.json")
json.dump(dict(V=V, checks=CHK), open(os.path.join(OUT, "verified_numbers.json"), "w", encoding="utf-8"), indent=1, default=str)
bad_ = [c for c in CHK if c["status"] != "match"]
print(f"{len(CHK)} checks, {len(bad_)} not exact:")
for c in bad_:
    print("  ", c["what"], c["quoted"], c["recomputed"], c["status"])
