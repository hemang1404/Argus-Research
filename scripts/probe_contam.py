"""Exploratory contamination screen (signal, not proof). Issue text only, NO code, NO file: ask for the file to edit and a unified diff.
Scores: (a) file-path exact match with the gold patch's file, (b) share of the gold patch's added lines (>= 12 chars, stripped) that appear
among the model's added lines. Compared across the Gemini probe models and gpt-oss-120b (Groq) on the same 30 tasks.
A model that does far better than gpt-oss-120b with no repository access may have seen the fix; the converse is not evidence of a clean model.

  python -X utf8 scripts/probe_contam.py --cap-usd 0.3
"""
import argparse, json, os, re, sys, time, urllib.request, urllib.error, concurrent.futures as cf
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from harness.keypool import KeyPool

ENV = r"C:\coding\Argus\.env"
TASKS = r"C:\coding\Argus-research-archive\data\swe_bench_verified_tasks.jsonl"
API = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
PRICE = {"gemini-2.5-flash-lite": (0.10, 0.40), "gemini-3.1-flash-lite": (0.25, 1.50), "gemini-3.5-flash-lite": (0.30, 2.50)}
GEMINI = list(PRICE)
GROQ = "openai/gpt-oss-120b"
D = os.path.join(ROOT, "data", "probe_gemini")
OUT = os.path.join(D, "contam.jsonl")

ap = argparse.ArgumentParser()
ap.add_argument("--cap-usd", type=float, default=0.3)
ap.add_argument("--models", nargs="*", default=GEMINI)
ap.add_argument("--no-groq", action="store_true")
args = ap.parse_args()

key = None
for l in open(ENV, encoding="utf-8", errors="replace"):
    m = re.match(r"\s*GOOGLE_API_KEY\s*=\s*(.*)", l)
    if m:
        key = m.group(1).strip().strip("\"'")
ids = json.load(open(os.path.join(D, "task_ids.json")))["ids"]
man = json.load(open(os.path.join(ROOT, "manifests", "pilot100_manifest.json"), encoding="utf-8"))
gold_file = {t["instance_id"]: t["gold_file"] for t in man["primary"]}
full = {}
for l in open(TASKS, encoding="utf-8"):
    d = json.loads(l); full[d["instance_id"]] = d

SYS = "You are an expert Python engineer."
USER = ("Repository: {repo}\n\n## Issue\n{issue}\n\nYou cannot see the repository. From your knowledge of this project, answer in two parts.\n"
        "1. On one line starting with `FILE:` give the repo-relative path of the single source file that must be modified.\n"
        "2. Then write the fix as a unified diff for that file.")


def messages(t):
    return [{"role": "system", "content": SYS}, {"role": "user", "content": USER.format(repo=t["repo"], issue=t["problem_statement"][:6000])}]


def gemini_call(model, msgs):
    body = {"model": model, "messages": msgs, "temperature": 1.0, "max_completion_tokens": 6000, "reasoning_effort": "low"}
    for attempt in range(1, 6):
        req = urllib.request.Request(API, data=json.dumps(body).encode(), headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(10 * attempt); continue
            return {"error": e.read().decode("utf-8", "replace")[:300].replace(key, "<key>")}
        except Exception as e:
            time.sleep(5 * attempt)
    return {"error": "exhausted"}


pool = None if args.no_groq else KeyPool(ENV)
done = set()
if os.path.exists(OUT):
    for l in open(OUT, encoding="utf-8"):
        r = json.loads(l)
        if r.get("content") is not None:
            done.add((r["iid"], r["model"]))
spent = 0.0


def job(iid, model):
    global spent
    t = full[iid]
    msgs = messages(t)
    rec = dict(iid=iid, model=model)
    if model.startswith("gemini"):
        if spent >= args.cap_usd:
            return None
        d = gemini_call(model, msgs)
        if "choices" in d:
            u = d.get("usage", {})
            pin, pout = PRICE[model]
            spent += (u.get("prompt_tokens", 0) * pin + (u.get("total_tokens", 0) - u.get("prompt_tokens", 0)) * pout) / 1e6
            rec.update(content=d["choices"][0]["message"].get("content") or "", usage=u)
        else:
            rec.update(content=None, error=d.get("error"))
    else:
        res = pool.chat({"model": model, "messages": msgs, "temperature": 1.0, "max_completion_tokens": 4000, "reasoning_effort": "medium"})
        if res["status"] == 200:
            rec.update(content=res["data"]["choices"][0]["message"].get("content") or "", usage=res["data"].get("usage"))
        else:
            rec.update(content=None, error=str(res.get("error"))[:200])
    open(OUT, "a", encoding="utf-8").write(json.dumps(rec) + "\n")
    return rec


models = list(args.models) + ([] if args.no_groq else [GROQ])
work = [(i, m) for m in models for i in ids if (i, m) not in done]
print(len(work), "jobs", flush=True)
with cf.ThreadPoolExecutor(4) as ex:
    list(ex.map(lambda w: job(*w), work))
print(f"estimated Gemini spend ${spent:.4f}", flush=True)


def added(diff):
    return {x[1:].strip() for x in diff.split("\n") if x.startswith("+") and not x.startswith("+++") and len(x[1:].strip()) >= 12}


def score(rec):
    t = full[rec["iid"]]
    c = rec.get("content") or ""
    m = re.search(r"FILE:\s*`?([^\s`]+)", c)
    path = m.group(1).strip().lstrip("ab/") if m else ""
    path_ok = path.replace("\\", "/").lstrip("/") == gold_file[rec["iid"]] or path == gold_file[rec["iid"]].lstrip("ab/")
    g = added(t["gold_patch"])
    mine = added(c)
    return path_ok, (len(g & mine) / len(g) if g else None)


rows = {}
for l in open(OUT, encoding="utf-8"):
    r = json.loads(l)
    if r.get("content") is None:
        continue
    rows.setdefault(r["model"], {})[r["iid"]] = score(r)
summ = {}
for mdl, d in rows.items():
    n = len(d)
    ov = [v[1] for v in d.values() if v[1] is not None]
    summ[mdl] = dict(n=n, file_exact=sum(v[0] for v in d.values()), file_rate=round(sum(v[0] for v in d.values()) / n, 3),
                     mean_gold_line_overlap=round(sum(ov) / len(ov), 3), tasks_with_overlap_ge_half=sum(1 for x in ov if x >= 0.5))
json.dump(summ, open(os.path.join(D, "contam_summary.json"), "w", encoding="utf-8"), indent=1)
print(json.dumps(summ, indent=1))
