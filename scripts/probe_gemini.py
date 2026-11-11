"""Exploratory Gemini probe (not pre-registered; screening only). Generation step.

Same prompt as Pilot-100 / Revision 4 (prompt p1, 6,000-token context budget, same target file), one draw per (task, model), through
Google's OpenAI-compatible endpoint. Key is read from C:\\coding\\Argus\\.env (GOOGLE_API_KEY) and never printed or logged.
A hard dollar cap stops the run; usage is recorded raw so cost can be recomputed.

  python -X utf8 scripts/probe_gemini.py --models gemini-2.5-flash-lite --limit 2 --out data/probe_gemini/smoke.jsonl
"""
import argparse, json, os, random, re, sys, threading, time, datetime, urllib.request, urllib.error, concurrent.futures as cf
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from harness.context import fetch_source, build_file_context, ntok
from harness.prompts import SYSTEM, build_messages, prompt_hash, PROMPT_VERSION

ENV = r"C:\coding\Argus\.env"
TASKS = r"C:\coding\Argus-research-archive\data\swe_bench_verified_tasks.jsonl"
API = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
# $/1M tokens (input, output), standard paid tier, pricing page read 2026-11-11 (3.1 and 2.5 Flash-Lite rows from a page summary)
PRICE = {"gemini-2.5-flash-lite": (0.10, 0.40), "gemini-3.1-flash-lite": (0.25, 1.50), "gemini-3.5-flash-lite": (0.30, 2.50),
         "gemini-3.8-flash": (0.75, 3.75)}
PROMPT_BUDGET = 6000
SAMPLE_SEED = 20261112

ap = argparse.ArgumentParser()
ap.add_argument("--models", nargs="+", required=True)
ap.add_argument("--n-tasks", type=int, default=30)
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--effort", default="medium")
ap.add_argument("--temperature", type=float, default=1.0)
ap.add_argument("--max-out", type=int, default=16000)
ap.add_argument("--cap-usd", type=float, default=1.0, help="stop issuing calls once estimated spend (this invocation + file) reaches this")
ap.add_argument("--cap-new-usd", type=float, default=0, help="if set, cap = spend already in the output file + this")
ap.add_argument("--samples", type=int, default=1, help="draws per (task, model); draw k is stored as sample=k")
ap.add_argument("--task-set", choices=["probe", "full"], default="probe", help="probe = 30 sampled tasks; full = the 99 valid tasks plus the replacement astropy__astropy-13579")
ap.add_argument("--workers", type=int, default=4)
ap.add_argument("--out", required=True)
args = ap.parse_args()

key = None
for l in open(ENV, encoding="utf-8", errors="replace"):
    m = re.match(r"\s*GOOGLE_API_KEY\s*=\s*(.*)", l)
    if m:
        key = m.group(1).strip().strip("\"'")
if not key:
    sys.exit("GOOGLE_API_KEY not found in .env")

man = json.load(open(os.path.join(ROOT, "manifests", "pilot100_manifest.json"), encoding="utf-8"))
meta = {t["instance_id"]: t for t in man["primary"] + man["reserve"]}
REPLACEMENT = "astropy__astropy-13579"
gold_ok = set()
for l in open(os.path.join(ROOT, "results", "grading", "state.jsonl"), encoding="utf-8"):
    r = json.loads(l)
    if "gold" in (r.get("labels") or []) and r.get("resolved") is True:
        gold_ok.add(r["iid"])
valid = sorted(t["instance_id"] for t in man["primary"] if t["instance_id"] in gold_ok)
ids = sorted(random.Random(SAMPLE_SEED).sample(valid, args.n_tasks)) if args.task_set == "probe" else sorted(valid + [REPLACEMENT])
os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
json.dump(dict(seed=SAMPLE_SEED, n_valid=len(valid), ids=ids), open(os.path.join(os.path.dirname(os.path.abspath(args.out)), "task_ids.json" if args.task_set == "probe" else "task_ids_full.json"), "w"), indent=1)
if args.limit:
    ids = ids[:args.limit]
full = {}
for l in open(TASKS, encoding="utf-8"):
    d = json.loads(l); full[d["instance_id"]] = d


def cost_of(model, rec):
    pin, pout = PRICE.get(model, (0, 0))
    u = rec.get("usage_raw") or {}
    # Gemini's compat endpoint leaves thought tokens out of completion_tokens (measured 2026-11-11: total - prompt >> completion), but bills them as output
    out = (u["total_tokens"] - u["prompt_tokens"]) if u.get("total_tokens") and u.get("prompt_tokens") else (rec.get("completion_tokens") or 0)
    return ((rec.get("prompt_tokens") or 0) * pin + out * pout) / 1e6


done, spent = set(), 0.0
if os.path.exists(args.out):
    for l in open(args.out, encoding="utf-8"):
        r = json.loads(l)
        spent += cost_of(r["model"].split("/")[-1], r)
        if r.get("http") == 200:
            done.add((r["iid"], r["model"], r.get("sample", 0)))
if args.cap_new_usd:
    args.cap_usd = spent + args.cap_new_usd
lock = threading.Lock()
state = dict(spent=spent, stop=False)


def call(body):
    last = None
    for attempt in range(1, 7):
        req = urllib.request.Request(API, data=json.dumps(body).encode(), headers={
            "Authorization": "Bearer " + key, "Content-Type": "application/json", "User-Agent": "argus-research-probe/0.1"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                return 200, json.loads(r.read()), round(time.time() - t0, 2), attempt
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            last = (e.code, raw[:400].replace(key, "<key>"), round(time.time() - t0, 2), attempt)
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(min(10 * attempt, 60)); continue
            return last
        except Exception as e:
            last = (-1, str(e)[:200], round(time.time() - t0, 2), attempt)
            time.sleep(5 * attempt)
    return last


def job(iid, model, sample):
    with lock:
        if state["stop"]:
            return None
    t = full[iid]
    path = meta[iid]["gold_file"]
    src = fetch_source(t["repo"], t["base_commit"], path)
    code_budget = max(500, PROMPT_BUDGET - ntok(SYSTEM) - ntok(t["problem_statement"][:6000]) - 250)
    code, spans, info = build_file_context(t, src, code_budget)
    messages = build_messages(t, path, code)
    body = {"model": model, "messages": messages, "temperature": args.temperature, "max_completion_tokens": args.max_out,
            "reasoning_effort": args.effort}
    status, data, dt, tries = call(body)
    rec = dict(iid=iid, repo=t["repo"], model="google/" + model, effort=args.effort, regime="file", sample=sample, prompt_version=PROMPT_VERSION,
               prompt_hash=prompt_hash(), ctx=info, target_file=path, ts=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
               http=status, latency_s=dt, tries=tries)
    if status == 200:
        ch = data["choices"][0]; u = data.get("usage", {})
        rec.update(content=ch["message"].get("content"), finish=ch.get("finish_reason"), prompt_tokens=u.get("prompt_tokens"),
                   completion_tokens=u.get("completion_tokens"), reasoning_tokens=(u.get("completion_tokens_details") or {}).get("reasoning_tokens"),
                   usage_raw=u, served_model=data.get("model"))
    else:
        rec["error"] = data
    c = cost_of(model, rec)
    with lock:
        state["spent"] += c
        if state["spent"] >= args.cap_usd:
            state["stop"] = True
        open(args.out, "a", encoding="utf-8").write(json.dumps(rec) + "\n")
    return rec


work = [(i, m, k) for k in range(args.samples) for m in args.models for i in ids if (i, "google/" + m, k) not in done]
print(f"{len(work)} jobs ({len(done)} done); prior spend est ${spent:.4f}; cap ${args.cap_usd}; prompt_hash={prompt_hash()}", flush=True)
t0 = time.time(); n = 0
with cf.ThreadPoolExecutor(args.workers) as ex:
    futs = [ex.submit(job, *w) for w in work]
    for f in cf.as_completed(futs):
        r = f.result(); n += 1
        if r is None:
            continue
        print(f"[{n}/{len(work)} {time.time()-t0:.0f}s ${state['spent']:.3f}] {r['iid']} {r['model'].split('/')[-1]} http={r['http']} "
              f"prompt={r.get('prompt_tokens')} out={r.get('completion_tokens')} reas={r.get('reasoning_tokens')} finish={r.get('finish')} "
              f"lat={r['latency_s']} err={str(r.get('error',''))[:120]}", flush=True)
print(f"done {time.time()-t0:.0f}s; estimated spend ${state['spent']:.4f}; stopped_by_cap={state['stop']}")
