"""Merge generation, plain apply, Argus apply and Docker grading into one table and compute the failure funnel.

Outputs results/analysis/records.jsonl (one row per task x model, both arms) and results/analysis/summary.json.
Labels (earliest stage that failed), per arm:
  F1_budget_truncation   model hit the output cap while reasoning, no answer
  F2_format              no parseable SEARCH/REPLACE block (or empty search)
  F3_wrong_file          edit addressed a file other than the target
  F4_search_not_found    SEARCH text not found
  F4_ambiguous           SEARCH text matched more than once (plain) / Argus refusal for ambiguity
  F4_refused_other       Argus refused for another reason (AST, margin, ...)
  F5_syntax              applied but does not parse
  F7_wrong_fix           applied; hidden target tests still fail, no regression
  F8_regression          target tests pass but previously-passing tests break
  F78_both               target tests fail and regressions
  F7_no_op               applied but changed nothing
  PASS                   official harness: resolved
  F0_harness             gold patch did not resolve (task excluded) or no grading report
"""
import collections, hashlib, json, math, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "results", "analysis")
os.makedirs(OUT, exist_ok=True)

man = json.load(open(os.path.join(ROOT, "manifests", "pilot100_manifest.json"), encoding="utf-8"))
ids = [t["instance_id"] for t in man["primary"]]
meta = {t["instance_id"]: t for t in man["primary"]}
full = {}
for l in open(r"C:\coding\Argus-research-archive\data\swe_bench_verified_tasks.jsonl", encoding="utf-8"):
    d = json.loads(l); full[d["instance_id"]] = d

gen = {}
for l in open(os.path.join(ROOT, "data", "raw", "phase1_file_medium_v1.jsonl"), encoding="utf-8"):
    r = json.loads(l); gen[(r["iid"], r["model"])] = r
apply = {}
for kind in ("plain", "argus"):
    for tag in ("gpt-oss-20b", "gpt-oss-120b"):
        for l in open(os.path.join(ROOT, "data", "phase1", f"{kind}_apply_{tag}.jsonl"), encoding="utf-8"):
            r = json.loads(l); apply[(kind, r["iid"], r["model"])] = r
state = {}
gold = {}
for l in open(os.path.join(ROOT, "results", "grading", "state.jsonl"), encoding="utf-8"):
    r = json.loads(l)
    state[(r["iid"], r["hash"])] = r
    if "gold" in (r.get("labels") or []):
        gold[r["iid"]] = r


def sha(d):
    return hashlib.sha1(d.encode()).hexdigest()[:10]


def hunks_old(diff):
    out = []
    for m in re.finditer(r"^@@ -(\d+)(?:,(\d+))? ", diff, re.M):
        a = int(m.group(1)); b = int(m.group(2) or 1)
        out.append((a, a + max(b, 1) - 1))
    return out


def overlap(d1, d2, pad=5):
    h1, h2 = hunks_old(d1), hunks_old(d2)
    return any(a1 - pad <= b2 and a2 - pad <= b1 for a1, b1 in h1 for a2, b2 in h2)


def label(kind, iid, model):
    a = apply[(kind, iid, model)]
    st = a["status"]
    if st == "truncated_no_output":
        return "F1_budget_truncation", None
    if st in ("empty_output", "no_blocks", "empty_search"):
        return "F2_format", None
    if st in ("wrong_file", "path_refused"):
        return "F3_wrong_file", None
    if st == "no_match":
        return "F4_search_not_found", None
    if st == "ambiguous":
        return "F4_ambiguous", None
    if st == "refused":
        rr = (a.get("refusal_reason") or "").upper()
        if "AMBIG" in rr:
            return "F4_ambiguous", None
        if "NO_MATCH" in rr or "NOT_FOUND" in rr:
            return "F4_search_not_found", None
        return "F4_refused_other", None
    if st == "no_change":
        return "F7_no_op", None
    if st == "applied":
        g = state.get((iid, sha(a["diff"])))
        if kind == "plain" and a.get("ast_ok") is False:
            return "F5_syntax", g
        if not g or g.get("resolved") is None:
            return "F0_harness", g
        if g["resolved"]:
            return "PASS", g
        f2p_fail, p2p_fail = g.get("f2p_fail", 0), g.get("p2p_fail", 0)
        if not g.get("applied"):
            return "F5_harness_apply_fail", g
        if f2p_fail and p2p_fail:
            return "F78_both", g
        if p2p_fail:
            return "F8_regression", g
        return "F7_wrong_fix", g
    return "F0_harness", None


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(100 * (c - h), 1), round(100 * (c + h), 1))


def binom2(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


# gold validity (F0): task is excluded if the gold patch did not resolve in the harness
excluded = sorted(i for i in ids if i in gold and gold[i].get("resolved") is not True)
pending = [i for i in ids if i not in gold]
valid = [i for i in ids if i in gold and gold[i].get("resolved") is True]

rows = []
for iid in valid:
    for model in ("openai/gpt-oss-20b", "openai/gpt-oss-120b"):
        g = gen[(iid, model)]
        row = dict(iid=iid, model=model.split("/")[-1], repo=full[iid]["repo"], coverage=g["ctx"]["coverage"], covered_fully=g["ctx"]["covered_fully"],
                   ctx_mode=g["ctx"]["mode"], reasoning_tokens=g.get("reasoning_tokens"), completion_tokens=g.get("completion_tokens"),
                   prompt_tokens=g.get("prompt_tokens"), finish=g.get("finish"), gold_changed=meta[iid]["gold_changed_lines"])
        for kind in ("plain", "argus"):
            lab, gr = label(kind, iid, model)
            row[kind] = lab
            a = apply[(kind, iid, model)]
            if a["status"] == "applied":
                row[kind + "_changed_lines"] = a.get("changed_lines")
                row[kind + "_hits_gold_region"] = overlap(a["diff"], full[iid]["gold_patch"])
                if kind == "argus":
                    row["argus_max_tier"] = a.get("max_tier")
            if gr:
                row[kind + "_f2p"] = f"{gr.get('f2p_pass')}/{(gr.get('f2p_pass') or 0) + (gr.get('f2p_fail') or 0)}"
                row[kind + "_p2p_fail"] = gr.get("p2p_fail")
        rows.append(row)
with open(os.path.join(OUT, "records.jsonl"), "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")

S = dict(n_tasks=len(ids), valid_tasks=len(valid), excluded_gold_failed=excluded, pending_gold=len(pending))
for model in ("gpt-oss-20b", "gpt-oss-120b"):
    x = [r for r in rows if r["model"] == model]
    n = len(x)
    S[model] = {}
    for kind in ("plain", "argus"):
        c = collections.Counter(r[kind] for r in x)
        k = c.get("PASS", 0)
        S[model][kind] = dict(n=n, labels=dict(c.most_common()), resolved=k, rate=round(100 * k / n, 1) if n else None, wilson=wilson(k, n))
    # by coverage
    for nm, cond in (("fully_covered", lambda r: r["covered_fully"]), ("not_fully", lambda r: not r["covered_fully"]), ("zero_cov", lambda r: r["coverage"] == 0)):
        y = [r for r in x if cond(r)]
        S[model]["cov_" + nm] = dict(n=len(y), plain_pass=sum(r["plain"] == "PASS" for r in y), argus_pass=sum(r["argus"] == "PASS" for r in y))
S["paired_plain_20_vs_120"] = None
a = {r["iid"]: r for r in rows if r["model"] == "gpt-oss-20b"}
b = {r["iid"]: r for r in rows if r["model"] == "gpt-oss-120b"}
for kind in ("plain", "argus"):
    both = sum(a[i][kind] == "PASS" and b[i][kind] == "PASS" for i in a if i in b)
    only20 = sum(a[i][kind] == "PASS" and b[i][kind] != "PASS" for i in a if i in b)
    only120 = sum(a[i][kind] != "PASS" and b[i][kind] == "PASS" for i in a if i in b)
    S["paired_" + kind] = dict(both=both, only_20b=only20, only_120b=only120, neither=len(a) - both - only20 - only120, p_exact_two_sided=round(binom2(only20, only120), 4))
    S["gap_tasks_" + kind] = sorted(i for i in a if i in b and a[i][kind] != "PASS" and b[i][kind] == "PASS")
# Argus vs plain deltas
for model in ("gpt-oss-20b", "gpt-oss-120b"):
    x = [r for r in rows if r["model"] == model]
    S[model]["argus_gained_pass"] = sorted(r["iid"] for r in x if r["plain"] != "PASS" and r["argus"] == "PASS")
    S[model]["argus_lost_pass"] = sorted(r["iid"] for r in x if r["plain"] == "PASS" and r["argus"] != "PASS")
    S[model]["argus_newly_applied"] = sorted(r["iid"] for r in x if r["plain"].startswith(("F4", "F2")) and r["argus"] not in ("F4_search_not_found", "F4_ambiguous", "F4_refused_other", "F2_format", "F3_wrong_file"))
    S[model]["argus_newly_refused"] = sorted(r["iid"] for r in x if r["plain"] in ("PASS", "F7_wrong_fix", "F8_regression", "F78_both") and r["argus"].startswith("F4"))
json.dump(S, open(os.path.join(OUT, "summary.json"), "w"), indent=1)
print(json.dumps({k: v for k, v in S.items() if k in ("n_tasks", "valid_tasks", "excluded_gold_failed", "pending_gold")}, indent=1))
for model in ("gpt-oss-20b", "gpt-oss-120b"):
    print(model)
    for kind in ("plain", "argus"):
        d = S[model][kind]; print("  ", kind, "resolved", d["resolved"], "/", d["n"], d["wilson"], d["labels"])
