"""Revision 10 analysis: Qwen size-ladder probe. Applies each outputs_*.jsonl (plain and Argus), classifies why edits fail, and compares with the
predictions written in PILOT50_PROTOCOL.md before any output. No Docker grading.

  python -X utf8 scripts/analyze_qwen_probe.py [dir]   (default data/qwen_probe/kaggle_run1) -> results/analysis/qwen_probe_summary.json
"""
import collections, json, os, re, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D_IN = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(ROOT, "data", "qwen_probe", "kaggle_run1")
APPLY = os.path.join(D_IN, "apply")
os.makedirs(APPLY, exist_ok=True)

# reuse the helper functions of analyze_failures.py (everything before Part A)
src = open(os.path.join(ROOT, "scripts", "analyze_failures.py"), encoding="utf-8").read().split("# ---------------- Part A")[0]
g = {"__file__": os.path.join(ROOT, "scripts", "analyze_failures.py")}
exec(compile(src, "analyze_failures_helpers", "exec"), g)
parse, find_all, source_lines, squash, classify = g["parse"], g["find_all"], g["source_lines"], g["squash"], g["classify"]


def load(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")] if os.path.exists(p) else []


def indent_kind(F, S):
    """for a whitespace-only failure: which kind(s) of difference"""
    Fn = [(i, squash(x)) for i, x in enumerate(F) if x.strip()]
    Sn = [squash(x) for x in S if x.strip()]
    seq = [x for _, x in Fn]
    hit = [j for j in range(len(seq) - len(Sn) + 1) if seq[j:j + len(Sn)] == Sn] if Sn else []
    if not hit:
        return "unknown"
    j = hit[0]; idx = [Fn[j + t][0] for t in range(len(Sn))]
    W = [F[i] for i in idx]; Se = [x for x in S if x.strip()]
    kinds = set()
    if any(a.lstrip() == b.lstrip() and (len(a) - len(a.lstrip())) != (len(b) - len(b.lstrip())) for a, b in zip(Se, W)):
        kinds.add("indent")
    if len(S) != len(Se) or (idx[-1] - idx[0] + 1) != len(idx):
        kinds.add("blank_lines")
    return "+".join(sorted(kinds)) or "internal_ws"


out = {}
for fn in sorted(f for f in os.listdir(D_IN) if f.startswith("outputs_") and f.endswith(".jsonl")):
    raw = os.path.join(D_IN, fn)
    recs = load(raw)
    for r in recs:  # apply scripts expect these fields
        r.setdefault("sample", 0); r.setdefault("http", 200)
    tmp = os.path.join(APPLY, "in_" + fn)
    open(tmp, "w", encoding="utf-8").write("".join(json.dumps(r) + "\n" for r in recs))
    for script in ("apply_plain.py", "apply_argus.py"):
        subprocess.run([sys.executable, "-X", "utf8", os.path.join(ROOT, "scripts", script), "--raw", tmp, "--out-dir", APPLY], capture_output=True, text=True)
    tag = recs[0]["model"].split("/")[-1] + ("-nf4" if recs[0].get("quant") == "nf4" else "")
    mtag = recs[0]["model"].split("/")[-1]
    pl = {r["iid"]: r for r in load(os.path.join(APPLY, f"plain_apply_{mtag}.jsonl"))}
    ar = {r["iid"]: r for r in load(os.path.join(APPLY, f"argus_apply_{mtag}.jsonl"))}
    by = {r["iid"]: r for r in recs}
    row = dict(n=len(recs), finish=dict(collections.Counter(r.get("finish") or r.get("error") for r in recs)),
               mean_new_tokens=round(sum(r.get("new_tokens") or 0 for r in recs) / len(recs)),
               plain=dict(collections.Counter(pl[i]["status"] for i in by)), argus=dict(collections.Counter(ar[i]["status"] for i in by)))
    causes, kinds, cross = collections.Counter(), collections.Counter(), collections.Counter()
    for i, r in by.items():
        if pl[i]["status"] not in ("no_match", "ambiguous"):
            continue
        F = source_lines(i, r["target_file"]); lines = list(F)
        cause = "plain_replay_found_no_failure"
        for s, rr in parse(r["content"] or ""):
            S = s.replace("\r\n", "\n").split("\n"); R = rr.replace("\r\n", "\n").split("\n")
            pos = find_all(lines, S)
            if len(pos) == 1:
                lines[pos[0]:pos[0] + len(S)] = R; continue
            cause = "elision_marker_in_search" if any("lines omitted" in x for x in S) else classify(lines, S, len(pos))
            if cause == "whitespace_or_blank_lines_only":
                kinds[indent_kind(lines, S)] += 1
            break
        causes[cause] += 1
        a = ar[i]
        cross[f"{cause} | " + (f"rescued_tier{a.get('max_tier')}" if a["status"] == "applied" else "refused_" + (a.get("refusal_reason") or a["status"]))] += 1
    row["plain_edit_failures"] = sum(causes.values()); row["causes"] = dict(causes); row["whitespace_kinds"] = dict(kinds); row["cause_x_argus"] = dict(cross)
    pa, aa = row["plain"].get("applied", 0), row["argus"].get("applied", 0)
    row["plain_applied"], row["argus_applied"], row["argus_rescued"] = pa, aa, aa - pa
    out[tag] = row
json.dump(out, open(os.path.join(ROOT, "results", "analysis", "qwen_probe_summary.json"), "w", encoding="utf-8"), indent=1)
print(json.dumps(out, indent=1))
