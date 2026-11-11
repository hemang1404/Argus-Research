"""Exploratory: (A) gpt-oss on the same 30 probe tasks (Revision 4 draws, T=1) next to the Gemini probe draws;
(B) why the Argus apply layer helps some models and not others: per model, plain vs Argus apply rate, rescued draws and their pass rate,
and for draws where plain apply failed, how close the SEARCH text was to the file (near miss vs absent text).

  python -X utf8 scripts/analyze_probe.py          -> results/analysis/probe_summary.json
"""
import collections, difflib, hashlib, json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from harness.context import fetch_source, CACHE

P = os.path.join(ROOT, "data", "probe_gemini")
TASKS = r"C:\coding\Argus-research-archive\data\swe_bench_verified_tasks.jsonl"
full = {}
for l in open(TASKS, encoding="utf-8"):
    d = json.loads(l); full[d["instance_id"]] = d
ids30 = json.load(open(os.path.join(P, "task_ids.json")))["ids"]


def load(path):
    return [json.loads(l) for l in open(path, encoding="utf-8")] if os.path.exists(path) else []


def sha(s):
    return hashlib.sha1(s.encode()).hexdigest()[:10]


# ---- results store: (iid, patch hash) -> resolved, from every grading file
res = {}
for f in (os.path.join(ROOT, "results", "grading", "state_t1.jsonl"), os.path.join(ROOT, "results", "grading", "state.jsonl")):
    for r in load(f):
        h = r.get("hash") or r.get("h")
        if h and r.get("resolved") is not None:
            res[(r["iid"], h)] = r["resolved"]
for r in load(os.path.join(P, "grading.jsonl")):
    if r.get("resolved") is not None:
        res[(r["iid"], r["h"])] = r["resolved"]

# ---- draws: unified records {model, iid, sample, content, finish, plain, argus}
draws = []
for tag in ("gpt-oss-20b", "gpt-oss-120b"):
    plain = {(r["iid"], r["sample"]): r for r in load(os.path.join(ROOT, "data", "phase2_t1", f"plain_apply_{tag}.jsonl"))}
    argus = {(r["iid"], r["sample"]): r for r in load(os.path.join(ROOT, "data", "phase2_t1", f"argus_apply_{tag}.jsonl"))}
    for g in load(os.path.join(ROOT, "data", "raw", "phase2_t1_clean.jsonl")):
        if g["model"].endswith(tag):
            k = (g["iid"], g["sample"])
            draws.append(dict(model=tag, iid=g["iid"], sample=g["sample"], content=g.get("content"), target=g["target_file"], plain=plain[k], argus=argus[k]))
gem_tags = ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-3.8-flash"]
rawg = {(r["model"].split("/")[-1], r["iid"]): r for r in load(os.path.join(P, "raw.jsonl")) if r.get("http") == 200}
for tag in gem_tags:
    plain = {r["iid"]: r for r in load(os.path.join(P, "apply", f"plain_apply_{tag}.jsonl"))}
    argus = {r["iid"]: r for r in load(os.path.join(P, "apply", f"argus_apply_{tag}.jsonl"))}
    for (t, iid), g in rawg.items():
        if t == tag:
            draws.append(dict(model=tag, iid=iid, sample=0, content=g.get("content"), target=g["target_file"], plain=plain[iid], argus=argus[iid]))


def resolved(rec):
    if rec["status"] != "applied":
        return False
    return bool(res.get((rec["iid"], sha(rec["diff"]))))


def known(rec):
    return rec["status"] != "applied" or (rec["iid"], sha(rec["diff"])) in res


BLOCK = re.compile(r"<{3,}[ \t]*SEARCH[ \t]*\r?\n(.*?)\r?\n={3,}[ \t]*\r?\n(.*?)\r?\n>{3,}[ \t]*REPLACE", re.DOTALL)


def best_similarity(d):
    """similarity of the first SEARCH block (stripped lines) to its best window in the target file"""
    m = BLOCK.search(d["content"] or "")
    if not m:
        return None
    t = full[d["iid"]]
    fetch_source(t["repo"], t["base_commit"], d["target"])
    raw = open(os.path.join(CACHE, t["repo"].replace("/", "__"), t["base_commit"], *d["target"].split("/")), "rb").read().decode("utf-8", "replace")
    F = [x.strip() for x in raw.replace("\r\n", "\n").split("\n")]
    S = [x.strip() for x in m.group(1).replace("\r\n", "\n").split("\n")]
    n = len(S)
    if not "".join(S):
        return 0.0
    target = "\n".join(S)
    best = 0.0
    for i in range(0, max(1, len(F) - n + 1)):
        w = "\n".join(F[i:i + n])
        sm = difflib.SequenceMatcher(None, w, target, autojunk=False)
        if sm.real_quick_ratio() <= best or sm.quick_ratio() <= best:
            continue
        best = max(best, sm.ratio())
        if best >= 0.999:
            break
    return best


def summarize(rows, with_anatomy):
    n = len(rows)
    out = dict(draws=n)
    out["plain_applied"] = sum(r["plain"]["status"] == "applied" for r in rows)
    out["argus_applied"] = sum(r["argus"]["status"] == "applied" for r in rows)
    out["plain_resolved"] = sum(resolved(r["plain"]) for r in rows)
    out["argus_resolved"] = sum(resolved(r["argus"]) for r in rows)
    resc = [r for r in rows if r["plain"]["status"] != "applied" and r["argus"]["status"] == "applied"]
    lost = [r for r in rows if r["plain"]["status"] == "applied" and r["argus"]["status"] != "applied"]
    out["rescued"] = len(resc)
    out["rescued_resolved"] = sum(resolved(r["argus"]) for r in resc)
    out["lost_to_argus_refusal"] = len(lost)
    out["lost_resolved"] = sum(resolved(r["plain"]) for r in lost)
    ap = [r for r in rows if r["argus"]["status"] == "applied"]
    out["argus_pass_given_applied"] = round(sum(resolved(r["argus"]) for r in ap) / len(ap), 3) if ap else None
    out["plain_status"] = dict(collections.Counter(r["plain"]["status"] for r in rows))
    out["argus_status"] = dict(collections.Counter(r["argus"]["status"] for r in rows))
    out["ungraded_applied"] = sum(1 for r in rows for a in ("plain", "argus") if not known(r[a]))
    if with_anatomy:
        fails = [r for r in rows if r["plain"]["status"] in ("no_match", "ambiguous")]
        bins = collections.Counter()
        for r in fails:
            s = best_similarity(r)
            b = "no_block" if s is None else ("near_miss>=0.82" if s >= 0.82 else ("partial_0.5-0.82" if s >= 0.5 else "text_absent<0.5"))
            bins[b] += 1
            r["sim_bin"] = b
        out["plain_match_failures_by_similarity"] = dict(bins)
        out["argus_on_those"] = dict(collections.Counter((r["sim_bin"], r["argus"]["status"]) .__repr__() for r in fails))
    return out


summary = {}
for scope, pick in (("same30", lambda r: r["iid"] in ids30), ("all99", lambda r: True)):
    for model in ["gpt-oss-20b", "gpt-oss-120b"] + gem_tags:
        rows = [r for r in draws if r["model"] == model and pick(r)]
        if scope == "all99" and model.startswith("gemini"):
            continue
        if not rows:
            continue
        summary[f"{scope}:{model}"] = summarize(rows, with_anatomy=(scope == "same30"))
# gpt-oss draw 0 only on the 30 tasks, to match the single Gemini draw
for model in ("gpt-oss-20b", "gpt-oss-120b"):
    rows = [r for r in draws if r["model"] == model and r["iid"] in ids30 and r["sample"] == 0]
    summary[f"same30_draw0:{model}"] = summarize(rows, with_anatomy=False)
os.makedirs(os.path.join(ROOT, "results", "analysis"), exist_ok=True)
json.dump(summary, open(os.path.join(ROOT, "results", "analysis", "probe_summary.json"), "w", encoding="utf-8"), indent=1)
for k, v in summary.items():
    print(k, json.dumps(v))
