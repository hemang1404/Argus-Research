"""Revision 19 (pre-registered, tag pilot100-rev19-prereg): arm P in the DEPLOYED Argus prompt format on gpt-oss-20b / 120b. Same as Revision 8/9 (run_loop3.py) except that
attempts 2-3 are ONE user prompt (original prompt + "Previous Attempt (FAILED)" block, previous answer <= 3000 chars, + result block + "include ALL necessary changes"), not a multi-turn chat;
this is the format of Revision 17 (run_loop_f.py arm P) and of Argus src/swebench/patch_builder.py. Only the PREVIOUS attempt is shown. Attempt 1 = Revision 7 draw 0 (seed 5000, cached);
attempts 2-3 use fresh seeds 9000+turn. Comparators: Revision 7/9 arms R and F (not re-run).
(older text follows)
Revision 8 (pre-registered, tag pilot100-loop3-prereg): repair loop that shows the model its own previous answer.

Same as Revision 7 (gpt-oss-120b, medium, T=1.0, cap 8000, <= 3 attempts, stop at first patch passing all FAIL_TO_PASS, solved iff resolved) except
that attempts 2-3 are a multi-turn chat: original messages, then per earlier attempt an assistant message with its answer (<= 4000 chars) and a user
message with the result block (failing test + <= 2000 chars, or Argus's apply error). Attempt 1 = Revision 7 draw 0 (seed 5000, cached call);
attempts 2-3 use seed 7000+attempt. Comparators are the Revision 7 arms R and F (not re-run). Resumable.

  python -X utf8 scripts/run_loop3.py --ids astropy__astropy-12907 --out-dir data/loop3_smoke
"""
import argparse, hashlib, json, os, re, sys, threading, time, datetime, concurrent.futures as cf
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
ap = argparse.ArgumentParser()
ap.add_argument("--ids", nargs="*")
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--out-dir", default=os.path.join(ROOT, "data", "loop4"))
ap.add_argument("--workers", type=int, default=3)
ap.add_argument("--max-turns", type=int, default=3)
ap.add_argument("--model", default="openai/gpt-oss-120b")
ap.add_argument("--gemma-fill", action="store_true", help="with --gemma: run Gemma on the tasks that were skipped when it was added (frozen in skip_ids.json) instead of the others")
ap.add_argument("--gemma", action="store_true", help="also run Gemma 26B arm P in the same image pull, on tasks not already done for the Groq model")
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
MODEL, EFFORT = args.model, "medium"
TEMP, MAX_OUT, PROMPT_BUDGET, EXCERPT = 1.0, 8000, 6000, 2000
PRICE = {"openai/gpt-oss-20b": (0.075, 0.30), "openai/gpt-oss-120b": (0.15, 0.60)}

man = json.load(open(os.path.join(ROOT, "manifests", "pilot100_manifest.json"), encoding="utf-8"))
meta = {t["instance_id"]: t for t in man["primary"] + man["reserve"]}
ids = args.ids or json.load(open(os.path.join(ROOT, "data", "gemini_sweep", "task_ids_full.json")))["ids"]
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

# --gemma: Gemma 26B arm P in the same pulls, only for tasks NOT already finished by the Groq run when Gemma was added (those are left for later)
GTODO, GDRAWS, GKEY = set(), {}, None
GDIR = os.path.join(ROOT, "data", "loop4_gemma26"); GTRAJ = os.path.join(GDIR, "trajectories.jsonl"); GCALLS = os.path.join(GDIR, "calls.jsonl")
gcalls = {}
if args.gemma:
    os.makedirs(GDIR, exist_ok=True)
    skip_p = os.path.join(GDIR, "skip_ids.json")
    if not os.path.exists(skip_p):  # frozen once: tasks already done for the Groq model at the moment Gemma was added
        json.dump(sorted(done), open(skip_p, "w", encoding="utf-8"))
    skip = set(json.load(open(skip_p, encoding="utf-8")))
    gdone = {json.loads(l)["iid"] for l in open(GTRAJ, encoding="utf-8")} if os.path.exists(GTRAJ) else set()
    GTODO = {i for i in ids if (i in skip if args.gemma_fill else i not in skip) and i not in gdone}  # --gemma-fill: the tasks skipped when Gemma was added
    for r in (json.loads(l) for l in open(os.path.join(ROOT, "data", "gemma_sweep", "raw.jsonl"), encoding="utf-8")):
        if r["model"] == "google/gemma-4-26b-a4b-it" and r.get("http") == 200:
            GDRAWS.setdefault(r["iid"], {})[r.get("sample", 0)] = r
    for l in (open(GCALLS, encoding="utf-8") if os.path.exists(GCALLS) else []):
        r = json.loads(l); gcalls[r["key"]] = r
    for l in open(ENV, encoding="utf-8", errors="replace"):  # key is read once and never printed
        mm = re.match(r"\s*GOOGLE_API_KEY\s*=\s*(.*)", l)
        if mm:
            GKEY = mm.group(1).strip().strip("\"'")
    assert GKEY, "GOOGLE_API_KEY missing"
GAPI = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"


def gcall(body, nonce=""):
    import urllib.request, urllib.error
    ck = hashlib.sha256((json.dumps(body, sort_keys=True) + nonce).encode()).hexdigest()[:20]
    with lock:
        c = gcalls.get(ck)
    if c and c.get("http") == 200:
        return c
    last = None
    for attempt in range(1, 7):
        req = urllib.request.Request(GAPI, data=json.dumps(body).encode(), headers={"Authorization": "Bearer " + GKEY, "Content-Type": "application/json", "User-Agent": "argus-research-probe/0.1"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                d = json.loads(r.read()); mm = d["choices"][0]["message"]; u = d.get("usage", {})
                rec = dict(key=ck, http=200, tries=attempt, latency_s=round(time.time() - t0, 2), model=body["model"], content=mm.get("content"), finish=d["choices"][0].get("finish_reason"),
                           prompt_tokens=u.get("prompt_tokens"), completion_tokens=u.get("completion_tokens"), usage_raw=u)
                break
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            last = dict(key=ck, http=e.code, tries=attempt, latency_s=round(time.time() - t0, 2), model=body["model"], error=raw[:300].replace(GKEY, "<key>"))
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(min(10 * attempt, 60)); continue
            rec = last; break
        except Exception as e:
            last = dict(key=ck, http=-1, tries=attempt, latency_s=round(time.time() - t0, 2), model=body["model"], error=str(e)[:200].replace(GKEY, "<key>"))
            time.sleep(5 * attempt)
    else:
        rec = last
    with lock:
        gcalls[ck] = rec
        open(GCALLS, "a", encoding="utf-8").write(json.dumps(rec) + "\n")
    return rec


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
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)  # strip ANSI colour codes (pytest) before locating sections
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


def accept_state(ap_res, grade):
    """-> 'accepted_resolved' | 'accepted_regressed' | 'continue'"""
    if ap_res["status"] == "applied" and grade and grade.get("applied") and grade.get("f2p_fail") == 0 and (grade.get("f2p_pass") or 0) > 0:
        return "accepted_resolved" if grade.get("resolved") else "accepted_regressed"
    return "continue"


def run_task(iid):
    t0 = time.time()
    t = full[iid]; target = meta[iid]["gold_file"]
    src = fetch_source(t["repo"], t["base_commit"], target)
    issue_tokens = ntok(t["problem_statement"][:6000])
    code_budget = max(500, PROMPT_BUDGET - ntok(SYSTEM) - issue_tokens - 250)
    code, spans, info = build_file_context(t, src, code_budget)
    base_msgs = build_messages(t, target, code)
    st = dict(pulled=False, memo={})

    def attempt(seed, history, turn):
        """history = [(previous answer text, result block), ...]; multi-turn conversation as in a real chat"""
        user = base_msgs[1]["content"]
        if history:
            prev, fbk = history[-1]
            user = (user + f"\n\n## Previous Attempt (FAILED) (turn {turn - 1} of {args.max_turns})\n```\n{(prev or '')[:3000]}\n```\n\n"
                    f"## Result of the previous attempt\n{fbk}\n\n"
                    "The file shown above is the original, unmodified file. Write corrected SEARCH/REPLACE block(s) against it. "
                    "Include ALL necessary changes (the valid parts of your previous attempt and the corrections), without breaking existing behaviour.")
        msgs = [base_msgs[0], dict(base_msgs[1], content=user)]
        feedback = history[-1][1] if history else None
        body = {"model": MODEL, "messages": msgs, "temperature": TEMP, "max_completion_tokens": MAX_OUT, "reasoning_effort": EFFORT, "seed": seed}
        rec = call_model(body)
        tr = dict(turn=turn, seed=seed, http=rec["http"], feedback_in=feedback)
        if rec["http"] != 200:
            tr.update(error=rec.get("error"), state="api_error", cost_usd=0)
            return tr, None
        cost = (rec["prompt_tokens"] * PRICE[MODEL][0] + rec["completion_tokens"] * PRICE[MODEL][1]) / 1e6
        ap_res = apply_output(t["repo"], t["base_commit"], target, rec.get("content"), rec.get("finish"))
        tr.update(finish=rec["finish"], prompt_tokens=rec["prompt_tokens"], completion_tokens=rec["completion_tokens"], reasoning_tokens=rec["reasoning_tokens"],
                  cost_usd=round(cost, 6), apply_status=ap_res["status"], max_tier=ap_res.get("max_tier"), refusal_reason=ap_res.get("refusal_reason"))
        grade, test_text = None, ""
        if ap_res["status"] == "applied":
            h = sha(ap_res["diff"]); tr["patch_hash"] = h
            if h in st["memo"]:
                grade, test_text = st["memo"][h]
            else:
                grade, test_text = known_grade(iid, h)
                if grade is None:
                    if not st["pulled"]:
                        if not DG.pull(iid):
                            tr["state"] = "image_pull_failed"
                            return tr, None
                        st["pulled"] = True
                    grade, test_text = DG.grade_one(iid, h, ap_res["diff"]); tr["graded_fresh"] = True
                st["memo"][h] = (grade, test_text)
            tr["grade"] = {k: v for k, v in grade.items() if k not in ("log_text",)}
            if grade.get("resolved") is None:
                tr["state"] = "grade_error"
                return tr, None
        tr["state"] = accept_state(ap_res, grade)
        tr["answer_chars"] = len(rec.get("content") or "")
        return tr, (rec.get("content") or "", feedback_for(ap_res, grade or {}, test_text))

    def gemma_chain():
        """Gemma 26B arm P in the same image pull: attempt 1 = stored draw 0 (gemma sweep), attempts 2-3 new calls (Google endpoint, T=1.0, 16000 out, no seed)."""
        d0 = GDRAWS.get(iid, {}).get(0)
        if d0 is None:
            return None
        atts, prev, fb = [], None, None
        for turn in range(1, args.max_turns + 1):
            if turn == 1:
                rec = d0; tr = dict(turn=1, source="existing_draw_0")
            else:
                user = base_msgs[1]["content"] + (f"\n\n## Previous Attempt (FAILED) (turn {turn - 1} of {args.max_turns})\n```\n{(prev or '')[:3000]}\n```\n\n"
                                                  f"## Result of the previous attempt\n{fb}\n\n"
                                                  "The file shown above is the original, unmodified file. Write corrected SEARCH/REPLACE block(s) against it. "
                                                  "Include ALL necessary changes (the valid parts of your previous attempt and the corrections), without breaking existing behaviour.")
                body = {"model": "gemma-4-26b-a4b-it", "messages": [base_msgs[0], dict(base_msgs[1], content=user)], "temperature": TEMP, "max_completion_tokens": 16000}
                rec = gcall(body, f"P-turn{turn}")
                tr = dict(turn=turn, source="new_call", http=rec["http"], feedback_in=fb)
                if rec["http"] != 200:
                    tr.update(state="api_error", error=rec.get("error")); atts.append(tr); break
            tr.update(finish=rec.get("finish"), prompt_tokens=rec.get("prompt_tokens"), completion_tokens=rec.get("completion_tokens"))
            ap_res = apply_output(t["repo"], t["base_commit"], target, rec.get("content"), rec.get("finish"))
            tr.update(apply_status=ap_res["status"], max_tier=ap_res.get("max_tier"), refusal_reason=ap_res.get("refusal_reason"))
            grade, test_text = None, ""
            if ap_res["status"] == "applied":
                h = sha(ap_res["diff"]); tr["patch_hash"] = h
                if h in st["memo"]:
                    grade, test_text = st["memo"][h]
                else:
                    grade, test_text = known_grade(iid, h)
                    if grade is None:
                        if not st["pulled"]:
                            if not DG.pull(iid):
                                tr["state"] = "image_pull_failed"; atts.append(tr); break
                            st["pulled"] = True
                        grade, test_text = DG.grade_one(iid, h, ap_res["diff"]); tr["graded_fresh"] = True
                    st["memo"][h] = (grade, test_text)
                tr["grade"] = {k: v for k, v in grade.items() if k not in ("log_text",)}
                if grade.get("resolved") is None:
                    tr["state"] = "grade_error"; atts.append(tr); break
            tr["state"] = accept_state(ap_res, grade)
            atts.append(tr)
            if tr["state"] != "continue":
                break
            prev = rec.get("content") or ""; fb = feedback_for(ap_res, grade or {}, test_text)
        return atts

    arms = {"P": []}
    gem = None
    try:
        history = []
        tr, nxt = attempt(5000, history, 1)  # attempt 1 = Revision 7 draw 0 (cached call)
        arms["P"].append(tr)
        turn = 1
        while arms["P"][-1]["state"] == "continue" and turn < args.max_turns and nxt:
            history.append(nxt)
            turn += 1
            tr, nxt = attempt(9000 + turn, history, turn)
            tr["feedback_out"] = history[-1][1]
            arms["P"].append(tr)
        if args.gemma and iid in GTODO:
            try:
                gem = gemma_chain()
            except Exception as e:  # a Gemma failure must not lose the Groq record; the task stays undone for Gemma and is reported
                import traceback
                DG.say(f"  GEMMA EXCEPTION {iid} {repr(e)[:200]}"); DG.say(traceback.format_exc()[-600:])
    finally:
        if st["pulled"]:
            DG.cleanup(iid)
    if gem:
        last = gem[-1]
        gout = dict(iid=iid, ctx=info, prompt_hash=prompt_hash(), ts=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), model="gemma-4-26b-a4b-it",
                    P=dict(attempts=gem, n=len(gem), stop=last["state"], solved=last["state"] == "accepted_resolved", cost_usd=0.0))
        with lock:
            open(GTRAJ, "a", encoding="utf-8").write(json.dumps(gout) + "\n")
    out = dict(iid=iid, ctx=info, prompt_hash=prompt_hash(), secs=round(time.time() - t0, 1), ts=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"))
    for a, trs in arms.items():
        last = trs[-1]
        out[a] = dict(attempts=trs, n=len(trs), stop=last["state"], solved=last["state"] == "accepted_resolved", cost_usd=round(sum(x.get("cost_usd", 0) for x in trs), 6))
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
            DG.say(f"[{n}/{len(todo)}] {r['iid']} P: {r['P']['stop']} n={r['P']['n']} ${r['P']['cost_usd']:.4f} {r['secs']:.0f}s")
        except Exception as e:
            import traceback
            DG.say(f"[{n}/{len(todo)}] {futs[f]} EXCEPTION {repr(e)[:300]}")
            DG.say(traceback.format_exc()[-800:])
DG.say("all done")
