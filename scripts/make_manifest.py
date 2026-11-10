"""Draw the Pilot-100 task manifest.  Outcome-independent: uses only task properties.

Eligibility (decided before any model call):
  E1  The gold SOURCE patch touches exactly one file.
  E2  That file is a non-test Python file (Argus's AST gate and single-file scope).
Sampling:
  Proportional allocation by repository (largest remainder) to 100 primary tasks,
  uniform random within each repository with a fixed seed. A reserve list (about 30%
  extra per repo, same procedure) is used only to replace tasks that hit a harness
  defect (class F0), in the pre-registered order.  Replacements are logged.
"""
import json, re, hashlib, random, os, math, collections, datetime
import tiktoken

SRC = r"C:\coding\Argus-research-archive\data\swe_bench_verified_tasks.jsonl"
OUT = r"C:\coding\Argus-pilot50\manifests"
SEED = 20261110
N = 100
enc = tiktoken.get_encoding("o200k_base")  # close to gpt-oss's tokenizer; approximate


def sha(path):
    h = hashlib.sha256()
    h.update(open(path, "rb").read())
    return h.hexdigest()


rows = [json.loads(l) for l in open(SRC, encoding="utf-8")]


def parse_list(v):
    if isinstance(v, list):
        return v
    try:
        return json.loads(v)
    except Exception:
        return []


elig = []
for r in rows:
    gp = r["gold_patch"]
    files = re.findall(r"^diff --git a/(\S+) b/", gp, re.M)
    if len(files) != 1:
        continue
    f = files[0]
    if not f.endswith(".py") or re.search(r"(^|/)(tests?|testing)(/|_)|/test_|_test\.py$|conftest", f):
        continue
    changed = sum(1 for l in gp.split("\n") if (l.startswith("+") or l.startswith("-")) and not l.startswith("+++") and not l.startswith("---"))
    elig.append(dict(
        instance_id=r["instance_id"], repo=r["repo"], base_commit=r["base_commit"], gold_file=f,
        gold_changed_lines=changed, f2p_count=len(parse_list(r["fail_to_pass"])), p2p_count=len(parse_list(r["pass_to_pass"])),
        problem_tokens_approx=len(enc.encode(r["problem_statement"])),
    ))
print("eligible", len(elig), "of", len(rows))

by = collections.defaultdict(list)
for e in elig:
    by[e["repo"]].append(e)
CAPS = {"django/django": 30}  # owner decision 2026-11-10: spread the sample beyond Django
capped = {rp: min(c, len(by[rp])) for rp, c in CAPS.items()}
free = {rp: v for rp, v in by.items() if rp not in capped}
n_free = N - sum(capped.values())
tot = sum(len(v) for v in free.values())
quota = {rp: n_free * len(v) / tot for rp, v in free.items()}
alloc = {rp: int(math.floor(q)) for rp, q in quota.items()}
rem = n_free - sum(alloc.values())
for rp in sorted(quota, key=lambda x: (-(quota[x] - alloc[x]), x))[:rem]:
    alloc[rp] += 1
alloc.update(capped)

rng = random.Random(SEED)
primary, reserve = [], []
for rp in sorted(by):
    pool = sorted(by[rp], key=lambda e: e["instance_id"])
    rng.shuffle(pool)
    k = alloc[rp]
    extra = min(len(pool) - k, math.ceil(0.3 * k))
    primary += pool[:k]
    reserve += pool[k:k + extra]
primary.sort(key=lambda e: e["instance_id"])
print("allocation", dict(sorted(alloc.items())))
print("primary", len(primary), "reserve", len(reserve))
print("problem tokens (approx): median", sorted(e["problem_tokens_approx"] for e in primary)[len(primary) // 2],
      "max", max(e["problem_tokens_approx"] for e in primary))
print("gold changed lines: median", sorted(e["gold_changed_lines"] for e in primary)[len(primary) // 2], "max", max(e["gold_changed_lines"] for e in primary))

manifest = dict(
    name="pilot100", seed=SEED, n_primary=N, created=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    source_file=SRC, source_sha256=sha(SRC),
    eligibility="gold source patch touches exactly one non-test .py file",
    sampling="django capped at 30; remaining 70 slots proportional by repo among other repos (largest remainder), uniform within repo, python random.Random(seed), reserve ~30% per repo for F0 replacements only",
    tokenizer="tiktoken o200k_base (approximation of gpt-oss tokenizer)",
    primary=primary, reserve=reserve,
)
os.makedirs(OUT, exist_ok=True)
p = os.path.join(OUT, "pilot100_manifest.json")
json.dump(manifest, open(p, "w", encoding="utf-8"), indent=1)
open(os.path.join(OUT, "pilot100_manifest.sha256"), "w").write(sha(p) + "  pilot100_manifest.json\n")
print("manifest sha256", sha(p))
