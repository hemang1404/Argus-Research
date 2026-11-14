import json, sys, re
D = json.load(open(r"C:\coding\Argus-pilot50\results\analysis\e3_resolved.json"))
sel = [o for o in D if o["rescued"] and not (o["tri"]["same_added"] and o["tri"]["same_removed"])]
seen=set(); uniq=[]
for o in sel:
    k=(o["iid"],o["diff"])
    if k in seen: continue
    seen.add(k); uniq.append(o)
print(len(sel), "non-identical rescued;", len(uniq), "unique")
def chg(d): return "\n".join(l for l in d.split("\n") if (l[:1] in "+-" and not l.startswith(("+++","---"))) or l.startswith("@@"))
a,b=int(sys.argv[1]),int(sys.argv[2])
for n,o in enumerate(uniq[a:b],a):
    print(f"\n##### [{n}] {o['iid']} {o['model']} s{o['sample']} tier{o['max_tier']}\n--- GOLD\n{chg(o['gold'])[:1400]}\n--- CAND\n{chg(o['diff'])[:1400]}")
