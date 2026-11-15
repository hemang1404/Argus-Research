"""Why does feedback help (or not)? Three offline checks on stored attempts (Rev 7/9 R,F and Rev 19 P). Nothing re-run."""
import json, os, random, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def load(d): return {r["iid"]: r for r in map(json.loads, open(os.path.join(ROOT, "data", d, "trajectories.jsonl"), encoding="utf-8"))}
def boot(v, B=5000, seed=20261113):
    r = random.Random(seed); n = len(v); xs = sorted(sum(v[r.randrange(n)] for _ in range(n)) / n for _ in range(B))
    return round(100 * xs[int(.025 * B)], 1), round(100 * xs[int(.975 * B)], 1)
SETS = {"120b": ("loop4", "loop2"), "20b": ("loop4_20b", "loop2_20b")}
for m, (pd, fd) in SETS.items():
    P, X = load(pd), load(fd)
    ids = sorted(set(P) & set(X))
    A = {"P": {i: P[i]["P"] for i in ids}, "F": {i: X[i]["F"] for i in ids}, "R": {i: X[i]["R"] for i in ids}}
    print(f"\n######## {m}  n={len(ids)}")
    print("attempt-1 identical across arms (should be shared):", sum(A["P"][i]["attempts"][0].get("patch_hash") == A["F"][i]["attempts"][0].get("patch_hash") == A["R"][i]["attempts"][0].get("patch_hash") for i in ids))
    # ---- check 1: anchoring / repeats
    print("\n-- check 1: does attempt 2 repeat attempt 1? (tasks where attempt 1 failed and attempt 2 exists)")
    for a in "PFR":
        n = same = applied2 = 0
        for i in ids:
            at = A[a][i]["attempts"]
            if len(at) < 2: continue
            n += 1; h1, h2 = at[0].get("patch_hash"), at[1].get("patch_hash")
            if at[1].get("apply_status") == "applied": applied2 += 1
            same += bool(h1 and h1 == h2)
        print(f"   {a}: {n} tasks with attempt 2; identical patch to attempt 1: {same} ({100*same/n:.0f}%); attempt 2 applied: {applied2} ({100*applied2/n:.0f}%)")
    # ---- check 2: recovery by attempt-1 failure type
    print("\n-- check 2: recovery by why attempt 1 failed (share of tasks eventually solved)")
    def ftype(at):
        s = at.get("apply_status")
        if s != "applied": return "not applied (" + str(at.get("finish") or "no content") + ")" if at.get("finish") == "length" else "not applied"
        return "applied, F2P still failing"
    groups = collections.defaultdict(list)
    for i in ids:
        a1 = A["F"][i]["attempts"][0]
        if a1["state"] != "continue": continue
        groups[ftype(a1)].append(i)
    for g, gi in sorted(groups.items(), key=lambda x: -len(x[1])):
        row = "   ".join(f"{a} {sum(A[a][i]['solved'] for i in gi)}/{len(gi)}" for a in "PFR")
        print(f"   attempt 1 = {g:36s} n={len(gi):3d}   {row}")
    # ---- check 3: loops (attempt-1 truncated at the output limit) removed
    print("\n-- check 3: does the feedback gain survive removing degenerate/truncated runs? (any attempt in R or F hit finish=length)")
    def trunc(i): return any(t.get("finish") == "length" for a in "RF" for t in A[a][i]["attempts"])
    for label, keep in (("all tasks", ids), ("no truncated runs", [i for i in ids if not trunc(i)]), ("only truncated-run tasks", [i for i in ids if trunc(i)])):
        if not keep: continue
        row = []
        for x, y in (("F", "R"), ("P", "R"), ("P", "F")):
            d = [float(A[x][i]["solved"]) - float(A[y][i]["solved"]) for i in keep]
            row.append(f"{x}-{y} {100*sum(d)/len(d):+.1f} {boot(d)}")
        print(f"   {label:26s} n={len(keep):3d}  " + "  ".join(row))
    ft = [t for i in ids for t in A["R"][i]["attempts"] if t.get("finish")]
    print("   share of R attempts that hit the output limit:", f"{100*sum(t['finish']=='length' for t in ft)/len(ft):.1f}%", " F:", f"{100*sum(t['finish']=='length' for i in ids for t in A['F'][i]['attempts'] if t.get('finish')=='length')/sum(1 for i in ids for t in A['F'][i]['attempts'] if t.get('finish')):.1f}%")
