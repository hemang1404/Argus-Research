"""Re-apply the stored attempt-1 outputs of the blind set (200 sealed tasks, 3 models) with the REMEDIATED Argus patch engine and compare with what the old engine did
(recorded apply_status / max_tier / graded resolved). No model calls, no Docker. Configurations of the new engine: T1-3 (default), T1-2 only (enable_tier3=False).
  python -X utf8 scripts/compare_apply_engines.py
"""
import json, os, sys, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
NEW = r"C:\coding\Argus-remediation"
sys.path.insert(0, NEW)  # remediated package first
import argus
assert os.path.dirname(os.path.dirname(argus.__file__)).lower() == NEW.lower(), argus.__file__
from harness.context import fetch_source, CACHE
from argus.patch.parser import PatchParser
from argus.patch.paths import PatchTargetError, validate_patch_blocks
from argus.patch.fuzzy_engine import ResilientPatchEngine

TASKS = r"C:\coding\Argus-research-archive\data\swe_bench_verified_tasks.jsonl"
full = {}
for l in open(TASKS, encoding="utf-8"):
    d = json.loads(l)
    full[d["instance_id"]] = d


def reapply(row, content, enable_tier3):
    t = full[row["iid"]]
    target = row["target_file"]
    blocks = PatchParser.parse(content or "")
    if not blocks:
        return "no_blocks", 0
    try:
        validate_patch_blocks(blocks, target)
    except PatchTargetError:
        return "path_refused", 0
    fetch_source(t["repo"], t["base_commit"], target)
    cp = os.path.join(CACHE, t["repo"].replace("/", "__"), t["base_commit"], *target.split("/"))
    code = open(cp, "rb").read().decode("utf-8", errors="replace")
    engine = ResilientPatchEngine(similarity_threshold=0.82, ambiguity_margin=0.10, enforce_ast=True, enable_tier4=False, enable_tier3=enable_tier3)
    mx = 0
    for b in blocks:
        res = engine.apply_patch(code, b, filename=target)
        if not res.success:
            return "refused", mx
        mx = max(mx, res.tier_used or 0)
        code = res.patched_code or code
    return "applied", mx


rows = [json.loads(l) for l in open(os.path.join(ROOT, "data", "blind", "trajectories.jsonl"), encoding="utf-8")]
OUT = {}
for model in ("gpt-oss-20b", "gpt-oss-120b", "gemma-4-26b-a4b-it"):
    stats = collections.Counter()
    detail = []
    for r in rows:
        if not r["gold"]["resolved"]:
            continue
        a = ((r["models"].get(model) or {}).get("R") or {}).get("attempts") or []
        if not a or a[0].get("http") not in (None, 200) or "content" not in a[0]:
            continue
        a0 = a[0]
        old_applied = a0.get("apply_status") == "applied"
        old_tier = a0.get("max_tier") or 0
        old_res = bool(a0.get("grade") and a0["grade"].get("resolved"))
        stats["n"] += 1
        stats["old_applied"] += old_applied
        stats["old_resolved"] += old_res
        for cfg, t3 in (("T123", True), ("T12", False)):
            st, mx = reapply(r, a0["content"], t3)
            ap = st == "applied"
            stats[f"{cfg}_applied"] += ap
            if old_applied and not ap:
                stats[f"{cfg}_lost_applied"] += 1
                stats[f"{cfg}_lost_resolved"] += old_res
                detail.append((r["iid"], cfg, "old applied (tier %s, resolved=%s), new %s" % (old_tier, old_res, st)))
            if ap and not old_applied:
                stats[f"{cfg}_gained_applied"] += 1
                detail.append((r["iid"], cfg, "old refused/%s, new applied (tier %s)" % (a0.get("apply_status"), mx)))
            if ap:
                stats[f"{cfg}_tier{mx}"] += 1
        if old_applied:
            stats[f"old_tier{old_tier}"] += 1
    OUT[model] = dict(stats=dict(stats), detail=detail)
    print(f"\n== {model}: n={stats['n']}  old engine applied {stats['old_applied']} (resolved {stats['old_resolved']}); old tiers: " + ", ".join(f"T{k}={stats[f'old_tier{k}']}" for k in (1, 2, 3, 4) if stats[f'old_tier{k}']))
    for cfg in ("T123", "T12"):
        print(f"   new {cfg}: applied {stats[cfg+'_applied']}  lost vs old {stats[cfg+'_lost_applied']} (of which graded resolved {stats[cfg+'_lost_resolved']})  gained {stats[cfg+'_gained_applied']}  tiers used: " + ", ".join(f"T{k}={stats[f'{cfg}_tier{k}']}" for k in (1, 2, 3) if stats[f'{cfg}_tier{k}']))
    for d in detail[:12]:
        print("   ", d)
json.dump(OUT, open(os.path.join(ROOT, "results", "analysis", "apply_engine_comparison.json"), "w"), indent=1)
