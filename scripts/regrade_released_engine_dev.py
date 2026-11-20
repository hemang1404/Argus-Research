"""Re-apply the STORED development-set (design-set) model outputs of gpt-oss-20b / gpt-oss-120b with a chosen Argus patch engine, and (for the released
engine) re-grade the patches that changed. Mirror of scripts/regrade_released_engine.py (sealed set). No model calls.

Stored runs used (100 development tasks, manifests/pilot100_manifest.json):
  set "orig": data/loop2 (120B R, F), data/loop2_20b (20B R, F), data/loop4 (120B P), data/loop4_20b (20B P)  - original runs (feedback bug present)
  set "fix" : data/dev_fix (corrected-harness reruns of F and P for the 32 tasks in data/dev_fix_ids.json, both gpt-oss models)
Arm P is the single-prompt Patch+Feedback format of Revision 19 (run_loop4.py / run_dev_fix.py). The multi-turn format (data/loop3*) and the Gemma, Qwen and
Gemini runs are NOT covered. The request body of every stored attempt is rebuilt exactly as the run scripts built it and its cached reply is looked up by
request hash (union of the calls.jsonl files of the directories above).

Stages (resumable):
  apply   --engine-dir DIR --tag TAG    -> results/analysis/regrade_dev_apply_TAG.jsonl
  grade   --tag TAG                     grade in Docker every patch that differs from a patch with a known grade -> regrade_dev_grades_TAG.jsonl
  summary --tag TAG --control CTRL      -> results/analysis/regrade_dev_summary_TAG.json and regrade_dev_per_task_TAG.csv
Engines: experimental = 0.2.0b1 (commit 467b720), released = 0.2.0b2 (commit 6c7592f).
"""
import argparse, collections, csv, difflib, hashlib, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AN = os.path.join(ROOT, "results", "analysis")
TASKS = r"C:\coding\Argus-research-archive\data\swe_bench_verified_tasks.jsonl"
MODELS = {"gpt-oss-20b": "openai/gpt-oss-20b", "gpt-oss-120b": "openai/gpt-oss-120b"}
EFFORT, TEMP, MAX_OUT, PROMPT_BUDGET, MAX_TURNS = "medium", 1.0, 8000, 6000, 3
# (set, directory, model, arms)
SOURCES = [("orig", "loop2", "gpt-oss-120b", ("R", "F")), ("orig", "loop2_20b", "gpt-oss-20b", ("R", "F")),
           ("orig", "loop4", "gpt-oss-120b", ("P",)), ("orig", "loop4_20b", "gpt-oss-20b", ("P",))]
CALL_DIRS = ["loop2", "loop2_20b", "loop4", "loop4_20b", "dev_fix", "loop3", "loop3_20b"]


def sha1(s):
    return hashlib.sha1(s.encode()).hexdigest()[:10]


def load_jsonl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def stored_chains():
    """-> {(set, iid, model, arm): [attempt dicts]}"""
    out = {}
    for sname, d, model, arms in SOURCES:
        for r in load_jsonl(os.path.join(ROOT, "data", d, "trajectories.jsonl")):
            for a in arms:
                if a in r:
                    out[(sname, r["iid"], model, a)] = r[a]["attempts"]
    for r in load_jsonl(os.path.join(ROOT, "data", "dev_fix", "trajectories.jsonl")):
        for model, arms in r.get("models", {}).items():
            for a, ar in arms.items():
                out[("fix", r["iid"], model, a)] = ar["attempts"]
    return out


def load_calls():
    calls = {}
    for d in CALL_DIRS:
        p = os.path.join(ROOT, "data", d, "calls.jsonl")
        if os.path.exists(p):
            for r in load_jsonl(p):
                if r.get("http") == 200 and r["key"] not in calls:
                    calls[r["key"]] = r
    return calls


def prompt_with_feedback(base_user, turn, feedback):
    if not feedback:
        return base_user
    return (base_user + f"\n\n## Result of your previous attempt (turn {turn - 1} of {MAX_TURNS})\n{feedback}\n\n"
            "The file shown above is the original, unmodified file. Write corrected SEARCH/REPLACE block(s) against it.")


def prompt_p(base_user, turn, prev, fbk):
    return (base_user + f"\n\n## Previous Attempt (FAILED) (turn {turn - 1} of {MAX_TURNS})\n```\n{(prev or '')[:3000]}\n```\n\n"
            f"## Result of the previous attempt\n{fbk}\n\n"
            "The file shown above is the original, unmodified file. Write corrected SEARCH/REPLACE block(s) against it. "
            "Include ALL necessary changes (the valid parts of your previous attempt and the corrections), without breaking existing behaviour.")


# ------------------------------------------------------------------------------------------------ apply stage
def stage_apply(a):
    engine_dir = os.path.abspath(a.engine_dir)
    sys.path.insert(0, ROOT)
    sys.path.insert(0, engine_dir)
    import argus
    assert os.path.dirname(os.path.dirname(os.path.abspath(argus.__file__))).lower() == engine_dir.lower(), argus.__file__
    from argus.config import ArgusConfig
    from argus.patch.parser import PatchParser
    from argus.patch.paths import PatchTargetError, validate_patch_blocks
    from argus.patch.fuzzy_engine import ResilientPatchEngine, RefusalReason
    from harness.context import fetch_source, build_file_context, ntok, CACHE
    from harness.prompts import SYSTEM, build_messages
    cfg = ArgusConfig()
    kw = dict(similarity_threshold=cfg.similarity_threshold, ambiguity_margin=cfg.ambiguity_margin, enforce_ast=True,
              enable_tier4=getattr(cfg, "enable_tier4", False))
    if hasattr(cfg, "enable_tier3"):
        kw["enable_tier3"] = cfg.enable_tier3
    engine = ResilientPatchEngine(**kw)
    print("engine", getattr(argus, "__version__", "?"), engine_dir, kw)
    full = {d["instance_id"]: d for d in load_jsonl(TASKS)}
    man = json.load(open(os.path.join(ROOT, "manifests", "pilot100_manifest.json"), encoding="utf-8"))
    meta = {t["instance_id"]: t for t in man["primary"] + man["reserve"]}
    calls, chains = load_calls(), stored_chains()

    def apply_output(repo, base_commit, target, content, finish):
        content = content or ""
        if finish == "length" and not content.strip():
            return dict(status="truncated_no_output")
        if not content.strip():
            return dict(status="empty_output")
        blocks = PatchParser.parse(content)
        if not blocks:
            return dict(status="no_blocks")
        try:
            validate_patch_blocks(blocks, target)
        except PatchTargetError as e:
            return dict(status="path_refused", details=f"{e.code}: {e.message}")
        fetch_source(repo, base_commit, target)
        cp = os.path.join(CACHE, repo.replace("/", "__"), base_commit, *target.split("/"))
        raw = open(cp, "rb").read().decode("utf-8", errors="replace")
        crlf = "\r\n" in raw and raw.count("\r\n") >= raw.count("\n") * 0.9
        eol = "\r\n" if crlf else "\n"
        code, tiers = raw, []
        for i, b in enumerate(blocks):
            res = engine.apply_patch(code, b, filename=target)
            if not res.success:
                return dict(status="refused", block=i, tiers=tiers,
                            refusal_reason=res.refusal_reason.value if res.refusal_reason != RefusalReason.NONE else "", details=(res.details or "")[:200])
            tiers.append(res.tier_used)
            code = res.patched_code or code
        old, new = raw.replace("\r\n", "\n"), code.replace("\r\n", "\n")
        if new == old:
            return dict(status="no_change", tiers=tiers)
        x = [l + eol for l in old.split("\n")]
        y = [l + eol for l in new.split("\n")]
        diff = f"diff --git a/{target} b/{target}\n" + "".join(difflib.unified_diff(x, y, fromfile="a/" + target, tofile="b/" + target, n=3))
        return dict(status="applied", tiers=tiers, max_tier=max(tiers), diff=diff)

    ctx_cache = {}

    def base_msgs(iid, target):
        if iid not in ctx_cache:
            t = full[iid]
            src = fetch_source(t["repo"], t["base_commit"], target)
            budget = max(500, PROMPT_BUDGET - ntok(SYSTEM) - ntok(t["problem_statement"][:6000]) - 250)
            code, _, _ = build_file_context(t, src, budget)
            ctx_cache[iid] = build_messages(t, target, code)
        return ctx_cache[iid]

    def key_of(body):
        return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:20]

    out_path = os.path.join(AN, f"regrade_dev_apply_{a.tag}.jsonl")
    n = miss = 0
    with open(out_path, "w", encoding="utf-8") as fo:
        for (sname, iid, model, arm), atts in sorted(chains.items()):
            target, t = meta[iid]["gold_file"], full[iid]
            m = base_msgs(iid, target)
            prev_content, chain_broken = None, False
            for tr in atts:
                if tr.get("http") != 200:
                    continue
                turn, seed, fb = tr["turn"], tr["seed"], tr.get("feedback_in")
                if arm == "R" or not fb:
                    user = m[1]["content"]
                elif arm == "F":
                    user = prompt_with_feedback(m[1]["content"], turn, fb)
                else:
                    user = prompt_p(m[1]["content"], turn, prev_content, fb)
                body = {"model": MODELS[model], "messages": [m[0], dict(m[1], content=user)], "temperature": TEMP, "max_completion_tokens": MAX_OUT,
                        "reasoning_effort": EFFORT, "seed": seed}
                rec = None if (arm == "P" and fb and chain_broken) else calls.get(key_of(body))
                row_out = dict(set=sname, iid=iid, model=model, arm=arm, turn=turn, seed=seed,
                               stored_status=tr.get("apply_status"), stored_tier=tr.get("max_tier"), stored_hash=tr.get("patch_hash"),
                               stored_state=tr.get("state"), stored_resolved=bool((tr.get("grade") or {}).get("resolved")))
                if rec is None:
                    miss += 1
                    chain_broken = True
                    row_out.update(new_status="content_missing", content_src=None)
                else:
                    prev_content = rec.get("content")
                    res = apply_output(t["repo"], t["base_commit"], target, rec.get("content"), rec.get("finish"))
                    row_out.update(content_src="calls", new_status=res["status"], new_tier=res.get("max_tier"),
                                   new_hash=sha1(res["diff"]) if res.get("diff") else None, new_diff=res.get("diff"), new_reason=res.get("refusal_reason"))
                fo.write(json.dumps(row_out) + "\n")
                n += 1
    print(f"attempts processed {n}, content missing {miss} -> {out_path}")


# ------------------------------------------------------------------------------------------------ grade stage
def stored_grades():
    g = {}
    for (sname, iid, model, arm), atts in stored_chains().items():
        for tr in atts:
            if tr.get("patch_hash") and tr.get("grade"):
                g[(iid, tr["patch_hash"])] = tr["grade"]
    return g


def cached_grade(DG, iid, h):
    for base in (DG.GRADE, DG.OLD_GRADE):
        res, _ = DG.read_grade(base, iid, h)
        if res is not None and res.get("resolved") is not None:
            return {k: v for k, v in res.items() if k != "log_text"}
    return None


def stage_grade(a):
    rows = load_jsonl(os.path.join(AN, f"regrade_dev_apply_{a.tag}.jsonl"))
    have = stored_grades()
    out_path = os.path.join(AN, f"regrade_dev_grades_{a.tag}.jsonl")
    new = {}
    if os.path.exists(out_path):
        for r in load_jsonl(out_path):
            new[(r["iid"], r["hash"])] = r
    sys.path.insert(0, ROOT)
    import harness.dockergrade as DG  # changes cwd and redirects stdout; use DG.say
    need = collections.defaultdict(dict)
    for r in rows:
        if r["new_status"] != "applied":
            continue
        k = (r["iid"], r["new_hash"])
        if k in have or k in new:
            continue
        cg = cached_grade(DG, *k)
        if cg is not None:  # graded earlier by some run (grade cache), reuse
            new[k] = dict(iid=k[0], hash=k[1], grade=cg, source="cache")
            with open(out_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(new[k]) + "\n")
            continue
        need[r["iid"]][r["new_hash"]] = r["new_diff"]
    DG.say("patches to grade in Docker:", sum(len(v) for v in need.values()), "in", len(need), "tasks")
    for iid, diffs in need.items():
        if not DG.pull(iid):
            DG.say("pull failed", iid)
            continue
        try:
            for h, diff in diffs.items():
                grade, _ = DG.grade_one(iid, h, diff)
                g = {k: v for k, v in grade.items() if k != "log_text"}
                with open(out_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(dict(iid=iid, hash=h, grade=g, source="docker")) + "\n")
                DG.say("graded", iid, h, "resolved=", g.get("resolved"))
        finally:
            DG.cleanup(iid)


# ------------------------------------------------------------------------------------------------ summary stage
def accept_state(status, grade):
    if status == "applied" and grade and grade.get("applied") and grade.get("f2p_fail") == 0 and (grade.get("f2p_pass") or 0) > 0:
        return "accepted_resolved" if grade.get("resolved") else "accepted_regressed"
    return "continue"


def stage_summary(a):
    new = load_jsonl(os.path.join(AN, f"regrade_dev_apply_{a.tag}.jsonl"))
    ctrl = load_jsonl(os.path.join(AN, f"regrade_dev_apply_{a.control}.jsonl"))
    grades = dict(stored_grades())
    gp = os.path.join(AN, f"regrade_dev_grades_{a.tag}.jsonl")
    if os.path.exists(gp):
        for r in load_jsonl(gp):
            grades[(r["iid"], r["hash"])] = r["grade"]
    summ = {"engine_tag": a.tag, "control_tag": a.control}

    def same_as_stored(r):
        return r["new_status"] == (r["stored_status"] or r["new_status"]) and (r["new_hash"] == r["stored_hash"] if r["stored_status"] == "applied" else True)

    # 1. control: does the experimental engine reproduce what was stored?
    c = collections.defaultdict(collections.Counter)
    for r in ctrl:
        key = r["set"]
        if r["new_status"] == "content_missing":
            c[key]["content_missing"] += 1
            continue
        c[key]["n"] += 1
        c[key]["reproduced" if same_as_stored(r) else "not_reproduced"] += 1
    summ["control"] = {k: dict(v) for k, v in c.items()}

    # 2. apply outcome changes (released engine against stored outcome)
    ch = collections.defaultdict(collections.Counter)
    changed_rows = []
    for r in new:
        if r["new_status"] == "content_missing":
            continue
        key = f"{r['set']}|{r['model']}|{r['arm']}"
        ch[key]["attempts"] += 1
        old_ap, new_ap = r["stored_status"] == "applied", r["new_status"] == "applied"
        if old_ap and not new_ap:
            kind = "applied_to_refused"
        elif new_ap and not old_ap:
            kind = "refused_to_applied"
        elif old_ap and new_ap and r["new_hash"] != r["stored_hash"]:
            kind = "applied_different_patch"
        else:
            kind = "same"
        ch[key][kind] += 1
        if kind != "same":
            if r["stored_resolved"] and old_ap:
                ch[key][kind + "_old_resolved"] += 1
            changed_rows.append(dict(set=r["set"], iid=r["iid"], model=r["model"], arm=r["arm"], turn=r["turn"], kind=kind, stored_status=r["stored_status"],
                                     stored_tier=r["stored_tier"], new_status=r["new_status"], new_tier=r["new_tier"], stored_resolved=r["stored_resolved"],
                                     new_reason=r.get("new_reason")))
    summ["apply_changes"] = {k: dict(v) for k, v in sorted(ch.items())}

    # 3. replay of the stop rule on stored replies
    by = collections.defaultdict(list)
    for r in new:
        by[(r["set"], r["iid"], r["model"], r["arm"])].append(r)
    for v in by.values():
        v.sort(key=lambda x: x["turn"])
    fixed_ids = set(json.load(open(os.path.join(ROOT, "data", "dev_fix_ids.json"))))

    def replay(seq):
        path_changed = False
        for r in seq:
            st, h = r["new_status"], r["new_hash"]
            if st == "content_missing":
                return "content_missing", None, None, path_changed, True
            g = grades.get((r["iid"], h)) if st == "applied" else None
            if st == "applied" and g is None:
                return "grade_missing", None, None, path_changed, True
            state = accept_state(st, g)
            if (r["new_status"], r["new_hash"]) != (r["stored_status"], r["stored_hash"] if r["stored_status"] == "applied" else r["new_hash"]):
                path_changed = True
            if state != "continue":
                return state, r["turn"], state == "accepted_resolved", path_changed, False
        return "continue", None, False, path_changed, len(seq) < MAX_TURNS

    res = collections.defaultdict(collections.Counter)
    detail = []
    ids = sorted({k[1] for k in by if k[0] == "orig"})
    for gname in ("orig", "corrected"):
        for model in MODELS:
            for arm in ("R", "F", "P"):
                if gname == "corrected" and arm == "R":
                    continue
                cnt = res[f"{gname}|{model}|{arm}"]
                for iid in ids:
                    use = "fix" if (gname == "corrected" and iid in fixed_ids) else "orig"
                    seq = by.get((use, iid, model, arm))
                    if not seq:
                        continue
                    old_last = max(seq, key=lambda x: x["turn"])
                    old_solved = old_last["stored_state"] == "accepted_resolved"
                    state, turn, nsolved, pchg, unav = replay(seq)
                    cnt["tasks"] += 1
                    cnt["old_solved"] += old_solved
                    cnt["new_solved_lower"] += bool(nsolved)
                    if unav and not nsolved:
                        cnt["unavailable"] += 1
                        if old_solved:
                            cnt["unavailable_old_solved"] += 1
                    if pchg:
                        cnt["path_changed"] += 1
                    if bool(nsolved) != old_solved or (unav and not nsolved) or pchg:
                        detail.append(dict(group=gname, model=model, arm=arm, iid=iid, old_solved=old_solved, new_state=state, new_solved=bool(nsolved),
                                           turn_accepted=turn, path_changed=pchg, needs_new_draw=bool(unav and not nsolved)))
    summ["replay"] = {k: dict(v) for k, v in sorted(res.items())}
    summ["changed_apply_rows"] = changed_rows
    summ["replay_task_detail"] = detail
    outp = os.path.join(AN, f"regrade_dev_summary_{a.tag}.json")
    json.dump(summ, open(outp, "w"), indent=1)
    with open(os.path.join(AN, f"regrade_dev_per_task_{a.tag}.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["group", "model", "arm", "iid", "old_solved", "new_state", "new_solved", "turn_accepted", "path_changed", "needs_new_draw"])
        w.writeheader()
        w.writerows(detail)
    print(json.dumps(dict(control=summ["control"], apply_changes=summ["apply_changes"], replay=summ["replay"]), indent=1))
    print("->", outp)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["apply", "grade", "summary"])
    ap.add_argument("--engine-dir")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--control", default="experimental")
    a = ap.parse_args()
    os.makedirs(AN, exist_ok=True)
    {"apply": stage_apply, "grade": stage_grade, "summary": stage_summary}[a.stage](a)
