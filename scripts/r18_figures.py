"""Figures for Report 18. Every plotted number is read from reports/Report18/verified_numbers.json or the committed
analysis JSON; nothing is typed in by hand except the pre-registered prediction ranges (copied from PILOT50_PROTOCOL.md).
Colour-blind-safe Okabe-Ito palette."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "reports", "Report18")
FIG = os.path.join(OUT, "figures")
os.makedirs(FIG, exist_ok=True)
VN = json.load(open(os.path.join(OUT, "verified_numbers.json"), encoding="utf-8"))
V = VN["V"]


def J(f):
    return json.load(open(os.path.join(ROOT, f), encoding="utf-8"))


BLUE, ORANGE, GREEN, RED, SKY, PURPLE, YELLOW, GREY, NAVY = "#0072B2", "#E69F00", "#009E73", "#D55E00", "#56B4E9", "#CC79A7", "#F0E442", "#7F7F7F", "#1F4E79"
plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"], "font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titlesize": 10, "axes.labelsize": 9, "figure.dpi": 150, "savefig.dpi": 200, "axes.grid": True, "grid.alpha": 0.25, "grid.linewidth": 0.5})


def save(fig, name):
    p = os.path.join(FIG, name)
    fig.savefig(p, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return p


def fig1_pipeline():
    import r18_fig1
    return r18_fig1.draw(os.path.join(FIG, "fig01_design.png"))


def fig2_design_resolved():
    S = V["design_summary"]
    fig, ax = plt.subplots(figsize=(5.4, 3.1))
    x = [0, 1]; w = 0.34
    for i, (arm, col) in enumerate((("plain", GREY), ("argus", GREEN))):
        vals = [S[m][arm]["rate"] for m in ("gpt-oss-20b", "gpt-oss-120b")]
        lo = [S[m][arm]["rate"] - S[m][arm]["wilson"][0] for m in ("gpt-oss-20b", "gpt-oss-120b")]
        hi = [S[m][arm]["wilson"][1] - S[m][arm]["rate"] for m in ("gpt-oss-20b", "gpt-oss-120b")]
        bars = ax.bar([a + (i - 0.5) * w for a in x], vals, w, yerr=[lo, hi], capsize=3, color=col, label="plain exact-match apply" if arm == "plain" else "Argus v0.2.0b1 apply layer")
        for b, m in zip(bars, ("gpt-oss-20b", "gpt-oss-120b")):
            ax.text(b.get_x() + b.get_width() / 2, 3, f"{S[m][arm]['resolved']}/99", ha="center", color="white", fontsize=8, fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels(["gpt-oss-20b", "gpt-oss-120b"]); ax.set_ylabel("Resolved tasks (%), 95% Wilson CI"); ax.set_ylim(0, 65)
    ax.legend(frameon=False, loc="upper left")
    ax.set_title("Pilot-100 design set, T=0, one draw, 99 valid tasks")
    return save(fig, "fig02_design_resolved.png")


def fig3_funnel():
    S = V["design_summary"]
    def groups(lab):
        g = dict(Resolved=0, Truncated=0, NotApplied=0, Wrong=0)
        for k, n in lab.items():
            if k == "PASS": g["Resolved"] += n
            elif k.startswith("F1"): g["Truncated"] += n
            elif k.startswith("F4") or k.startswith("F2") or k.startswith("F3"): g["NotApplied"] += n
            else: g["Wrong"] += n
        return g
    conds = [("20B plain", S["gpt-oss-20b"]["plain"]["labels"]), ("20B + Argus", S["gpt-oss-20b"]["argus"]["labels"]),
             ("120B plain", S["gpt-oss-120b"]["plain"]["labels"]), ("120B + Argus", S["gpt-oss-120b"]["argus"]["labels"])]
    cats = [("Resolved", GREEN, "Resolved"), ("Wrong", RED, "Applied but wrong / regression / crash"), ("NotApplied", ORANGE, "Edit not applied, refused, or unusable format"), ("Truncated", GREY, "Budget truncation (no answer)")]
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    left = [0] * 4
    for key, col, lab in cats:
        vals = [groups(l)[key] for _, l in conds]
        ax.barh([c for c, _ in conds], vals, left=left, color=col, label=lab)
        for i, v in enumerate(vals):
            if v >= 4: ax.text(left[i] + v / 2, i, str(v), ha="center", va="center", color="white", fontsize=8, fontweight="bold")
        left = [a + b for a, b in zip(left, vals)]
    ax.invert_yaxis(); ax.set_xlabel("Tasks (of 99)"); ax.set_xlim(0, 99)
    ax.legend(frameon=False, ncol=2, fontsize=7.4, loc="upper center", bbox_to_anchor=(0.5, -0.22))
    ax.set_title("Where each task ends (Pilot-100, T=0)")
    return save(fig, "fig03_funnel.png")


def fig4_ladder():
    D = V["deep"]
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.9), sharey=False)
    steps = ["plain_line_exact", "substring_exact", "plus_whitespace_norm", "argus_all_tiers"]
    labs = ["line-exact\n(plain arm)", "+ substring\n(str_replace)", "+ whitespace\ntolerance", "+ Tier 3 fuzzy\n(full Argus)"]
    for ax, m, c in zip(axes, ("gpt-oss-20b", "gpt-oss-120b"), (BLUE, ORANGE)):
        vals = [D[f"baseline_ladder_{m}"][s]["pass_"] for s in steps]
        bars = ax.bar(range(4), vals, color=c)
        for b, v in zip(bars, vals): ax.text(b.get_x() + b.get_width() / 2, v + 0.6, str(v), ha="center", fontsize=8)
        ax.set_xticks(range(4)); ax.set_xticklabels(labs, fontsize=6.8); ax.set_title(m); ax.set_ylim(0, 54)
    axes[0].set_ylabel("Resolved tasks (of 99)")
    fig.suptitle("A tolerant apply tool, not fuzzy matching, supplies most of the gain", fontsize=9.5, y=1.02)
    fig.tight_layout()
    return save(fig, "fig04_ladder.png")


def fig5_scatter():
    pts = V["spearman"]["points"]
    fig, ax = plt.subplots(figsize=(5.2, 3.3))
    for k, (x, y) in pts.items():
        ax.scatter(x, y, s=38, color=NAVY, zorder=3)
        ax.annotate(k, (x, y), textcoords="offset points", xytext=(4, 4), fontsize=7)
    ax.set_xlabel("Plain 'edit not applied' rate (% of draws)"); ax.set_ylabel("Argus gain in applied edits (points)")
    rho = V["spearman"]["tie_corrected"]
    ax.set_title(f"Apply-layer gain follows how often edits fail to match (Spearman {rho:.2f}, 8 models)")
    ax.title.set_fontsize(8.6)
    return save(fig, "fig05_gain_vs_failrate.png")


def fig6_cost():
    c = V["sweep"]["cost"]
    names = [("gpt-oss-20b", "gpt-oss-20b"), ("gpt-oss-120b", "gpt-oss-120b"), ("gemini-3.1-flash-lite", "Gemini 3.1\nFlash-Lite"), ("gemini-3.5-flash-lite", "Gemini 3.5\nFlash-Lite")]
    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    vals = [c[k]["usd_per_solve"] for k, _ in names]
    bars = ax.bar([n for _, n in names], vals, color=[BLUE, ORANGE, GREEN, PURPLE])
    for b, v in zip(bars, vals): ax.text(b.get_x() + b.get_width() / 2, v * 1.12, f"${v:.4f}", ha="center", fontsize=8)
    ax.set_yscale("log"); ax.set_ylim(0.001, 0.07); ax.set_ylabel("USD per solved task (log scale)")
    ax.set_title("Cost per solve, Argus apply, one call per draw (Revision 6 price book)")
    ax.title.set_fontsize(8.8)
    return save(fig, "fig06_cost_per_solve.png")


def fig7_pareto():
    T = V["t1"]
    fig, ax = plt.subplots(figsize=(5.8, 3.5))
    sr = T["stop_rules"]
    for m, col, lab in (("gpt-oss-20b", BLUE, "20B, test-gated retries K=1,2,3"), ("gpt-oss-120b", ORANGE, "120B, test-gated retries K=1,2,3")):
        pts = [sr[m][k] for k in ("no_retry (K=1)", "retry to K=2", "retry to K=3 (baseline)")]
        ax.plot([p["spend"] for p in pts], [p["solves"] for p in pts], "-o", color=col, label=lab, ms=4)
    so = T["oracle"]["single_draw_each"]
    ax.scatter(so["cascade_test_gated"]["mean_spend"], so["cascade_test_gated"]["mean_solves"], marker="s", color=GREEN, s=48, label="20B->120B cascade, test-gated", zorder=4)
    ax.scatter(so["cascade_observable_only"]["mean_spend"], so["cascade_observable_only"]["mean_solves"], marker="s", color=RED, s=48, label="20B->120B cascade, observable-only", zorder=4)
    ax.scatter(so["O1_model_choice_only"]["mean_spend"], so["O1_model_choice_only"]["mean_solves"], marker="*", color="black", s=90, label="oracle router O1 (perfect model choice)", zorder=4)
    ax.scatter(so["O3_skip_hopeless"]["mean_spend"], so["O3_skip_hopeless"]["mean_solves"], marker="*", color=GREY, s=90, label="oracle O3 (also skips hopeless tasks)", zorder=4)
    ax.set_xlabel("Spend for 99 tasks (USD, Groq list price)"); ax.set_ylabel("Solved tasks (mean of draw orders)")
    ax.legend(frameon=False, fontsize=6.6, loc="lower right")
    ax.set_title("Temperature 1.0, 3 draws: retrying the large model beats cascading", fontsize=9)
    return save(fig, "fig07_pareto.png")


def fig8_localization():
    L = V["loc"]
    ks = ["recall@1", "recall@3", "recall@5", "recall@10"]
    fig, ax = plt.subplots(figsize=(5.0, 2.9))
    w = 0.38
    for i, (key, col, lab) in enumerate((("L-B BM25", BLUE, "BM25 over repo files"), ("L-A Argus", ORANGE, "Argus DeterministicLocalizer"))):
        vals = [L[key][k] for k in ks]
        bars = ax.bar([j + (i - 0.5) * w for j in range(4)], vals, w, color=col, label=lab)
        for b, v in zip(bars, vals): ax.text(b.get_x() + b.get_width() / 2, v + 1, str(v), ha="center", fontsize=7.5)
    ax.set_xticks(range(4)); ax.set_xticklabels(["top-1", "top-3", "top-5", "top-10"]); ax.set_ylabel("Gold file found (% of 100 tasks)"); ax.set_ylim(0, 95)
    ax.legend(frameon=False, fontsize=7.5)
    ax.set_title("Issue-only file localization (no gold information)")
    return save(fig, "fig08_localization.png")


def fig9_forest():
    d2 = J("results/analysis/loop2_summary.json")["within_3_attempts"]["F_minus_R"]
    d20 = J("results/analysis/loop2_20b_summary.json")["within_3_attempts"]["F_minus_R"]
    LF = V["loop_f"]; R18 = V["rev18"]; BR = V["blind_report"]["results"]
    rows = [("DESIGN set (100 tasks, discovery)", None, None, None, None),
            ("gpt-oss-120b", d2["diff"], d2["ci95"][0], d2["ci95"][1], BLUE),
            ("gpt-oss-20b", d20["diff"], d20["ci95"][0], d20["ci95"][1], BLUE),
            ("Gemma 26B", LF["gemma26|all"]["diff"], LF["gemma26|all"]["ci"][0], LF["gemma26|all"]["ci"][1], GREEN),
            ("Qwen3.8-27B", LF["qwen38|all"]["diff"], LF["qwen38|all"]["ci"][0], LF["qwen38|all"]["ci"][1], PURPLE),
            ("Gemini 3.1 FL (1 session)", LF["gemini31|all"]["diff"], LF["gemini31|all"]["ci"][0], LF["gemini31|all"]["ci"][1], ORANGE),
            ("Gemini 3.5 FL (1 session)", LF["gemini35|all"]["diff"], LF["gemini35|all"]["ci"][0], LF["gemini35|all"]["ci"][1], ORANGE),
            ("Gemini 3.1 FL (2 replicates)", R18["gemini31:F-R"]["diff"], R18["gemini31:F-R"]["ci"][0], R18["gemini31:F-R"]["ci"][1], ORANGE),
            ("Gemini 3.5 FL (2 replicates)", R18["gemini35:F-R"]["diff"], R18["gemini35:F-R"]["ci"][0], R18["gemini35:F-R"]["ci"][1], ORANGE),
            ("BLIND set (198 sealed tasks)", None, None, None, None)]
    key = {"gpt-oss-20b": "gpt-oss-20b", "gpt-oss-120b": "gpt-oss-120b", "gemma-4-26b-a4b-it": "Gemma 26B (exploratory)"}
    lab = "all analysed (infra failures = unsolved)"
    for m in ("gpt-oss-20b", "gpt-oss-120b", "gemma-4-26b-a4b-it"):
        r = BR[m][lab]
        rows.append((key[m], r["diff"], r["ci"][0], r["ci"][1], RED))
    fig, ax = plt.subplots(figsize=(6.6, 4.1))
    y = len(rows)
    for lbl, d, lo, hi, col in rows:
        y -= 1
        if d is None:
            ax.text(-13.5, y, lbl, fontsize=7.6, fontweight="bold", color=NAVY, va="center")
            continue
        ax.plot([lo, hi], [y, y], color=col, lw=2)
        ax.scatter([d], [y], color=col, s=26, zorder=3)
        ax.text(-13.5, y, lbl, fontsize=7.4, va="center")
        ax.text(14.2, y, f"{d:+.1f} ({lo:+.1f}, {hi:+.1f})", fontsize=7.2, va="center")
    ax.axvline(0, color="black", lw=0.8)
    ax.set_xlim(-14, 21); ax.set_ylim(-0.7, len(rows) - 0.3); ax.set_yticks([]); ax.spines["left"].set_visible(False); ax.grid(axis="y", visible=False)
    ax.set_xticks([-10, -5, 0, 5, 10]); ax.set_xlabel("F minus R: tasks solved per 100 within 3 attempts (95% CI)")
    ax.set_title("Test-failure feedback vs independent re-draws, by model", fontsize=9.5)
    return save(fig, "fig09_forest_FR.png")


def fig10_blind():
    B = V["blind_stats"]; BR = V["blind_report"]["results"]; lab = "all analysed (infra failures = unsolved)"
    ms = [("gpt-oss-20b", "gpt-oss-20b"), ("gpt-oss-120b", "gpt-oss-120b"), ("gemma-4-26b-a4b-it", "Gemma 26B\n(exploratory)")]
    fig, ax = plt.subplots(figsize=(5.8, 3.1)); w = 0.34
    for i, (arm, col, name) in enumerate((("R", GREY, "R: independent re-draws"), ("F", RED, "F: test-failure feedback"))):
        vals = [100 * B[f"{m}:{arm}"]["solved"] / 198 for m, _ in ms]
        bars = ax.bar([j + (i - 0.5) * w for j in range(3)], vals, w, color=col, label=name)
        for b, m in zip(bars, ms): ax.text(b.get_x() + b.get_width() / 2, 2, f"{B[m[0] + ':' + arm]['solved']}", ha="center", color="white", fontsize=8, fontweight="bold")
    for j, (m, _) in enumerate(ms):
        r = BR[m][lab]
        ax.text(j, max(100 * B[f"{m}:R"]["solved"] / 198, 100 * B[f"{m}:F"]["solved"] / 198) + 2.5, f"F-R {r['diff']:+.1f}\n({r['ci'][0]:+.1f}, {r['ci'][1]:+.1f})", ha="center", fontsize=7.6)
    ax.set_xticks(range(3)); ax.set_xticklabels([n for _, n in ms]); ax.set_ylabel("Solved within 3 attempts (% of 198)"); ax.set_ylim(0, 75)
    ax.legend(frameon=False, fontsize=7.5, loc="upper right")
    ax.set_title("Sealed blind test, 198 tasks (2 gold-control failures excluded)")
    return save(fig, "fig10_blind.png")


def fig11_rev19():
    R = V["rev19"]; ls = V["loops"]; ln = V["loops_n"]
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.1), gridspec_kw=dict(width_ratios=[1.0, 1.25]))
    ax = axes[0]; w = 0.26
    mods = [("120B", "120B R", "120B F", "120B P19"), ("20B", "20B R", "20B F", "20B P19")]
    for i, (arm, col, idx) in enumerate((("R", GREY, 1), ("F", RED, 2), ("P", BLUE, 3))):
        vals = [ls[m[idx]] for m in mods]
        bars = ax.bar([j + (i - 1) * w for j in range(2)], vals, w, color=col, label={"R": "R re-draw", "F": "F test feedback", "P": "P feedback + previous patch"}[arm])
        for b, v in zip(bars, vals): ax.text(b.get_x() + b.get_width() / 2, v + 0.8, str(v), ha="center", fontsize=8)
    ax.set_xticks(range(2)); ax.set_xticklabels(["gpt-oss-120b", "gpt-oss-20b"]); ax.set_ylim(0, 72); ax.set_ylabel("Solved of 100 (within 3 attempts)"); ax.legend(frameon=False, fontsize=6.8, loc="upper right")
    ax = axes[1]
    items = [("120B  P-F", R["120b:P-F"]), ("120B  P-R", R["120b:P-R"]), ("20B  P-F", R["20b:P-F"]), ("20B  P-R", R["20b:P-R"]), ("Gemma  P-F", R["gemma:P-F"])]
    for k, (lbl, r) in enumerate(items):
        y = len(items) - 1 - k
        col = RED if r["pred"] and not (r["pred"][0] <= r["diff"] <= r["pred"][1]) else BLUE
        if r["pred"]: ax.add_patch(plt.Rectangle((r["pred"][0], y - 0.32), r["pred"][1] - r["pred"][0], 0.64, color="#DDDDDD", zorder=0))
        ax.plot(r["ci"], [y, y], color=col, lw=2); ax.scatter([r["diff"]], [y], color=col, zorder=3, s=26)
        ax.text(13.5, y, f"{r['diff']:+.1f}", fontsize=7.6, va="center")
    ax.axvline(0, color="black", lw=0.8); ax.set_yticks(range(len(items))); ax.set_yticklabels([l for l, _ in items][::-1], fontsize=7.6)
    ax.set_xlim(-12, 16); ax.set_xlabel("difference in solved per 100 (95% CI)\ngrey band = pre-registered prediction"); ax.grid(axis="y", visible=False)
    fig.tight_layout()
    return save(fig, "fig11_rev19.png")


def fig12_why():
    # recovery by attempt-1 failure type; counts transcribed from scripts/analyze_why19.py output (verify/analyze_why19.out), parsed here
    import re
    txt = open(os.path.join(OUT, "verify", "analyze_why19.out"), encoding="utf-8").read()
    blocks = re.split(r"######## ", txt)[1:]
    data = {}
    for b in blocks:
        m = b.split()[0]
        for g in re.finditer(r"attempt 1 = (.+?)\s+n=\s*(\d+)\s+P (\d+)/(\d+)\s+F (\d+)/(\d+)\s+R (\d+)/(\d+)", b):
            data.setdefault(m, []).append((g.group(1).strip(), int(g.group(2)), int(g.group(3)), int(g.group(5)), int(g.group(7))))
    V["why_parsed"] = data
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.0), sharey=True)
    for ax, m in zip(axes, ("120b", "20b")):
        rows = data[m]; w = 0.26
        for i, (arm, col, idx) in enumerate((("R", GREY, 4), ("F", RED, 3), ("P", BLUE, 2))):
            vals = [100 * r[idx] / r[1] for r in rows]
            ax.bar([j + (i - 1) * w for j in range(len(rows))], vals, w, color=col, label={"R": "R re-draw", "F": "F feedback", "P": "P previous+feedback"}[arm])
        ax.set_xticks(range(len(rows))); ax.set_xticklabels([f"{r[0].replace('applied, F2P still failing', 'applied,\ntests fail').replace('not applied', 'not\napplied')}\n(n={r[1]})" for r in rows], fontsize=6.6)
        ax.set_title(f"gpt-oss-{m.upper()}", fontsize=9)
    axes[0].set_ylabel("Tasks eventually solved (%)\namong those failing attempt 1"); axes[0].legend(frameon=False, fontsize=6.8, loc="upper right")
    fig.tight_layout()
    return save(fig, "fig12_recovery_by_type.png")


def fig13_predictions():
    R18 = V["rev18"]; R19 = V["rev19"]; LF = V["loop_f"]; LP = V["loop_p17"]
    P = []  # (label, lo, hi, value)
    P.append(("Rev15 Gemma F-R", 2, 10, LF["gemma26|all"]["diff"]))
    P.append(("Rev15 Qwen3.8 F-R", -4, 4, LF["qwen38|all"]["diff"]))
    P.append(("Rev16 Gemini 3.1 F-R", -4, 4, LF["gemini31|all"]["diff"]))
    P.append(("Rev16 Gemini 3.5 F-R", -4, 4, LF["gemini35|all"]["diff"]))
    P.append(("Rev17 Gemini 3.1 P-R", -2, 6, LP["gemini31|all"]["diff"]))
    P.append(("Rev17 Gemini 3.5 P-R", -2, 6, LP["gemini35|all"]["diff"]))
    names = {"gemini31:P-R": "Rev18 Gemini 3.1 P-R", "gemini31:P-F": "Rev18 Gemini 3.1 P-F", "gemini31:F-R": "Rev18 Gemini 3.1 F-R", "gemini31:Pg-Fg": "Rev18 Gemini 3.1 greedy P-F",
             "gemini35:P-R": "Rev18 Gemini 3.5 P-R", "gemini35:P-F": "Rev18 Gemini 3.5 P-F", "gemini35:F-R": "Rev18 Gemini 3.5 F-R", "gemini35:Pg-Fg": "Rev18 Gemini 3.5 greedy P-F"}
    for k, nm in names.items():
        r = R18[k]; P.append((nm, r["pred"][0], min(r["pred"][1], 12), r["diff"]))
    P.append(("Rev19 120B P-F", -5, 4, R19["120b:P-F"]["diff"])); P.append(("Rev19 120B P-R", -4, 6, R19["120b:P-R"]["diff"]))
    P.append(("Rev19 20B P-F", -5, 4, R19["20b:P-F"]["diff"])); P.append(("Rev19 20B P-R", -2, 8, R19["20b:P-R"]["diff"]))
    P.append(("Rev19 Gemma P-F", -5, 5, R19["gemma:P-F"]["diff"]))
    fig, ax = plt.subplots(figsize=(6.6, 5.4))
    held = 0
    for i, (lbl, lo, hi, v) in enumerate(P):
        y = len(P) - 1 - i; ok = lo <= v <= hi; held += ok
        ax.add_patch(plt.Rectangle((lo, y - 0.34), hi - lo, 0.68, color="#D9D9D9", zorder=0))
        ax.scatter([v], [y], color=BLUE if ok else RED, s=34, zorder=3, marker="o" if ok else "X")
    ax.set_yticks(range(len(P))); ax.set_yticklabels([p[0] for p in P][::-1], fontsize=7.2)
    ax.axvline(0, color="black", lw=0.8); ax.set_xlabel("solved per 100: outcome (dot) vs pre-registered range (grey)"); ax.grid(axis="y", visible=False)
    ax.set_title(f"Pre-registered predictions: {held} of {len(P)} difference predictions held, {len(P) - held} missed", fontsize=9)
    V["pred_counts"] = dict(held=held, total=len(P))
    return save(fig, "fig13_predictions.png")


def fig14_regression():
    R18 = V["rev18"]; LP = V["loop_p17"]
    fig, ax = plt.subplots(figsize=(4.8, 3.0))
    for k, (m, col, nm) in enumerate((("gemini31", ORANGE, "Gemini 3.1 FL"), ("gemini35", PURPLE, "Gemini 3.5 FL"))):
        a, b = LP[f"{m}|all"]["diff"], R18[f"{m}:P-R"]["diff"]
        ax.plot([0, 1], [a, b], "-o", color=col, label=nm)
        ax.text(1.04, b, f"{b:+.1f}", fontsize=8, va="center", color=col); ax.text(-0.04, a, f"{a:+.1f}", fontsize=8, va="center", ha="right", color=col)
    ax.axhline(0, color="black", lw=0.8); ax.set_xticks([0, 1]); ax.set_xticklabels(["Revision 17\n(one session)", "Revision 18\n(two fresh replicates)"]); ax.set_xlim(-0.35, 1.35)
    ax.set_ylabel("P minus R (solved per 100)"); ax.legend(frameon=False, fontsize=7.5)
    ax.set_title("The same comparison, re-drawn: single-session P-R moved", fontsize=9)
    return save(fig, "fig14_replicates.png")


def fig15_e3():
    fig, ax = plt.subplots(figsize=(5.8, 2.4))
    groups = [("Rescued by apply layer (n=38)", [29, 5, 3, 1]), ("Not rescued (n=227)", [165, 15, 46, 1]), ("All (n=265)", [194, 20, 49, 2])]
    cats = [("Correct", GREEN), ("Partial", YELLOW), ("Wrong or fragile", RED), ("Junk but equivalent", GREY)]
    for gi, (nm, vals) in enumerate(groups):
        tot = sum(vals); left = 0
        for (c, col), v in zip(cats, vals):
            ax.barh(gi, 100 * v / tot, left=left, color=col, label=c if gi == 0 else None)
            if v / tot > 0.05: ax.text(left + 50 * v / tot, gi, f"{v}", ha="center", va="center", fontsize=7.5, color="black" if col in (YELLOW,) else "white")
            left += 100 * v / tot
    ax.set_yticks(range(3)); ax.set_yticklabels([g[0] for g in groups], fontsize=7.6); ax.invert_yaxis(); ax.set_xlabel("Share of resolved patches (%)"); ax.legend(frameon=False, ncol=4, fontsize=6.8, loc="upper center", bbox_to_anchor=(0.5, -0.3))
    ax.set_title("Reader-judged quality of patches the harness marks resolved", fontsize=9)
    return save(fig, "fig15_e3_quality.png")


def build_all():
    out = {}
    for f in (fig1_pipeline, fig2_design_resolved, fig3_funnel, fig4_ladder, fig5_scatter, fig6_cost, fig7_pareto, fig8_localization, fig9_forest, fig10_blind,
              fig11_rev19, fig12_why, fig13_predictions, fig14_regression, fig15_e3):
        out[f.__name__] = f()
    return out


if __name__ == "__main__":
    for k, v in build_all().items():
        print(k, v)
    print(V.get("pred_counts"))
