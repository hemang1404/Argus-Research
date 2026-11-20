"""Re-apply the STORED sealed-set model outputs with a chosen Argus patch engine, and (for the released engine) re-grade the patches that changed.

No model calls. Stored outputs come from data/blind/{trajectories,calls}.jsonl (original Redraw and Feedback runs) and
data/blind_fix/{trajectories,calls}.jsonl (corrected Feedback reruns). The request body of every stored attempt is rebuilt
(same prompt, same context, same seed, same feedback text), and its cached reply is looked up by request hash.

Stages (run in this order; each is resumable):
  apply   --engine-dir DIR --tag TAG   re-apply every stored reply with the engine in DIR      -> results/analysis/regrade_apply_TAG.jsonl
  grade   --tag TAG                    grade in Docker (official swebench harness) every patch that differs from a stored,
                                       already graded patch                                       -> results/analysis/regrade_grades_TAG.jsonl
  summary --tag TAG --control CTRL     replay stop rule, write JSON + per-task table              -> results/analysis/regrade_summary_TAG.json
Engines used for the paper: experimental = commit 467b720 (0.2.0b1), released = commit 6c7592f (0.2.0b2).
A control run with the experimental engine must reproduce the stored apply outcomes; the summary reports how well it does.
"""
import argparse, collections, difflib, hashlib, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AN = os.path.join(ROOT, "results", "analysis")
TASKS = r"C:\coding\Argus-research-archive\data\swe_bench_verified_tasks.jsonl"
MODELS = {"gpt-oss-20b": "openai/gpt-oss-20b", "gpt-oss-120b": "openai/gpt-oss-120b", "gemma-4-26b-a4b-it": "google/gemma-4-26b-a4b-it"}
EFFORT, TEMP, MAX_OUT, PROMPT_BUDGET, MAX_TURNS = "medium", 1.0, 8000, 6000, 3


def sha1(s):
    return hashlib.sha1(s.encode()).hexdigest()[:10]


def load_jsonl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def stored_sets():
    """orig: original sealed runs (all arms); fix: corrected Feedback reruns (gpt-oss, F only)."""
    out = {}
    for name in ("blind", "blind_fix"):
        rows = [r for r in load_jsonl(os.path.join(ROOT, "data", name, "trajectories.jsonl")) if "models" in r]
        out[name] = {r["iid"]: r for r in rows}
    return out


def load_calls():
    calls = {}
    for name in ("blind", "blind_fix"):
        for r in load_jsonl(os.path.join(ROOT, "data", name, "calls.jsonl")):
            if r.get("http") == 200:
                calls[r["key"]] = r
    return calls


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
    full = {}
    for d in load_jsonl(TASKS):
        full[d["instance_id"]] = d
    calls, sets = load_calls(), stored_sets()

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

    def body_for(model, msgs, seed):
        if model == "gemma-4-26b-a4b-it":
            return {"model": "gemma-4-26b-a4b-it", "messages": msgs, "temperature": TEMP, "max_completion_tokens": 16000}, seed
        return {"model": MODELS[model], "messages": msgs, "temperature": TEMP, "max_completion_tokens": MAX_OUT, "reasoning_effort": EFFORT, "seed": seed}, None

    def key_of(body, nonce):
        return hashlib.sha256(json.dumps([body, nonce] if nonce else body, sort_keys=True).encode()).hexdigest()[:20]

    out_path = os.path.join(AN, f"regrade_apply_{a.tag}.jsonl")
    n = miss = 0
    with open(out_path, "w", encoding="utf-8") as fo:
        for sname, rows in sets.items():
            for iid, row in rows.items():
                target, t = row["target_file"], full[iid]
                for model, arms in row["models"].items():
                    for arm, ar in arms.items():
                        for tr in ar["attempts"]:
                            if tr.get("http") != 200:
                                continue
                            turn, seed, fb = tr["turn"], tr["seed"], tr.get("feedback_in")
                            m = base_msgs(iid, target)
                            user = m[1]["content"]
                            if fb:
                                user = (user + f"\n\n## Result of your previous attempt (turn {turn - 1} of {MAX_TURNS})\n{fb}\n\n"
                                        "The file shown above is the original, unmodified file. Write corrected SEARCH/REPLACE block(s) against it.")
                            body, nonce = body_for(model, [m[0], dict(role="user", content=user)], seed)
                            rec = calls.get(key_of(body, nonce))
                            src = "calls"
                            if rec is None and tr.get("content") is not None:
                                rec, src = dict(content=tr["content"], finish=tr.get("finish")), "trajectory"
                            row_out = dict(set=sname, iid=iid, model=model, arm=arm, turn=turn, seed=seed,
                                           stored_status=tr.get("apply_status"), stored_tier=tr.get("max_tier"), stored_hash=tr.get("patch_hash"),
                                           stored_state=tr.get("state"), stored_resolved=bool((tr.get("grade") or {}).get("resolved")))
                            if rec is None:
                                miss += 1
                                row_out.update(new_status="content_missing", content_src=None)
                            else:
                                res = apply_output(t["repo"], t["base_commit"], target, rec.get("content"), rec.get("finish"))
                                row_out.update(content_src=src, new_status=res["status"], new_tier=res.get("max_tier"),
                                               new_hash=sha1(res["diff"]) if res.get("diff") else None, new_diff=res.get("diff"),
                                               new_reason=res.get("refusal_reason"))
                            fo.write(json.dumps(row_out) + "\n")
                            n += 1
    print(f"attempts processed {n}, content missing {miss} -> {out_path}")


# ------------------------------------------------------------------------------------------------ grade stage
def stored_grades():
    g = {}
    for sname, rows in stored_sets().items():
        for iid, row in rows.items():
            for model, arms in row["models"].items():
                for arm, ar in arms.items():
                    for tr in ar["attempts"]:
                        if tr.get("patch_hash") and tr.get("grade"):
                            g[(iid, tr["patch_hash"])] = tr["grade"]
    return g


def stage_grade(a):
    rows = load_jsonl(os.path.join(AN, f"regrade_apply_{a.tag}.jsonl"))
    have = stored_grades()
    out_path = os.path.join(AN, f"regrade_grades_{a.tag}.jsonl")
    new = {}
    if os.path.exists(out_path):
        for r in load_jsonl(out_path):
            new[(r["iid"], r["hash"])] = r
    need = collections.defaultdict(dict)
    for r in rows:
        if r["new_status"] == "applied" and (r["iid"], r["new_hash"]) not in have and (r["iid"], r["new_hash"]) not in new:
            need[r["iid"]][r["new_hash"]] = r["new_diff"]
    print("patches to grade:", sum(len(v) for v in need.values()), "in", len(need), "tasks")
    if not need:
        return
    sys.path.insert(0, ROOT)
    import harness.dockergrade as DG  # changes cwd and redirects stdout; use DG.say
    for iid, diffs in need.items():
        if not DG.pull(iid):
            DG.say("pull failed", iid)
            continue
        try:
            for h, diff in diffs.items():
                grade, _ = DG.grade_one(iid, h, diff)
                g = {k: v for k, v in grade.items() if k != "log_text"}
                with open(out_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(dict(iid=iid, hash=h, grade=g)) + "\n")
                DG.say("graded", iid, h, "resolved=", g.get("resolved"))
        finally:
            DG.cleanup(iid)


# ------------------------------------------------------------------------------------------------ summary stage
def accept_state(status, grade):
    if status == "applied" and grade and grade.get("applied") and grade.get("f2p_fail") == 0 and (grade.get("f2p_pass") or 0) > 0:
        return "accepted_resolved" if grade.get("resolved") else "accepted_regressed"
    return "continue"


def stage_summary(a):
    new = load_jsonl(os.path.join(AN, f"regrade_apply_{a.tag}.jsonl"))
    ctrl = load_jsonl(os.path.join(AN, f"regrade_apply_{a.control}.jsonl"))
    grades = dict(stored_grades())
    gp = os.path.join(AN, f"regrade_grades_{a.tag}.jsonl")
    if os.path.exists(gp):
        for r in load_jsonl(gp):
            grades[(r["iid"], r["hash"])] = r["grade"]
    summ = {"engine_tag": a.tag, "control_tag": a.control}

    # 1. control: does the experimental engine reproduce what was stored?
    c = collections.Counter()
    for r in ctrl:
        if r["new_status"] == "content_missing":
            c["content_missing"] += 1
            continue
        c["n"] += 1
        same = r["new_status"] == (r["stored_status"] or r["new_status"]) and (r["new_hash"] == r["stored_hash"] if r["stored_status"] == "applied" else True)
        c["reproduced"] += same
        if not same:
            c["not_reproduced"] += 1
    summ["control"] = dict(c)

    # 2. apply outcome changes over every stored attempt (released engine against stored outcome)
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
    fixed_ids = {k[1] for k in by if k[0] == "blind_fix"}

    def replay(seq):
        """returns (state, turn_accepted, new_solved, path_changed, unavailable)."""
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
        # no acceptance within the stored attempts
        unavailable = len(seq) < MAX_TURNS
        return "continue", None, False, path_changed, unavailable

    res = collections.defaultdict(lambda: collections.Counter())
    detail = []
    groups = [("orig", "blind", None), ("corrected", "blind_fix", fixed_ids)]
    for gname, sname, fixed in groups:
        for model in MODELS:
            for arm in ("R", "F"):
                if gname == "corrected" and (arm != "F" or model == "gemma-4-26b-a4b-it"):
                    continue
                iids = sorted({k[1] for k in by if k[0] == "blind" and k[2] == model and k[3] == arm})
                cnt = res[f"{gname}|{model}|{arm}"]
                for iid in iids:
                    use = "blind_fix" if (gname == "corrected" and iid in fixed) else "blind"
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
    outp = os.path.join(AN, f"regrade_summary_{a.tag}.json")
    json.dump(summ, open(outp, "w"), indent=1)
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
