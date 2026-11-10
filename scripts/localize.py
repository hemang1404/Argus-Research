"""No-oracle localization (Revision 3). Gold patch is NOT read here; recall is scored in analyze_nooracle.py.
For each task: download the repo tarball at base_commit, build a throwaway git index, run
  L-A  Argus DeterministicLocalizer (as published)   L-B  file-level BM25 over non-test .py files
and write the ranked candidate lists to data/loc/candidates.jsonl. The snapshot is deleted afterwards.
"""
import argparse, io, json, math, os, re, shutil, subprocess, sys, tarfile, time, urllib.request, collections, concurrent.futures as cf
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, r"C:\coding\Argus")
from argus.localization.localizer import DeterministicLocalizer

ap = argparse.ArgumentParser()
ap.add_argument("--out", default=os.path.join(ROOT, "data", "loc", "candidates.jsonl"))
ap.add_argument("--ids", nargs="*")
ap.add_argument("--workers", type=int, default=3)
args = ap.parse_args()
os.makedirs(os.path.dirname(args.out), exist_ok=True)
SNAP = os.path.join(ROOT, "data", "snap")
os.makedirs(SNAP, exist_ok=True)

man = json.load(open(os.path.join(ROOT, "manifests", "pilot100_manifest.json"), encoding="utf-8"))
ids = args.ids or [t["instance_id"] for t in man["primary"]]
tasks = {}
for l in open(r"C:\coding\Argus-research-archive\data\swe_bench_verified_tasks.jsonl", encoding="utf-8"):
    d = json.loads(l)
    tasks[d["instance_id"]] = dict(repo=d["repo"], base_commit=d["base_commit"], problem_statement=d["problem_statement"])  # gold deliberately not kept

done = set()
if os.path.exists(args.out):
    done = {json.loads(l)["iid"] for l in open(args.out, encoding="utf-8")}
lock = __import__("threading").Lock()

TESTY = re.compile(r"(^|/)(tests?|testing|docs?|examples?|benchmarks?|doc|build|dist|tools|scripts?)(/|$)|(^|/)(test_[^/]*|[^/]*_tests?|conftest|setup)\.py$")


def words(s):
    return [w.lower() for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", s)]


def bm25_rank(docs, query, k1=1.5, b=0.75):
    """docs: {path: text}; returns [(path, score)] descending"""
    toks = {p: words(t + " " + p.replace("/", " ").replace("_", " ")) for p, t in docs.items()}
    N = len(toks); avg = sum(len(v) for v in toks.values()) / max(1, N)
    df = collections.Counter()
    for v in toks.values():
        df.update(set(v))
    q = set(words(query))
    out = []
    for p, v in toks.items():
        tf = collections.Counter(v); L = len(v); s = 0.0
        for w in q:
            f = tf.get(w, 0)
            if not f:
                continue
            idf = math.log(1 + (N - df[w] + 0.5) / (df[w] + 0.5))
            s += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * L / avg))
        out.append((p, s))
    out.sort(key=lambda x: -x[1])
    return out


def run(iid):
    try:
        return _run(iid)
    except Exception as e:
        import traceback
        shutil.rmtree(os.path.join(SNAP, iid), ignore_errors=True)
        return dict(iid=iid, error="exception: " + repr(e)[:200])


def _run(iid):
    t = tasks[iid]
    d = os.path.join(SNAP, iid)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    url = f"https://codeload.github.com/{t['repo']}/tar.gz/{t['base_commit']}"
    for attempt in range(4):
        try:
            data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "argus-pilot"}), timeout=180).read()
            break
        except Exception as e:
            err = repr(e)[:100]; time.sleep(5 * (attempt + 1))
    else:
        return dict(iid=iid, error="download failed: " + err)
    with tarfile.open(fileobj=io.BytesIO(data)) as tf:
        members = [m for m in tf.getmembers() if m.isfile() and m.name.count("/") >= 1]
        for m in members:
            rel = m.name.split("/", 1)[1]
            if not rel.endswith((".py", ".pyi", ".cfg", ".toml", ".txt", ".ini", ".rst", ".md")) and "/" in rel and not rel.endswith("py"):
                continue
            dest = os.path.join(d, *rel.split("/"))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with tf.extractfile(m) as src, open(dest, "wb") as out:
                out.write(src.read())
    docs = {}
    for root, _, files in os.walk(d):
        for f in files:
            if f.endswith(".py"):
                rel = os.path.relpath(os.path.join(root, f), d).replace("\\", "/")
                if not TESTY.search(rel):
                    try:
                        docs[rel] = open(os.path.join(root, f), "rb").read().decode("utf-8", "replace")
                    except OSError:
                        pass
    subprocess.run(["git", "init", "-q"], cwd=d, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=d, capture_output=True, timeout=300)
    loc = DeterministicLocalizer(d)
    try:
        la = loc.locate(t["problem_statement"])
    except Exception as e:
        la = []
    seen, la_files = set(), []
    for c in la:
        if c.relative_path not in seen:
            seen.add(c.relative_path); la_files.append(dict(path=c.relative_path, score=c.score, reason=c.reason[:120]))
    lb = [dict(path=p, score=round(s, 3)) for p, s in bm25_rank(docs, t["problem_statement"])[:10]]
    shutil.rmtree(d, ignore_errors=True)
    return dict(iid=iid, n_py_files=len(docs), LA=la_files[:10], LB=lb)


todo = [i for i in ids if i not in done]
print(len(todo), "tasks to localize", flush=True)
with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
    futs = {ex.submit(run, i): i for i in todo}
    for n, fu in enumerate(cf.as_completed(futs), 1):
        r = fu.result()
        with lock:
            open(args.out, "a", encoding="utf-8").write(json.dumps(r) + "\n")
        print(f"[{n}/{len(todo)}] {r['iid']} {'ERR '+r['error'] if 'error' in r else 'LA='+str(len(r['LA']))+' LB top='+r['LB'][0]['path']}", flush=True)
