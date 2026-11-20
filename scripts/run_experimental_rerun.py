"""Redo the CORRECTED-feedback reruns (sealed set: data/blind_fix; development set: data/dev_fix) with the EXPERIMENTAL patch engine (0.2.0b1).

Why: scripts/regrade_released_engine.py found that the corrected reruns were applied with the released engine (0.2.0b2), because
harness/argus_apply.py imports whatever `argus` is installed at C:\\coding\\Argus. This script imports the 0.2.0b1 sources (commit 467b720,
extracted by `git archive` outside the repo) BEFORE any harness module, then replays every chain with the same prompts, seeds, corrected ANSI
cleaning and stop rule as scripts/run_blind_fix.py and scripts/run_dev_fix.py.

Method (as instructed): generate first, grade afterwards, one image pull per task.
  * Model calls are cached by request hash (all data/*/calls.jsonl). A call is made only when the prompt is new, i.e. when the corrected
    feedback differs because an earlier apply outcome changed under the experimental engine.
  * Rounds: each round replays all chains as far as possible. A chain stops ("need") when an applied patch has no known grade (known grades are read
    from results/loop_grading and results/grading by patch hash). After the round, ALL patches needed by ANY chain (sealed and development sets,
    both models, all arms) are de-duplicated, grouped by task, and graded in one pass with ONE image pull per task. Then the next round continues.
  * Chains that make no new model call and need no new grade reproduce their stored trajectory.

  python -X utf8 scripts/run_experimental_rerun.py --engine-dir C:\\Users\\dell\\AppData\\Local\\Temp\\exp_b1
"""
import argparse, collections, hashlib, json, os, re, subprocess, sys, threading, time, datetime, concurrent.futures as cf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument("--engine-dir", required=True)
ap.add_argument("--out-dir", default=os.path.join(ROOT, "data", "exp_engine_rerun"))
ap.add_argument("--workers", type=int, default=3)
ap.add_argument("--max-turns", type=int, default=3)
ap.add_argument("--max-rounds", type=int, default=8)
ap.add_argument("--no-grade", action="store_true", help="generation only: list the patches that need grading and stop")
ap.add_argument("--grade-workers", type=int, default=2, help="images graded concurrently")
args = ap.parse_args()
OUT = os.path.abspath(args.out_dir)
os.makedirs(OUT, exist_ok=True)

# ---- the experimental engine must be imported first
ENGINE = os.path.abspath(args.engine_dir)
sys.path.insert(0, ROOT)
sys.path.insert(0, ENGINE)
import argus  # noqa: E402
assert os.path.dirname(os.path.dirname(os.path.abspath(argus.__file__))).lower() == ENGINE.lower(), argus.__file__
assert argus.__version__ == "0.2.0b1", argus.__version__
import argus.patch.fuzzy_engine  # noqa: E402,F401  (loaded from the experimental sources before harness.argus_apply can touch sys.path)
import argus.patch.parser, argus.patch.paths  # noqa: E402,F401

from harness.keypool import KeyPool  # noqa: E402
from harness.context import fetch_source, build_file_context, ntok  # noqa: E402
from harness.prompts import SYSTEM, build_messages, prompt_hash  # noqa: E402
from harness.argus_apply import apply_output  # noqa: E402
import harness.dockergrade as DG  # noqa: E402  (chdir + stdout redirect; use DG.say)
assert "argus" in sys.modules and os.path.dirname(os.path.dirname(os.path.abspath(sys.modules["argus"].__file__))).lower() == ENGINE.lower()

ENVF = r"C:\coding\Argus\.env"
TASKS = r"C:\coding\Argus-research-archive\data\swe_bench_verified_tasks.jsonl"
MODELS = ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]
EFFORT, TEMP, MAX_OUT, PROMPT_BUDGET, EXCERPT = "medium", 1.0, 8000, 6000, 2000
PRICE = {"openai/gpt-oss-20b": (0.075, 0.30), "openai/gpt-oss-120b": (0.15, 0.60)}

full = {}
for l in open(TASKS, encoding="utf-8"):
    d = json.loads(l)
    full[d["instance_id"]] = d
man = json.load(open(os.path.join(ROOT, "manifests", "pilot100_manifest.json"), encoding="utf-8"))
meta = {t["instance_id"]: t for t in man["primary"] + man["reserve"]}


def load_traj(d):
    p = os.path.join(ROOT, "data", d, "trajectories.jsonl")
    return {r["iid"]: r for r in (json.loads(l) for l in open(p, encoding="utf-8")) if "models" in r}


def gold_file(t):
    fs = [f for f in re.findall(r"^diff --git a/(\S+) b/", t["gold_patch"], re.M) if not re.search(r"(^|/)(tests?|testing)(/|$)|test_|_test\.py|conftest", f)]
    assert len(fs) == 1, (t["instance_id"], fs)
    return fs[0]


SEALED_IDS = sorted(load_traj("blind_fix"))
DEV_IDS = json.load(open(os.path.join(ROOT, "data", "dev_fix_ids.json")))
# chains: (set, iid, model, arm)
CHAINS = [("sealed", i, m, "F") for i in SEALED_IDS for m in MODELS] + [("dev", i, m, a) for i in DEV_IDS for m in MODELS for a in ("F", "P")]

# ---- caches
lock = threading.Lock()
calls = {}
for dname in sorted(os.listdir(os.path.join(ROOT, "data"))):
    p = os.path.join(ROOT, "data", dname, "calls.jsonl")
    if dname == os.path.basename(OUT) or not os.path.exists(p):
        continue
    for l in open(p, encoding="utf-8"):
        try:
            r = json.loads(l)
        except Exception:
            continue
        if r.get("http") == 200 and r["key"] not in calls:
            calls[r["key"]] = r
CALLS = os.path.join(OUT, "calls.jsonl")
if os.path.exists(CALLS):
    for l in open(CALLS, encoding="utf-8"):
        r = json.loads(l)
        if r.get("http") == 200:
            calls[r["key"]] = r
SEEDED = len(calls)
NEWCALLS = [0]
pool = KeyPool(ENVF)
KLOCKS = {}
CTX = {}


def sha(s):
    return hashlib.sha1(s.encode()).hexdigest()[:10]


def call_model(body):
    key = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:20]
    with lock:
        kl = KLOCKS.setdefault(key, threading.Lock())
    with kl:
        with lock:
            c = calls.get(key)
        if c and c.get("http") == 200:
            return c
        res = pool.chat(body)
        rec = dict(key=key, http=res["status"], tries=res.get("tries"), latency_s=res.get("latency_s"), model=body["model"], effort=body["reasoning_effort"])
        if res["status"] == 200:
            d = res["data"]
            m = d["choices"][0]["message"]
            u = d.get("usage", {})
            rec.update(content=m.get("content"), finish=d["choices"][0].get("finish_reason"), prompt_tokens=u.get("prompt_tokens"), completion_tokens=u.get("completion_tokens"),
                       reasoning_tokens=(u.get("completion_tokens_details") or {}).get("reasoning_tokens"), served_model=d.get("model"))
        else:
            rec["error"] = str(res.get("error"))[:300]
        with lock:
            if res["status"] == 200:
                calls[key] = rec
            NEWCALLS[0] += 1
            open(CALLS, "a", encoding="utf-8").write(json.dumps(rec) + "\n")
        return rec


def failure_excerpt(text, failed_names, limit=EXCERPT):
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)  # corrected pattern (the original lacked the escape character)
    seg = text
    a, b = text.find(">>>>> Start Test Output"), text.find(">>>>> End Test Output")
    if a != -1:
        seg = text[a:b if b != -1 else len(text)]
    name = failed_names[0] if failed_names else ""
    core = re.split(r"::", name)[-1]
    core = re.sub(r"\[.*\]$", "", core)
    m = re.match(r"\w+", core)
    core = m.group(0) if m else ""
    out = None
    if core:
        lines = seg.split("\n")
        pos = 0
        for ln in lines:
            if re.match(r"^(={5,}|_{5,}|FAIL:|ERROR:)", ln) and core in ln:
                out = seg[pos:pos + limit]
                break
            pos += len(ln) + 1
        if out is None:
            i = seg.find(core)
            if i != -1:
                out = seg[max(0, i - 200):max(0, i - 200) + limit]
    if out is None:
        out = seg[-limit:]
    return out.strip()


def feedback_for(ap_res, grade, test_text):
    st = ap_res["status"]
    if st in ("truncated_no_output", "empty_output"):
        return "Your previous answer was cut off before it contained any SEARCH/REPLACE block (too much reasoning). Keep reasoning short and answer with the block(s) directly."
    if st == "no_blocks":
        return "Formatting error: Please output exact SEARCH/REPLACE blocks."
    if st == "path_refused":
        return f"Unsafe patch target: {ap_res.get('details', '')}"
    if st == "refused":
        return f"Patch application failed: {ap_res.get('refusal_reason', '')} {ap_res.get('details', '')}".strip()
    if st == "no_change":
        return "The edit produced no change to the file."
    if grade.get("applied") is False:
        if "cleanly" in (grade.get("log_text") or ""):
            return "The edit was applied, but the test run produced no results (the test suite crashed on startup). Make sure the edit keeps the module importable and syntactically valid."
        return "The edit could not be applied to the repository (the patch was rejected). Re-copy the SEARCH lines exactly from the file."
    names = grade.get("f2p_failed_names") or []
    ex = failure_excerpt(test_text, names)
    head = f"The edit was applied but the failing test still fails.\nFirst failing test: {names[0]}" if names else "The edit was applied but the tests still fail."
    return f"{head}\n```\n{ex}\n```"


def prompt_with_feedback(base_user, turn, feedback):
    if not feedback:
        return base_user
    return (base_user + f"\n\n## Result of your previous attempt (turn {turn - 1} of {args.max_turns})\n{feedback}\n\n"
            "The file shown above is the original, unmodified file. Write corrected SEARCH/REPLACE block(s) against it.")


def prompt_p(base_user, turn, prev, fbk):
    return (base_user + f"\n\n## Previous Attempt (FAILED) (turn {turn - 1} of {args.max_turns})\n```\n{(prev or '')[:3000]}\n```\n\n"
            f"## Result of the previous attempt\n{fbk}\n\n"
            "The file shown above is the original, unmodified file. Write corrected SEARCH/REPLACE block(s) against it. "
            "Include ALL necessary changes (the valid parts of your previous attempt and the corrections), without breaking existing behaviour.")


LOCAL_GRADES = os.path.join(OUT, "grades.jsonl")
LG = {}
if os.path.exists(LOCAL_GRADES):
    for _l in open(LOCAL_GRADES, encoding="utf-8"):
        _r = json.loads(_l)
        LG[(_r["iid"], _r["hash"])] = _r


def known_grade(iid, h):
    # grades without a harness report (the patch could not be applied inside the container) are kept here
    if (iid, h) in LG:
        return LG[(iid, h)]["grade"], LG[(iid, h)].get("test_text", "")
    for base in (DG.GRADE, DG.OLD_GRADE):
        res, text = DG.read_grade(base, iid, h)
        if res is not None and res.get("resolved") is not None:
            return res, text
    # earlier re-grade runs wrote grades through DG.grade_one as well (same directory); nothing else to look up
    return None, None


def accept_state(ap_res, grade):
    if ap_res["status"] == "applied" and grade and grade.get("applied") and grade.get("f2p_fail") == 0 and (grade.get("f2p_pass") or 0) > 0:
        return "accepted_resolved" if grade.get("resolved") else "accepted_regressed"
    return "continue"


def context(iid, target):
    with lock:
        if iid in CTX:
            return CTX[iid]
    t = full[iid]
    src = fetch_source(t["repo"], t["base_commit"], target)
    code_budget = max(500, PROMPT_BUDGET - ntok(SYSTEM) - ntok(t["problem_statement"][:6000]) - 250)
    code, spans, info = build_file_context(t, src, code_budget)
    msgs = build_messages(t, target, code)
    with lock:
        CTX[iid] = (msgs, info)
    return CTX[iid]


class Need(Exception):
    def __init__(self, iid, h, diff):
        self.iid, self.h, self.diff = iid, h, diff


def run_chain(cset, iid, model, arm):
    """Replay one chain. Returns ('done', attempts) or ('need', (iid, hash, diff))."""
    t = full[iid]
    target = meta[iid]["gold_file"] if cset == "dev" else gold_file(t)
    base_msgs, info = context(iid, target)

    def attempt(seed, turn, feedback, prev):
        if arm == "F":
            user = prompt_with_feedback(base_msgs[1]["content"], turn, feedback)
        else:
            user = prompt_p(base_msgs[1]["content"], turn, prev, feedback) if feedback else base_msgs[1]["content"]
        body = {"model": model, "messages": [base_msgs[0], dict(base_msgs[1], content=user)], "temperature": TEMP, "max_completion_tokens": MAX_OUT, "reasoning_effort": EFFORT, "seed": seed}
        rec = call_model(body)
        tr = dict(turn=turn, seed=seed, http=rec["http"], feedback_in=feedback)
        if rec["http"] != 200:
            tr.update(error=rec.get("error"), state="api_error", cost_usd=0)
            return tr, None, None
        cost = (rec["prompt_tokens"] * PRICE[model][0] + rec["completion_tokens"] * PRICE[model][1]) / 1e6
        ap_res = apply_output(t["repo"], t["base_commit"], target, rec.get("content"), rec.get("finish"))
        tr.update(finish=rec["finish"], prompt_tokens=rec["prompt_tokens"], completion_tokens=rec["completion_tokens"], reasoning_tokens=rec["reasoning_tokens"],
                  cost_usd=round(cost, 6), apply_status=ap_res["status"], max_tier=ap_res.get("max_tier"), refusal_reason=ap_res.get("refusal_reason"))
        grade, test_text = None, ""
        if ap_res["status"] == "applied":
            h = sha(ap_res["diff"])
            tr["patch_hash"] = h
            grade, test_text = known_grade(iid, h)
            if grade is None:
                raise Need(iid, h, ap_res["diff"])
            tr["grade"] = {k: v for k, v in grade.items() if k not in ("log_text",)}
        tr["state"] = accept_state(ap_res, grade)
        return tr, feedback_for(ap_res, grade or {}, test_text), (rec.get("content") or "")

    trs = []
    try:
        tr, fb, content = attempt(5000, 1, None, None)
        trs.append(tr)
        turn = 1
        while trs[-1]["state"] == "continue" and turn < args.max_turns and fb is not None:
            turn += 1
            tr, nfb, ncontent = attempt((6000 if arm == "F" else 9000) + turn, turn, fb, content)
            tr["feedback_out"] = nfb
            trs.append(tr)
            fb, content = nfb, ncontent
    except Need as n:
        return "need", (n.iid, n.h, n.diff)
    return "done", trs


def other_grader_active():
    """True if another Docker grading run seems active (a SWE-bench container, or another harness grading script)."""
    try:
        names = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True, timeout=60).stdout.split()
    except Exception:
        names = []
    if any(n.startswith("sweb.eval") for n in names):
        return True
    cmd = ("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'regrade_released_engine|run_dev_fix|run_blind_fix|grade_docker|run_evaluation' "
           "-and $_.Name -match '^python' -and $_.ProcessId -ne " + str(os.getpid()) + " } | Select-Object -ExpandProperty ProcessId")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=120).stdout.split()
    except Exception:
        out = []
    return bool(out)


def grade_batch(need):
    """need: {iid: {hash: diff}}. One image pull per task; all patches of the task graded on it."""
    while other_grader_active():
        DG.say("another grading run is active; waiting 120 s")
        time.sleep(120)

    def one(iid):
        diffs = need[iid]
        if not DG.pull(iid):
            DG.say("pull failed", iid)
            return iid, 0
        n = 0
        try:
            for h, diff in diffs.items():
                grade, ttext = DG.grade_one(iid, h, diff)
                n += 1
                if grade.get("resolved") is not None:
                    rec = dict(iid=iid, hash=h, grade=grade, test_text=ttext or "")
                    with lock:
                        LG[(iid, h)] = rec
                        open(LOCAL_GRADES, "a", encoding="utf-8").write(json.dumps(rec) + chr(10))
                DG.say("graded", iid, h, "resolved=", grade.get("resolved"), "applied=", grade.get("applied"))
        finally:
            DG.cleanup(iid)
        return iid, n

    done = 0
    with cf.ThreadPoolExecutor(args.grade_workers) as ex:
        for iid, n in ex.map(one, list(need)):
            done += n
    return done


results = {}
DG.say(f"engine {argus.__version__} at {ENGINE}; chains {len(CHAINS)} (sealed {len(SEALED_IDS)} tasks x2, dev {len(DEV_IDS)} tasks x4); {SEEDED} cached calls; prompt_hash={prompt_hash()}")
for rnd in range(1, args.max_rounds + 1):
    pending = [c for c in CHAINS if c not in results]
    if not pending:
        break
    need = collections.defaultdict(dict)
    t0 = time.time()
    c0 = NEWCALLS[0]
    with cf.ThreadPoolExecutor(args.workers) as ex:
        futs = {ex.submit(run_chain, *c): c for c in pending}
        for f in cf.as_completed(futs):
            c = futs[f]
            try:
                kind, val = f.result()
            except Exception as e:
                import traceback
                DG.say("EXCEPTION", c, repr(e)[:200])
                DG.say(traceback.format_exc()[-600:])
                continue
            if kind == "done":
                results[c] = val
            else:
                iid, h, diff = val
                need[iid][h] = diff
    n_need = sum(len(v) for v in need.values())
    DG.say(f"round {rnd}: {len(results)}/{len(CHAINS)} chains complete, new model calls this round {NEWCALLS[0] - c0}, patches to grade {n_need} in {len(need)} tasks, {time.time() - t0:.0f}s")
    json.dump({i: dict(diffs) for i, diffs in need.items()}, open(os.path.join(OUT, f"need_round{rnd}.json"), "w"), indent=0)
    if not need:
        break
    if args.no_grade:
        DG.say("--no-grade: stopping before grading")
        sys.exit(0)
    DG.say(f"grading {n_need} patches over {len(need)} images (one pull per task)")
    grade_batch(need)

DG.say(f"finished after rounds: {len(results)}/{len(CHAINS)} chains complete; total new model calls {NEWCALLS[0]}")

# ---- write trajectories in the schema of data/blind_fix and data/dev_fix
trajs = {"sealed": {}, "dev": {}}
for (cset, iid, model, arm), trs in results.items():
    last = trs[-1]
    o = dict(attempts=trs, n=len(trs), stop=last["state"], solved=last["state"] == "accepted_resolved", cost_usd=round(sum(x.get("cost_usd", 0) for x in trs), 6))
    trajs[cset].setdefault(iid, dict(iid=iid, engine="0.2.0b1", models={}))["models"].setdefault(model.split("/")[-1], {})[arm] = o
for cset, rows in trajs.items():
    with open(os.path.join(OUT, f"trajectories_{cset}.jsonl"), "w", encoding="utf-8") as f:
        for iid in sorted(rows):
            f.write(json.dumps(rows[iid]) + "\n")
DG.say("wrote trajectories to", OUT)
