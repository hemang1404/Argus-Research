"""Docker grading of one candidate patch with the official swebench harness (5.0.2, pre-built images). Used by scripts/run_loop.py.

Importing this module changes the process cwd to the grading directory (swebench writes logs relative to cwd) and redirects
stdout/stderr to a log file; use `say()` for console output. All paths handed in must be absolute.
Same Windows fixes as scripts/grade_docker.py: LF line endings for harness-written patch/eval files.
"""
import json, os, pathlib, shutil, subprocess, sys, threading, time
os.environ["PYTHONIOENCODING"] = "utf-8"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRADE = os.path.join(ROOT, "results", "loop_grading")
OLD_GRADE = os.path.join(ROOT, "results", "grading")
os.makedirs(GRADE, exist_ok=True)
os.chdir(GRADE)

_orig_write_text = pathlib.Path.write_text
def _write_text_lf(self, data, encoding=None, errors=None, newline=None):
    return _orig_write_text(self, data, encoding=encoding or "utf-8", errors=errors, newline="\n")
pathlib.Path.write_text = _write_text_lf

_real_out = sys.stdout
_logf = open(os.path.join(GRADE, "swebench_stdout.log"), "a", encoding="utf-8", buffering=1)
sys.stdout = _logf
sys.stderr = _logf
_say_lock = threading.Lock()


def say(*a):
    with _say_lock:
        print(*a, file=_real_out, flush=True)


import swebench.harness.run_evaluation as RE

MIN_FREE_GB = 15.0


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
    while free_gb() < MIN_FREE_GB:
        say(f"  low disk ({free_gb():.1f} GB), waiting")
        time.sleep(60)
    for attempt in range(3):
        t0 = time.time()
        r = sh(["docker", "pull", "-q", img], timeout=3 * 3600)
        if r.returncode == 0:
            say(f"  pulled {iid} in {time.time()-t0:.0f}s")
            return True
        say(f"  pull failed ({attempt+1}) {iid}: {r.stderr.strip()[:150]}")
        time.sleep(20)
    return False


def cleanup(iid):
    sh(["docker", "rmi", "-f", image_name(iid)])
    sh(["docker", "container", "prune", "-f"])


def _parse_report(rep):
    d = json.load(open(rep, encoding="utf-8"))
    return d


def _result_from_run(run_id, h, iid):
    rep = os.path.join(GRADE, "logs", "run_evaluation", run_id, f"c{h}", iid, "report.json")
    return rep


def read_grade(base_dir, iid, h, run_prefix="p100"):
    """Return (result dict, test_output text) from an existing grading directory, or (None, None)."""
    run_id = f"{run_prefix}_{iid}_{h}"
    d = os.path.join(base_dir, "logs", "run_evaluation", run_id, f"c{h}", iid)
    rep = os.path.join(d, "report.json")
    if not os.path.exists(rep):
        return None, None
    ts = json.load(open(rep, encoding="utf-8")).get(iid, {})
    st = ts.get("tests_status", {})
    cnt = lambda k, w: len(st.get(k, {}).get(w, []))
    res = dict(applied=ts.get("patch_successfully_applied"), resolved=ts.get("resolved"),
               f2p_pass=cnt("FAIL_TO_PASS", "success"), f2p_fail=cnt("FAIL_TO_PASS", "failure"),
               p2p_pass=cnt("PASS_TO_PASS", "success"), p2p_fail=cnt("PASS_TO_PASS", "failure"),
               f2p_failed_names=st.get("FAIL_TO_PASS", {}).get("failure", [])[:10], p2p_failed_names=st.get("PASS_TO_PASS", {}).get("failure", [])[:10])
    to = os.path.join(d, "test_output.txt")
    text = open(to, encoding="utf-8", errors="replace").read() if os.path.exists(to) else ""
    log = os.path.join(d, "run_instance.log")
    res["log_text"] = open(log, encoding="utf-8", errors="replace").read()[-3000:] if os.path.exists(log) else ""
    return res, text


def grade_one(iid, h, diff, timeout=1800):
    """Grade a diff in Docker (image must already be pulled). Returns (result dict, test_output text)."""
    run_id = f"p100_{iid}_{h}"
    pred_path = os.path.join(GRADE, f"pred_{iid}_{h}.jsonl")
    open(pred_path, "w", encoding="utf-8").write(json.dumps(dict(instance_id=iid, model_name_or_path=f"c{h}", model_patch=diff)) + "\n")
    t0 = time.time()
    err = None
    try:
        RE.main(dataset_name="SWE-bench/SWE-bench_Verified", split="test", instance_ids=[iid], predictions_path=pred_path, max_workers=1,
                open_file_limit=4096, run_id=run_id, timeout=timeout, rewrite_reports=False, modal=False, report_dir=os.path.join(GRADE, "reports"))
    except Exception as e:
        err = repr(e)[:300]
    res, text = read_grade(GRADE, iid, h)
    if res is None:
        # harness aborts before writing a report when the diff cannot be applied inside the container
        lg = os.path.join(GRADE, "logs", "run_evaluation", run_id, f"c{h}", iid, "run_instance.log")
        txt = open(lg, encoding="utf-8", errors="replace").read() if os.path.exists(lg) else ""
        if "Patch Apply Failed" in txt:
            res = dict(applied=False, resolved=False, f2p_pass=0, f2p_fail=0, p2p_pass=0, p2p_fail=0, f2p_failed_names=[], p2p_failed_names=[],
                       note="harness Patch Apply Failed", log_text=txt[-3000:])
        else:
            res = dict(applied=None, resolved=None, error=err or "no report", log_text=txt[-3000:])
        text = ""
    res["secs"] = round(time.time() - t0, 1)
    try:
        os.remove(pred_path)
    except OSError:
        pass
    return res, text
