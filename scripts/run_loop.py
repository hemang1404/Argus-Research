"""Revision 5: Argus-loop discovery run. One trajectory per task (test-given arm L-B); arm L-A is read off the same trajectory
(the first applied patch), because both arms see identical prompts until the first patch applies.

Ladder (argus/runtime/controller.py): turn 1 gpt-oss-20b medium; turn 2 gpt-oss-20b high; turns 3-4 gpt-oss-120b high. Temperature 1.0,
max_completion_tokens 8000, seed 2000+turn, prompt p1 + whole target file (as in Pilot-100) + one feedback block from turn 2.
Feedback: apply/format failure -> Argus's error message (loop/empty output -> one short sentence, the only added message);
applied patch that fails -> first failing FAIL_TO_PASS test, name + up to 2,000 chars of its failure text, never the test source or the gold patch.
Stop: all FAIL_TO_PASS pass (resolved, or 'stopped_f2p_pass_regressed' if PASS_TO_PASS broke), else after turn 4.
Docker: image pulled once per task, removed after. Resumable (one JSON line per finished task; model calls cached by request hash).

  python -X utf8 scripts/run_loop.py --ids astropy__astropy-12907 --out-dir data/loop_smoke
"""
import argparse, hashlib, json, os, re, sys, threading, time, datetime, concurrent.futures as cf
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
ap = argparse.ArgumentParser()
ap.add_argument("--ids", nargs="*")
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--out-dir", default=os.path.join(ROOT, "data", "loop"))
ap.add_argument("--workers", type=int, default=3)
ap.add_argument("--max-turns", type=int, default=4)
args = ap.parse_args()
OUT = os.path.abspath(args.out_dir)
os.makedirs(OUT, exist_ok=True)

from harness.keypool import KeyPool
from harness.context import fetch_source, build_file_context, ntok
from harness.prompts import SYSTEM, build_messages, prompt_hash, PROMPT_VERSION
from harness.argus_apply import apply_output
import harness.dockergrade as DG  # chdir + stdout redirect happen here; use DG.say for console output

ENV = r"C:\coding\Argus\.env"
TASKS = r"C:\coding\Argus-research-archive\data\swe_bench_verified_tasks.jsonl"
LADDER = [("openai/gpt-oss-20b", "medium"), ("openai/gpt-oss-20b", "high"), ("openai/gpt-oss-120b", "high"), ("openai/gpt-oss-120b", "high")]
TEMP, MAX_OUT, PROMPT_BUDGET, SEED0, EXCERPT = 1.0, 8000, 6000, 2000, 2000
PRICE = {"openai/gpt-oss-20b": (0.075, 0.30), "openai/gpt-oss-120b": (0.15, 0.60)}

man = json.load(open(os.path.join(ROOT, "manifests", "pilot100_manifest.json"), encoding="utf-8"))
meta = {t["instance_id"]: t for t in man["primary"]}
gold_state = {}
for l in open(os.path.join(ROOT, "results", "grading", "state.jsonl"), encoding="utf-8"):
    r = json.loads(l)
    if "gold" in (r.get("labels") or []):
        gold_state[r["iid"]] = r
valid = [t["instance_id"] for t in man["primary"] if gold_state.get(t["instance_id"], {}).get("resolved") is True]
ids = args.ids or valid
if args.limit:
    ids = ids[:args.limit]
full = {}
for l in open(TASKS, encoding="utf-8"):
    d = json.loads(l); full[d["instance_id"]] = d

pool = KeyPool(ENV)
lock = threading.Lock()
CALLS = os.path.join(OUT, "calls.jsonl")
TRAJ = os.path.join(OUT, "trajectories.jsonl")
calls = {}
if os.path.exists(CALLS):
    for l in open(CALLS, encoding="utf-8"):
        r = json.loads(l); calls[r["key"]] = r
done = set()
if os.path.exists(TRAJ):
    for l in open(TRAJ, encoding="utf-8"):
        done.add(json.loads(l)["iid"])


def sha(s):
    return hashlib.sha1(s.encode()).hexdigest()[:10]


def call_model(body):
    key = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:20]
    with lock:
        c = calls.get(key)
    if c and c.get("http") == 200:
        return c
    res = pool.chat(body)
    rec = dict(key=key, http=res["status"], tries=res.get("tries"), latency_s=res.get("latency_s"), model=body["model"], effort=body["reasoning_effort"])
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
    """text of the first failing FAIL_TO_PASS test from the harness test output (heuristic: nearest section header naming the test)."""
    text = re.sub(r"\[[0-9;]*[A-Za-z]|\[[0-9;]*m", "", text)  # strip ANSI colour codes (pytest) before locating sections
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
    # applied: grade tells us what the tests did
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


def known_grade(iid, h):
    for base in (DG.GRADE, DG.OLD_GRADE):
        res, text = DG.read_grade(base, iid, h)
        if res is not None and res.get("resolved") is not None:
            return res, text
    return None, None


def run_task(iid):
    t0 = time.time()
    t = full[iid]; target = meta[iid]["gold_file"]
    src = fetch_source(t["repo"], t["base_commit"], target)
    issue_tokens = ntok(t["problem_statement"][:6000])
    code_budget = max(500, PROMPT_BUDGET - ntok(SYSTEM) - issue_tokens - 250)
    code, spans, info = build_file_context(t, src, code_budget)
    base_msgs = build_messages(t, target, code)
    turns, feedback, pulled, stop = [], None, False, "max_turns"
    try:
        for turn in range(1, args.max_turns + 1):
            model, effort = LADDER[turn - 1]
            msgs = [base_msgs[0], dict(role="user", content=prompt_with_feedback(base_msgs[1]["content"], turn, feedback))]
            body = {"model": model, "messages": msgs, "temperature": TEMP, "max_completion_tokens": MAX_OUT, "reasoning_effort": effort, "seed": SEED0 + turn}
            rec = call_model(body)
            tr = dict(turn=turn, model=model, effort=effort, http=rec["http"], feedback_in=feedback)
            if rec["http"] != 200:
                tr.update(error=rec.get("error"))
                turns.append(tr); stop = "api_error_%s" % rec["http"]; break
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
                    if not pulled:
                        if not DG.pull(iid):
                            tr["grade_error"] = "image pull failed"; turns.append(tr); stop = "image_pull_failed"; break
                        pulled = True
                    grade, test_text = DG.grade_one(iid, h, ap_res["diff"])
                    tr["graded_fresh"] = True
                tr["grade"] = {k: v for k, v in grade.items() if k not in ("log_text",)}
                if grade.get("resolved") is None:
                    turns.append(tr); stop = "grade_error"; break
                if grade["resolved"]:
                    turns.append(tr); stop = "resolved"; break
                if grade.get("applied") and grade.get("f2p_fail") == 0 and grade.get("f2p_pass", 0) > 0:
                    turns.append(tr); stop = "stopped_f2p_pass_regressed"; break
            feedback = feedback_for(ap_res, grade or {}, test_text)
            tr["feedback_out"] = feedback
            turns.append(tr)
    finally:
        if pulled:
            DG.cleanup(iid)
    final = turns[-1] if turns else {}
    out = dict(iid=iid, stop=stop, n_turns=len(turns), resolved=bool((final.get("grade") or {}).get("resolved")), turns=turns,
               total_cost_usd=round(sum(x.get("cost_usd", 0) for x in turns), 6), ctx=info, prompt_hash=prompt_hash(), secs=round(time.time() - t0, 1),
               ts=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"))
    with lock:
        open(TRAJ, "a", encoding="utf-8").write(json.dumps(out) + "\n")
    return out


todo = [i for i in ids if i not in done]
DG.say(f"{len(pool.keys)} keys; {len(todo)} tasks to run ({len(done)} done); out={OUT}; prompt_hash={prompt_hash()}")
n = 0
with cf.ThreadPoolExecutor(args.workers) as ex:
    futs = {ex.submit(run_task, i): i for i in todo}
    for f in cf.as_completed(futs):
        n += 1
        try:
            r = f.result()
            DG.say(f"[{n}/{len(todo)}] {r['iid']} stop={r['stop']} turns={r['n_turns']} resolved={r['resolved']} cost=${r['total_cost_usd']:.4f} {r['secs']:.0f}s")
        except Exception as e:
            import traceback
            DG.say(f"[{n}/{len(todo)}] {futs[f]} EXCEPTION {repr(e)[:300]}")
            DG.say(traceback.format_exc()[-800:])
DG.say("all done")
