"""Revision 6: apply the stored Gemini sweep outputs (plain and Argus) and the gpt-oss draws of the replacement task, then grade every distinct
unseen patch in Docker, one task image at a time. Known grades are reused by (task, patch hash) from the earlier grading files.
Resumable. Aborts if the replacement task's gold patch did not resolve.

  python -X utf8 scripts/sweep_grade.py
"""
import collections, hashlib, json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
D = os.path.join(ROOT, "data", "gemini_sweep")
RAW = os.path.join(D, "raw.jsonl")
APPLY = os.path.join(D, "apply")
REQ_RAW = os.path.join(ROOT, "data", "raw", "phase2_t1_repl.jsonl")
REQ_APPLY = os.path.join(ROOT, "data", "phase2_t1_repl")
STATE = os.path.join(D, "grading.jsonl")
NEW = "astropy__astropy-13579"
TAGS = ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]

import harness.dockergrade as DG  # chdir + stdout redirect; console output via DG.say

os.makedirs(APPLY, exist_ok=True)
os.makedirs(REQ_APPLY, exist_ok=True)
for raw, out in ((RAW, APPLY), (REQ_RAW, REQ_APPLY)):
    for script in ("apply_plain.py", "apply_argus.py"):
        r = subprocess.run([sys.executable, "-X", "utf8", os.path.join(ROOT, "scripts", script), "--raw", raw, "--out-dir", out],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        DG.say(script, os.path.basename(raw), "->", (r.stdout.strip().splitlines() or [""])[-1][:300], r.stderr.strip()[-200:] if r.returncode else "")


def load(path):
    return [json.loads(l) for l in open(path, encoding="utf-8")] if os.path.exists(path) else []


def sha(s):
    return hashlib.sha1(s.encode()).hexdigest()[:10]


# gold control for the replacement task
gold = [r for r in load(os.path.join(ROOT, "results", "grading", "state_new.jsonl")) if r["iid"] == NEW]
if not gold or gold[0].get("resolved") is not True:
    DG.say("ABORT: gold patch for", NEW, "has not resolved:", gold[:1])
    sys.exit(1)

known = {}
for f in (os.path.join(ROOT, "results", "grading", "state_t1.jsonl"), os.path.join(ROOT, "results", "grading", "state.jsonl"),
          os.path.join(ROOT, "results", "grading", "state_new.jsonl")):
    for r in load(f):
        if r.get("hash") and r.get("resolved") is not None:
            known[(r["iid"], r["hash"])] = r["resolved"]
for f in (os.path.join(ROOT, "data", "probe_gemini", "grading.jsonl"), STATE):
    for r in load(f):
        if r.get("h") and r.get("resolved") is not None:
            known[(r["iid"], r["h"])] = r["resolved"]

need = collections.defaultdict(dict)  # iid -> hash -> diff
for tag in TAGS:
    for arm in ("plain", "argus"):
        for r in load(os.path.join(APPLY, f"{arm}_apply_{tag}.jsonl")):
            if r["status"] == "applied":
                need[r["iid"]][sha(r["diff"])] = r["diff"]
for tag in ("gpt-oss-20b", "gpt-oss-120b"):
    for arm in ("plain", "argus"):
        for r in load(os.path.join(REQ_APPLY, f"{arm}_apply_{tag}.jsonl")):
            if r["status"] == "applied":
                need[r["iid"]][sha(r["diff"])] = r["diff"]
todo = [(iid, h) for iid, hs in sorted(need.items()) for h in hs if (iid, h) not in known]
DG.say(f"{sum(len(v) for v in need.values())} distinct applied patches over {len(need)} tasks; {len(todo)} to grade")
n = 0
for iid in sorted({i for i, _ in todo}):
    hs = [h for i, h in todo if i == iid]
    if not DG.pull(iid):
        DG.say("  pull failed", iid)
        for h in hs:
            open(STATE, "a", encoding="utf-8").write(json.dumps(dict(iid=iid, h=h, error="image_pull_failed")) + "\n")
        continue
    for h in hs:
        res, _ = DG.grade_one(iid, h, need[iid][h])
        rec = dict(iid=iid, h=h, applied=res.get("applied"), resolved=res.get("resolved"), f2p_pass=res.get("f2p_pass"), f2p_fail=res.get("f2p_fail"),
                   p2p_fail=res.get("p2p_fail"), error=res.get("error"), note=res.get("note"))
        open(STATE, "a", encoding="utf-8").write(json.dumps(rec) + "\n")
        n += 1
        DG.say(f"  [{n}/{len(todo)}] {iid} {h} applied={rec['applied']} resolved={rec['resolved']}")
    DG.cleanup(iid)
DG.say("grading complete")
