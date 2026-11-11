"""Exploratory (not pre-registered): WHY do edits fail to apply, and where do applied-but-wrong patches go wrong?

Part A. For every draw whose PLAIN apply failed on a SEARCH block (no exact single match), replay plain apply to find the first failing
        block and classify the cause by comparing the block with the file text it was meant to match; then cross with what Argus did
        (rescued at tier 2 or 3, or refused and why).
Part B. For applied draws, does the patch touch the lines the gold patch touches (right place) or elsewhere (wrong place), split by
        resolved vs not. Gold hunk overlap uses base-file line numbers within +/-5 lines.
Part C. Ceiling arithmetic: if every refused-but-recoverable draw had applied, how many extra solves per draw index (using each model's
        pass rate given applied).  An estimate, not a measurement.

  python -X utf8 scripts/analyze_failures.py   -> results/analysis/failures_summary.json
"""
import collections, difflib, hashlib, json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from harness.context import fetch_source, CACHE

TASKS = r"C:\coding\Argus-research-archive\data\swe_bench_verified_tasks.jsonl"
IDS = json.load(open(os.path.join(ROOT, "data", "gemini_sweep", "task_ids_full.json")))["ids"]
IDSET = set(IDS)
MODELS = ["gpt-oss-20b", "gpt-oss-120b", "gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]
K = 3
full = {}
for l in open(TASKS, encoding="utf-8"):
    d = json.loads(l); full[d["instance_id"]] = d


def load(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")] if os.path.exists(p) else []


def sha(s):
    return hashlib.sha1(s.encode()).hexdigest()[:10]


res = {}
for f in ("state_t1.jsonl", "state.jsonl", "state_new.jsonl"):
    for r in load(os.path.join(ROOT, "results", "grading", f)):
        if r.get("hash") and r.get("resolved") is not None:
            res[(r["iid"], r["hash"])] = r["resolved"]
for f in (os.path.join(ROOT, "data", "probe_gemini", "grading.jsonl"), os.path.join(ROOT, "data", "gemini_sweep", "grading.jsonl")):
    for r in load(f):
        if r.get("h") and r.get("resolved") is not None:
            res[(r["iid"], r["h"])] = r["resolved"]

D = {m: {} for m in MODELS}
for m in MODELS[:2]:
    for raw, ad in ((os.path.join(ROOT, "data", "raw", "phase2_t1_clean.jsonl"), os.path.join(ROOT, "data", "phase2_t1")),
                    (os.path.join(ROOT, "data", "raw", "phase2_t1_repl.jsonl"), os.path.join(ROOT, "data", "phase2_t1_repl"))):
        pl = {(r["iid"], r["sample"]): r for r in load(os.path.join(ad, f"plain_apply_{m}.jsonl"))}
        ar = {(r["iid"], r["sample"]): r for r in load(os.path.join(ad, f"argus_apply_{m}.jsonl"))}
        for g in load(raw):
            if g["model"].endswith(m) and g["iid"] in IDSET and g.get("http") == 200:
                k = (g["iid"], g["sample"]); D[m][k] = dict(plain=pl[k], argus=ar[k], content=g.get("content") or "", target=g["target_file"], ctx=g.get("ctx"))
for m in MODELS[2:]:
    ad = os.path.join(ROOT, "data", "gemini_sweep", "apply")
    pl = {(r["iid"], r["sample"]): r for r in load(os.path.join(ad, f"plain_apply_{m}.jsonl"))}
    ar = {(r["iid"], r["sample"]): r for r in load(os.path.join(ad, f"argus_apply_{m}.jsonl"))}
    for g in load(os.path.join(ROOT, "data", "gemini_sweep", "raw.jsonl")):
        if g["model"].endswith(m) and g.get("http") == 200:
            k = (g["iid"], g["sample"]); D[m][k] = dict(plain=pl[k], argus=ar[k], content=g.get("content") or "", target=g["target_file"], ctx=g.get("ctx"))

BLOCK = re.compile(r"<{3,}[ \t]*SEARCH[ \t]*\r?\n(.*?)\r?\n={3,}[ \t]*\r?\n(.*?)\r?\n>{3,}[ \t]*REPLACE", re.DOTALL)
HEAD = re.compile(r"^#{0,4}\s*File:\s*`?([^\n`]+?)`?\s*$", re.M)
ELIDE = re.compile(r"^\s*(#|//)?\s*(\.\.\.|\u2026|\.\.\.\s*\(.*\)|\.\.\.\s*(rest|existing|unchanged).*|(rest of|existing|unchanged|other).*(code|lines|methods|unchanged).*)\s*$", re.I)


def parse(content):
    return [(m.group(1), m.group(2)) for m in BLOCK.finditer(content)]


def find_all(lines, part):
    n = len(part)
    return [i for i in range(len(lines) - n + 1) if lines[i:i + n] == part] if n else []


def source_lines(iid, target):
    t = full[iid]
    fetch_source(t["repo"], t["base_commit"], target)
    raw = open(os.path.join(CACHE, t["repo"].replace("/", "__"), t["base_commit"], *target.split("/")), "rb").read().decode("utf-8", "replace")
    return raw.replace("\r\n", "\n").split("\n")


def best_window(F, S):
    """best char-similarity window of len(S) lines among F (stripped lines); returns (sim, start)"""
    Fs = [x.strip() for x in F]; Ss = [x.strip() for x in S]
    n = len(Ss)
    target = "\n".join(Ss)
    best, at = 0.0, 0
    for i in range(0, max(1, len(Fs) - n + 1)):
        w = "\n".join(Fs[i:i + n])
        sm = difflib.SequenceMatcher(None, w, target, autojunk=False)
        if sm.real_quick_ratio() <= best or sm.quick_ratio() <= best:
            continue
        r = sm.ratio()
        if r > best:
            best, at = r, i
        if best >= 0.999:
            break
    return best, at


def squash(x):
    return re.sub(r"\s+", " ", x.strip())


def classify(F, S, nm):
    """cause for a SEARCH block (list of lines S) that has nm exact matches in F (0 or >1)"""
    if nm > 1:
        return "ambiguous_multiple_exact_matches"
    if not "".join(S).strip():
        return "empty_search"
    if any(ELIDE.match(x) for x in S):
        return "elision_marker_in_search"
    # whitespace / blank-line differences only
    Fn = [(i, squash(x)) for i, x in enumerate(F) if x.strip()]
    Sn = [squash(x) for x in S if x.strip()]
    seq = [x for _, x in Fn]
    if Sn and any(seq[j:j + len(Sn)] == Sn for j in range(len(seq) - len(Sn) + 1)):
        return "whitespace_or_blank_lines_only"
    sim, at = best_window(F, S)
    if sim >= 0.82:
        a = [x.strip() for x in S]; b = [x.strip() for x in F[at:at + len(S)]]
        ops = [o for o in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes() if o[0] != "equal"]
        return "near_miss_missing_or_extra_lines" if ops and all(o[0] in ("insert", "delete") for o in ops) else "near_miss_changed_lines"
    return "partial_overlap_0.5_0.82" if sim >= 0.5 else "text_absent_under_0.5"


def first_plain_failure(content, target, iid):
    F = source_lines(iid, target)
    lines = list(F)
    for i, (s, r) in enumerate(parse(content)):
        S = s.replace("\r\n", "\n").split("\n"); R = r.replace("\r\n", "\n").split("\n")
        pos = find_all(lines, S)
        if len(pos) != 1:
            return i, classify(lines, S, len(pos)), len(S), len(parse(content))
        p = pos[0]
        lines[p:p + len(S)] = R
    return None


# ---------------- Part A
A = {}
for m in MODELS:
    c = collections.Counter(); cross = collections.Counter(); nblocks = []
    for (iid, k), d in sorted(D[m].items()):
        if d["plain"]["status"] not in ("no_match", "ambiguous"):
            continue
        r = first_plain_failure(d["content"], d["target"], iid)
        if r is None:
            cause, nb = "plain_replay_found_no_failure", 0
            bi, nl = -1, 0
        else:
            bi, cause, nl, nb = r
        c[cause] += 1
        a = d["argus"]
        outcome = ("rescued_tier%s" % a.get("max_tier")) if a["status"] == "applied" else ("refused_" + (a.get("refusal_reason") or a["status"]))
        cross[(cause, outcome)] += 1
        nblocks.append(nb)
    A[m] = dict(n=sum(c.values()), by_cause=dict(c), cause_x_argus={f"{a} | {b}": v for (a, b), v in sorted(cross.items())},
                mean_blocks_in_failed_patch=round(sum(nblocks) / len(nblocks), 2) if nblocks else None)

# also: block count of all draws that produced blocks (is failure just about many blocks?)
B_ = {}
for m in MODELS:
    rows = []
    for (iid, k), d in D[m].items():
        nb = len(parse(d["content"]))
        if nb:
            rows.append((nb, d["plain"]["status"] in ("no_match", "ambiguous")))
    byn = collections.defaultdict(lambda: [0, 0])
    for nb, f in rows:
        key = "1" if nb == 1 else ("2" if nb == 2 else ("3-4" if nb <= 4 else "5+"))
        byn[key][0] += 1; byn[key][1] += f
    B_[m] = {k: dict(draws=v[0], plain_edit_failed=v[1], rate=round(v[1] / v[0], 3)) for k, v in sorted(byn.items())}


# ---------------- Part B: location of applied patches vs gold hunks
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def touched(diff, path):
    """set of base-file line numbers changed (deleted lines) or adjacent to an insertion, for diff text restricted to `path`"""
    out, cur, old = set(), False, None
    for ln in diff.split("\n"):
        if ln.startswith("diff --git"):
            cur = ln.endswith("b/" + path); old = None; continue
        if not cur:
            continue
        m = HUNK.match(ln)
        if m:
            old = int(m.group(1)); continue
        if old is None or ln.startswith("---") or ln.startswith("+++"):
            continue
        if ln.startswith("-"):
            out.add(old); old += 1
        elif ln.startswith("+"):
            out.add(old); out.add(old - 1)
        else:
            old += 1
    return out


Bloc = {}
for m in MODELS:
    c = collections.Counter(); sizes = collections.defaultdict(list)
    for (iid, k), d in D[m].items():
        a = d["argus"]
        if a["status"] != "applied":
            continue
        ok = res.get((iid, sha(a["diff"])))
        gold = touched(full[iid]["gold_patch"], d["target"])
        mine = touched(a["diff"], d["target"])
        near = bool(gold) and any(abs(x - g) <= 5 for x in mine for g in gold)
        c[("resolved" if ok else "unresolved", "touches_gold_region" if near else "elsewhere")] += 1
        gl = sum(1 for x in full[iid]["gold_patch"].split("\n") if x[:1] in "+-" and not x.startswith(("+++", "---")))
        ml = a.get("changed_lines") or 0
        sizes["resolved" if ok else "unresolved"].append(ml / gl if gl else 0)
    Bloc[m] = dict(counts={f"{a} | {b}": v for (a, b), v in sorted(c.items())},
                   median_patch_size_over_gold_size={k: round(sorted(v)[len(v) // 2], 2) for k, v in sizes.items() if v})

# ---------------- Part C: ceiling estimate
RECOVERABLE = {"whitespace_or_blank_lines_only", "near_miss_missing_or_extra_lines", "near_miss_changed_lines", "elision_marker_in_search"}
C = {}
for m in MODELS:
    ap_ = [x for x, d in D[m].items() if d["argus"]["status"] == "applied"]
    pg = sum(1 for (iid, k) in ap_ if res.get((iid, sha(D[m][(iid, k)]["argus"]["diff"])))) / len(ap_)
    refused = [x for x, d in D[m].items() if d["argus"]["status"] == "refused"]
    still_rec = 0
    for (iid, k) in refused:
        d = D[m][(iid, k)]
        r = first_plain_failure(d["content"], d["target"], iid)
        if r and r[1] in RECOVERABLE:
            still_rec += 1
    C[m] = dict(argus_refused_draws=len(refused), refused_with_recoverable_cause=still_rec, pass_rate_given_applied=round(pg, 3),
                est_extra_solves_per_draw_index=round(still_rec * pg / K, 2),
                est_extra_solves_if_all_refused_applied=round(len(refused) * pg / K, 2))

out = dict(A_edit_failure_causes=A, B_failure_rate_by_blocks_in_patch=B_, B_location_of_applied=Bloc, C_ceiling=C)
json.dump(out, open(os.path.join(ROOT, "results", "analysis", "failures_summary.json"), "w", encoding="utf-8"), indent=1)
print(json.dumps(out, indent=1))
