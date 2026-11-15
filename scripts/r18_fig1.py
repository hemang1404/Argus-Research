"""Figure 1 of Report 18 (study design diagram)."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

NAVY, ORANGE, GREEN, GREY = "#1F4E79", "#E69F00", "#009E73", "#7F7F7F"


def draw(path):
    fig, ax = plt.subplots(figsize=(7.6, 4.3))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 60)
    ax.axis("off")

    def box(x, y, w, h, text, fc, ec=NAVY, fs=6.9):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.2", fc=fc, ec=ec, lw=1.1))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color="black", linespacing=1.25)

    def arrow(x1, y1, x2, y2, c=NAVY, ls="-", rad=0.0):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=9, color=c, lw=1.1, ls=ls, connectionstyle=f"arc3,rad={rad}"))

    W, GAP = 16.8, 3.2
    xs = [1 + i * (W + GAP) for i in range(5)]
    box(xs[0], 40, W, 15, "TASK\nSWE-bench Verified\nsingle-file issue\nmanifest + SHA-256\nfixed before any run", "#EAF1F8")
    box(xs[1], 40, W, 15, "CONTEXT BUILDER\ntarget file GIVEN\nwhole file, else BM25\nchunks (6,000 tokens)\nno localization", "#FFF3D6", ec=ORANGE)
    box(xs[2], 40, W, 15, "MODEL CALL\ngpt-oss 20B / 120B\nGemma, Gemini, Qwen\nT = 1.0\nat most 3 attempts", "#EAF1F8")
    box(xs[3], 40, W, 15, "ARGUS APPLY LAYER\nTier 1 exact\nTier 2 whitespace\nTier 3 fuzzy + guards\nAST syntax gate", "#E3F4EC", ec=GREEN)
    box(xs[4], 40, W, 15, "OFFICIAL DOCKER\nswebench harness\nFAIL_TO_PASS and\nPASS_TO_PASS tests\ngold-patch control", "#EAF1F8")
    for i in range(4):
        arrow(xs[i] + W + 0.4, 47.5, xs[i + 1] - 0.4, 47.5)
    box(57, 17, 42, 15, "STOP RULE\nstop at the first patch that passes\nall FAIL_TO_PASS tests.\nSOLVED = that patch resolves F2P and P2P\nin the official harness.\naccepted_regressed counts as unsolved", "#F7F7F7", fs=6.2)
    arrow(xs[4] + W / 2, 39.4, 90, 32.6)
    box(1, 17, 46, 15, "RETRY ARMS (attempts 2 and 3)\nR  independent re-draw, no failure information\nF  failing-test text (<= 2,000 chars) or apply\n    error; previous patch hidden\nP  F + previous patch (<= 3,000 chars): the\n    deployed Argus repair prompt", "#F7F7F7", ec=GREY, fs=6.0)
    arrow(56.6, 24.5, 47.6, 24.5, c=GREY, ls="--")
    ax.text(52.1, 27.2, "not accepted,\nattempts < 3", ha="center", fontsize=5.4, color=GREY)
    arrow(25, 32.6, xs[2] + 4, 39.4, c=GREY, ls="--")
    box(1, 1.5, 98, 11, "Rules that protect the result\ngold-patch control on every task (a failing gold patch excludes the task; no replacement after seeing results)  |  every run pre-registered in git before any call\ndesign (discovery) set and sealed blind set kept apart  |  paired task-clustered bootstrap, 5,000 resamples  |  one price card  |  patches graded by the harness, never by a model", "#FFFFFF", ec=GREY, fs=5.4)
    fig.savefig(path, bbox_inches="tight", facecolor="white", dpi=200)
    plt.close(fig)
    return path
