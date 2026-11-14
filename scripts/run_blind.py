"""Revision 13 (pre-registered, tag blind200-prereg): confirmatory blind test on the 200 sealed tasks of manifests/blind200_manifest.json.

Per task, with ONE image pull: (1) grade the gold patch (control; a task whose gold does not resolve is excluded without replacement);
(2) for gpt-oss-20b and gpt-oss-120b run arm R (independent re-draws, seed 5000+d) and arm F (Revision 5 result block, previous answer not shown,
seed 6000+attempt; attempt 1 shared with R), <= 3 attempts, medium effort, T=1.0, cap 8000, prompt p1 + 6,000-token context, target file GIVEN,
stock Argus apply layer; stop at the first patch that passes all FAIL_TO_PASS tests; solved iff that patch resolves in the full harness.
Resumable (one JSON line per finished task; model calls cached by request hash). Smoke tests only on design tasks:

  python -X utf8 scripts/run_blind.py --ids astropy__astropy-12907 --out-dir data/blind_smoke
"""
import argparse, hashlib, json, os, re, sys, threading, time, datetime, urllib.request, urllib.error, concurrent.futures as cf
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
ap = argparse.ArgumentParser()
ap.add_argument("--ids", nargs="*")
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--out-dir", default=os.path.join(ROOT, "data", "blind"))
ap.add_argument("--workers", type=int, default=3)
ap.add_argument("--max-turns", type=int, default=3)
args = ap.parse_args()
OUT = os.path.abspath(args.out_dir)
os.makedirs(OUT, exist_ok=True)

from harness.keypool import KeyPool
from harness.context import fetch_source, build_file_context, ntok
from harness.prompts import SYSTEM, build_messages, prompt_hash
from harness.argus_apply import apply_output
import harness.dockergrade as DG  # chdir + stdout redirect happen here; use DG.say for console output

ENV = r"C:\coding\Argus\.env"
TASKS = r"C:\coding\Argus-research-archive\data\swe_bench_verified_tasks.jsonl"
MODELS = ["openai/gpt-oss-20b", "openai/gpt-oss-120b"] + ([] if os.environ.get("ARGUS_NO_GEMMA") else ["google/gemma-4-26b-a4b-it"])  # Revision 16: Gemma 26B added as EXPLORATORY arms in the same image pull
GEMMA = "google/gemma-4-26b-a4b-it"
EFFORT, TEMP, MAX_OUT, PROMPT_BUDGET, EXCERPT = "medium", 1.0, 8000, 6000, 2000
PRICE = {"openai/gpt-oss-20b": (0.075, 0.30), "openai/gpt-oss-120b": (0.15, 0.60), GEMMA: (0.0, 0.0)}

ids = args.ids or json.load(open(os.path.join(ROOT, "manifests", "blind200_manifest.json"), encoding="utf-8"))["ids"]
if args.limit:
    ids = ids[:args.limit]
full = {}
for l in open(TASKS, encoding="utf-8"):
    d = json.loads(l); full[d["instance_id"]] = d

pool = KeyPool(ENV)
gkey = None
if GEMMA in MODELS:
    for _l in open(ENV, encoding="utf-8", errors="replace"):
        _m = re.match(r"\s*GOOGLE_API_KEY\s*=\s*(.*)", _l)
        if _m:
            gkey = _m.group(1).strip().strip("\"'")
    assert gkey, "GOOGLE_API_KEY missing"
GAPI = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"


def google_chat(body):
    last = None
    for attempt in range(1, 7):
        req = urllib.request.Request(GAPI, data=json.dumps(body).encode(), headers={"Authorization": "Bearer " + gkey, "Content-Type": "application/json", "User-Agent": "argus-research-pilot50"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                return dict(status=200, data=json.loads(r.read()), latency_s=round(time.time() - t0, 2), tries=attempt)
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            last = dict(status=e.code, error=raw[:300].replace(gkey, "<key>"), latency_s=round(time.time() - t0, 2), tries=attempt)
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(min(10 * attempt, 60)); continue
            return last
        except Exception as e:
            last = dict(status=-1, error=str(e)[:200], latency_s=round(time.time() - t0, 2), tries=attempt)
            time.sleep(5 * attempt)
    return last
lock = threading.Lock()
CALLS = os.path.join(OUT, "calls.jsonl")
TRAJ = os.path.join(OUT, "trajectories.jsonl")
PULLFAIL = os.path.join(OUT, "pull_failures.jsonl")
calls = {}
KLOCKS, HLOCKS = {}, {}
GRADE_SEM = threading.Semaphore(4)  # at most 4 harness containers at once from this process
if os.path.exists(CALLS):
    for l in open(CALLS, encoding="utf-8"):
        r = json.loads(l); calls[r["key"]] = r
done = set()
if os.path.exists(TRAJ):
    for l in open(TRAJ, encoding="utf-8"):
        done.add(json.loads(l)["iid"])


def sha(s):
    return hashlib.sha1(s.encode()).hexdigest()[:10]


def gold_file(t):
    fs = [f for f in re.findall(r"^diff --git a/(\S+) b/", t["gold_patch"], re.M) if not re.search(r"(^|/)(tests?|testing)(/|$)|test_|_test\.py|conftest", f)]
    assert len(fs) == 1, (t["instance_id"], fs)
    return fs[0]


def call_model(body, nonce=None):
    # nonce only separates cache entries of unseeded Gemma draws; it is never sent to the API
    key = hashlib.sha256(json.dumps([body, nonce] if nonce else body, sort_keys=True).encode()).hexdigest()[:20]
    with lock:
        klock = KLOCKS.setdefault(key, threading.Lock())
    with klock:  # identical requests issued by the R and F arms at the same time are made once (attempt 1 is shared)
        return _call_model(body, nonce, key)


def _call_model(body, nonce, key):
    with lock:
        c = calls.get(key)
    if c and c.get("http") == 200:
        return c
    res = google_chat(body) if body["model"] == "gemma-4-26b-a4b-it" else pool.chat(body)
    rec = dict(key=key, http=res["status"], tries=res.get("tries"), latency_s=res.get("latency_s"), model=body["model"], effort=body.get("reasoning_effort"))
    if res["status"] == 200:
        d = res["data"]; m = d["choices"][0]["message"]; u = d.get("usage", {})
        rec.update(content=m.get("content"), finish=d["choices"][0].get("finish_reason"), prompt_tokens=u.get("prompt_tokens"),
                   completion_tokens=u.get("completion_tokens"), reasoning_tokens=(u.get("completion_tokens_details") or {}).get("reasoning_tokens"),
                   served_model=d.get("model"))
    else:
        rec["error"] = str(res.get("error"))[:300]
    with lock:
        calls[key] = rec
        open(CALLS, "a", encoding="utf-8").write(json.dumps(rec) + "\n")
    return rec


def failure_excerpt(text, failed_names, limit=EXCERPT):
    """text of the first failing FAIL_TO_PASS test from the harness test output (same heuristic as Revisions 5, 7, 9)."""
    text = re.sub(r"\[[0-9;]*[A-Za-z]|\[[0-9;]*m", "", text)
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
                out = seg[pos:pos + limit]; break
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


def accept_state(ap_res, grade):
    if ap_res["status"] == "applied" and grade and grade.get("applied") and grade.get("f2p_fail") == 0 and (grade.get("f2p_pass") or 0) > 0:
        return "accepted_resolved" if grade.get("resolved") else "accepted_regressed"
    return "continue"


def run_task(iid):
    t0 = time.time()
    t = full[iid]; target = gold_file(t)
    st = dict(pulled=False, memo={})
    if not DG.pull(iid):
        with lock:
            open(PULLFAIL, "a", encoding="utf-8").write(json.dumps(dict(iid=iid, ts=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"))) + "\n")
        return dict(iid=iid, pull_failed=True)
    st["pulled"] = True
    try:
        gh = sha(t["gold_patch"])
        gres, _ = DG.grade_one(iid, gh, t["gold_patch"])
        gold = dict(resolved=gres.get("resolved"), applied=gres.get("applied"), f2p_pass=gres.get("f2p_pass"), f2p_fail=gres.get("f2p_fail"), p2p_fail=gres.get("p2p_fail"))
        out = dict(iid=iid, target_file=target, gold=gold, prompt_hash=prompt_hash(), ts=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"))
        if gold["resolved"] is not True:
            out.update(excluded="gold_failed", secs=round(time.time() - t0, 1))
            with lock:
                open(TRAJ, "a", encoding="utf-8").write(json.dumps(out) + "\n")
            return out
        src = fetch_source(t["repo"], t["base_commit"], target)
        code_budget = max(500, PROMPT_BUDGET - ntok(SYSTEM) - ntok(t["problem_statement"][:6000]) - 250)
        code, spans, info = build_file_context(t, src, code_budget)
        base_msgs = build_messages(t, target, code)
        out["ctx"] = info

        def attempt(model, seed, feedback, turn):
            msgs = [base_msgs[0], dict(role="user", content=prompt_with_feedback(base_msgs[1]["content"], turn, feedback))]
            if model == GEMMA:  # as the Gemma sweep and Revision 15: no reasoning parameter, no seed, 16,000 output tokens
                body = {"model": "gemma-4-26b-a4b-it", "messages": msgs, "temperature": TEMP, "max_completion_tokens": 16000}
                rec = call_model(body, nonce=seed)
            else:
                body = {"model": model, "messages": msgs, "temperature": TEMP, "max_completion_tokens": MAX_OUT, "reasoning_effort": EFFORT, "seed": seed}
                rec = call_model(body)
            tr = dict(turn=turn, seed=seed, http=rec["http"], feedback_in=feedback)
            if rec["http"] != 200:
                tr.update(error=rec.get("error"), state="api_error", cost_usd=0)
                return tr, None
            cost = (rec["prompt_tokens"] * PRICE[model][0] + rec["completion_tokens"] * PRICE[model][1]) / 1e6
            ap_res = apply_output(t["repo"], t["base_commit"], target, rec.get("content"), rec.get("finish"))
            tr.update(finish=rec["finish"], prompt_tokens=rec["prompt_tokens"], completion_tokens=rec["completion_tokens"], reasoning_tokens=rec["reasoning_tokens"],
                      cost_usd=round(cost, 6), apply_status=ap_res["status"], max_tier=ap_res.get("max_tier"), refusal_reason=ap_res.get("refusal_reason"))
            if turn == 1 and feedback is None:
                tr["content"] = rec.get("content")  # needed later for the plain-apply comparison (H4)
            grade, test_text = None, ""
            if ap_res["status"] == "applied":
                h = sha(ap_res["diff"]); tr["patch_hash"] = h
                with lock:
                    hl = HLOCKS.setdefault((iid, h), threading.Lock())
                with hl:
                    if h in st["memo"]:
                        grade, test_text = st["memo"][h]
                    else:
                        with GRADE_SEM:
                            grade, test_text = DG.grade_one(iid, h, ap_res["diff"])
                        tr["graded_fresh"] = True
                        st["memo"][h] = (grade, test_text)
                tr["grade"] = {k: v for k, v in grade.items() if k not in ("log_text",)}
                if grade.get("resolved") is None:
                    tr["state"] = "grade_error"
                    return tr, None
            tr["state"] = accept_state(ap_res, grade)
            return tr, feedback_for(ap_res, grade or {}, test_text)

        out["models"] = {}

        def run_arm(model, arm):
            trs = []
            if arm == "R":
                for d in range(args.max_turns):
                    tr, _ = attempt(model, 5000 + d, None, d + 1)
                    trs.append(tr)
                    if tr["state"] != "continue":
                        break
            else:
                tr, fb = attempt(model, 5000, None, 1)
                trs.append(tr)
                turn = 1
                while trs[-1]["state"] == "continue" and turn < args.max_turns:
                    turn += 1
                    tr, nfb = attempt(model, 6000 + turn, fb, turn)
                    tr["feedback_out"] = nfb
                    trs.append(tr)
                    fb = nfb
            return trs

        with cf.ThreadPoolExecutor(2 * len(MODELS)) as aex:  # Revision 16: the six (model, arm) chains of one task run concurrently; results are identical to the sequential order
            jobs = {(m, a): aex.submit(run_arm, m, a) for m in MODELS for a in ("R", "F")}
            armres = {k: f.result() for k, f in jobs.items()}
        for model in MODELS:
            res = {}
            for a in ("R", "F"):
                trs = armres[(model, a)]
                last = trs[-1]
                res[a] = dict(attempts=trs, n=len(trs), stop=last["state"], solved=last["state"] == "accepted_resolved", cost_usd=round(sum(x.get("cost_usd", 0) for x in trs), 6))
            out["models"][model.split("/")[-1]] = res
        out["secs"] = round(time.time() - t0, 1)
        with lock:
            open(TRAJ, "a", encoding="utf-8").write(json.dumps(out) + "\n")
        return out
    finally:
        if st["pulled"]:
            DG.cleanup(iid)


todo = [i for i in ids if i not in done]
DG.say(f"{len(pool.keys)} keys; {len(todo)} tasks to run ({len(done)} done); out={OUT}; prompt_hash={prompt_hash()}")
n = 0
with cf.ThreadPoolExecutor(args.workers) as ex:
    futs = {ex.submit(run_task, i): i for i in todo}
    for f in cf.as_completed(futs):
        n += 1
        try:
            r = f.result()
            if r.get("pull_failed"):
                DG.say(f"[{n}/{len(todo)}] {r['iid']} IMAGE PULL FAILED (will be retried on the next run)")
            elif r.get("excluded"):
                DG.say(f"[{n}/{len(todo)}] {r['iid']} EXCLUDED: {r['excluded']}")
            else:
                s = " | ".join(f"{m}: R {v['R']['stop']} n={v['R']['n']}, F {v['F']['stop']} n={v['F']['n']}" for m, v in r["models"].items())
                DG.say(f"[{n}/{len(todo)}] {r['iid']} {s} {r['secs']:.0f}s")
        except Exception as e:
            import traceback
            DG.say(f"[{n}/{len(todo)}] {futs[f]} EXCEPTION {repr(e)[:300]}")
            DG.say(traceback.format_exc()[-800:])
DG.say("all done")
