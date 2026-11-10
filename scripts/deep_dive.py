"""Second-level breakdowns for the Pilot-100 reports (reads results/analysis/records.jsonl + raw data; no model calls).
Writes results/analysis/deep.json and prints a readable summary."""
import collections, json, math, os, statistics as st, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(ROOT, "results", "analysis")
rows = [json.loads(l) for l in open(os.path.join(A, "records.jsonl"), encoding="utf-8")]
by = {(r["iid"], r["model"]): r for r in rows}
iids = sorted({r["iid"] for r in rows})
S = json.load(open(os.path.join(A, "summary.json")))


def binom2(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def mc(x, y, kind_x, kind_y, mx, my):
    """paired comparison of (model mx, arm kind_x) vs (model my, arm kind_y)"""
    only_x = sum(by[(i, mx)][kind_x] == "PASS" and by[(i, my)][kind_y] != "PASS" for i in iids)
    only_y = sum(by[(i, mx)][kind_x] != "PASS" and by[(i, my)][kind_y] == "PASS" for i in iids)
    both = sum(by[(i, mx)][kind_x] == "PASS" and by[(i, my)][kind_y] == "PASS" for i in iids)
    return dict(only_first=only_x, only_second=only_y, both=both, p=round(binom2(only_x, only_y), 4))


D = {}
M20, M120 = "gpt-oss-20b", "gpt-oss-120b"
D["mcnemar_20argus_vs_20plain"] = mc(0, 0, "argus", "plain", M20, M20)
D["mcnemar_120argus_vs_120plain"] = mc(0, 0, "argus", "plain", M120, M120)
D["mcnemar_20argus_vs_120plain"] = mc(0, 0, "argus", "plain", M20, M120)
D["mcnemar_20argus_vs_120argus"] = mc(0, 0, "argus", "argus", M20, M120)

# --- truncation (20B)
T = [i for i in iids if by[(i, M20)]["plain"] == "F1_budget_truncation"]
NT = [i for i in iids if i not in T]
D["trunc"] = dict(
    n=len(T),
    ids=T,
    outcome_120b_plain_on_T=dict(collections.Counter(by[(i, M120)]["plain"] for i in T)),
    pass_120b_on_T=sum(by[(i, M120)]["plain"] == "PASS" for i in T),
    pass_120b_on_nonT=sum(by[(i, M120)]["plain"] == "PASS" for i in NT),
    n_nonT=len(NT),
    pass_20b_on_nonT_plain=sum(by[(i, M20)]["plain"] == "PASS" for i in NT),
    pass_20b_on_nonT_argus=sum(by[(i, M20)]["argus"] == "PASS" for i in NT),
    repos=dict(collections.Counter(by[(i, M20)]["repo"] for i in T)),
    covered_fully_T=sum(by[(i, M20)]["covered_fully"] for i in T),
    median_prompt_T=st.median(by[(i, M20)]["prompt_tokens"] for i in T),
    median_prompt_nonT=st.median(by[(i, M20)]["prompt_tokens"] for i in NT),
    median_gold_lines_T=st.median(by[(i, M20)]["gold_changed"] for i in T),
    median_gold_lines_nonT=st.median(by[(i, M20)]["gold_changed"] for i in NT),
    median_reasoning_120b_on_T=st.median(by[(i, M120)]["reasoning_tokens"] or 0 for i in T),
    median_reasoning_120b_on_nonT=st.median(by[(i, M120)]["reasoning_tokens"] or 0 for i in NT),
)

# --- token usage
for m in (M20, M120):
    x = [r for r in rows if r["model"] == m]
    D["tokens_" + m] = dict(
        mean_completion=round(st.mean(r["completion_tokens"] or 0 for r in x)),
        median_completion=st.median(r["completion_tokens"] or 0 for r in x),
        mean_reasoning=round(st.mean(r["reasoning_tokens"] or 0 for r in x)),
        mean_prompt=round(st.mean(r["prompt_tokens"] or 0 for r in x)),
        finish=dict(collections.Counter(r["finish"] for r in x)),
    )
    # reasoning tokens by plain outcome
    g = collections.defaultdict(list)
    for r in x:
        g[r["plain"]].append(r["reasoning_tokens"] or 0)
    D["reasoning_by_outcome_" + m] = {k: dict(n=len(v), median=st.median(v), mean=round(st.mean(v))) for k, v in g.items()}

# --- wrong-fix anatomy (applied, not PASS)
for m in (M20, M120):
    x = [r for r in rows if r["model"] == m and r["plain"] in ("F7_wrong_fix", "F78_both", "F8_regression")]
    D["wrongfix_" + m] = dict(
        n=len(x),
        labels=dict(collections.Counter(r["plain"] for r in x)),
        hit_gold_region=sum(bool(r.get("plain_hits_gold_region")) for r in x),
        miss_gold_region=sum(not r.get("plain_hits_gold_region") for r in x),
        median_changed_lines=st.median(r.get("plain_changed_lines") or 0 for r in x),
        median_gold_lines=st.median(r["gold_changed"] for r in x),
        f2p_partial=sum(1 for r in x if r.get("plain_f2p") and r["plain_f2p"].split("/")[0] not in ("0", "None") and r["plain_f2p"].split("/")[0] != r["plain_f2p"].split("/")[1]),
    )
    ap = [r for r in rows if r["model"] == m and r["plain"] in ("PASS", "F7_wrong_fix", "F78_both", "F8_regression")]
    hit = [r for r in ap if r.get("plain_hits_gold_region")]
    miss = [r for r in ap if not r.get("plain_hits_gold_region")]
    D["region_pass_" + m] = dict(hit_n=len(hit), hit_pass=sum(r["plain"] == "PASS" for r in hit), miss_n=len(miss), miss_pass=sum(r["plain"] == "PASS" for r in miss))

# --- coverage effect
for m in (M20, M120):
    x = [r for r in rows if r["model"] == m and r["plain"] != "F1_budget_truncation"]
    out = {}
    for nm, cond in (("full", lambda r: r["covered_fully"]), ("partial", lambda r: (not r["covered_fully"]) and r["coverage"] > 0), ("zero", lambda r: r["coverage"] == 0)):
        y = [r for r in x if cond(r)]
        out[nm] = dict(n=len(y), plain_pass=sum(r["plain"] == "PASS" for r in y), argus_pass=sum(r["argus"] == "PASS" for r in y))
    D["coverage_nontrunc_" + m] = out
    D["ctxmode_" + m] = {k: dict(n=sum(1 for r in rows if r["model"] == m and r["ctx_mode"] == k),
                                 plain_pass=sum(1 for r in rows if r["model"] == m and r["ctx_mode"] == k and r["plain"] == "PASS"))
                         for k in sorted({r["ctx_mode"] for r in rows})}

# --- by repo (pass counts)
repos = sorted({r["repo"] for r in rows})
D["by_repo"] = {rp: {m: dict(n=sum(1 for r in rows if r["repo"] == rp and r["model"] == m),
                              plain=sum(1 for r in rows if r["repo"] == rp and r["model"] == m and r["plain"] == "PASS"),
                              argus=sum(1 for r in rows if r["repo"] == rp and r["model"] == m and r["argus"] == "PASS"))
                    for m in (M20, M120)} for rp in repos}

# --- Argus detail
for m in (M20, M120):
    x = [r for r in rows if r["model"] == m]
    D["argus_tiers_" + m] = dict(collections.Counter(r.get("argus_max_tier") for r in x if r["argus"] in ("PASS", "F7_wrong_fix", "F78_both", "F8_regression", "F5_harness_apply_fail")))
    # tasks where plain != argus label
    D["argus_changed_" + m] = [(r["iid"], r["plain"], r["argus"], r.get("argus_max_tier")) for r in x if r["plain"] != r["argus"]]
    D["plain_not_found_" + m] = [(r["iid"], r["argus"]) for r in x if r["plain"] == "F4_search_not_found"]
    D["plain_ambig_" + m] = [(r["iid"], r["argus"]) for r in x if r["plain"] == "F4_ambiguous"]
    D["argus_refused_other_" + m] = [r["iid"] for r in x if r["argus"] == "F4_refused_other"]

# --- ceiling analysis: how many failures are not recoverable at the apply stage
for m in (M20, M120):
    x = [r for r in rows if r["model"] == m]
    D["funnel_" + m] = dict(
        total=len(x),
        produced_output=sum(r["plain"] != "F1_budget_truncation" for r in x),
        parsed_and_addressed_target=sum(r["plain"] not in ("F1_budget_truncation", "F2_format", "F3_wrong_file") for r in x),
        plain_applied=sum(r["plain"] in ("PASS", "F7_wrong_fix", "F78_both", "F8_regression", "F5_syntax", "F5_harness_apply_fail", "F6_crash_all_tests") for r in x),
        argus_applied=sum(r["argus"] in ("PASS", "F7_wrong_fix", "F78_both", "F8_regression", "F5_syntax", "F5_harness_apply_fail", "F6_crash_all_tests") for r in x),
        plain_pass=sum(r["plain"] == "PASS" for r in x),
        argus_pass=sum(r["argus"] == "PASS" for r in x),
        pass_rate_given_plain_applied=None,
    )
    pa = D["funnel_" + m]["plain_applied"]; D["funnel_" + m]["pass_rate_given_plain_applied"] = round(100 * D["funnel_" + m]["plain_pass"] / pa, 1) if pa else None
    aa = D["funnel_" + m]["argus_applied"]; D["funnel_" + m]["pass_rate_given_argus_applied"] = round(100 * D["funnel_" + m]["argus_pass"] / aa, 1) if aa else None

# 20B tasks that 120B plain solves and 20B argus does not, split by 20B argus label
D["gap_after_argus_labels_20b"] = dict(collections.Counter(by[(i, M20)]["argus"] for i in iids if by[(i, M20)]["argus"] != "PASS" and by[(i, M120)]["argus"] == "PASS"))
D["both_fail_labels"] = {f"{a} | {b}": n for (a, b), n in collections.Counter((by[(i, M20)]["argus"], by[(i, M120)]["argus"]) for i in iids if by[(i, M20)]["argus"] != "PASS" and by[(i, M120)]["argus"] != "PASS").most_common(12)}
D["tasks_neither_model_applied_to_gold_region"] = sum(
    1 for i in iids if not (by[(i, M20)].get("argus_hits_gold_region") or by[(i, M120)].get("argus_hits_gold_region")))

# --- fairer baselines derived from the same frozen outputs (no re-grading needed: where a stronger plain tool and Argus
# apply the same text at the same place the resulting diff is identical, so the graded outcome is Argus's graded outcome)
NOT_APPLIED = ("F4_search_not_found", "F4_ambiguous", "F4_refused_other")
for m in (M20, M120):
    x = [r for r in rows if r["model"] == m]
    out = {}
    for nm, maxtier in (("plain_line_exact", 0), ("substring_exact", 1), ("plus_whitespace_norm", 2), ("argus_all_tiers", 3)):
        k = 0; app = 0
        gains = []
        for r in x:
            lab = r["plain"]
            if r["plain"] in NOT_APPLIED and r["argus"] not in NOT_APPLIED + ("F2_format", "F3_wrong_file") and (r.get("argus_max_tier") or 99) <= maxtier:
                lab = r["argus"]; gains.append((r["iid"], r.get("argus_max_tier"), lab))
            k += lab == "PASS"
        out[nm] = dict(pass_=k, gains=gains)
    D["baseline_ladder_" + m] = out
D["tier_of_applied_nonpass_and_pass_" + M20] = [(r["iid"], r.get("argus_max_tier"), r["argus"]) for r in rows if r["model"] == M20 and (r.get("argus_max_tier") or 0) >= 2]
D["tier_of_applied_nonpass_and_pass_" + M120] = [(r["iid"], r.get("argus_max_tier"), r["argus"]) for r in rows if r["model"] == M120 and (r.get("argus_max_tier") or 0) >= 2]

json.dump(D, open(os.path.join(A, "deep.json"), "w"), indent=1, default=str)
for k, v in D.items():
    print(k, json.dumps(v, default=str))
