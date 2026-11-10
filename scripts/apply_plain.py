"""Phase 1b: apply the bare one-shot outputs with PLAIN exact matching (no Argus code) and write SWE-bench predictions.

Rules (a minimal str_replace-style tool, the 'no Argus' arm):
  - blocks are SEARCH/REPLACE with a '### File:' header; header path must name the target file (else status wrong_file)
  - SEARCH must match the file exactly, line for line (line endings ignored); exactly ONE match required
    (0 matches -> no_match, >1 -> ambiguous); blocks apply in order on the evolving text; any failure fails the candidate
  - nothing else: no whitespace tolerance, no fuzzy matching, no syntax gate (syntax is only RECORDED)
Output per (task, model): status, details, ast_ok, diff.  Also records n_matches so a 'first match' tool can be simulated later.
"""
import argparse, ast, difflib, json, os, re, sys, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from harness.context import fetch_source, CACHE

ap = argparse.ArgumentParser()
ap.add_argument("--raw", default=os.path.join(ROOT, "data", "raw", "phase1_file_medium_v1.jsonl"))
ap.add_argument("--out-dir", default=os.path.join(ROOT, "data", "phase1"))
args = ap.parse_args()
os.makedirs(args.out_dir, exist_ok=True)

TASKS = r"C:\coding\Argus-research-archive\data\swe_bench_verified_tasks.jsonl"
full = {}
for l in open(TASKS, encoding="utf-8"):
    d = json.loads(l); full[d["instance_id"]] = d

BLOCK = re.compile(r"<{3,}[ \t]*SEARCH[ \t]*\r?\n(.*?)\r?\n={3,}[ \t]*\r?\n(.*?)\r?\n>{3,}[ \t]*REPLACE", re.DOTALL)
HEAD = re.compile(r"^#{0,4}\s*File:\s*`?([^\n`]+?)`?\s*$", re.M)


def parse(content):
    """-> list of (path_or_None, search, replace) in order of appearance"""
    heads = [(m.start(), m.group(1).strip()) for m in HEAD.finditer(content)]
    out = []
    for m in BLOCK.finditer(content):
        path = None
        for pos, p in heads:
            if pos < m.start():
                path = p
        out.append((path, m.group(1), m.group(2)))
    return out


def norm_path(p):
    p = (p or "").strip().strip("`'\"").replace("\\", "/")
    return re.sub(r"^(a|b)/", "", p)


def find_all(lines, part):
    n = len(part)
    return [i for i in range(len(lines) - n + 1) if lines[i:i + n] == part] if n else []


def process(rec):
    t = full[rec["iid"]]
    target = rec["target_file"]
    base = dict(iid=rec["iid"], model=rec["model"], finish=rec.get("finish"), sample=rec.get("sample", 0), target_file=target)
    content = rec.get("content") or ""
    if rec.get("finish") == "length" and not content.strip():
        return dict(base, status="truncated_no_output")
    if not content.strip():
        return dict(base, status="empty_output")
    blocks = parse(content)
    if not blocks:
        return dict(base, status="no_blocks")
    fetch_source(t["repo"], t["base_commit"], target)
    cp = os.path.join(CACHE, t["repo"].replace("/", "__"), t["base_commit"], *target.split("/"))
    raw = open(cp, "rb").read().decode("utf-8", errors="replace")
    crlf = "\r\n" in raw and raw.count("\r\n") >= raw.count("\n") * 0.9
    eol = "\r\n" if crlf else "\n"
    orig_lines = raw.replace("\r\n", "\n").split("\n")
    lines = list(orig_lines)
    details, n_matches_list = [], []
    for i, (path, s, r) in enumerate(blocks):
        if path is not None and norm_path(path) != target:
            return dict(base, status="wrong_file", n_blocks=len(blocks), details=f"block {i}: wrote {path!r}")
        sl = s.replace("\r\n", "\n").split("\n")
        rl = r.replace("\r\n", "\n").split("\n")
        if not "".join(sl).strip():
            return dict(base, status="empty_search", n_blocks=len(blocks), details=f"block {i}")
        pos = find_all(lines, sl)
        n_matches_list.append(len(pos))
        if len(pos) == 0:
            return dict(base, status="no_match", n_blocks=len(blocks), n_matches=n_matches_list, details=f"block {i}")
        if len(pos) > 1:
            return dict(base, status="ambiguous", n_blocks=len(blocks), n_matches=n_matches_list, details=f"block {i}: {len(pos)} matches")
        k = pos[0]
        lines = lines[:k] + rl + lines[k + len(sl):]
    new = "\n".join(lines)
    old = "\n".join(orig_lines)
    ast_ok = True
    try:
        ast.parse(new)
    except SyntaxError as e:
        ast_ok = False
        details.append(f"syntax error line {e.lineno}: {e.msg}")
    if new == old:
        return dict(base, status="no_change", n_blocks=len(blocks), n_matches=n_matches_list, ast_ok=ast_ok)
    a = [x + eol for x in old.split("\n")]
    b = [x + eol for x in new.split("\n")]
    diff = "".join(difflib.unified_diff(a, b, fromfile="a/" + target, tofile="b/" + target, n=3))
    diff = f"diff --git a/{target} b/{target}\n" + diff
    return dict(base, status="applied", n_blocks=len(blocks), n_matches=n_matches_list, ast_ok=ast_ok, details="; ".join(details), diff=diff,
                changed_lines=sum(1 for x in diff.split("\n") if (x.startswith("+") or x.startswith("-")) and not x.startswith("+++") and not x.startswith("---")))


recs = [json.loads(l) for l in open(args.raw, encoding="utf-8")]
res = [process(r) for r in recs]
for model in sorted(set(r["model"] for r in res)):
    tag = model.split("/")[-1]
    x = [r for r in res if r["model"] == model]
    with open(os.path.join(args.out_dir, f"plain_apply_{tag}.jsonl"), "w", encoding="utf-8") as f:
        for r in x:
            f.write(json.dumps(r) + "\n")
    with open(os.path.join(args.out_dir, f"predictions_plain_{tag}.jsonl"), "w", encoding="utf-8") as f:
        for r in x:
            if r["status"] == "applied":
                f.write(json.dumps(dict(instance_id=r["iid"], model_name_or_path=f"plain-{tag}", model_patch=r["diff"])) + "\n")
    c = collections.Counter(r["status"] for r in x)
    print(tag, dict(c), "| applied but syntax-broken:", sum(1 for r in x if r["status"] == "applied" and not r.get("ast_ok", True)))
