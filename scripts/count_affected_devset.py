"""Count design-set (development set) gpt-oss feedback attempts whose feedback text changes under the corrected ANSI regex. No Docker, no model calls."""
import json, os, re, sys, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import harness.dockergrade as DG
OLD = r"\[[0-9;]*[A-Za-z]|\[[0-9;]*m"
NEW = r"\x1b\[[0-9;]*[A-Za-z]"
EXC = 2000
def excerpt(text, names, rx, limit=EXC):
    text = re.sub(rx, "", text)
    seg = text
    a, b = text.find(">>>>> Start Test Output"), text.find(">>>>> End Test Output")
    if a != -1: seg = text[a:b if b != -1 else len(text)]
    name = names[0] if names else ""
    core = re.split(r"::", name)[-1]
    core = re.sub(r"\[.*\]$", "", core)
    m = re.match(r"\w+", core); core = m.group(0) if m else ""
    out = None
    if core:
        pos = 0
        for ln in seg.split("\n"):
            if re.match(r"^(={5,}|_{5,}|FAIL:|ERROR:)", ln) and core in ln:
                out = seg[pos:pos + limit]; break
            pos += len(ln) + 1
        if out is None:
            i = seg.find(core)
            if i != -1: out = seg[max(0, i - 200):max(0, i - 200) + limit]
    if out is None: out = seg[-limit:]
    return out.strip()
def fb(names, text, rx):
    head = f"The edit was applied but the failing test still fails.\nFirst failing test: {names[0]}" if names else "The edit was applied but the tests still fail."
    return f"{head}\n```\n{excerpt(text, names, rx)}\n```"
def known(iid, h):
    for base in (DG.GRADE, DG.OLD_GRADE):
        res, text = DG.read_grade(base, iid, h)
        if res is not None and res.get("resolved") is not None: return res, text
    return None, None
ARMS = [("F", "loop2", "120B"), ("F", "loop2_20b", "20B"), ("P multi-turn", "loop3", "120B"), ("P multi-turn", "loop3_20b", "20B"),
        ("P single-prompt", "loop4", "120B"), ("P single-prompt", "loop4_20b", "20B")]
out = {}; summary = []
for arm, d, model in ARMS:
    key = "F" if arm == "F" else "P"
    rows = [json.loads(l) for l in open(os.path.join(ROOT, "data", d, "trajectories.jsonl"), encoding="utf-8")]
    n_fb = n_old_match = n_chg = 0; tasks_total = 0; tasks_chg = set(); nograde = 0
    for r in rows:
        atts = r[key]["attempts"]
        if r[key]["n"] > 1: tasks_total += 1
        prev = atts[0] if atts else None
        for a in atts[1:]:
            fin = a.get("feedback_in") or ""
            pg = prev.get("grade") if prev else None
            if fin.startswith(("The edit was applied but the failing test", "The edit was applied but the tests still")) and pg and pg.get("applied") is not False and prev.get("patch_hash"):
                res, text = known(r["iid"], prev["patch_hash"])
                if text is None: nograde += 1
                else:
                    names = pg.get("f2p_failed_names") or []
                    n_fb += 1
                    n_old_match += fb(names, text, OLD) == fin
                    if fb(names, text, NEW) != fin: n_chg += 1; tasks_chg.add(r["iid"])
            prev = a
    summary.append(dict(arm=arm, model=model, dir=d, tasks_with_retry=tasks_total, excerpt_feedbacks=n_fb, old_regex_reproduces_stored=n_old_match, changed_feedbacks=n_chg, tasks_changed=len(tasks_chg), ungraded=nograde))
    out[f"{arm}|{model}"] = sorted(tasks_chg)
for s in summary: print(s)
json.dump(dict(summary=summary, tasks=out), open(os.path.join(ROOT, "results", "analysis", "devset_affected.json"), "w"), indent=1)
