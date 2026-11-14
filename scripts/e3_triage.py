import json, re, collections
D = json.load(open(r"C:\coding\Argus-pilot50\results\analysis\e3_resolved.json"))
def parse(d):
    hunks = []; cur = None; f = None
    for ln in d.split("\n"):
        if ln.startswith("+++ "): f = ln[4:].lstrip("b/").strip()
        m = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", ln)
        if m:
            cur = dict(file=f, old=int(m.group(1)), n=int(m.group(2) or 1), add=[], rem=[]); hunks.append(cur); continue
        if cur is None: continue
        if ln.startswith("+") and not ln.startswith("+++"): cur["add"].append(ln[1:])
        elif ln.startswith("-") and not ln.startswith("---"): cur["rem"].append(ln[1:])
    return hunks
norm = lambda ls: [re.sub(r"\s+", "", x) for x in ls if x.strip()]
def tri(o):
    c, g = parse(o["diff"]), parse(o["gold"])
    cf, gf = {h["file"] for h in c}, {h["file"] for h in g}
    ca, ga = norm(sum([h["add"] for h in c], [])), norm(sum([h["add"] for h in g], []))
    cr, gr = norm(sum([h["rem"] for h in c], [])), norm(sum([h["rem"] for h in g], []))
    ov = any(not (a["old"]+a["n"] < b["old"] or b["old"]+b["n"] < a["old"]) for a in c for b in g if a["file"]==b["file"])
    return dict(same_file=cf==gf, overlap=ov, same_added=(ca==ga), same_removed=(cr==gr), added_subset=set(ca)<=set(ga) or set(ga)<=set(ca))
for o in D: o["tri"] = tri(o)
json.dump(D, open(r"C:\coding\Argus-pilot50\results\analysis\e3_resolved.json","w"))
def cls(o):
    t=o["tri"]
    if not t["same_file"]: return "diff_file"
    if t["same_added"] and t["same_removed"]: return "identical_edit"
    if t["same_added"]: return "same_added_diff_removed"
    if not t["overlap"]: return "no_overlap_with_gold"
    return "overlaps_gold_but_differs"
for name, sub in (("rescued", [o for o in D if o["rescued"]]), ("not rescued", [o for o in D if not o["rescued"]])):
    print(name, len(sub), dict(collections.Counter(cls(o) for o in sub)))
