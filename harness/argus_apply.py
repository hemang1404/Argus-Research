"""Stock Argus apply layer as a function (same logic as scripts/apply_argus.py, no prototype fixes).

Parse SEARCH/REPLACE blocks -> validate single target -> ResilientPatchEngine per block (similarity 0.82, margin 0.10, AST gate on,
Tier 4 off). Returns a dict with status in {truncated_no_output, empty_output, no_blocks, path_refused, refused, no_change, applied}.
Self-test: scripts/check_loop_apply.py replays the Revision 4 outputs and compares diffs with data/phase2_t1/argus_apply_*.jsonl.
"""
import difflib, os, sys
ARGUS = r"C:\coding\Argus"
if ARGUS not in sys.path:
    sys.path.insert(0, ARGUS)
from harness.context import fetch_source, CACHE
from argus.patch.parser import PatchParser
from argus.patch.paths import PatchTargetError, validate_patch_blocks
from argus.patch.fuzzy_engine import ResilientPatchEngine, RefusalReason


def apply_output(repo, base_commit, target, content, finish):
    content = content or ""
    if finish == "length" and not content.strip():
        return dict(status="truncated_no_output")
    if not content.strip():
        return dict(status="empty_output")
    blocks = PatchParser.parse(content)
    if not blocks:
        return dict(status="no_blocks")
    try:
        validate_patch_blocks(blocks, target)
    except PatchTargetError as e:
        return dict(status="path_refused", n_blocks=len(blocks), details=f"{e.code}: {e.message}")
    fetch_source(repo, base_commit, target)
    cp = os.path.join(CACHE, repo.replace("/", "__"), base_commit, *target.split("/"))
    raw = open(cp, "rb").read().decode("utf-8", errors="replace")
    crlf = "\r\n" in raw and raw.count("\r\n") >= raw.count("\n") * 0.9
    eol = "\r\n" if crlf else "\n"
    engine = ResilientPatchEngine(similarity_threshold=0.82, ambiguity_margin=0.10, enforce_ast=True, enable_tier4=False)
    code = raw
    tiers = []
    for i, b in enumerate(blocks):
        res = engine.apply_patch(code, b, filename=target)
        if not res.success:
            return dict(status="refused", n_blocks=len(blocks), block=i, tier_reached=res.tier_used, tiers=tiers,
                        refusal_reason=res.refusal_reason.value if res.refusal_reason != RefusalReason.NONE else "", details=(res.details or "")[:300])
        tiers.append(res.tier_used)
        code = res.patched_code or code
    old = raw.replace("\r\n", "\n")
    new = code.replace("\r\n", "\n")
    if new == old:
        return dict(status="no_change", n_blocks=len(blocks), tiers=tiers)
    a = [x + eol for x in old.split("\n")]
    b2 = [x + eol for x in new.split("\n")]
    diff = f"diff --git a/{target} b/{target}\n" + "".join(difflib.unified_diff(a, b2, fromfile="a/" + target, tofile="b/" + target, n=3))
    return dict(status="applied", n_blocks=len(blocks), tiers=tiers, max_tier=max(tiers), diff=diff)
