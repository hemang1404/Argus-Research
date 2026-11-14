"""Analysis of the sealed blind test (Revision 13/16): H1-H4 as pre-registered, Gemma 26B exploratory, sensitivity analyses.
  python -X utf8 scripts/analyze_blind.py            (works on partial data; the report must be run on the full set)
All bootstraps: task-clustered, 5,000 resamples, seed 20261113. Nothing here changes any setting of the run.
"""
import json, os, random, re, sys, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from harness.context import fetch_source, CACHE

TASKS = r"C:\coding\Argus-research-archive\data\swe_bench_verified_tasks.jsonl"
full = {}
for l in open(TASKS, encoding="utf-8"):
    d = json.loads(l); full[d["instance_id"]] = d
MAN = json.load(open(os.path.join(ROOT, "manifests", "blind200_manifest.json"), encoding="utf-8"))
SEALED = set(MAN["ids"]) if "ids" in MAN else {t["instance_id"] for t in MAN.get("tasks", [])}
rows = {}
for l in open(os.path.join(ROOT, "data", "blind", "trajectories.jsonl"), encoding="utf-8"):
    r = json.loads(l); rows[r["iid"]] = r  # last record per task wins
gold_bad = sorted(i for i, r in rows.items() if not r["gold"]["resolved"])
IDS = sorted(i for i, r in rows.items() if r["gold"]["resolved"])
M20, M120, MG = "gpt-oss-20b", "gpt-oss-120b", "gemma-4-26b-a4b-it"
print(f"tasks recorded {len(rows)} of {len(SEALED) or 200} sealed; gold control failed (excluded): {len(gold_bad)} {gold_bad}; analysed {len(IDS)}")


def boot(v, B=5000, seed=20261113, cluster=None):
    r = random.Random(seed)
    if cluster is None:
        n = len(v); xs = sorted(sum(v[r.randrange(n)] for _ in range(n)) / n for _ in range(B))
    else:  # cluster = list of group labels aligned with v; resample groups
        g = collections.defaultdict(list)
        for x, c in zip(v, cluster): g[c].append(x)
        keys = list(g); n = len(v); xs = []
        for _ in range(B):
            tot = cnt = 0
            for _k in range(len(keys)):
                k = keys[r.randrange(len(keys))]; tot += sum(g[k]); cnt += len(g[k])
            xs.append(tot / cnt)
        xs.sort()
    return round(100 * xs[int(.025 * B)], 1), round(100 * xs[int(.975 * B)], 1)


def arm(i, m, a):
    return rows[i]["models"].get(m, {}).get(a)


def infra(i, m):
    """tasks with any infrastructure failure for model m (api / grade error / non-200 call)"""
    for a in ("R", "F"):
        x = arm(i, m, a)
        if not x: return True
        for t in x["attempts"]:
            if t.get("state") in ("api_error", "grade_error") or (t.get("http") not in (None, 200)):
                return True
    return False


def solved(i, m, a): x = arm(i, m, a); return bool(x and x["solved"])


def compare(m, label, ids):
    ids = [i for i in ids if arm(i, m, "R") and arm(i, m, "F")]
    if not ids: print(f"  {m} [{label}]: no data"); return None
    R = [float(solved(i, m, "R")) for i in ids]; F = [float(solved(i, m, "F")) for i in ids]
    d = [f - r for f, r in zip(F, R)]; n = len(ids)
    rep = [i.rsplit("-", 1)[0] for i in ids]
    out = dict(n=n, R=round(100 * sum(R) / n, 1), F=round(100 * sum(F) / n, 1), diff=round(100 * sum(d) / n, 1), ci=boot(d), ci_repo=boot(d, cluster=rep),
               F_only=sum(x > 0 for x in d), R_only=sum(x < 0 for x in d))
    print(f"  {m} [{label}] n={n}: R {out['R']}  F {out['F']}  F-R {out['diff']:+.1f}  95% CI {out['ci']}  (repo-clustered {out['ci_repo']})  F-only {out['F_only']} R-only {out['R_only']}")
    return out


print("\n== Solved within 3 attempts (percent of tasks); F-R paired, task-clustered bootstrap")
RES = {}
for m in (M20, M120, MG):
    RES[m] = {}
    for label, ids in (("all analysed (infra failures = unsolved)", IDS), ("excluding tasks with infra failures", [i for i in IDS if not infra(i, m)])):
        RES[m][label] = compare(m, label, ids)

print("\n== H1 (confirmatory): gpt-oss-20b F > R, CI excludes 0 in F's favour")
h1 = RES[M20]["all analysed (infra failures = unsolved)"]
if h1: print("  H1 CONFIRMED" if h1["ci"][0] > 0 else "  H1 NOT confirmed", f"(F-R {h1['diff']:+.1f}, CI {h1['ci']}); design estimate was +8 (CI +2 to +14)")
print("\n== H2: gpt-oss-120b F-R upper 95% bound <= +5")
h2 = RES[M120]["all analysed (infra failures = unsolved)"]
if h2: print("  H2 holds" if h2["ci"][1] <= 5 else "  H2 does not hold", f"(F-R {h2['diff']:+.1f}, CI {h2['ci']})")


def cost_of(attempts, upto):
    return sum((t.get("cost_usd") or 0) for t in attempts[:upto])


def replay_first_n(att, n):
    """first <= n attempts, stop at first accepted state; returns (solved, accepted, used attempts)"""
    for k, t in enumerate(att[:n], 1):
        if t.get("state") in ("accepted_resolved", "accepted_regressed"):
            return t["state"] == "accepted_resolved", True, k
    return False, False, min(n, len(att))


print("\n== H3: cascade (20B arm F <= 2 attempts, then 120B arm R <= 2 attempts) vs 120B arm R <= 3 attempts; spend ratio <= 1.2")
ids3 = [i for i in IDS if arm(i, M20, "F") and arm(i, M120, "R")]
cs, cc, bs, bc = [], 0.0, [], 0.0
for i in ids3:
    f20 = arm(i, M20, "F")["attempts"]; r120 = arm(i, M120, "R")["attempts"]
    s, acc, k = replay_first_n(f20, 2); c = cost_of(f20, k)
    if not acc:
        s2, acc2, k2 = replay_first_n(r120, 2); s = s2; c += cost_of(r120, k2)
    cs.append(float(s)); cc += c
    s3, acc3, k3 = replay_first_n(r120, 3); bs.append(float(s3)); bc += cost_of(r120, k3)
if ids3:
    d = [a - b for a, b in zip(cs, bs)]; n = len(ids3)
    print(f"  n={n}: cascade {100*sum(cs)/n:.1f} at ${cc:.4f}; 120B-R-3 {100*sum(bs)/n:.1f} at ${bc:.4f}; diff {100*sum(d)/n:+.1f} CI {boot(d)}; spend ratio {cc/bc if bc else float('nan'):.2f}")
    print("  H3 supported" if (sum(d) > 0 and boot(d)[0] > 0 and cc <= 1.2 * bc) else "  H3 not supported (needs higher solve count within 1.2x spend, CI > 0)")
    print("  note: attempt-1 cost is taken from the stored attempt records; 20B F attempt 1 is shared with R")

print("\n== H4: apply-layer gain on attempt-1 draws (Argus applied minus plain exact-match applied, percentage points)")
BLOCK = re.compile(r"<{3,}[ \t]*SEARCH[ \t]*\r?\n(.*?)\r?\n={3,}[ \t]*\r?\n(.*?)\r?\n>{3,}[ \t]*REPLACE", re.DOTALL)
HEAD = re.compile(r"^#{0,4}\s*File:\s*`?([^\n`]+?)`?\s*$", re.M)


def plain_applies(i, content):
    """re-implementation of scripts/apply_plain.py rules: header path = target, exact line match, exactly one match, blocks in order"""
    t = full[i]; target = rows[i]["target_file"]
    fetch_source(t["repo"], t["base_commit"], target)
    cp = os.path.join(CACHE, t["repo"].replace("/", "__"), t["base_commit"], *target.split("/"))
    text = open(cp, "rb").read().decode("utf-8", errors="replace").replace("\r\n", "\n")
    lines = text.split("\n")
    heads = [(m.start(), m.group(1).strip()) for m in HEAD.finditer(content or "")]
    blocks = list(BLOCK.finditer(content or ""))
    if not blocks: return False
    for b in blocks:
        path = None
        for pos, p in heads:
            if pos < b.start(): path = p
        np_ = re.sub(r"^(a|b)/", "", (path or "").strip().strip("`'\"").replace("\\", "/"))
        if np_ != target: return False
        part = b.group(1).replace("\r\n", "\n").split("\n")
        hits = [k for k in range(len(lines) - len(part) + 1) if lines[k:k + len(part)] == part]
        if len(hits) != 1: return False
        k = hits[0]; lines = lines[:k] + b.group(2).replace("\r\n", "\n").split("\n") + lines[k + len(part):]
    return True


H4 = {}
for m in (M20, M120, MG):
    ap_n = pl_n = n = 0
    for i in IDS:
        x = arm(i, m, "R")
        if not x or not x["attempts"]: continue
        t = x["attempts"][0]
        if t.get("http") not in (None, 200) or "content" not in t: continue
        n += 1
        ap_n += t.get("apply_status") == "applied"
        try: pl_n += plain_applies(i, t["content"])
        except Exception: pass
    if n:
        H4[m] = dict(n=n, argus=round(100 * ap_n / n, 1), plain=round(100 * pl_n / n, 1), gain=round(100 * (ap_n - pl_n) / n, 1))
        print(f"  {m}: n={n} plain applied {H4[m]['plain']}%  Argus applied {H4[m]['argus']}%  gain {H4[m]['gain']:+.1f} pp")
if M20 in H4 and M120 in H4:
    print("  H4 (applied-edit part):", "holds" if (H4[M20]["gain"] > H4[M120]["gain"] > 0) else "does not hold", "(design: +10.7 vs +5.3). Resolved-task ordering not computed here (exploratory).")

print("\n== Funnel, regressions, cost per arm")
for m in (M20, M120, MG):
    for a in ("R", "F"):
        xs = [arm(i, m, a) for i in IDS if arm(i, m, a)]
        if not xs: continue
        stops = collections.Counter(x["stop"] for x in xs)
        cost = sum(x.get("cost_usd") or 0 for x in xs); ns = sum(x["solved"] for x in xs)
        at1 = sum(1 for x in xs if x["attempts"] and x["attempts"][0].get("state") == "accepted_resolved")
        print(f"  {m:24s} {a}: tasks {len(xs)} solved {ns} (attempt-1 solved {at1}) stops {dict(stops)} cost ${cost:.3f}" + (f" per solve ${cost/ns:.4f}" if ns and cost else ""))

print("\n== Per-repo (django vs others) F-R")
for m in (M20, M120, MG):
    for label, ids in (("django", [i for i in IDS if i.startswith("django")]), ("other repos", [i for i in IDS if not i.startswith("django")])):
        compare(m, label, ids)
json.dump(dict(analysed=len(IDS), gold_failed=gold_bad, results=RES, h4=H4), open(os.path.join(ROOT, "results", "analysis", "blind_report_data.json"), "w"), indent=1, default=str)
print("\nwrote results/analysis/blind_report_data.json")
