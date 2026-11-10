"""Phase 2 (apply layer only): apply the SAME frozen model outputs with Argus, as published.

Mirrors argus/runtime/controller.py: PatchParser.parse -> validate_patch_blocks (single-target safety) ->
ResilientPatchEngine.apply_patch per block, sequentially, default settings (similarity 0.82, ambiguity margin 0.10,
AST gate on, Tier 4 off).  Argus is imported from the product repo, pinned by commit (recorded in the output).
No model calls.  Nothing is tuned here: this measures Argus v0.2.0b1 as it is.
"""
import argparse, ast, difflib, json, os, subprocess, sys, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARGUS = r"C:\coding\Argus"
sys.path.insert(0, ROOT)
sys.path.insert(0, ARGUS)
from harness.context import fetch_source, CACHE
from argus.patch.parser import PatchParser
from argus.patch.paths import PatchTargetError, validate_patch_blocks
from argus.patch.fuzzy_engine import ResilientPatchEngine, RefusalReason

ap = argparse.ArgumentParser()
ap.add_argument("--raw", default=os.path.join(ROOT, "data", "raw", "phase1_file_medium_v1.jsonl"))
ap.add_argument("--out-dir", default=os.path.join(ROOT, "data", "phase1"))
args = ap.parse_args()
os.makedirs(args.out_dir, exist_ok=True)
commit = subprocess.run(["git", "-C", ARGUS, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
dirty = bool(subprocess.run(["git", "-C", ARGUS, "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True).stdout.strip())
print("argus commit", commit, "dirty" if dirty else "clean")

TASKS = r"C:\coding\Argus-research-archive\data\swe_bench_verified_tasks.jsonl"
full = {}
for l in open(TASKS, encoding="utf-8"):
    d = json.loads(l); full[d["instance_id"]] = d


def process(rec, engine):
    t = full[rec["iid"]]
    target = rec["target_file"]
    base = dict(iid=rec["iid"], model=rec["model"], finish=rec.get("finish"), sample=rec.get("sample", 0), target_file=target, argus_commit=commit)
    content = rec.get("content") or ""
    if rec.get("finish") == "length" and not content.strip():
        return dict(base, status="truncated_no_output")
    if not content.strip():
        return dict(base, status="empty_output")
    blocks = PatchParser.parse(content)
    if not blocks:
        return dict(base, status="no_blocks")
    try:
        validate_patch_blocks(blocks, target)
    except PatchTargetError as e:
        return dict(base, status="path_refused", n_blocks=len(blocks), details=f"{e.code}: {e.message}")
    fetch_source(t["repo"], t["base_commit"], target)
    cp = os.path.join(CACHE, t["repo"].replace("/", "__"), t["base_commit"], *target.split("/"))
    raw = open(cp, "rb").read().decode("utf-8", errors="replace")
    crlf = "\r\n" in raw and raw.count("\r\n") >= raw.count("\n") * 0.9
    eol = "\r\n" if crlf else "\n"
    code = raw
    tiers, confs, strategies = [], [], []
    for i, b in enumerate(blocks):
        res = engine.apply_patch(code, b, filename=target)
        if not res.success:
            return dict(base, status="refused", n_blocks=len(blocks), block=i, tier_reached=res.tier_used,
                        refusal_reason=res.refusal_reason.value if res.refusal_reason != RefusalReason.NONE else "", details=(res.details or "")[:200],
                        tiers=tiers)
        tiers.append(res.tier_used); confs.append(res.confidence); strategies.append(res.strategy)
        code = res.patched_code or code
    old = raw.replace("\r\n", "\n")
    new = code.replace("\r\n", "\n")
    if new == old:
        return dict(base, status="no_change", n_blocks=len(blocks), tiers=tiers)
    a = [x + eol for x in old.split("\n")]
    b2 = [x + eol for x in new.split("\n")]
    diff = f"diff --git a/{target} b/{target}\n" + "".join(difflib.unified_diff(a, b2, fromfile="a/" + target, tofile="b/" + target, n=3))
    return dict(base, status="applied", n_blocks=len(blocks), tiers=tiers, max_tier=max(tiers), confidences=confs, strategies=strategies,
                diff=diff, crlf_file=crlf,
                changed_lines=sum(1 for x in diff.split("\n") if (x.startswith("+") or x.startswith("-")) and not x.startswith("+++") and not x.startswith("---")))


engine = ResilientPatchEngine(similarity_threshold=0.82, ambiguity_margin=0.10, enforce_ast=True, enable_tier4=False)
recs = [json.loads(l) for l in open(args.raw, encoding="utf-8")]
res = [process(r, engine) for r in recs]
for model in sorted(set(r["model"] for r in res)):
    tag = model.split("/")[-1]
    x = [r for r in res if r["model"] == model]
    with open(os.path.join(args.out_dir, f"argus_apply_{tag}.jsonl"), "w", encoding="utf-8") as f:
        for r in x:
            f.write(json.dumps(r) + "\n")
    with open(os.path.join(args.out_dir, f"predictions_argus_{tag}.jsonl"), "w", encoding="utf-8") as f:
        for r in x:
            if r["status"] == "applied":
                f.write(json.dumps(dict(instance_id=r["iid"], model_name_or_path=f"argus-{tag}", model_patch=r["diff"])) + "\n")
    c = collections.Counter(r["status"] for r in x)
    tiers = collections.Counter(r.get("max_tier") for r in x if r["status"] == "applied")
    print(tag, dict(c), "| max tier among applied:", dict(tiers))
