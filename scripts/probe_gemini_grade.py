"""Exploratory Gemini probe: apply the stored outputs with PLAIN and ARGUS apply, grade the distinct patches in Docker (one image at a time),
and print a per-model summary. Resumable. Run after scripts/probe_gemini.py.

  python -X utf8 scripts/probe_gemini_grade.py
"""
import collections, hashlib, json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
D = os.path.join(ROOT, "data", "probe_gemini")
RAW = os.path.join(D, "raw.jsonl")
APPLY = os.path.join(D, "apply")
STATE = os.path.join(D, "grading.jsonl")
SUMMARY = os.path.join(D, "summary.json")
PRICE = {"gemini-2.5-flash-lite": (0.10, 0.40), "gemini-3.1-flash-lite": (0.25, 1.50), "gemini-3.5-flash-lite": (0.30, 2.50),
         "gemini-3.8-flash": (0.75, 3.75)}

import harness.dockergrade as DG  # chdir + stdout redirect; console output via DG.say

os.makedirs(APPLY, exist_ok=True)
for script in ("apply_plain.py", "apply_argus.py"):
    r = subprocess.run([sys.executable, "-X", "utf8", os.path.join(ROOT, "scripts", script), "--raw", RAW, "--out-dir", APPLY],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    DG.say(script, "->", (r.stdout.strip().splitlines() or [""])[-1][:300], r.stderr.strip()[-200:] if r.returncode else "")


def load(path):
    return [json.loads(l) for l in open(path, encoding="utf-8")] if os.path.exists(path) else []


def sha(s):
    return hashlib.sha1(s.encode()).hexdigest()[:10]


arms = {}  # (iid, model, arm) -> apply record
for tag in ("gemini-2.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-3.8-flash"):
    for arm, fn in (("plain", f"plain_apply_{tag}.jsonl"), ("argus", f"argus_apply_{tag}.jsonl")):
        for r in load(os.path.join(APPLY, fn)):
            arms[(r["iid"], tag, arm)] = r

graded = {}
for r in load(STATE):
    graded[(r["iid"], r["h"])] = r
need = collections.defaultdict(dict)  # iid -> h -> diff
for (iid, tag, arm), r in arms.items():
    if r["status"] == "applied":
        need[iid][sha(r["diff"])] = r["diff"]
todo = [(iid, h) for iid, hs in need.items() for h in hs if (iid, h) not in graded]
DG.say(f"{sum(len(v) for v in need.values())} distinct applied patches over {len(need)} tasks; {len(todo)} to grade")
for iid in sorted({i for i, _ in todo}):
    hs = [h for i, h in todo if i == iid]
    if not DG.pull(iid):
        for h in hs:
            graded[(iid, h)] = dict(iid=iid, h=h, error="image_pull_failed")
            open(STATE, "a", encoding="utf-8").write(json.dumps(graded[(iid, h)]) + "\n")
        continue
    for h in hs:
        res, _ = DG.grade_one(iid, h, need[iid][h])
        rec = dict(iid=iid, h=h, applied=res.get("applied"), resolved=res.get("resolved"), f2p_pass=res.get("f2p_pass"), f2p_fail=res.get("f2p_fail"),
                   p2p_fail=res.get("p2p_fail"), error=res.get("error"), note=res.get("note"))
        graded[(iid, h)] = rec
        open(STATE, "a", encoding="utf-8").write(json.dumps(rec) + "\n")
        DG.say(f"  {iid} {h} applied={rec['applied']} resolved={rec['resolved']}")
    DG.cleanup(iid)

gen = collections.defaultdict(list)
for r in load(RAW):
    if r.get("http") == 200:
        gen[r["model"].split("/")[-1]].append(r)
summary = {}
for tag, rs in gen.items():
    pin, pout = PRICE[tag]
    cost = sum((r["usage_raw"]["prompt_tokens"] * pin + (r["usage_raw"]["total_tokens"] - r["usage_raw"]["prompt_tokens"]) * pout) / 1e6 for r in rs)
    s = dict(n=len(rs), cost_usd=round(cost, 4), truncated=sum(1 for r in rs if r.get("finish") == "length"),
             mean_visible_out=round(sum(r["usage_raw"]["completion_tokens"] for r in rs) / len(rs)),
             mean_hidden_thought=round(sum(r["usage_raw"]["total_tokens"] - r["usage_raw"]["prompt_tokens"] - r["usage_raw"]["completion_tokens"] for r in rs) / len(rs)))
    for arm in ("plain", "argus"):
        sts = collections.Counter(arms[(r["iid"], tag, arm)]["status"] for r in rs if (r["iid"], tag, arm) in arms)
        res = sum(1 for r in rs if (r["iid"], tag, arm) in arms and arms[(r["iid"], tag, arm)]["status"] == "applied"
                  and graded.get((r["iid"], sha(arms[(r["iid"], tag, arm)]["diff"])), {}).get("resolved") is True)
        s[arm] = dict(statuses=dict(sts), resolved=res)
    s["usd_per_solve_argus"] = round(cost / s["argus"]["resolved"], 4) if s["argus"]["resolved"] else None
    summary[tag] = s
json.dump(summary, open(SUMMARY, "w", encoding="utf-8"), indent=1)
DG.say(json.dumps(summary, indent=1))
