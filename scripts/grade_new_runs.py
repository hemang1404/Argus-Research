"""Revisions 11 and 12: apply (plain and Argus) the stored outputs of one or more run groups, then Docker-grade every distinct unseen patch of ALL groups
together, one task image at a time, so each task image is pulled once. Known grades are reused by (task, patch hash). Resumable.

  python -X utf8 scripts/grade_new_runs.py qwen gemma26     # several groups in one pass (one image pull per task)
  python -X utf8 scripts/grade_new_runs.py gemma31          # a later group alone

Groups: gemma26 / gemma31 = data/gemma_sweep/raw.jsonl with model gemma-4-26b-a4b-it / gemma-4-31b-it (31B: content before the last </thought> removed first);
qwen = Qwen3.5 2B/4B/9B on the 100 tasks (30 Revision 10 outputs + 70 Revision 11 outputs). Grades are appended to data/new_runs_grading.jsonl.
"""
import collections, hashlib, json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
GROUPS = sys.argv[1:]
assert GROUPS, "give at least one group"
IDS = set(json.load(open(os.path.join(ROOT, "data", "gemini_sweep", "task_ids_full.json")))["ids"])
import harness.dockergrade as DG  # chdir + stdout redirect; console output via DG.say

STATE = os.path.join(ROOT, "data", "new_runs_grading.jsonl")


def load(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")] if os.path.exists(p) else []


def sha(s):
    return hashlib.sha1(s.encode()).hexdigest()[:10]


def strip_thought(c):
    i = (c or "").rfind("</thought>")
    return c[i + len("</thought>"):].lstrip() if i != -1 else c


def prepare(group):
    """write the raw file of a group, apply plain and Argus, return (tags, apply_dir)"""
    if group.startswith("gemma"):
        D = os.path.join(ROOT, "data", "gemma_sweep")
        model = "gemma-4-26b-a4b-it" if group == "gemma26" else "gemma-4-31b-it"
        recs = [r for r in load(os.path.join(D, "raw.jsonl")) if r["model"].endswith(model) and r.get("http") == 200]
        if group == "gemma31":
            for r in recs:
                r["raw_content"] = r.get("content"); r["content"] = strip_thought(r.get("content"))
        tags = [model]
    elif group == "qwen":
        D = os.path.join(ROOT, "data", "qwen_probe")
        recs = []
        for tag in ("2B", "4B", "9B"):
            probe = load(os.path.join(D, "kaggle_run1", f"outputs_Qwen3.5-{tag}.jsonl"))
            rem = load(os.path.join(D, "kaggle_run2", f"outputs_Qwen3.5-{tag}_remaining.jsonl"))
            for r in probe + rem:
                if r.get("content") is not None and r["iid"] in IDS:
                    r["sample"] = 0; r["http"] = 200
                    recs.append(r)
        tags = ["Qwen3.5-2B", "Qwen3.5-4B", "Qwen3.5-9B"]
    else:
        sys.exit("unknown group " + group)
    recs = [r for r in recs if r["iid"] in IDS]
    raw = os.path.join(D, f"raw_{group}.jsonl")
    apply_dir = os.path.join(D, f"apply_{group}")
    os.makedirs(apply_dir, exist_ok=True)
    open(raw, "w", encoding="utf-8").write("".join(json.dumps(r) + "\n" for r in recs))
    DG.say(f"{group}: {len(recs)} outputs for {len(IDS)} tasks")
    for script in ("apply_plain.py", "apply_argus.py"):
        r = subprocess.run([sys.executable, "-X", "utf8", os.path.join(ROOT, "scripts", script), "--raw", raw, "--out-dir", apply_dir], capture_output=True, text=True, encoding="utf-8", errors="replace")
        DG.say(script, "->", (r.stdout.strip().splitlines() or [""])[-1][:300], r.stderr.strip()[-200:] if r.returncode else "")
    return tags, apply_dir


known = {}
for f in ("results/grading/state_t1.jsonl", "results/grading/state.jsonl", "results/grading/state_new.jsonl"):
    for r in load(os.path.join(ROOT, f)):
        if r.get("hash") and r.get("resolved") is not None:
            known[(r["iid"], r["hash"])] = r["resolved"]
for f in ("data/probe_gemini/grading.jsonl", "data/gemini_sweep/grading.jsonl", "data/new_runs_grading.jsonl"):
    for r in load(os.path.join(ROOT, f)):
        if r.get("h") and r.get("resolved") is not None:
            known[(r["iid"], r["h"])] = r["resolved"]

need = collections.defaultdict(dict)
for group in GROUPS:
    tags, apply_dir = prepare(group)
    for tag in tags:
        for arm in ("plain", "argus"):
            for r in load(os.path.join(apply_dir, f"{arm}_apply_{tag}.jsonl")):
                if r["status"] == "applied":
                    need[r["iid"]][sha(r["diff"])] = r["diff"]
todo = [(iid, h) for iid, hs in sorted(need.items()) for h in hs if (iid, h) not in known]
DG.say(f"{sum(len(v) for v in need.values())} distinct applied patches over {len(need)} tasks; {len(todo)} to grade; groups {GROUPS}")
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
