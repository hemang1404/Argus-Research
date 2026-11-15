"""Revision 20 (algorithmic tasks, pre-registered in PILOT50_PROTOCOL.md): arms one-shot / R / F / P on HumanEval+ and MBPP+ (EvalPlus), no Docker.
Verifier = the ORIGINAL (base) tests; solved = also passes the EvalPlus extra ("plus") tests, which are never shown to the model.
Attempt 1 is shared by all arms (draw 0). Attempts 2-3: R = fresh re-draw with the original prompt; F = + failing-test text (previous answer hidden);
P = + previous answer (<=3000 chars) and failing-test text. Stop at the first attempt that passes the base tests (accepted_resolved if plus also passes,
accepted_regressed if not). Model code runs in a subprocess with a timeout and a scrubbed environment (no API keys).
The Argus apply layer is not used (whole-function answers, no search/replace edits).
  python -X utf8 scripts/run_algo.py --model openai/gpt-oss-20b --sample 30 --out-dir data/algo_check_20b
"""
import argparse, ast, hashlib, json, os, random, re, subprocess, sys, tempfile, threading, time, concurrent.futures as cf
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
ap = argparse.ArgumentParser()
ap.add_argument("--model", default="openai/gpt-oss-20b")  # or gemma-4-26b-a4b-it (Google endpoint)
ap.add_argument("--sample", type=int, default=0, help="n tasks, half HumanEval+ half MBPP+, fixed seed")
ap.add_argument("--seed", type=int, default=20261115)
ap.add_argument("--ids", nargs="*")
ap.add_argument("--out-dir", required=True)
ap.add_argument("--workers", type=int, default=3)
ap.add_argument("--max-turns", type=int, default=3)
ap.add_argument("--selftest", action="store_true", help="verify the sandbox with gold solutions and a broken solution, no model calls")
args = ap.parse_args()
OUT = os.path.abspath(args.out_dir)
os.makedirs(OUT, exist_ok=True)
ENV = r"C:\coding\Argus\.env"
MODEL = args.model
GEMMA = MODEL.startswith("gemma")
TEMP, MAX_OUT = 1.0, (16000 if GEMMA else 8000)
PRICE = {"openai/gpt-oss-20b": (0.075, 0.30), "openai/gpt-oss-120b": (0.15, 0.60), "gemma-4-26b-a4b-it": (0.0, 0.0)}


def load(p):
    return [json.loads(l) for l in open(os.path.join(ROOT, "data", "algo", p), encoding="utf-8")]


HE = {"humaneval/" + r["task_id"].split("/")[1]: r for r in load("he_plus.jsonl")}
MB = {"mbpp/" + str(r["task_id"]): r for r in load("mbpp_plus.jsonl")}
bp = os.path.join(ROOT, "data", "algo", "he_base.jsonl")
if not os.path.exists(bp):  # original HumanEval tests (verifier source), frozen once
    from datasets import load_dataset
    with open(bp, "w", encoding="utf-8") as o:
        for r in load_dataset("openai/openai_humaneval", split="test"):
            o.write(json.dumps(dict(task_id=r["task_id"], test=r["test"], entry_point=r["entry_point"])) + "\n")
BASE_HE = {"humaneval/" + r["task_id"].split("/")[1]: r for r in load("he_base.jsonl")}
TASKS = {**HE, **MB}
EXCLUDED = set(json.load(open(os.path.join(ROOT, "data", "algo", "excluded.json"), encoding="utf-8")))  # gold solution fails the extra tests (self-test)
for _x in EXCLUDED:
    HE.pop(_x, None); MB.pop(_x, None)
if args.ids:
    ids = args.ids
elif args.sample:
    rnd = random.Random(args.seed)
    ids = sorted(rnd.sample(sorted(HE), args.sample // 2)) + sorted(rnd.sample(sorted(MB), args.sample - args.sample // 2))
else:
    ids = sorted(TASKS)

# ---------------- sandbox
SAFE_ENV = {k: v for k, v in os.environ.items() if k.upper() in ("PATH", "SYSTEMROOT", "TEMP", "TMP", "COMSPEC", "PATHEXT", "WINDIR", "APPDATA", "LOCALAPPDATA", "USERPROFILE", "HOMEDRIVE", "HOMEPATH")}


def run_py(code, timeout):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "t.py")
        open(p, "w", encoding="utf-8").write(code)
        try:
            r = subprocess.run([sys.executable, "-X", "utf8", p], capture_output=True, text=True, timeout=timeout, cwd=d, env=SAFE_ENV,
                               stdin=subprocess.DEVNULL, errors="replace")
            return r.returncode == 0, (r.stdout + r.stderr)[-4000:]
        except subprocess.TimeoutExpired:
            return False, "TimeoutError: the solution did not finish within the time limit (possible infinite loop or too slow)"


def extract_code(text):
    blocks = re.findall(r"```(?:python|py)?[ \t]*\r?\n(.*?)```", text or "", re.DOTALL)
    return blocks[-1] if blocks else None


def syntax_err(code):
    try:
        ast.parse(code)
        return None
    except SyntaxError as e:
        return f"SyntaxError: {e.msg} (line {e.lineno})"


def tests_of(t):
    v = t["test_list"]
    return ast.literal_eval(v) if isinstance(v, str) else v


def imports_of(t):
    v = t.get("test_imports") or "[]"
    return "\n".join(ast.literal_eval(v) if isinstance(v, str) else v)


def build_base(iid, code):
    t = TASKS[iid]
    if iid in HE:
        return t["prompt"] + "\n\n" + code + "\n\n" + BASE_HE[iid]["test"] + f"\n\ncheck({t['entry_point']})\n"
    lines = ["import sys", imports_of(t), code, "_fails = []"]
    for a in tests_of(t):
        lines.append(f"try:\n    exec({a!r})\nexcept BaseException as _e:\n    _fails.append(({a!r}, type(_e).__name__ + ': ' + str(_e)[:200]))")
    lines.append("if _fails:\n    for a, e in _fails[:3]:\n        print('FAILED: ' + a + '  ->  ' + e)\n    sys.exit(1)")
    return "\n".join(lines) + "\n"


def build_plus(iid, code):
    t = TASKS[iid]
    if iid in HE:
        return t["prompt"] + "\n\n" + code + "\n\n" + t["test"] + f"\n\ncheck({t['entry_point']})\n"
    return imports_of(t) + "\n" + code + "\n\n" + t["test"] + "\n"


def verify(iid, code):
    """-> (base_pass, plus_pass or None, feedback_text)"""
    err = syntax_err(code)
    if err:
        return False, None, err
    ok, out = run_py(build_base(iid, code), 20)
    if not ok:
        return False, None, "The solution fails the example tests:\n" + out.strip()[-1800:]
    ok2, _ = run_py(build_plus(iid, code), 60)
    return True, ok2, ""


# ---------------- model calls
lock = threading.Lock()
CALLS = os.path.join(OUT, "calls.jsonl")
TRAJ = os.path.join(OUT, "trajectories.jsonl")
calls = {}
if os.path.exists(CALLS):
    for l in open(CALLS, encoding="utf-8"):
        r = json.loads(l)
        calls[r["key"]] = r
done = {json.loads(l)["iid"] for l in open(TRAJ, encoding="utf-8")} if os.path.exists(TRAJ) else set()
GKEY = None
if GEMMA:
    for l in open(ENV, encoding="utf-8", errors="replace"):  # read once, never printed
        mm = re.match(r"\s*GOOGLE_API_KEY\s*=\s*(.*)", l)
        if mm:
            GKEY = mm.group(1).strip().strip("\"'")
    assert GKEY, "GOOGLE_API_KEY missing"
else:
    from harness.keypool import KeyPool
    pool = KeyPool(ENV)
GAPI = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"


def call_model(body, nonce=""):
    key = hashlib.sha256((json.dumps(body, sort_keys=True) + nonce).encode()).hexdigest()[:20]
    with lock:
        c = calls.get(key)
    if c and c.get("http") == 200:
        return c
    if GEMMA:
        import urllib.request, urllib.error
        rec = None
        for attempt in range(1, 7):
            req = urllib.request.Request(GAPI, data=json.dumps(body).encode(),
                                         headers={"Authorization": "Bearer " + GKEY, "Content-Type": "application/json", "User-Agent": "argus-research-probe/0.1"})
            t0 = time.time()
            try:
                with urllib.request.urlopen(req, timeout=600) as r:
                    d = json.loads(r.read())
                    u = d.get("usage", {})
                    rec = dict(key=key, http=200, tries=attempt, latency_s=round(time.time() - t0, 2), model=MODEL, content=d["choices"][0]["message"].get("content"),
                               finish=d["choices"][0].get("finish_reason"), prompt_tokens=u.get("prompt_tokens"), completion_tokens=u.get("completion_tokens"))
                    break
            except urllib.error.HTTPError as e:
                rec = dict(key=key, http=e.code, tries=attempt, model=MODEL, error=e.read().decode("utf-8", "replace")[:300].replace(GKEY, "<key>"))
                if e.code in (429, 500, 502, 503, 504):
                    time.sleep(min(10 * attempt, 60))
                    continue
                break
            except Exception as e:
                rec = dict(key=key, http=-1, tries=attempt, model=MODEL, error=str(e)[:200].replace(GKEY, "<key>"))
                time.sleep(5 * attempt)
    else:
        res = pool.chat(body)
        rec = dict(key=key, http=res["status"], tries=res.get("tries"), latency_s=res.get("latency_s"), model=MODEL)
        if res["status"] == 200:
            d = res["data"]
            u = d.get("usage", {})
            rec.update(content=d["choices"][0]["message"].get("content"), finish=d["choices"][0].get("finish_reason"), prompt_tokens=u.get("prompt_tokens"),
                       completion_tokens=u.get("completion_tokens"), reasoning_tokens=(u.get("completion_tokens_details") or {}).get("reasoning_tokens"))
        else:
            rec["error"] = str(res.get("error"))[:300]
    with lock:
        calls[key] = rec
        open(CALLS, "a", encoding="utf-8").write(json.dumps(rec) + "\n")
    return rec


SYSTEM = "You are an expert Python programmer. Reply with ONE complete Python code block containing the full solution (the function definition plus any imports it needs). No explanation."


def user_prompt(iid):
    t = TASKS[iid]
    if iid in HE:
        return "Complete the following function.\n\n```python\n" + t["prompt"] + "\n```"
    return t["prompt"].strip() + "\n\nYour code must pass this example test (the function name and signature must match it):\n```python\n" + tests_of(t)[0] + "\n```"


def make_attempt(iid, arm, turn, prev_text, fbk):
    user = user_prompt(iid)
    if turn > 1 and arm == "F":
        user += f"\n\n## Result of the previous attempt\n{fbk}\n\nWrite a corrected, complete solution."
    elif turn > 1 and arm == "P":
        user += (f"\n\n## Previous Attempt (FAILED) (turn {turn - 1} of {args.max_turns})\n```\n{(prev_text or '')[:3000]}\n```\n\n## Result of the previous attempt\n{fbk}\n\n"
                 "Write the complete corrected solution. Include ALL necessary parts (the valid parts of your previous attempt and the corrections).")
    seed = 5000 if turn == 1 else 9000 + turn
    body = {"model": MODEL, "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}], "temperature": TEMP, "max_completion_tokens": MAX_OUT}
    if not GEMMA:
        body.update(reasoning_effort="medium", seed=seed)
    rec = call_model(body, nonce=f"{arm if turn > 1 else 'd0'}-{turn}")
    tr = dict(turn=turn, seed=seed, http=rec["http"])
    if rec["http"] != 200:
        tr.update(state="api_error", error=rec.get("error"), cost_usd=0)
        return tr, None
    cin, cout = PRICE[MODEL]
    tr.update(finish=rec.get("finish"), prompt_tokens=rec.get("prompt_tokens"), completion_tokens=rec.get("completion_tokens"), reasoning_tokens=rec.get("reasoning_tokens"),
              cost_usd=round(((rec.get("prompt_tokens") or 0) * cin + (rec.get("completion_tokens") or 0) * cout) / 1e6, 6))
    code = extract_code(rec.get("content"))
    if code is None:
        fb = ("Your previous answer was cut off before it contained a code block (too much reasoning). Keep reasoning short and answer with the code block directly."
              if rec.get("finish") == "length" else "Formatting error: reply with one complete Python code block.")
        tr.update(state="continue", base_pass=False, plus_pass=None, no_code=True)
        return tr, (rec.get("content") or "", fb)
    base_ok, plus_ok, fb = verify(iid, code)
    tr.update(base_pass=base_ok, plus_pass=plus_ok, answer_chars=len(rec.get("content") or ""))
    tr["state"] = ("accepted_resolved" if plus_ok else "accepted_regressed") if base_ok else "continue"
    return tr, (rec.get("content") or "", fb)


def run_chain(iid, arm, first):
    atts = [first[0]]
    nxt = first[1]
    while atts[-1]["state"] == "continue" and len(atts) < args.max_turns and nxt:
        tr, nxt = make_attempt(iid, arm, len(atts) + 1, nxt[0], nxt[1])
        atts.append(tr)
    return dict(attempts=atts, n=len(atts), stop=atts[-1]["state"], solved=atts[-1]["state"] == "accepted_resolved", cost_usd=round(sum(a.get("cost_usd") or 0 for a in atts), 6))


def run_task(iid):
    t0 = time.time()
    first = make_attempt(iid, "R", 1, None, None)
    row = dict(iid=iid, source="HumanEval+" if iid in HE else "MBPP+", model=MODEL, ts=time.strftime("%Y-%m-%dT%H:%M:%S"))
    row["ONE"] = dict(solved=first[0]["state"] == "accepted_resolved", state=first[0]["state"])
    for arm in ("R", "F", "P"):
        row[arm] = run_chain(iid, arm, first)
    row["secs"] = round(time.time() - t0, 1)
    with lock:
        open(TRAJ, "a", encoding="utf-8").write(json.dumps(row) + "\n")
    print(f"{iid:16s} one-shot {row['ONE']['state']:18s} R {row['R']['stop']}/{row['R']['n']}  F {row['F']['stop']}/{row['F']['n']}  P {row['P']['stop']}/{row['P']['n']}  {row['secs']}s", flush=True)
    return row


if args.selftest:
    bad = ok_n = 0
    for iid in ids:
        t = TASKS[iid]
        gold = (t["prompt"] + t["canonical_solution"] if iid in HE else t["code"])
        gold = gold if iid not in HE else gold  # HE: body only, prompt is prepended by the builder
        b, pl, fb = verify(iid, gold)
        broken = ("def " + (t.get("entry_point") or "f") + "(*a, **k):" + chr(10) + "    return None" + chr(10)) if iid in HE else ("def zzz():" + chr(10) + "    return 1" + chr(10))
        b2, pl2, fb2 = verify(iid, broken)
        ok_n += int(b and pl and not b2)
        if not (b and pl and not b2):
            bad += 1; print("SELFTEST PROBLEM", iid, "gold base/plus", b, pl, "| broken base", b2, "|", (fb or fb2)[:150].replace(chr(10), " "))
    print(f"selftest: {ok_n}/{len(ids)} ok, {bad} problems"); sys.exit(0)

todo = [i for i in ids if i not in done]
print(f"{MODEL}: {len(ids)} tasks, {len(todo)} to run -> {OUT}", flush=True)
with cf.ThreadPoolExecutor(args.workers) as ex:
    for f in cf.as_completed([ex.submit(run_task, i) for i in todo]):
        try:
            f.result()
        except Exception as e:
            print("TASK ERROR", repr(e)[:300], flush=True)
print("all done")
