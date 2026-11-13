"""Seal the blind (held-out) task set BEFORE any model is run on it. Writes manifests/blind200_manifest.json (ids, rule, seed, hashes).

Rule: SWE-bench Verified tasks whose gold patch touches exactly one non-test .py file (same eligibility as Pilot-100); exclude every task that
appeared in the Pilot-100 manifest (primary or reserve) or was tried as a replacement; django capped at 65 (uniform without replacement,
python random.Random(seed)); every other untouched eligible task is included. Reserve = the django tasks not drawn, in seeded order.
  python -X utf8 scripts/seal_blind_set.py
"""
import hashlib, json, os, random, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = r"C:\coding\Argus-research-archive\data\swe_bench_verified_tasks.jsonl"
SEED, DJANGO_CAP = 20261113, 65
man = json.load(open(os.path.join(ROOT, "manifests", "pilot100_manifest.json"), encoding="utf-8"))
touched = {t["instance_id"] for t in man["primary"] + man["reserve"]} | {"astropy__astropy-13579", "psf__requests-2317"}


def files(p):
    return re.findall(r"^diff --git a/(\S+) b/", p, re.M)


def is_test(f):
    return bool(re.search(r"(^|/)(tests?|testing)(/|$)|test_|_test\.py|conftest", f))


elig = []
for l in open(SRC, encoding="utf-8"):
    d = json.loads(l)
    fs = [f for f in files(d["gold_patch"]) if not is_test(f)]
    if len(fs) == 1 and fs[0].endswith(".py") and d["instance_id"] not in touched:
        elig.append(d["instance_id"])
elig.sort()
dj = [i for i in elig if i.startswith("django__")]
other = [i for i in elig if not i.startswith("django__")]
rng = random.Random(SEED)
order = dj[:]
rng.shuffle(order)
chosen_dj, reserve = sorted(order[:DJANGO_CAP]), order[DJANGO_CAP:]
ids = sorted(chosen_dj + other)
out = dict(name="blind200", seed=SEED, created=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(timespec="seconds"),
           source_sha256=hashlib.sha256(open(SRC, "rb").read()).hexdigest(), rule=__doc__.split("Rule:")[1].split("python -X")[0].strip(),
           n=len(ids), ids=ids, reserve_in_order=reserve, ids_sha256=hashlib.sha256("\n".join(ids).encode()).hexdigest(),
           note="No model has been run on these tasks at the time of sealing. Tasks whose gold patch does not resolve in the official harness are excluded without replacement.")
json.dump(out, open(os.path.join(ROOT, "manifests", "blind200_manifest.json"), "w", encoding="utf-8"), indent=1)
print(out["n"], "ids; django", len(chosen_dj), "others", len(other), "reserve", len(reserve), "| ids_sha256", out["ids_sha256"])
