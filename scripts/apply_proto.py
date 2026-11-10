"""PROTOTYPE (discovery only): Argus apply layer plus four candidate fixes, replayed on the frozen model outputs.

Nothing here touches the Argus repo. Fixes, each motivated by a specific failure seen in the Pilot-100 discovery set:
  F-A  parser accepts an EMPTY replacement section (a deletion). Argus's regex needs a newline before '>>>>>>> REPLACE',
       so an empty REPLACE swallows the next block (xarray-4356).
  F-B  '...' elision lines in SEARCH act as a wildcard between a unique head and a unique tail anchor (sympy-17655, 11618).
  F-C  consecutive identical lines in SEARCH are collapsed when the literal SEARCH is not found (django-14238 '@property' twice).
  F-D  scope gate: a new `def f(self, ...)` that is not inside a class body is refused (sympy-22914).
Output: data/proto/proto_apply_<tag>.jsonl and a diff against the stock-Argus result per task.
All design choices were made after reading these tasks, so results here are discovery numbers, not a claim.
"""
import argparse, ast, collections, difflib, json, os, re, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARGUS = r"C:\coding\Argus"
sys.path.insert(0, ROOT); sys.path.insert(0, ARGUS)
from harness.context import fetch_source, CACHE
from argus.patch.parser import PatchBlock
from argus.patch.paths import PatchTargetError, validate_patch_blocks
from argus.patch.fuzzy_engine import ResilientPatchEngine, RefusalReason

ap = argparse.ArgumentParser()
ap.add_argument("--raw", default=os.path.join(ROOT, "data", "raw", "phase1_file_medium_v1.jsonl"))
ap.add_argument("--stock-dir", default=os.path.join(ROOT, "data", "phase1"))
ap.add_argument("--out-dir", default=os.path.join(ROOT, "data", "proto"))
ap.add_argument("--off", nargs="*", default=[], help="disable fixes, e.g. --off A B")
args = ap.parse_args()
os.makedirs(args.out_dir, exist_ok=True)

full = {}
for l in open(r"C:\coding\Argus-research-archive\data\swe_bench_verified_tasks.jsonl", encoding="utf-8"):
    d = json.loads(l); full[d["instance_id"]] = d

# F-A: empty replacement allowed (lazy optional group)
PATTERN = re.compile(r"<{3,}[ \t]*SEARCH(?:[ \t]+([^\r\n]+))?\r?\n(.*?)\r?\n={3,}\r?\n(?:(.*?)\r?\n)??>{3,}[ \t]*REPLACE", re.DOTALL)
STOCK = re.compile(r"<{3,}[ \t]*SEARCH(?:[ \t]+([^\r\n]+))?\r?\n(.*?)\r?\n={3,}\r?\n(.*?)\r?\n>{3,}[ \t]*REPLACE", re.DOTALL)
HEAD = re.compile(r"(?:###|\*\*|##)?\s*(?:File|Path|Filename):\s*`?([^\n`\r]+)`?", re.I)


def parse(text, fixA):
    out = []
    for m in (PATTERN if fixA else STOCK).finditer(text):
        pre = text[:m.start()]
        hints = HEAD.findall(pre)
        path = m.group(1).strip() if m.group(1) else (hints[-1].strip().replace("\\", "/") if hints else None)
        out.append(PatchBlock(search_text=m.group(2), replace_text=m.group(3) or "", file_path=path))
    return out


def is_ell(line):
    return line.strip() in ("...", "…", "# ...", "# …")


def expand_ellipsis(code, search, replace):
    """-> (new_search, new_replace) or None if not applicable / anchors not unique"""
    sl = search.split("\n")
    idx = [i for i, x in enumerate(sl) if is_ell(x)]
    if not idx:
        return None
    segs, prev = [], 0
    for i in idx + [len(sl)]:
        seg = sl[prev:i]
        segs.append(seg)
        prev = i + 1
    segs = [s for s in segs if "".join(s).strip()]
    if len(segs) < 2:
        return None
    cl = code.split("\n")
    st = [x.strip() for x in cl]

    def find_all(seg, start):
        s = [x.strip() for x in seg]
        n = len(s)
        return [i for i in range(start, len(st) - n + 1) if st[i:i + n] == s]

    pos = 0
    spans = []
    for seg in segs:
        hits = find_all(seg, pos)
        if len(hits) != 1:
            return None
        spans.append((hits[0], hits[0] + len(seg)))
        pos = hits[0] + len(seg)
    start, end = spans[0][0], spans[-1][1]
    new_search = "\n".join(cl[start:end])
    # replacement: if it also contains '...', splice the verbatim middle segments back in
    rl = replace.split("\n")
    ridx = [i for i, x in enumerate(rl) if is_ell(x)]
    if ridx and len(ridx) == len(spans) - 1:
        parts, prev = [], 0
        for k, i in enumerate(ridx):
            parts.extend(rl[prev:i])
            parts.extend(cl[spans[k][1]:spans[k + 1][0]])
            prev = i + 1
        parts.extend(rl[prev:])
        new_rep = "\n".join(parts)
    elif ridx:
        return None
    else:
        new_rep = replace
    return new_search, new_rep


def collapse_dupes(search):
    sl = search.split("\n")
    out = [sl[0]]
    for x in sl[1:]:
        if x.strip() and x == out[-1]:
            continue
        out.append(x)
    return "\n".join(out)


def stray_self_defs(src):
    """names of defs whose first arg is 'self' that sit outside any class body"""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    bad = collections.Counter()

    def walk(node, in_class):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if ch.args.args and ch.args.args[0].arg == "self" and not in_class:
                    bad[ch.name] += 1
                walk(ch, False)  # a def inside a def is not directly in a class
            elif isinstance(ch, ast.ClassDef):
                walk(ch, True)
            else:
                walk(ch, in_class)  # if/for/with/try inside a class body or at module level keeps its scope
    walk(tree, False)
    return bad


engine = ResilientPatchEngine(similarity_threshold=0.82, ambiguity_margin=0.10, enforce_ast=True, enable_tier4=False)
off = set(args.off)


def process(rec):
    t = full[rec["iid"]]; target = rec["target_file"]
    base = dict(iid=rec["iid"], model=rec["model"], target_file=target)
    content = rec.get("content") or ""
    if rec.get("finish") == "length" and not content.strip():
        return dict(base, status="truncated_no_output")
    if not content.strip():
        return dict(base, status="empty_output")
    blocks = parse(content, "A" not in off)
    if not blocks:
        return dict(base, status="no_blocks")
    try:
        validate_patch_blocks(blocks, target)
    except PatchTargetError as e:
        return dict(base, status="path_refused", details=f"{e.code}: {e.message}")
    fetch_source(t["repo"], t["base_commit"], target)
    cp = os.path.join(CACHE, t["repo"].replace("/", "__"), t["base_commit"], *target.split("/"))
    raw = open(cp, "rb").read().decode("utf-8", errors="replace")
    crlf = "\r\n" in raw and raw.count("\r\n") >= raw.count("\n") * 0.9
    eol = "\r\n" if crlf else "\n"
    code = raw
    used = []
    for i, b in enumerate(blocks):
        s, r = b.search_text, b.replace_text
        res = engine.apply_patch(code, PatchBlock(search_text=s, replace_text=r, file_path=b.file_path), filename=target)
        note = None
        if not res.success and "B" not in off:
            ex = expand_ellipsis(code, s, r)
            if ex:
                res2 = engine.apply_patch(code, PatchBlock(search_text=ex[0], replace_text=ex[1], file_path=b.file_path), filename=target)
                if res2.success:
                    res, note = res2, "B_ellipsis"
        if not res.success and "C" not in off:
            s2 = collapse_dupes(s)
            if s2 != s:
                res2 = engine.apply_patch(code, PatchBlock(search_text=s2, replace_text=r, file_path=b.file_path), filename=target)
                if res2.success:
                    res, note = res2, "C_dupe_lines"
        if not res.success:
            return dict(base, status="refused", block=i, tier_reached=res.tier_used,
                        refusal_reason=res.refusal_reason.value if res.refusal_reason != RefusalReason.NONE else "", details=(res.details or "")[:200])
        used.append(dict(tier=res.tier_used, fix=note))
        code = res.patched_code or code
    if "D" not in off:
        before = stray_self_defs(raw.replace("\r\n", "\n")); after = stray_self_defs(code.replace("\r\n", "\n"))
        if before is not None and after is not None and sum((after - before).values()) > 0:
            return dict(base, status="refused", refusal_reason="SCOPE_GATE", details="new `def ...(self, ...)` outside a class body: " + ",".join(sorted((after - before).keys())), used=used)
    old = raw.replace("\r\n", "\n"); new = code.replace("\r\n", "\n")
    if new == old:
        return dict(base, status="no_change", used=used)
    a = [x + eol for x in old.split("\n")]; b2 = [x + eol for x in new.split("\n")]
    diff = f"diff --git a/{target} b/{target}\n" + "".join(difflib.unified_diff(a, b2, fromfile="a/" + target, tofile="b/" + target, n=3))
    return dict(base, status="applied", used=used, max_tier=max(u["tier"] for u in used), diff=diff,
                changed_lines=sum(1 for x in diff.split("\n") if (x.startswith("+") or x.startswith("-")) and not x.startswith(("+++", "---"))))


recs = [json.loads(l) for l in open(args.raw, encoding="utf-8")]
res = [process(r) for r in recs]
changes = []
for model in sorted(set(r["model"] for r in res)):
    tag = model.split("/")[-1]
    x = [r for r in res if r["model"] == model]
    stock_path = os.path.join(args.stock_dir, f"argus_apply_{tag}.jsonl")
    stock = {}
    if os.path.exists(stock_path):
        for l in open(stock_path, encoding="utf-8"):
            s = json.loads(l); stock[s["iid"]] = s
    with open(os.path.join(args.out_dir, f"proto_apply_{tag}.jsonl"), "w", encoding="utf-8") as f:
        for r in x:
            f.write(json.dumps(r) + "\n")
            s = stock.get(r["iid"])
            if not s:
                continue
            sd = s.get("diff"); pd = r.get("diff")
            if s["status"] != r["status"] or sd != pd:
                changes.append(dict(iid=r["iid"], model=tag, stock=s["status"], proto=r["status"], proto_reason=r.get("refusal_reason") or "", fixes=[u["fix"] for u in r.get("used", []) if u.get("fix")], stock_reason=s.get("refusal_reason") or ""))
    with open(os.path.join(args.out_dir, f"predictions_proto_{tag}.jsonl"), "w", encoding="utf-8") as f:
        for r in x:
            if r["status"] == "applied":
                f.write(json.dumps(dict(instance_id=r["iid"], model_name_or_path=f"proto-{tag}", model_patch=r["diff"])) + "\n")
    print(tag, dict(collections.Counter(r["status"] for r in x)))
json.dump(changes, open(os.path.join(args.out_dir, "changes_vs_stock.json"), "w"), indent=1)
print("changed vs stock Argus:", len(changes))
for c in changes:
    print(" ", c)
