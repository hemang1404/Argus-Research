"""Phase 1: bare one-shot generation (no Argus step).  Generation only; nothing is applied or graded here.

Example:
  python scripts/generate.py --models openai/gpt-oss-20b --effort medium --limit 3 --out data/smoke/run1.jsonl
"""
import argparse, json, os, sys, time, threading, concurrent.futures as cf, datetime, hashlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from harness.keypool import KeyPool
from harness.context import fetch_source, build_file_context, ntok
from harness.prompts import SYSTEM, build_messages, prompt_hash, PROMPT_VERSION

ENV = r"C:\coding\Argus\.env"
TASKS = r"C:\coding\Argus-research-archive\data\swe_bench_verified_tasks.jsonl"
MANIFEST = os.path.join(ROOT, "manifests", "pilot100_manifest.json")

ap = argparse.ArgumentParser()
ap.add_argument("--models", nargs="+", default=["openai/gpt-oss-20b"])
ap.add_argument("--effort", default="medium")
ap.add_argument("--regime", default="file")
ap.add_argument("--samples", type=int, default=1)
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--ids", nargs="*")
ap.add_argument("--prompt-budget", type=int, default=6000, help="estimated prompt tokens (tiktoken o200k); server limit is ~8000")
ap.add_argument("--max-out", type=int, default=6000)
ap.add_argument("--temperature", type=float, default=0.0)
ap.add_argument("--out", required=True)
ap.add_argument("--target-map", help="JSON {iid: path} overriding the target file (no-oracle run)")
ap.add_argument("--workers", type=int, default=16)
args = ap.parse_args()

manifest = json.load(open(MANIFEST, encoding="utf-8"))
full = {}
for l in open(TASKS, encoding="utf-8"):
    d = json.loads(l)
    full[d["instance_id"]] = d
ids = args.ids or [t["instance_id"] for t in manifest["primary"]]
if args.limit:
    ids = ids[:args.limit]
meta = {t["instance_id"]: t for t in manifest["primary"] + manifest["reserve"]}

TARGETS = json.load(open(args.target_map, encoding="utf-8")) if args.target_map else {}
done = set()
if os.path.exists(args.out):
    for l in open(args.out, encoding="utf-8"):
        r = json.loads(l)
        if r.get("http") != 200:
            continue  # failed records are retried
        done.add((r["iid"], r["model"], r["effort"], r["regime"], r["sample"]))
os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
lock = threading.Lock()
pool = KeyPool(ENV)
print(f"{len(pool.keys)} keys; prompt_hash={prompt_hash()}; manifest={manifest['name']}", flush=True)


def job(iid, model, sample):
    t = full[iid]
    path = TARGETS.get(iid) or meta[iid]["gold_file"]
    src = fetch_source(t["repo"], t["base_commit"], path)
    issue_tokens = ntok(t["problem_statement"][:6000])
    code_budget = max(500, args.prompt_budget - ntok(SYSTEM) - issue_tokens - 250)
    code, spans, info = build_file_context(t, src, code_budget)
    messages = build_messages(t, path, code)
    est_prompt = sum(ntok(m["content"]) for m in messages)
    body = {"model": model, "messages": messages, "temperature": args.temperature, "max_completion_tokens": args.max_out,
            "reasoning_effort": args.effort, "seed": 1000 + sample}
    rec = dict(iid=iid, repo=t["repo"], model=model, effort=args.effort, regime=args.regime, sample=sample,
               prompt_version=PROMPT_VERSION, prompt_hash=prompt_hash(), est_prompt_tokens=est_prompt, ctx=info,
               target_file=path, ts=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"))
    res = pool.chat(body)
    rec.update(http=res["status"], key_id=res.get("key_id"), tries=res.get("tries"), retries=res.get("retries"), latency_s=res.get("latency_s"))
    if res["status"] == 200:
        d = res["data"]
        m = d["choices"][0]["message"]
        u = d.get("usage", {})
        rec.update(content=m.get("content"), reasoning=m.get("reasoning"), finish=d["choices"][0].get("finish_reason"),
                   prompt_tokens=u.get("prompt_tokens"), completion_tokens=u.get("completion_tokens"),
                   reasoning_tokens=(u.get("completion_tokens_details") or {}).get("reasoning_tokens"),
                   served_model=d.get("model"), system_fingerprint=d.get("system_fingerprint"))
    else:
        rec.update(error=res.get("error"))
    with lock:
        with open(args.out, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    return rec


work = [(i, m, s) for i in ids for m in args.models for s in range(args.samples) if (i, m, args.effort, args.regime, s) not in done]
print(f"{len(work)} jobs ({len(done)} already done)", flush=True)
t0 = time.time()
n = 0
with cf.ThreadPoolExecutor(min(args.workers, len(pool.keys))) as ex:
    futs = [ex.submit(job, *w) for w in work]
    for f in cf.as_completed(futs):
        try:
            r = f.result()
            n += 1
            print(f"[{n}/{len(work)} {time.time()-t0:.0f}s] {r['iid']} {r['model'].split('/')[-1]} http={r['http']} "
                  f"prompt={r.get('prompt_tokens')} out={r.get('completion_tokens')} reas={r.get('reasoning_tokens')} "
                  f"finish={r.get('finish')} cov={r['ctx']['coverage']} tries={r['tries']}", flush=True)
        except Exception as e:
            n += 1
            print("job error:", repr(e)[:200], flush=True)
print("done", round(time.time() - t0), "s")
