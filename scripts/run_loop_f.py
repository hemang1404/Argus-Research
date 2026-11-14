"""Revision 15 (feedback loop on Gemma 26B and Qwen3.8-27B, design set): arm F (test feedback, previous answer not shown, <= 3 attempts, stop at the first
patch that passes all FAIL_TO_PASS tests) for models whose independent draws already exist.

  * attempt 1 of F = draw 0 of the existing sweep (shared with the re-draw arm R, as in Revisions 7-9); no new call;
  * the re-draw arm R is NOT regenerated: it is replayed offline from the three stored independent draws (draw order 0, 1, 2) and their stored grades;
  * a task whose attempt 1 is accepted for every model and that has no ungraded stored patch needs no Docker run at all; every other task gets ONE image
    pull, in which (a) ungraded stored patches of --also-grade are graded, (b) for each model whose attempt 1 is not accepted, attempt 1 is re-graded once
    (to obtain the failing-test text), and attempts 2 and 3 are generated with the feedback block of Revisions 5/7/9 and graded. All models share the pull.
Helper functions (failure excerpt, feedback text, acceptance rule) are the same as in scripts/run_blind.py.

  python -X utf8 scripts/run_loop_f.py --model gemma26 qwen38 --also-grade qwen38 --workers 2
"""
import argparse, hashlib, json, os, re, sys, threading, time, datetime, urllib.request, urllib.error, concurrent.futures as cf
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
ap = argparse.ArgumentParser()
ap.add_argument("--model", nargs="+", required=True, choices=["gemma26", "qwen38", "gemini31", "gemini35"])
ap.add_argument("--ids", nargs="*")
ap.add_argument("--out-root", help="parent of the loop_f_<model> output dirs (default: data/)")
ap.add_argument("--workers", type=int, default=2)
ap.add_argument("--rep", type=int, default=0, help="Rev 18 replicate number; >0 gives fresh, separately cached draws and its own output dir")
ap.add_argument("--temp", type=float, default=1.0, help="temperature of the new calls (attempts 2 and 3); Rev 18 greedy check uses 0")
ap.add_argument("--arm", choices=["F", "P", "R"], default="F", help="F: previous answer not shown (Rev 15). P (Rev 17): the model's previous answer (<=3000 chars) is shown with the test/apply feedback, as in Argus src/swebench/patch_builder.build_repair_prompt")
ap.add_argument("--specs", nargs="*", help="Rev 18 batch mode: several arm specs ARM:REP:TEMP (e.g. R:1:1 F:1:1 P:1:1 F:0:0 P:0:0) run against ONE image pull per task")
ap.add_argument("--max-turns", type=int, default=3)
ap.add_argument("--cap-usd", type=float, default=6.0, help="stop issuing paid Gemini calls once estimated new spend reaches this")
ap.add_argument("--also-grade", help="group whose stored patches (apply_<group>/ files, prepared by grade_new_runs.py) are graded in the SAME image pulls, e.g. qwen38")
args = ap.parse_args()
SPECS = [tuple(x.split(":")) for x in args.specs] if args.specs else [(args.arm, str(args.rep), str(args.temp))]
SPECS = [(a, int(r), float(t)) for a, r, t in SPECS]
for _a, _r, _t in SPECS:
    assert _a in ("F", "P", "R"), _a
    assert not (_a == "R" and not _r), "arm R needs rep >= 1 (otherwise attempts 2 and 3 would share one cached call)"
CFGS = dict(
    gemma26=dict(api="gemma-4-26b-a4b-it", raw=os.path.join("data", "gemma_sweep", "raw.jsonl"), raw_model="google/gemma-4-26b-a4b-it", backend="google", max_out=16000),
    qwen38=dict(api="qwen/qwen3.8-27b", raw=os.path.join("data", "qwen38", "raw.jsonl"), raw_model="qwen/qwen3.8-27b", backend="groq", max_out=4000),
    gemini31=dict(api="gemini-3.1-flash-lite", raw=os.path.join("data", "gemini_sweep", "raw.jsonl"), raw_model="google/gemini-3.1-flash-lite", backend="google", max_out=16000, price=(0.25, 1.50)),
    gemini35=dict(api="gemini-3.5-flash-lite", raw=os.path.join("data", "gemini_sweep", "raw.jsonl"), raw_model="google/gemini-3.5-flash-lite", backend="google", max_out=16000, price=(0.30, 2.50)))
SPENT = dict(usd=0.0)

from harness.keypool import KeyPool
from harness.context import fetch_source, build_file_context, ntok
from harness.prompts import SYSTEM, build_messages, prompt_hash
from harness.argus_apply import apply_output
import harness.dockergrade as DG  # chdir + stdout redirect happen here; use DG.say for console output

ENV = r"C:\coding\Argus\.env"
TASKS = r"C:\coding\Argus-research-archive\data\swe_bench_verified_tasks.jsonl"
TEMP, PROMPT_BUDGET, EXCERPT = args.temp, 6000, 2000
IDS = args.ids or json.load(open(os.path.join(ROOT, "data", "gemini_sweep", "task_ids_full.json")))["ids"]
man = json.load(open(os.path.join(ROOT, "manifests", "pilot100_manifest.json"), encoding="utf-8"))
meta = {t["instance_id"]: t for t in man["primary"] + man["reserve"]}
full = {}
for l in open(TASKS, encoding="utf-8"):
    d = json.loads(l); full[d["instance_id"]] = d


def load(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")] if os.path.exists(p) else []


def sha(s):
    return hashlib.sha1(s.encode()).hexdigest()[:10]


KNOWN = {}  # same grade sources as scripts/grade_new_runs.py (a patch graded for another model/arm is reused by (task, patch hash))
for f in ("results/grading/state_t1.jsonl", "results/grading/state.jsonl", "results/grading/state_new.jsonl"):
    for r in load(os.path.join(ROOT, f)):
        if r.get("hash") and r.get("resolved") is not None:
            KNOWN[(r["iid"], r["hash"])] = r
for f in ("data/probe_gemini/grading.jsonl", "data/gemini_sweep/grading.jsonl", "data/new_runs_grading.jsonl"):
    for r in load(os.path.join(ROOT, f)):
        if r.get("h") and r.get("resolved") is not None:
            KNOWN[(r["iid"], r["h"])] = r
STATE = os.path.join(ROOT, "data", "new_runs_grading.jsonl")
EXTRA = {}  # iid -> {hash: diff} of patches of --also-grade that still have no grade
if args.also_grade:
    _d = os.path.join(ROOT, "data", args.also_grade, "apply_" + args.also_grade)
    for _arm in ("plain", "argus"):
        for _f in os.listdir(_d):
            if _f.startswith(_arm + "_apply_"):
                for r in load(os.path.join(_d, _f)):
                    if r["status"] == "applied" and (r["iid"], sha(r["diff"])) not in KNOWN:
                        EXTRA.setdefault(r["iid"], {})[sha(r["diff"])] = r["diff"]
    print(f"{sum(len(v) for v in EXTRA.values())} patches of {args.also_grade} over {len(EXTRA)} tasks to grade in the same pulls", flush=True)

key, pool = None, None
if any(CFGS[m]["backend"] == "google" for m in args.model):  # (key is read once; never printed)
    for l in open(ENV, encoding="utf-8", errors="replace"):
        mm = re.match(r"\s*GOOGLE_API_KEY\s*=\s*(.*)", l)
        if mm:
            key = mm.group(1).strip().strip("\"'")
    assert key, "GOOGLE_API_KEY missing"
if any(CFGS[m]["backend"] == "groq" for m in args.model):
    pool = KeyPool(ENV)
lock = threading.Lock()
API = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

M = {}  # per (model, arm, replicate, temperature) state; key "model|arm|rep|temp"
_DRAWS = {}
for m in args.model:
    draws = {}
    for r in load(os.path.join(ROOT, CFGS[m]["raw"])):
        if r["model"] == CFGS[m]["raw_model"] and r.get("http") == 200:
            draws.setdefault(r["iid"], {})[r.get("sample", 0)] = r
    _DRAWS[m] = draws
for _arm, _rep, _temp in SPECS:
    for m in args.model:
        out_dir = os.path.abspath(os.path.join(args.out_root or os.path.join(ROOT, "data"), "loop_" + _arm.lower() + (f"_rep{_rep}" if _rep else "") + (f"_t{_temp:g}" if _temp != 1.0 else "") + "_" + m))
        os.makedirs(out_dir, exist_ok=True)
        paths = {n: os.path.join(out_dir, n + ".jsonl") for n in ("calls", "trajectories", "pull_failures")}
        M[f"{m}|{_arm}|{_rep}|{_temp:g}"] = dict(m=m, arm=_arm, rep=_rep, temp=_temp, cfg=CFGS[m], draws=_DRAWS[m], paths=paths,
                                                calls={r["key"]: r for r in load(paths["calls"])}, done={r["iid"] for r in load(paths["trajectories"])})
KEYS = list(M)


def google_chat(body):
    last = None
    for attempt in range(1, 7):
        req = urllib.request.Request(API, data=json.dumps(body).encode(), headers={"Authorization": "Bearer " + key, "Content-Type": "application/json", "User-Agent": "argus-research-probe/0.1"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                return dict(status=200, data=json.loads(r.read()), latency_s=round(time.time() - t0, 2), tries=attempt)
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            last = dict(status=e.code, error=raw[:300].replace(key, "<key>"), latency_s=round(time.time() - t0, 2), tries=attempt)
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(min(10 * attempt, 60)); continue
            return last
        except Exception as e:
            last = dict(status=-1, error=str(e)[:200], latency_s=round(time.time() - t0, 2), tries=attempt)
            time.sleep(5 * attempt)
    return last


def call_model(m, body, nonce=""):
    st = M[m]
    # nonce (never sent to the API) separates the cache entries of independent unseeded draws, as in run_blind.py
    ck = hashlib.sha256((json.dumps(body, sort_keys=True) + nonce).encode()).hexdigest()[:20]
    with lock:
        c = st["calls"].get(ck)
    if c and c.get("http") == 200:
        return c
    if st["cfg"].get("price") and SPENT["usd"] >= args.cap_usd:
        return dict(key=ck, http=-2, error="spend cap reached (not cached)", model=body["model"])
    res = google_chat(body) if st["cfg"]["backend"] == "google" else pool.chat(body)
    rec = dict(key=ck, http=res["status"], tries=res.get("tries"), latency_s=res.get("latency_s"), model=body["model"])
    if res["status"] == 200:
        d = res["data"]; mm = d["choices"][0]["message"]; u = d.get("usage", {})
        rec.update(content=mm.get("content"), finish=d["choices"][0].get("finish_reason"), prompt_tokens=u.get("prompt_tokens"), completion_tokens=u.get("completion_tokens"),
                   usage_raw=u if st["cfg"]["backend"] == "google" else None, served_model=d.get("model"))
    else:
        rec["error"] = str(res.get("error"))[:300]
    if st["cfg"].get("price") and res["status"] == 200:
        u = rec.get("usage_raw") or {}
        out_t = (u["total_tokens"] - u["prompt_tokens"]) if u.get("total_tokens") and u.get("prompt_tokens") else (rec.get("completion_tokens") or 0)
        rec["cost_usd"] = round(((rec.get("prompt_tokens") or 0) * st["cfg"]["price"][0] + out_t * st["cfg"]["price"][1]) / 1e6, 6)
        with lock:
            SPENT["usd"] += rec["cost_usd"]
    with lock:
        st["calls"][ck] = rec
        open(st["paths"]["calls"], "a", encoding="utf-8").write(json.dumps(rec) + "\n")
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
    mm = re.match(r"\w+", core)
    core = mm.group(0) if mm else ""
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


def prompt_with_feedback(base_user, turn, feedback, prev=None, arm="F"):
    if not feedback or arm == "R":
        return base_user  # arm R (Rev 18): a fresh independent re-draw, no information about the failure
    if arm == "P":
        return (base_user + f"\n\n## Previous Attempt (FAILED) (turn {turn - 1} of {args.max_turns})\n```\n{(prev or '')[:3000]}\n```\n\n"
                f"## Result of the previous attempt\n{feedback}\n\n"
                "The file shown above is the original, unmodified file. Write corrected SEARCH/REPLACE block(s) against it. "
                "Include ALL necessary changes (the valid parts of your previous attempt and the corrections), without breaking existing behaviour.")
    return (base_user + f"\n\n## Result of your previous attempt (turn {turn - 1} of {args.max_turns})\n{feedback}\n\n"
            "The file shown above is the original, unmodified file. Write corrected SEARCH/REPLACE block(s) against it.")


def accept_state(ap_res, grade):
    if ap_res["status"] == "applied" and grade and grade.get("applied") and grade.get("f2p_fail") == 0 and (grade.get("f2p_pass") or 0) > 0:
        return "accepted_resolved" if grade.get("resolved") else "accepted_regressed"
    return "continue"


def write_traj(m, out):
    with lock:
        open(M[m]["paths"]["trajectories"], "a", encoding="utf-8").write(json.dumps(out) + "\n")


def plan_model(m, iid, t, target):
    """attempt 1 of model m = its draw 0 (no call); returns a plan or None when draw 0 or an earlier result exists."""
    st = M[m]
    if iid in st["done"]:
        return None
    d0 = st["draws"].get(iid, {}).get(0)
    if d0 is None:
        return dict(m=m, skipped="draw0_missing")
    out = dict(iid=iid, target_file=target, prompt_hash=prompt_hash(), model=st["m"], spec=m, ts=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"))
    ap1 = apply_output(t["repo"], t["base_commit"], target, d0.get("content"), d0.get("finish"))
    g1, h1 = None, None
    if ap1["status"] == "applied":
        h1 = sha(ap1["diff"]); g1 = KNOWN.get((iid, h1))
    tr1 = dict(turn=1, source="existing_draw_0", apply_status=ap1["status"], max_tier=ap1.get("max_tier"), refusal_reason=ap1.get("refusal_reason"))
    if g1 is not None:
        tr1.update(patch_hash=h1, grade={k: g1.get(k) for k in ("applied", "resolved", "f2p_pass", "f2p_fail", "p2p_fail")})
    unknown = ap1["status"] == "applied" and g1 is None
    tr1["state"] = "unknown" if unknown else accept_state(ap1, g1)
    return dict(m=m, out=out, ap1=ap1, g1=g1, h1=h1, tr1=tr1, prev=d0.get("content"))


def finish_accepted(plan, t0, docker_used):
    out, tr1 = plan["out"], plan["tr1"]
    out["F"] = dict(attempts=[tr1], n=1, stop=tr1["state"], solved=tr1["state"] == "accepted_resolved", docker_used=docker_used)
    out["secs"] = round(time.time() - t0, 1)
    write_traj(plan["m"], out)


def run_loop(plan, iid, t, target, base_msgs, memo, t0):
    m, out, ap1, g1, h1, tr1 = plan["m"], plan["out"], plan["ap1"], plan["g1"], plan["h1"], plan["tr1"]
    cfg = M[m]["cfg"]; arm, rp, temp = M[m]["arm"], M[m]["rep"], M[m]["temp"]
    grade, test_text = None, ""
    if ap1["status"] == "applied":
        if h1 in memo:
            grade, test_text = memo[h1]
        else:
            grade, test_text = DG.grade_one(iid, h1, ap1["diff"]); memo[h1] = (grade, test_text)
        tr1["regrade"] = {k: v for k, v in grade.items() if k != "log_text"}
        if g1 is not None and grade.get("resolved") != g1.get("resolved"):
            tr1["regrade_differs_from_stored"] = True
        tr1["state"] = accept_state(ap1, grade)
    else:
        tr1["state"] = "continue"
    atts = [tr1]
    fb = feedback_for(ap1, grade or {}, test_text)
    turn = 1
    prev = plan["prev"]
    while atts[-1]["state"] == "continue" and turn < args.max_turns:
        turn += 1
        msgs = [base_msgs[0], dict(role="user", content=prompt_with_feedback(base_msgs[1]["content"], turn, fb, prev, arm))]
        body = {"model": cfg["api"], "messages": msgs, "temperature": temp, "max_completion_tokens": cfg["max_out"]}
        if cfg["backend"] == "groq":
            body["reasoning_effort"] = "none"; body["seed"] = 6000 + turn
        rec = call_model(m, body, f"{arm}-rep{rp}-turn{turn}" if rp else "")
        tr = dict(turn=turn, source="new_call", http=rec["http"], feedback_in=fb)
        if rec["http"] != 200:
            tr.update(state="api_error", error=rec.get("error")); atts.append(tr); break
        prev = rec.get("content")
        ap_res = apply_output(t["repo"], t["base_commit"], target, rec.get("content"), rec.get("finish"))
        tr.update(finish=rec["finish"], prompt_tokens=rec["prompt_tokens"], completion_tokens=rec["completion_tokens"], apply_status=ap_res["status"], max_tier=ap_res.get("max_tier"), refusal_reason=ap_res.get("refusal_reason"))
        grade, test_text = None, ""
        if ap_res["status"] == "applied":
            h = sha(ap_res["diff"]); tr["patch_hash"] = h
            if h in memo:
                grade, test_text = memo[h]
            else:
                grade, test_text = DG.grade_one(iid, h, ap_res["diff"]); memo[h] = (grade, test_text); tr["graded_fresh"] = True
            tr["grade"] = {k: v for k, v in grade.items() if k != "log_text"}
            if grade.get("resolved") is None:
                tr["state"] = "grade_error"; atts.append(tr); break
        tr["state"] = accept_state(ap_res, grade)
        atts.append(tr)
        fb = feedback_for(ap_res, grade or {}, test_text)
    last = atts[-1]
    out["F"] = dict(attempts=atts, n=len(atts), stop=last["state"], solved=last["state"] == "accepted_resolved", docker_used=True)
    out["secs"] = round(time.time() - t0, 1)
    write_traj(m, out)


def run_task(iid):
    t0 = time.time()
    t = full[iid]; target = meta[iid]["gold_file"]
    plans = [p for p in (plan_model(m, iid, t, target) for m in KEYS) if p is not None]
    skipped = [p["m"] for p in plans if p.get("skipped")]
    plans = [p for p in plans if not p.get("skipped")]
    pending = [p for p in plans if p["tr1"]["state"] in ("continue", "unknown")]
    extras = EXTRA.get(iid, {})
    if not pending and not extras:
        for p in plans:
            finish_accepted(p, t0, False)
        return dict(iid=iid, summary={p["m"]: (p["tr1"]["state"], 1, False) for p in plans}, skipped=skipped, secs=round(time.time() - t0, 1))
    if not DG.pull(iid):
        for p in pending:
            with lock:
                open(M[p["m"]]["paths"]["pull_failures"], "a", encoding="utf-8").write(json.dumps(dict(iid=iid, ts=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"))) + "\n")
        return dict(iid=iid, pull_failed=True)
    memo = {}
    try:
        src = fetch_source(t["repo"], t["base_commit"], target)
        code_budget = max(500, PROMPT_BUDGET - ntok(SYSTEM) - ntok(t["problem_statement"][:6000]) - 250)
        code, spans, info = build_file_context(t, src, code_budget)
        base_msgs = build_messages(t, target, code)
        for h, diff in sorted(extras.items()):  # stored patches of the other group: same image, no extra pull
            res, text = DG.grade_one(iid, h, diff)
            memo[h] = (res, text)
            rec = dict(iid=iid, h=h, applied=res.get("applied"), resolved=res.get("resolved"), f2p_pass=res.get("f2p_pass"), f2p_fail=res.get("f2p_fail"),
                       p2p_fail=res.get("p2p_fail"), error=res.get("error"), note=res.get("note"))
            with lock:
                open(STATE, "a", encoding="utf-8").write(json.dumps(rec) + "\n")
            DG.say(f"  [{args.also_grade}] {iid} {h} applied={rec['applied']} resolved={rec['resolved']}")
        summary = {}
        for p in plans:
            p["out"]["ctx"] = info
            if p["tr1"]["state"] not in ("continue", "unknown"):
                finish_accepted(p, t0, True)
                summary[p["m"]] = (p["tr1"]["state"], 1, True)
            else:
                run_loop(p, iid, t, target, base_msgs, memo, t0)
                tl = [json.loads(l) for l in open(M[p["m"]]["paths"]["trajectories"], encoding="utf-8")][-1]["F"]
                summary[p["m"]] = (tl["stop"], tl["n"], True)
        return dict(iid=iid, summary=summary, skipped=skipped, secs=round(time.time() - t0, 1))
    finally:
        DG.cleanup(iid)


todo = [i for i in IDS if any(i not in M[m]["done"] for m in KEYS)]
DG.say(f"models {args.model}; specs {SPECS}; {len(todo)} tasks to run; prompt_hash={prompt_hash()}")
n = 0
with cf.ThreadPoolExecutor(args.workers) as ex:
    futs = {ex.submit(run_task, i): i for i in todo}
    for f in cf.as_completed(futs):
        n += 1
        try:
            r = f.result()
            if r.get("pull_failed"):
                DG.say(f"[{n}/{len(todo)}] {r['iid']} IMAGE PULL FAILED (retried on the next run)")
            else:
                DG.say(f"[{n}/{len(todo)}] {r['iid']} " + " ".join(f"{m}:{v[0]}/n={v[1]}" for m, v in r["summary"].items()) + (f" SKIPPED {r['skipped']}" if r["skipped"] else "") + f" {r['secs']:.0f}s")
        except Exception as e:
            import traceback
            DG.say(f"[{n}/{len(todo)}] {futs[f]} EXCEPTION {repr(e)[:300]}")
            DG.say(traceback.format_exc()[-800:])
DG.say("all done")
