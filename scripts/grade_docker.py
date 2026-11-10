"""Grade every distinct candidate patch with the official SWE-bench harness (swebench 5.0.2, pre-built images).

One task at a time: pull the instance image, grade all distinct patches for that task (plain/Argus x 20B/120B, plus the
GOLD patch as a harness-validity control), then remove the image.  The next image is pulled in the background while the
current one is graded (at most two images on disk).  Resumable: results are appended to results/grading/state.jsonl.

Run with the SYSTEM python in UTF-8 mode (Windows default cp1252 loses reports):  python -X utf8 scripts/grade_docker.py [--limit N] [--ids ...]
"""
import argparse, collections, hashlib, io, json, os, shutil, subprocess, sys, threading, time, contextlib, traceback
os.environ["PYTHONIOENCODING"] = "utf-8"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRADE = os.path.join(ROOT, "results", "grading")
os.makedirs(GRADE, exist_ok=True)
ap = argparse.ArgumentParser()
ap.add_argument("--apply-dir", default=os.path.join(ROOT, "data", "phase1"))
ap.add_argument("--state", default=os.path.join(GRADE, "state.jsonl"))
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--ids", nargs="*")
ap.add_argument("--timeout", type=int, default=1800)
ap.add_argument("--min-free-gb", type=float, default=15.0)
ap.add_argument("--no-gold", action="store_true")
args = ap.parse_args()
STATE = os.path.abspath(args.state)
args.apply_dir = os.path.abspath(args.apply_dir)

man = json.load(open(os.path.join(ROOT, "manifests", "pilot100_manifest.json"), encoding="utf-8"))
ids = args.ids or [t["instance_id"] for t in man["primary"]]
full = {}
for l in open(r"C:\coding\Argus-research-archive\data\swe_bench_verified_tasks.jsonl", encoding="utf-8"):
    d = json.loads(l); full[d["instance_id"]] = d

# ---- candidates per task: distinct diffs with the labels that produced them
cands = collections.defaultdict(dict)  # iid -> hash -> dict(diff, labels)
for kind in ("plain", "argus"):
    for tag in ("gpt-oss-20b", "gpt-oss-120b"):
        p = os.path.join(args.apply_dir, f"{kind}_apply_{tag}.jsonl")
        if not os.path.exists(p):
            continue
        for l in open(p, encoding="utf-8"):
            r = json.loads(l)
            if r["status"] != "applied":
                continue
            h = hashlib.sha1(r["diff"].encode()).hexdigest()[:10]
            c = cands[r["iid"]].setdefault(h, dict(diff=r["diff"], labels=[]))
            c["labels"].append(f"{kind}:{tag}")
if not args.no_gold:
    for iid in ids:
        g = full[iid]["gold_patch"]
        h = hashlib.sha1(g.encode()).hexdigest()[:10]
        cands[iid].setdefault(h, dict(diff=g, labels=[]))["labels"].append("gold")

done = set()
if os.path.exists(STATE):
    for l in open(STATE, encoding="utf-8"):
        r = json.loads(l); done.add((r["iid"], r["hash"]))


def image_name(iid):
    return "swebench/sweb.eval.x86_64." + iid.replace("__", "_1776_").lower() + ":latest"


def sh(cmd, timeout=3600):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")


def free_gb():
    return shutil.disk_usage("C:\\").free / 1e9


def pull(iid):
    img = image_name(iid)
    if sh(["docker", "image", "inspect", img]).returncode == 0:
        return True
    while free_gb() < args.min_free_gb:
        say(f"  low disk ({free_gb():.1f} GB), waiting", flush=True)
        time.sleep(60)
    for attempt in range(3):
        t0 = time.time()
        r = sh(["docker", "pull", "-q", img], timeout=3 * 3600)
        if r.returncode == 0:
            say(f"  pulled {img.split('.')[-1]} in {time.time()-t0:.0f}s", flush=True)
            return True
        say(f"  pull failed ({attempt+1}): {r.stderr.strip()[:150]}", flush=True)
        time.sleep(20)
    return False


def cleanup(iid):
    sh(["docker", "rmi", "-f", image_name(iid)])
    sh(["docker", "container", "prune", "-f"])


os.chdir(GRADE)  # swebench writes logs/run_evaluation relative to cwd

# Windows fix: the harness writes patch.diff and eval.sh with Path.write_text (text mode -> CRLF), which breaks
# git apply and bash inside the Linux container (even the gold patch fails). Force LF.
import pathlib
_orig_write_text = pathlib.Path.write_text
def _write_text_lf(self, data, encoding=None, errors=None, newline=None):
    return _orig_write_text(self, data, encoding=encoding or "utf-8", errors=errors, newline="\n")
pathlib.Path.write_text = _write_text_lf

_real_out = sys.stdout
_logf = open(os.path.join(GRADE, "swebench_stdout.log"), "a", encoding="utf-8", buffering=1)
sys.stdout = _logf
sys.stderr = _logf
def say(*a, **k):
    print(*a, file=_real_out, flush=True)

import swebench.harness.run_evaluation as RE


def grade_one(iid, h, diff):
    run_id = f"p100_{iid}_{h}"
    pred_path = os.path.join(GRADE, f"pred_{iid}_{h}.jsonl")
    open(pred_path, "w", encoding="utf-8").write(json.dumps(dict(instance_id=iid, model_name_or_path=f"c{h}", model_patch=diff)) + "\n")
    t0 = time.time()
    err = None
    try:
        if True:
            RE.main(dataset_name="SWE-bench/SWE-bench_Verified", split="test", instance_ids=[iid], predictions_path=pred_path,
                    max_workers=1, open_file_limit=4096, run_id=run_id, timeout=args.timeout, rewrite_reports=False, modal=False,
                    report_dir=os.path.join(GRADE, "reports"))
    except Exception as e:
        err = repr(e)[:300]
    rep = os.path.join(GRADE, "logs", "run_evaluation", run_id, f"c{h}", iid, "report.json")
    out = dict(iid=iid, hash=h, secs=round(time.time() - t0, 1))
    if os.path.exists(rep):
        d = json.load(open(rep, encoding="utf-8")).get(iid, {})
        ts = d.get("tests_status", {})
        cnt = lambda k, w: len(ts.get(k, {}).get(w, []))
        out.update(applied=d.get("patch_successfully_applied"), resolved=d.get("resolved"),
                   f2p_pass=cnt("FAIL_TO_PASS", "success"), f2p_fail=cnt("FAIL_TO_PASS", "failure"),
                   p2p_pass=cnt("PASS_TO_PASS", "success"), p2p_fail=cnt("PASS_TO_PASS", "failure"),
                   f2p_failed_names=ts.get("FAIL_TO_PASS", {}).get("failure", [])[:10], p2p_failed_names=ts.get("PASS_TO_PASS", {}).get("failure", [])[:10],
                   completed=d.get("completed"))
    else:
        out.update(applied=None, resolved=None, error=err or "no report")
    try:
        os.remove(pred_path)
    except OSError:
        pass
    return out


todo = [i for i in ids if any((i, h) not in done for h in cands[i])]
if args.limit:
    todo = todo[:args.limit]
say(f"{len(todo)} tasks to grade; {sum(len(cands[i]) for i in todo)} distinct patches; free disk {free_gb():.0f} GB", flush=True)

import concurrent.futures as cf
state_lock = threading.Lock()
counter = {"n": 0}
WORKERS = 3  # tasks in parallel; each task's patches run in series (the harness shares one logger per instance id)


def do_task(iid):
    t0 = time.time()
    if not pull(iid):
        with state_lock:
            for h in cands[iid]:
                if (iid, h) not in done:
                    open(STATE, "a", encoding="utf-8").write(json.dumps(dict(iid=iid, hash=h, labels=cands[iid][h]["labels"], error="image pull failed")) + "\n")
        say(f"{iid}: image pull failed")
        return
    try:
        for h, c in cands[iid].items():
            if (iid, h) in done:
                continue
            r = grade_one(iid, h, c["diff"])
            r["labels"] = c["labels"]
            with state_lock:
                open(STATE, "a", encoding="utf-8").write(json.dumps(r) + "\n")
            say(f"{iid} {h} {','.join(c['labels'])}: applied={r.get('applied')} resolved={r.get('resolved')} f2p {r.get('f2p_pass')}/{(r.get('f2p_pass') or 0)+(r.get('f2p_fail') or 0)} {r['secs']}s")
    finally:
        cleanup(iid)
    with state_lock:
        counter["n"] += 1
        say(f"[{counter['n']}/{len(todo)}] {iid} done in {time.time()-t0:.0f}s; free disk {free_gb():.0f} GB")


with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
    list(ex.map(do_task, todo))
say("all done")
