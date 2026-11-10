"""Score localizers against the gold file (gold used ONLY here) and write the primary target map."""
import json, os, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
man = json.load(open(os.path.join(ROOT, "manifests", "pilot100_manifest.json"), encoding="utf-8"))
gold = {t["instance_id"]: t["gold_file"] for t in man["primary"]}
repo = {t["instance_id"]: t["repo"] for t in man["primary"]}
cand = {}
for l in open(os.path.join(ROOT, "data", "loc", "candidates.jsonl"), encoding="utf-8"):
    r = json.loads(l); cand[r["iid"]] = r
ok = [i for i in gold if i in cand and "error" not in cand[i]]
print("scored", len(ok), "of", len(gold), "| download errors:", [i for i in gold if i in cand and "error" in cand[i]])


def primary_list(c):
    seen, out = set(), []
    for x in c["LA"] + c["LB"]:
        if x["path"] not in seen:
            seen.add(x["path"]); out.append(x["path"])
    return out


def rec(getter, k):
    return sum(gold[i] in getter(cand[i])[:k] for i in ok)


res = {}
for name, g in (("L-A Argus", lambda c: [x["path"] for x in c["LA"]]), ("L-B BM25", lambda c: [x["path"] for x in c["LB"]]), ("primary (LA, else LB)", primary_list)):
    res[name] = {f"recall@{k}": rec(g, k) for k in (1, 3, 5, 10)}
    res[name]["returned_nothing"] = sum(not g(cand[i]) for i in ok)
for n, v in res.items():
    print(n, v)
tm = {i: primary_list(cand[i])[0] for i in ok if primary_list(cand[i])}
json.dump(tm, open(os.path.join(ROOT, "data", "loc", "target_map.json"), "w"), indent=1)
wrong = sorted(i for i in tm if tm[i] != gold[i])
json.dump(dict(chosen_equals_oracle=sorted(i for i in tm if tm[i] == gold[i]), chosen_wrong=wrong, no_candidate=[i for i in ok if i not in tm], results=res), open(os.path.join(ROOT, "data", "loc", "recall_summary.json"), "w"), indent=1)
print("chosen == oracle:", len(tm) - len(wrong), "| chosen wrong:", len(wrong))
by = collections.defaultdict(lambda: [0, 0])
for i in tm:
    by[repo[i]][1] += 1; by[repo[i]][0] += tm[i] == gold[i]
print({k: f"{a}/{b}" for k, (a, b) in sorted(by.items())})
