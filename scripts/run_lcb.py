"""Revision 21 (post-cutoff competitive-programming tasks, pre-registered in PILOT50_PROTOCOL.md): arms one-shot / R / F / P on LiveCodeBench code_generation_lite test6
(175 problems dated 2025-01..04, after the training cutoffs of the gpt-oss models), no Docker. Verifier = the PUBLIC (example) tests; solved = also passes the PRIVATE tests, never shown.
Attempt 1 is shared by all arms. Attempts 2-3: R = fresh re-draw; F = + failing-public-test text (previous answer hidden); P = + previous answer (<=3000 chars) + failing-test text.
Model code runs in a subprocess with timeouts and an environment without API keys. Private tests were decoded with a restricted unpickler (only plain strings allowed).
  python -X utf8 scripts/run_lcb.py --model openai/gpt-oss-20b --out-dir data/lcb_20b
"""
import argparse, ast, hashlib, json, math, os, re, subprocess, sys, tempfile, threading, time, concurrent.futures as cf
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
ap = argparse.ArgumentParser()
ap.add_argument("--model", default="openai/gpt-oss-20b")  # or gemma-4-26b-a4b-it (Google endpoint)
ap.add_argument("--ids", nargs="*")
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--out-dir")
ap.add_argument("--workers", type=int, default=3)
ap.add_argument("--max-turns", type=int, default=3)
ap.add_argument("--selftest", action="store_true", help="check the grader with hand-written solutions, no model calls")
args = ap.parse_args()
OUT = os.path.abspath(args.out_dir or os.path.join(ROOT, "data", "lcb_selftest"))
os.makedirs(OUT, exist_ok=True)
ENV = r"C:\coding\Argus\.env"
MODEL = args.model
GEMMA = MODEL.startswith("gemma")
TEMP, MAX_OUT = 1.0, 16000
PRICE = {"openai/gpt-oss-20b": (0.075, 0.30), "openai/gpt-oss-120b": (0.15, 0.60), "gemma-4-26b-a4b-it": (0.0, 0.0)}
TASKS = {}
for l in open(os.path.join(ROOT, "data", "algo", "lcb_v6_decoded.jsonl"), encoding="utf-8"):
    r = json.loads(l)
    TASKS[r["question_id"]] = r
ids = args.ids or sorted(TASKS)
if args.limit:
    ids = ids[:args.limit]

# ---------------- sandbox
SAFE_ENV = {k: v for k, v in os.environ.items() if k.upper() in ("PATH", "SYSTEMROOT", "TEMP", "TMP", "COMSPEC", "PATHEXT", "WINDIR", "APPDATA", "LOCALAPPDATA", "USERPROFILE", "HOMEDRIVE", "HOMEPATH")}
PREAMBLE = ("import sys, math, re, heapq, bisect, itertools, functools, collections, string, random\n"
            "from typing import *\nfrom collections import *\nfrom heapq import *\nfrom bisect import *\nfrom itertools import *\nfrom functools import *\nfrom math import *\n")


def extract_code(text):
    blocks = re.findall(r"```(?:python|py)?[ \t]*\r?\n(.*?)```", text or "", re.DOTALL)
    return blocks[-1] if blocks else None


def syntax_err(code):
    try:
        ast.parse(code)
        return None
    except SyntaxError as e:
        return f"SyntaxError: {e.msg} (line {e.lineno})"


def same(out, exp):
    a = [l.split() for l in out.strip().splitlines()]
    b = [l.split() for l in exp.strip().splitlines()]
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if len(x) != len(y):
            return False
        for u, v in zip(x, y):
            if u != v:
                try:
                    if not math.isclose(float(u), float(v), rel_tol=1e-6, abs_tol=1e-6):
                        return False
                except ValueError:
                    return False
    return True


def run_stdin_tests(code, tests, per_test_timeout):
    """-> (all_pass, feedback_text or '')"""
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "sol.py")
        open(p, "w", encoding="utf-8").write(PREAMBLE + "\n" + code + "\n")
        for t in tests:
            try:
                r = subprocess.run([sys.executable, "-X", "utf8", p], input=t["input"], capture_output=True, text=True, timeout=per_test_timeout, cwd=d, env=SAFE_ENV, errors="replace")
            except subprocess.TimeoutExpired:
                return False, f"Time limit exceeded ({per_test_timeout}s) on this input:\n{t['input'][:600]}"
            if r.returncode != 0:
                return False, f"Runtime error on this input:\n{t['input'][:400]}\n{r.stderr.strip()[-600:]}"
            if not same(r.stdout, t["output"]):
                return False, f"Wrong answer.\nInput:\n{t['input'][:500]}\nExpected output:\n{t['output'][:300]}\nYour output:\n{r.stdout.strip()[:300]}"
    return True, ""


HARNESS = r"""
import json, sys, math
exec(compile(open(sys.argv[1], encoding='utf-8').read(), 'sol', 'exec'))
tests = json.load(open(sys.argv[2], encoding='utf-8'))
fn = sys.argv[3]
def close(a, b):
    if isinstance(a, float) or isinstance(b, float):
        try: return math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-6)
        except Exception: return False
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(close(x, y) for x, y in zip(a, b))
    return a == b
for t in tests:
    args = [json.loads(x) for x in t['input'].split('\n') if x.strip() != '']
    exp = json.loads(t['output'])
    try:
        got = getattr(Solution(), fn)(*args)
    except BaseException as e:
        print('Runtime error on input:\n' + t['input'][:400] + '\n' + type(e).__name__ + ': ' + str(e)[:300]); sys.exit(1)
    if not close(got, exp):
        print('Wrong answer.\nInput:\n' + t['input'][:500] + '\nExpected output:\n' + json.dumps(exp)[:300] + '\nYour output:\n' + json.dumps(got, default=str)[:300]); sys.exit(1)
"""


def run_func_tests(code, tests, fn, timeout):
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, "sol.py"), "w", encoding="utf-8").write(PREAMBLE + "\n" + code + "\n")
        json.dump(tests, open(os.path.join(d, "tests.json"), "w", encoding="utf-8"))
        open(os.path.join(d, "h.py"), "w", encoding="utf-8").write(HARNESS)
        try:
            r = subprocess.run([sys.executable, "-X", "utf8", "h.py", "sol.py", "tests.json", fn], capture_output=True, text=True, timeout=timeout, cwd=d, env=SAFE_ENV, errors="replace")
        except subprocess.TimeoutExpired:
            return False, f"Time limit exceeded ({timeout}s)."
        if r.returncode != 0:
            return False, (r.stdout.strip() + "\n" + r.stderr.strip()[-600:]).strip()
    return True, ""


def run_tests(iid, code, tests, big):
    t = TASKS[iid]
    if t["func_name"]:
        return run_func_tests(code, tests, t["func_name"], 120 if big else 20)
    return run_stdin_tests(code, tests, 10 if big else 8)


def verify(iid, code):
    """-> (base_pass, plus_pass or None, feedback_text)  (base = public tests, plus = private tests)"""
    err = syntax_err(code)
    if err:
        return False, None, err
    t = TASKS[iid]
    ok, fb = run_tests(iid, code, t["public"], False)
    if not ok:
        return False, None, "The solution fails an example test:\n" + fb[-1800:]
    ok2, _ = run_tests(iid, code, t["private"], True)
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
pool = None
if not args.selftest:
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


SYSTEM = "You are an expert competitive programmer. Reply with ONE complete Python 3 code block containing the full solution. No explanation."


def user_prompt(iid):
    t = TASKS[iid]
    q = f"### Question:\n{t['content'].strip()}\n\n"
    if t["func_name"]:
        return q + "You will use the following starter code to write the solution and enclose your code within a single ```python block.\n```python\n" + t["starter_code"] + "\n```"
    return q + "Read the input from stdin, solve the problem and write the answer to stdout (do not just test on the sample inputs). Enclose your code within a single ```python block."


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
    row = dict(iid=iid, source=TASKS[iid]["platform"], difficulty=TASKS[iid]["difficulty"], model=MODEL, ts=time.strftime("%Y-%m-%dT%H:%M:%S"))
    row["ONE"] = dict(solved=first[0]["state"] == "accepted_resolved", state=first[0]["state"])
    for arm in ("R", "F", "P"):
        row[arm] = run_chain(iid, arm, first)
    row["secs"] = round(time.time() - t0, 1)
    with lock:
        open(TRAJ, "a", encoding="utf-8").write(json.dumps(row) + "\n")
    print(f"{iid:14s} {row['difficulty']:6s} one-shot {row['ONE']['state']:18s} R {row['R']['stop']}/{row['R']['n']}  F {row['F']['stop']}/{row['F']['n']}  P {row['P']['stop']}/{row['P']['n']}  {row['secs']}s", flush=True)
    return row


if args.selftest:
    good = "X = int(input())\nprint(sum(i*j for i in range(1,10) for j in range(1,10) if i*j != X))\n"
    for name, code in (("correct", good), ("wrong", "print(0)\n"), ("crash", "raise ValueError('x')\n"), ("slow", "while True: pass\n")):
        b, pl, fb = verify("abc387_b", code)
        print(f"abc387_b {name:8s} public {b} private {pl} | {fb[:110]!r}")
    f = [i for i in ids if TASKS[i]["func_name"]][0]
    print("functional task", f, TASKS[f]["func_name"])
    print("  trivial wrong solution ->", verify(f, "class Solution:\n    def " + TASKS[f]["func_name"] + "(self, *a):\n        return None\n")[2][:150].replace(chr(10), " "))
    sys.exit(0)

todo = [i for i in ids if i not in done]
print(f"{MODEL}: {len(ids)} tasks, {len(todo)} to run -> {OUT}", flush=True)
with cf.ThreadPoolExecutor(args.workers) as ex:
    for f in cf.as_completed([ex.submit(run_task, i) for i in todo]):
        try:
            f.result()
        except Exception as e:
            print("TASK ERROR", repr(e)[:300], flush=True)
print("all done")
