"""Corrected-harness rerun of the DEVELOPMENT-set feedback arms for gpt-oss-20b and gpt-oss-120b (arm F as in Revision 7, arm P in the single-prompt format of Revision 19).
Only tasks whose feedback text changes under the corrected ANSI regex are rerun (data/dev_fix_ids.json). Per task, ONE image pull is shared by all four chains
(20B F, 20B P, 120B F, 120B P); attempt 1 and every attempt whose prompt is unchanged are cache hits (calls seeded from the original runs), so only attempts that
see changed feedback make new model calls. Same context, prompts, seeds (F 6000+turn, P 9000+turn), apply layer and grading as run_loop2.py / run_loop4.py.
  python -X utf8 scripts/run_dev_fix.py --ids astropy__astropy-12907 --out-dir data/dev_fix_smoke
"""
import argparse, hashlib, json, os, re, sys, threading, time, datetime, concurrent.futures as cf
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
ap = argparse.ArgumentParser()
ap.add_argument("--ids", nargs="*")
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--out-dir", default=os.path.join(ROOT, "data", "dev_fix"))
ap.add_argument("--workers", type=int, default=2)
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
MODELS = ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]
EFFORT, TEMP, MAX_OUT, PROMPT_BUDGET, EXCERPT = "medium", 1.0, 8000, 6000, 2000
PRICE = {"openai/gpt-oss-20b": (0.075, 0.30), "openai/gpt-oss-120b": (0.15, 0.60)}
man = json.load(open(os.path.join(ROOT, "manifests", "pilot100_manifest.json"), encoding="utf-8"))
meta = {t["instance_id"]: t for t in man["primary"] + man["reserve"]}
ids = args.ids or json.load(open(os.path.join(ROOT, "data", "dev_fix_ids.json")))
if args.limit:
    ids = ids[:args.limit]
full = {}
for l in open(TASKS, encoding="utf-8"):
    d = json.loads(l)
    full[d["instance_id"]] = d

pool = KeyPool(ENV)
lock = threading.Lock()
CALLS, TRAJ = os.path.join(OUT, "calls.jsonl"), os.path.join(OUT, "trajectories.jsonl")
calls, KLOCKS, HLOCKS = {}, {}, {}
GRADE_SEM = threading.Semaphore(4)
SEEDED = 0
for srcname in ("loop2", "loop2_20b", "loop4", "loop4_20b"):  # original calls: unchanged prompts are cache hits
    p = os.path.join(ROOT, "data", srcname, "calls.jsonl")
    for l in (open(p, encoding="utf-8") if os.path.exists(p) else []):
        r = json.loads(l)
        if r.get("http") == 200 and r["key"] not in calls:
            calls[r["key"]] = r
            SEEDED += 1
if os.path.exists(CALLS):
    for l in open(CALLS, encoding="utf-8"):
        r = json.loads(l)
        calls[r["key"]] = r
done = set()
if os.path.exists(TRAJ):
    for l in open(TRAJ, encoding="utf-8"):
        done.add(json.loads(l)["iid"])
NEWCALLS = [0]


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
            calls[key] = rec
            NEWCALLS[0] += 1
            open(CALLS, "a", encoding="utf-8").write(json.dumps(rec) + "\n")
        return rec


def failure_excerpt(text, failed_names, limit=EXCERPT):
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)  # corrected pattern
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
        pos = 0
        for ln in seg.split("\n"):
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


def known_grade(iid, h):
    for base in (DG.GRADE, DG.OLD_GRADE):
        res, text = DG.read_grade(base, iid, h)
        if res is not None and res.get("resolved") is not None:
            return res, text
    return None, None


def accept_state(ap_res, grade):
    if ap_res["status"] == "applied" and grade and grade.get("applied") and grade.get("f2p_fail") == 0 and (grade.get("f2p_pass") or 0) > 0:
        return "accepted_resolved" if grade.get("resolved") else "accepted_regressed"
    return "continue"


def run_task(iid):
    t0 = time.time()
    t = full[iid]
    target = meta[iid]["gold_file"]
    src = fetch_source(t["repo"], t["base_commit"], target)
    code_budget = max(500, PROMPT_BUDGET - ntok(SYSTEM) - ntok(t["problem_statement"][:6000]) - 250)
    code, spans, info = build_file_context(t, src, code_budget)
    base_msgs = build_messages(t, target, code)
    st = dict(pulled=False, pull_failed=False, memo={})
    plock = threading.Lock()

    def ensure_pull():
        with plock:
            if not st["pulled"] and not st["pull_failed"]:
                if DG.pull(iid):
                    st["pulled"] = True
                else:
                    st["pull_failed"] = True
            return st["pulled"]

    def attempt(model, arm, seed, turn, feedback, prev):
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
            with lock:
                hl = HLOCKS.setdefault((iid, h), threading.Lock())
            with hl:
                if h in st["memo"]:
                    grade, test_text = st["memo"][h]
                else:
                    grade, test_text = known_grade(iid, h)
                    if grade is None:
                        if not ensure_pull():
                            tr["state"] = "image_pull_failed"
                            return tr, None, None
                        with GRADE_SEM:
                            grade, test_text = DG.grade_one(iid, h, ap_res["diff"])
                        tr["graded_fresh"] = True
                    st["memo"][h] = (grade, test_text)
            tr["grade"] = {k: v for k, v in grade.items() if k not in ("log_text",)}
            if grade.get("resolved") is None:
                tr["state"] = "grade_error"
                return tr, None, None
        tr["state"] = accept_state(ap_res, grade)
        return tr, feedback_for(ap_res, grade or {}, test_text), (rec.get("content") or "")

    def chain(model, arm):
        trs = []
        tr, fb, content = attempt(model, arm, 5000, 1, None, None)
        trs.append(tr)
        turn = 1
        while trs[-1]["state"] == "continue" and turn < args.max_turns and fb is not None:
            turn += 1
            tr, nfb, ncontent = attempt(model, arm, (6000 if arm == "F" else 9000) + turn, turn, fb, content)
            tr["feedback_out"] = nfb
            trs.append(tr)
            fb, content = nfb, ncontent
        return trs

    try:
        with cf.ThreadPoolExecutor(4) as aex:
            jobs = {(m, a): aex.submit(chain, m, a) for m in MODELS for a in ("F", "P")}
            res = {k: f.result() for k, f in jobs.items()}
    finally:
        if st["pulled"]:
            DG.cleanup(iid)
    out = dict(iid=iid, ctx=info, prompt_hash=prompt_hash(), image_pulled=st["pulled"], secs=round(time.time() - t0, 1),
               ts=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), models={})
    for model in MODELS:
        o = {}
        for a in ("F", "P"):
            trs = res[(model, a)]
            last = trs[-1]
            o[a] = dict(attempts=trs, n=len(trs), stop=last["state"], solved=last["state"] == "accepted_resolved", cost_usd=round(sum(x.get("cost_usd", 0) for x in trs), 6))
        out["models"][model.split("/")[-1]] = o
    with lock:
        open(TRAJ, "a", encoding="utf-8").write(json.dumps(out) + "\n")
    return out


todo = [i for i in ids if i not in done]
DG.say(f"{len(pool.keys)} keys; {len(todo)} tasks to run ({len(done)} done); {SEEDED} cached calls seeded; out={OUT}; prompt_hash={prompt_hash()}")
n = 0
with cf.ThreadPoolExecutor(args.workers) as ex:
    futs = {ex.submit(run_task, i): i for i in todo}
    for f in cf.as_completed(futs):
        n += 1
        try:
            r = f.result()
            s = " | ".join(f"{m}: " + " ".join(f"{a} {v[a]['stop']}/n{v[a]['n']}" for a in ("F", "P")) for m, v in r["models"].items())
            DG.say(f"[{n}/{len(todo)}] {r['iid']} {s} pulled={r['image_pulled']} newcalls={NEWCALLS[0]} {r['secs']:.0f}s")
        except Exception as e:
            import traceback
            DG.say(f"[{n}/{len(todo)}] {futs[f]} EXCEPTION {repr(e)[:300]}")
            DG.say(traceback.format_exc()[-800:])
DG.say("all done")
