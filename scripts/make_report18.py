"""Build Report 18 (docx + pdf) in the layout of Report 17.
   python -X utf8 scripts/report18_data.py      # recompute + verify numbers  -> reports/Report18/verified_numbers.json
   python -X utf8 scripts/make_report18.py      # figures + docx + pdf (Word COM)
Every number in the text comes from verified_numbers.json / committed analysis JSON, or is labelled 'from Report N, not re-run'."""
import json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import r18_figures as FG

ROOT = FG.ROOT
OUT = FG.OUT
FIGS = FG.build_all()
V = FG.V
VN = FG.VN
CHK = VN["checks"]
J = FG.J
NAVY = RGBColor(0x1F, 0x4E, 0x79)
SLATE = RGBColor(0x2E, 0x40, 0x53)
GREYC = RGBColor(0x64, 0x64, 0x64)
FONT = "Times New Roman"

doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
sec.left_margin = sec.right_margin = Cm(2.1)
sec.top_margin, sec.bottom_margin = Cm(2.0), Cm(2.0)
TEXTW = 21.0 - 4.2

# ---------------------------------------------------------------- styles
st = doc.styles["Normal"]
st.font.name = FONT
st.font.size = Pt(10.5)
st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
st.paragraph_format.space_after = Pt(5)
st.paragraph_format.line_spacing = 1.08
for name, size, color, before, after in (("Heading 1", 15, NAVY, 16, 6), ("Heading 2", 13, NAVY, 12, 4), ("Heading 3", 11.5, SLATE, 8, 3)):
    h = doc.styles[name]
    h.font.name = FONT
    h.font.size = Pt(size)
    h.font.bold = True
    h.font.italic = False
    h.font.color.rgb = color
    h.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    h.element.rPr.rFonts.set(qn("w:ascii"), FONT)
    h.element.rPr.rFonts.set(qn("w:hAnsi"), FONT)
    h.element.rPr.rFonts.set(qn("w:cs"), FONT)
    for att in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        k = qn(att)
        if k in h.element.rPr.rFonts.attrib:
            del h.element.rPr.rFonts.attrib[k]
    h.paragraph_format.space_before = Pt(before)
    h.paragraph_format.space_after = Pt(after)
    h.paragraph_format.keep_with_next = True


def runs(par, text, size=None, color=None, italic=False, bold_all=False):
    """**bold** and _italic_ inline markup"""
    parts = re.split(r"(\*\*.+?\*\*)", text)
    for part in parts:
        if not part:
            continue
        b = part.startswith("**") and part.endswith("**")
        r = par.add_run(part[2:-2] if b else part)
        r.bold = b or bold_all
        r.italic = italic
        r.font.name = FONT
        r._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
        if size:
            r.font.size = Pt(size)
        if color is not None:
            r.font.color.rgb = color
    return par


def P(text, justify=True, size=None, italic=False, color=None, after=None, keep=False, align=None):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY if justify else WD_ALIGN_PARAGRAPH.LEFT
    if align is not None:
        p.alignment = align
    runs(p, text, size=size, italic=italic, color=color)
    if after is not None:
        p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.keep_with_next = keep
    return p


def B(text, level=0):
    p = doc.add_paragraph(style="List Bullet")
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.left_indent = Cm(0.9 + 0.6 * level)
    p.paragraph_format.first_line_indent = Cm(-0.5)
    p.paragraph_format.space_after = Pt(3)
    runs(p, text)
    return p


def H1(t):
    return doc.add_heading(t, level=1)


def H2(t):
    return doc.add_heading(t, level=2)


def H3(t):
    return doc.add_heading(t, level=3)


def shade(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hexcolor)
    tcPr.append(shd)


def cell_borders(cell, color="C9CED6", sz=4):
    tcPr = cell._tc.get_or_add_tcPr()
    b = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), str(sz))
        e.set(qn("w:color"), color)
        b.append(e)
    tcPr.append(b)


def cell_margins(table, top=40, bottom=40, left=70, right=70):
    tblPr = table._tbl.tblPr
    m = OxmlElement("w:tblCellMar")
    for k, v in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        e = OxmlElement(f"w:{k}")
        e.set(qn("w:w"), str(v))
        e.set(qn("w:type"), "dxa")
        m.append(e)
    tblPr.append(m)


def no_split(row):
    trPr = row._tr.get_or_add_trPr()
    e = OxmlElement("w:cantSplit")
    trPr.append(e)


def repeat_header(row):
    trPr = row._tr.get_or_add_trPr()
    e = OxmlElement("w:tblHeader")
    trPr.append(e)


TN = [0]
FN = [0]


def caption_t(text):
    TN[0] += 1
    p = doc.add_paragraph()
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(3)
    runs(p, f"Table {TN[0]}: {text}", size=10)
    return TN[0]


def table(header, rows, widths, caption=None, size=8, aligns=None, bold_first=False, hl=None):
    if caption:
        caption_t(caption)
    t = doc.add_table(rows=1, cols=len(header))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    cell_margins(t)
    tot = sum(widths)
    widths = [w * min(1.0, TEXTW / tot) for w in widths]
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]
        c.width = Cm(widths[i])
        shade(c, "1F4E79")
        cell_borders(c, "1F4E79")
        c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        p = c.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        r = p.add_run(h)
        r.bold = True
        r.font.size = Pt(size)
        r.font.name = FONT
        r.font.color.rgb = RGBColor(255, 255, 255)
    repeat_header(t.rows[0])
    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        no_split(t.rows[-1])
        for i, v in enumerate(row):
            c = cells[i]
            c.width = Cm(widths[i])
            cell_borders(c)
            c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            if hl and ri in hl:
                shade(c, hl[ri])
            p = c.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.0
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if not aligns or aligns[i] == "l" else (WD_ALIGN_PARAGRAPH.CENTER if aligns[i] == "c" else WD_ALIGN_PARAGRAPH.RIGHT)
            runs(p, str(v), size=size, bold_all=(bold_first and i == 0))
    if len(rows) <= 9:
        for r_ in t.rows[:-1]:
            for c_ in r_.cells:
                for p_ in c_.paragraphs:
                    p_.paragraph_format.keep_with_next = True
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def figure(path, caption, width_cm=15.2):
    FN[0] += 1
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_before = Pt(4)
    p.add_run().add_picture(path, width=Cm(width_cm))
    c = doc.add_paragraph()
    c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    c.paragraph_format.space_after = Pt(8)
    runs(c, f"Figure {FN[0]}: {caption}", size=9, italic=True, color=GREYC)


def info_table(rows):
    t = doc.add_table(rows=len(rows), cols=2)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    cell_margins(t, 70, 70, 110, 110)
    for ri, row in enumerate(rows):
        for ci, (lab, val) in enumerate(row):
            c = t.rows[ri].cells[ci]
            c.width = Cm(TEXTW / 2)
            shade(c, "F2F4F8")
            cell_borders(c, "D0D5DD")
            p = c.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            runs(p, f"**{lab}** {val}", size=8.8)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def fmt(x, nd=1):
    return f"{x:.{nd}f}"


def sgn(x, nd=1):
    return f"{x:+.{nd}f}"


# ---------------------------------------------------------------- numbers
S, D, T1, SW, NR = V["design_summary"], V["deep"], V["t1"], V["sweep"], V["new_runs"]
LP_ = V["loops"]
AS = V["arm_stats"]
BS = V["blind_stats"]
BR = V["blind_report"]["results"]
BRL = "all analysed (infra failures = unsolved)"
R19 = V["rev19"]
R18 = V["rev18"]
LF, LP17 = V["loop_f"], V["loop_p17"]
L2 = J("results/analysis/loop2_summary.json")
L2b = J("results/analysis/loop2_20b_summary.json")
L3 = J("results/analysis/loop3_summary.json")
L3b = J("results/analysis/loop3_20b_summary.json")
L5 = J("results/analysis/loop_summary.json")
PR = lambda k: R19[k]
usd = lambda a, n: f"${a / n:.5f}"

# ---------------------------------------------------------------- TITLE BLOCK
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_before = Pt(6)
r = p.add_run("REPORT 18")
r.bold = True
r.font.size = Pt(22)
r.font.color.rgb = NAVY
r.font.name = FONT
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_after = Pt(4)
r = p.add_run("Argus After Report 17: From Retrospective Claims to a Pre-Registered, Docker-Graded Study of How Small Models Fail at Repository-Level Code Repair and What a Recovery Runtime Recovers")
r.bold = True
r.font.size = Pt(14)
r.font.color.rgb = NAVY
r.font.name = FONT
P("A Comprehensive Experimental Compendium: Failure Anatomy, the Patch-Apply Layer, Test Feedback versus Independent Re-Draws, Cost and Routing Replays, a Sealed 200-Task Blind Test, and Revision 19 (Pilot-100 Design Set, Revisions 2 to 19, 10 to 15 November 2026)",
  justify=False, size=9, italic=True, color=GREYC, align=WD_ALIGN_PARAGRAPH.CENTER, after=8)
info_table([[("Project:", "Project Argus (Adaptive Inference & Repair)"), ("Audit Status:", "Every headline number re-computed from raw stored data (Table 22)")],
            [("Evaluations:", "300 SWE-bench Verified single-file tasks (100 design + 200 sealed blind); every patch graded in the official Docker harness"),
             ("Models:", "gpt-oss-20b (primary) | gpt-oss-120b | Gemma 4 26B | Gemini 3.1 / 3.5 Flash-Lite | Qwen3.5 2B / 4B / 9B | Qwen3.8-27B")]])

H2("Summary: what the work after Report 17 established")
B("**The older headline numbers are not carried forward.** An independent audit (10 November 2026) refuted or qualified most of Report 17's headline claims (the 92% / 184-of-200 planner, the 72% to 78.5% few-shot lift, the 88% to 90.5% repair figures, the 200x to 400x cost claim). The work in this report starts from a clean, pre-registered design instead (Section 1).")
B(f"**The small model's deficit is mostly pipeline loss, not reasoning.** Once an edit applies, gpt-oss-20b and 120B pass at the same rate (31 of {V['t0_plain_applied']['gpt-oss-20b']} = {100*31/V['t0_plain_applied']['gpt-oss-20b']:.1f}% vs 44 of {V['t0_plain_applied']['gpt-oss-120b']} = {100*44/V['t0_plain_applied']['gpt-oss-120b']:.1f}%). The 20B loses 21 of 99 tasks to repetition loops that return no answer, and many more to edits that do not match the file (Section 4).")
B(f"**The tolerant apply layer is a conditional, small gain.** At temperature 1.0 it adds {sgn(T1['resolve']['argus_minus_plain:gpt-oss-20b']['mean_pp'])} points for the 20B (95% CI {T1['resolve']['argus_minus_plain:gpt-oss-20b']['ci95_pp'][0]} to {T1['resolve']['argus_minus_plain:gpt-oss-20b']['ci95_pp'][1]}) and {sgn(T1['resolve']['argus_minus_plain:gpt-oss-120b']['mean_pp'])} for the 120B; most of it comes from indentation tolerance that any competent edit tool has, and its size follows how often a model's edits fail to match (Section 5).")
B(f"**Test-failure feedback beats blind re-draws for the weakest gpt-oss model, on tasks nobody tuned on.** Pre-registered hypothesis H1 is confirmed on the sealed blind set: F minus R = {sgn(BR['gpt-oss-20b'][BRL]['diff'])} (CI {BR['gpt-oss-20b'][BRL]['ci'][0]} to {BR['gpt-oss-20b'][BRL]['ci'][1]}), consistent with +8 on the design set. For the 120B the effect is smaller and uncertain ({sgn(BR['gpt-oss-120b'][BRL]['diff'])}, CI {BR['gpt-oss-120b'][BRL]['ci'][0]} to {BR['gpt-oss-120b'][BRL]['ci'][1]}); for Gemma, Qwen3.8 and Gemini it is near zero (Sections 8 and 9).")
B(f"**Showing the previous patch (arm P, the deployed Argus repair prompt) does not beat feedback alone on gpt-oss** ({PR('120b:P-F')['diff']:+.1f} and {PR('20b:P-F')['diff']:+.1f} points; Revision 19). Two other families lean the other way (Gemini 3.5 Flash-Lite P minus R {sgn(R18['gemini35:P-R']['diff'])}; Gemma P minus F {sgn(PR('gemma:P-F')['diff'])}), which is exploratory and was missed by pre-registered predictions (Section 10).")
B("**The test gate accepts wrong patches.** 6.6% to 12.0% of patches that pass the target test break other tests, and a reader audit judged about 18% of 'resolved' patches wrong or fragile. 'Resolved' overstates correctness for these small models (Section 11).")
B(f"**Pre-registration did its job.** {V['pred_counts']['held']} of {V['pred_counts']['total']} numeric difference predictions held and {V['pred_counts']['total'] - V['pred_counts']['held']} were missed and reported as misses; a single-session +9.0 for Gemini 3.1 shrank to +2.0 on fresh replicates (Section 12).")
B("**What is not claimed:** no leaderboard score (the target file is given), no routing result across task families (the algorithmic-task half of the original question is untested), and nothing about agentic scaffolds (Section 14).")

# ---------------------------------------------------------------- 1. WHY
H1("1. Why We Did All of This After the Older Research")
H2("1.1 What the older work claimed and how it was built")
P("Report 17 (the 'Comprehensive Experimental Compendium') described Argus as a closed-loop recovery planner. On 200 algorithmic tasks (50 HumanEval and 150 MBPP) it reported a ladder from 72.0% (zero-shot) to 78.5% (few-shot) to 88.0% (compiler-traceback repair) to a learned planner at 92.0% on 100 held-out tasks, and a finding that 'sequential refinement dominates parallel sampling'. On SWE-bench it reported 30 of 300 (10.00%) on Lite and 63 of 500 (12.60%) on Verified at $0.001572 per task, framed as a 200x to 400x cost reduction against published agent frameworks, and credited a five-tier fuzzy patch engine with a +92.3% resolution lift (26 to 50 of 500).")
P("Two properties of that pipeline matter for what followed. First, on SWE-bench the pipeline included a **localization** stage (per the audit, BM25 candidates plus a 120B localizer picked the file before generation, and some scripts fell back to the gold file), so every resolution rate mixed three separate abilities: finding the file, writing a correct change, and getting that change applied to the file. Second, the loop was tuned and reported on the same tasks (hyperparameters on the same 500 tasks) and the feedback used inside the algorithmic loop was not independent of the scoring tests.")
H2("1.2 What the independent audit found")
P("On 10 November 2026 an adversarial audit recomputed Report 17's counts from stored per-task files and re-checked the largest claims by hand (audit_reports/ARGUS_ADVERSARIAL_AUDIT.md in the product repository). Its conclusion, in one line: the engineering is sound, but several headline numbers 'are arithmetically correct but mean something other than what is claimed'. Table 1 lists the claims that matter for this report. 'Verdict' is the audit's own word.")
table(["Report 17 claim", "Audit verdict", "Why (audit finding)"],
      [["72% / 77% zero-shot baselines reflect capability", "REFUTED (harness artifact)", "max_tokens=512 with reasoning counted truncated 22% of attempts; only 2 of 385 truncated attempts passed. On non-truncated first attempts 20B passes 84.1% and 120B 83.2%."],
       ["Few-shot lifts 72% to 78.5% (90.5% headline)", "REFUTED", "All 60 few-shot exemplars were the benchmark's own MBPP tasks; retrieval returned the task itself 60 of 60 times. On those 60 tasks few-shot went 36 to 50; on the other 140, 108 to 107."],
       ["Repair gain 88% to 90.5% is held-out", "REFUTED as held-out", "repair.py pasted the failing scoring assertions (inputs and expected values) into the next prompt and the loop stopped when those same tests passed. 26 of 28 rescues were MBPP, whose prompts contain no signature or tests."],
       ["Learned planner 92% / 184 of 200", "REFUTED as written", "92 of 100 was doubled to 184 of 200. The feature prev_pass_rate leaks the label (about 90% of feature importance, AUC 0.97); the 'tournament' is a table lookup over 20 failed tasks, one sample per (task, action)."],
       ["20B loop is about 3.9x cheaper than 120B; 200x to 400x cost reduction", "REFUTED as a cost result", "Code applied flat $0.08 and $0.65 per Mtok; at Groq list prices the two models cost about the same ($179 vs $176 per 1,000 tasks). The same tokens cost $0.29 to $0.86 under the project's four price cards."],
       ["SWE-bench Verified 26 to 50 of 500 ('doubled')", "QUALIFIED", "The 'strict' arm was never run: it is a replay classification of the same frozen candidates, and the candidates are SEARCH/REPLACE blocks, so 'git apply' is a straw man. An Aider-style applier ties Argus Tiers 1 to 3; only 2 of the 50 solves needed Tier 3."],
       ["63 of 500 'closed loop'", "Count verified; mechanism REFUTED", "The loop gave apply-error feedback, not test feedback; it was a 20B to 120B cascade; hyperparameters were tuned on the same 500 tasks; one unreplicated run."],
       ["Tier 4 contributed +10 solves; 76 of 500 'Cohort B'", "REFUTED / INVALID", "Tier 4 was disabled in code. The 76-of-500 task set was filtered using the gold patch and the generator fell back to the gold file."],
       ["'Frontier-grade at under 1.3 cents per bug'", "REFUTED ('frontier-grade')", "12.6% against published 53% to 61% for gpt-oss-20b on SWE-bench Verified (different scaffold, so a context gap, not a like-for-like gap)."],
       ["SWE-bench Lite 10% vs GPT-4 / Claude 2; $2.50 to $4.20 per task baselines", "Not re-examined; not carried forward", "Report 17 itself notes the comparison is against published numbers from different scaffolds rather than a matched head-to-head."]],
      [4.3, 3.0, 9.5], caption="Report 17 claims and the audit's verdict (from audit_reports/ARGUS_ADVERSARIAL_AUDIT.md, 10 November 2026; the audit is by reading and by execution of proofs of concept, not a re-run of the experiments).", size=7.6, aligns=["l", "l", "l"])
H2("1.3 Why we pivoted: separate the three things the old pipeline mixed")
P("The audit left a usable engine and no usable evidence. The decision (recorded in PILOT50_PROTOCOL.md, Revision 2) was to stop defending the older numbers and to build a smaller study whose every number could survive the audit's objections. The design choices below each answer a specific audit finding.")
B("**Give the model the target file, so recovery and apply are measured separately from localization.** In every run in this report the file to edit is the file the gold patch edits (scripts/run_loop4.py reads meta[iid]['gold_file'] from the frozen manifest; PILOT50_PROTOCOL.md Revision 13: 'Target file GIVEN (the gold file)'). The model sees the whole file if it fits a 6,000-token budget, otherwise BM25-selected chunks scored against the issue text. The gold patch is used only afterwards, to measure what share of the edit region was visible ('context coverage'). Nothing else from the gold patch or the hidden tests reaches the model. This is an **oracle-file setting**: it removes the localization problem on purpose.")
B(f"**Why remove localization.** Issue-only localization is weak and would dominate any end-to-end number. On the 100 design tasks (no gold information) BM25 over repository files puts the right file first for {V['loc']['L-B BM25']['recall@1']} tasks and the Argus localizer for {V['loc']['L-A Argus']['recall@1']} (Figure 1, Table 2). If a pipeline gets the file wrong about three times in four, a change to the edit mechanism or to retries is invisible next to it, and a 'resolution lift' cannot be assigned to the part that was changed.")
B("**Grade with the official swebench Docker harness and a gold-patch control, on every task.** A task whose own gold patch fails is excluded and counted, never swapped in after seeing results (1 of 100 design tasks, psf__requests-1766, was excluded; 2 of 200 blind tasks). The audit found the earlier pilot resolution check tested only the first FAIL_TO_PASS and PASS_TO_PASS test.")
B("**Pre-register before running, and keep two task sets.** Every revision is a numbered section of PILOT50_PROTOCOL.md committed under a git tag before any call (Table 4). The 100 design tasks are discovery numbers; 200 further tasks were hashed and sealed before any model ran on them (tag blind200-sealed) and are the only source of confirmatory claims. This answers the audit's finding that settings were tuned and reported on the same tasks.")
B("**Statistics that fit the sample sizes.** Paired task-clustered bootstrap (5,000 resamples), several draws per task, replicates, and a rule that a null is reported as a null and effects under about 5 points are not called real at 100 tasks. This answers the audit's 'one unreplicated run'.")
B("**Feedback that does not leak.** The model sees only the first failing FAIL_TO_PASS test's name and up to 2,000 characters of its failure text (or Argus's apply error), never the hidden test patch or gold patch; grading always uses the full F2P and P2P suites. This answers the audit's finding that the old repair prompt pasted the scoring assertions.")
B("**One price card, stated, with hidden thinking tokens billed.** This answers the four-price-card problem.")
table(["Recall (issue text only, 100 design tasks)", "top-1", "top-3", "top-5", "top-10", "returned nothing"],
      [["L-A: Argus DeterministicLocalizer (traceback frames, paths, symbols, git grep)", V["loc"]["L-A Argus"]["recall@1"], V["loc"]["L-A Argus"]["recall@3"], V["loc"]["L-A Argus"]["recall@5"], V["loc"]["L-A Argus"]["recall@10"], V["loc"]["L-A Argus"]["returned_nothing"]],
       ["L-B: BM25 over all non-test .py files", V["loc"]["L-B BM25"]["recall@1"], V["loc"]["L-B BM25"]["recall@3"], V["loc"]["L-B BM25"]["recall@5"], V["loc"]["L-B BM25"]["recall@10"], V["loc"]["L-B BM25"]["returned_nothing"]],
       ["Primary: L-A, else L-B", V["loc"]["primary (LA, else LB)"]["recall@1"], V["loc"]["primary (LA, else LB)"]["recall@3"], V["loc"]["primary (LA, else LB)"]["recall@5"], V["loc"]["primary (LA, else LB)"]["recall@10"], 0]],
      [8.2, 1.6, 1.6, 1.6, 1.6, 2.2], caption="No-oracle file localization recall (Revision 3; gold file used only for scoring). Counts are tasks of 100.", size=8, aligns=["l", "c", "c", "c", "c", "c"])
figure(FIGS["fig8_localization"], "Issue-only localization finds the right file first for roughly one task in four; this is why the study gives the file and measures what happens after (data/loc/recall_summary.json).", 11.0)
H2("1.4 What the pivot costs")
B("**The tasks are easier than real SWE-bench.** With the file given, rates are not comparable to leaderboards or to Report 17's SWE-bench figures. Of 500 Verified tasks, 429 qualify as single-file (gold patch touches exactly one non-test .py file); the design set is capped at 30 Django tasks of 100 and is not benchmark-proportional.")
B("**No agentic exploration.** Each attempt is one model call against one file; there is no repository search, no test running by the model, no multi-file change. Whether the recovery results transfer to an agent scaffold is untested.")
B("**Context is limited by a 6,000-token budget (free-tier Groq limits).** For 18 of 99 design tasks none of the gold edit region is visible; neither gpt-oss model solves more than 1 of them without Argus (Section 4). This is a harness limit, not an Argus property.")
B("**Contamination is not excluded.** SWE-bench Verified is public; in a 30-task issue-only screen Gemini named the right file more often than gpt-oss-120b (Report 6). Absolute Gemini rates may be inflated; paired differences are less exposed.")
B("**The algorithmic-task half of the original research question is not tested here.** No algorithmic-task data was collected under this design; the old HumanEval/MBPP results cannot be used (Table 1).")
H2("1.5 Numbers that are not carried forward")
P("The following Report 17 figures do not appear in this report as evidence: 72.0% / 78.5% / 88.0% / 91.5% / 90.5% / 92.0%; 184 of 200; the 3.9x and 200x to 400x cost ratios; the 5-tier +92.3% lift; 63 of 500 and 76 of 500; and the SWE-bench Lite comparison with GPT-4 and Claude 2. Where this report touches the same idea (apply-layer value, loop value, cost per solve) it re-measures it under Section 2's design.")

# ---------------------------------------------------------------- 2. DESIGN
H1("2. Study Design")
figure(FIGS["fig1_pipeline"], "Design of every run in this report: file given, one model call per attempt, Argus apply layer, official Docker grading, stop at the first patch that passes all FAIL_TO_PASS tests.", 15.6)
P("**Tasks.** Design set (Pilot-100): 100 single-file SWE-bench Verified tasks drawn by a fixed-seed stratified sample (Django 30, sympy 21, sphinx 11, matplotlib 9, scikit-learn 9, astropy 6, xarray 5, pytest 5, requests 3, pylint 1); manifest SHA-256 820d412d...12a5ca recorded before any model call (tag pilot100-prereg). One task (psf__requests-1766) fails its own gold-patch control and is excluded, leaving 99 valid tasks; for later revisions astropy__astropy-13579 replaced it. Blind set: 200 further single-file tasks (65 Django, 135 others) sealed under seed 20261113 (tag blind200-sealed) and never used in design; 198 analysed after two gold-control failures (psf__requests-1724, psf__requests-1921).")
P("**Arms.** R: independent re-draws, no failure information. F: the next call adds the first failing FAIL_TO_PASS test's name and at most 2,000 characters of failure text, or Argus's apply error; the previous answer is hidden. P: F plus the previous patch (at most 3,000 characters) in a 'Previous Attempt (FAILED)' block, the format of the deployed Argus repair prompt. All arms: at most 3 attempts; attempt 1 is a stored draw shared by all arms; a task stops at the first patch that passes all FAIL_TO_PASS tests; it counts as **solved** only if that patch resolves FAIL_TO_PASS and PASS_TO_PASS in the official harness. **accepted_regressed** means the target tests pass but other tests break; it counts as unsolved.")
table(["Setting", "gpt-oss-20b", "gpt-oss-120b", "Gemma 4 26B-A4B", "Gemini 3.1 / 3.5 Flash-Lite", "Qwen3.5 2B/4B/9B, Qwen3.8-27B"],
      [["Provider", "Groq (free keys)", "Groq (free keys)", "Google endpoint, no spend", "Google, paid (capped)", "Kaggle T4 (Qwen3.5); Groq (Qwen3.8)"],
       ["Reasoning / output cap", "medium; 8,000 tokens", "medium; 8,000 tokens", "not controllable; 16,000", "default thinking; 16,000", "thinking off; 4,000"],
       ["Temperature, seed", "1.0 (Pilot-100 first pass: 0); seeded", "1.0 (first pass: 0); seeded", "1.0; unseeded", "1.0; unseeded", "1.0; Qwen3.8 seeded"],
       ["List price per 1M in / out", "$0.075 / $0.30", "$0.15 / $0.60", "$0 (free tier)", "$0.25 / $1.50 and $0.30 / $2.50", "not priced here"],
       ["Prompt, context, apply", "p1 (hash 56e5b02fa8ed), 6,000-token file context, target file given, Argus v0.2.0b1 apply (commit 467b720)", "same", "same", "same", "same"]],
      [3.0, 2.6, 2.6, 2.6, 3.0, 3.0], caption="Common settings of the runs. Groq prices are list prices from undated docs; Gemini thinking tokens are billed as output.", size=7.4, aligns=["l"] * 6)
pre = [["Rev 2", "10 Nov", "pilot100-prereg", "100 single-file tasks, plain one-shot then Argus apply; Django capped at 30", "Done (Reports 1, 2)"],
       ["Rev 3", "10 Nov", "pilot100-nooracle-prereg", "No-oracle file localization recall (generation dropped by amendment)", "Done"],
       ["Rev 4", "11 Nov", "pilot100-t1-prereg", "Temperature 1.0, 3 draws; oracle router, cascades, stop rules", "Done (Report 4)"],
       ["Rev 5", "11 Nov", "pilot100-loop-prereg", "Argus-style 4-turn loop vs matched-spend re-draws", "Done (Report 5)"],
       ["Rev 6", "12 Nov", "pilot100-gemini-prereg", "Gemini Flash-Lite sweep, 3 draws, plain vs Argus apply", "Done (Report 6)"],
       ["Rev 7", "12 Nov", "pilot100-loop2-prereg", "F vs R, gpt-oss-120b", "Done (Report 7)"],
       ["Rev 8", "12 Nov", "pilot100-loop3-prereg", "P (multi-turn) vs F vs R, gpt-oss-120b", "Done (Report 8)"],
       ["Rev 9", "12 Nov", "pilot100-20b-loop-prereg", "F, P, R on gpt-oss-20b", "Done (Report 9)"],
       ["Rev 10", "12 Nov", "pilot100-qwen-prereg", "Qwen3.5 size ladder, 30-task edit-failure probe", "Done (Report 10 Qwen)"],
       ["Rev 11/12", "13 Nov", "pilot100-qwen100-prereg, pilot100-gemma-prereg", "Qwen3.5 to 100 tasks with Docker; Gemma 4 sweep", "Qwen and Gemma 26B done; Gemma 31B drafted (294 of 300 draws), not graded"],
       ["Rev 13", "13 Nov", "blind200-sealed, blind200-prereg", "Sealed blind test; hypotheses H1 to H5", "H1 to H4 done; H5 not run"],
       ["Rev 14/15", "13 Nov", "pilot100-qwen38-prereg, pilot100-loopf-prereg", "Qwen3.8-27B sweep; F loop for Gemma and Qwen3.8", "Done"],
       ["Rev 16", "14 Nov", "pilot100-rev16-prereg, blind200-run-code", "Gemma in the blind test; Gemini F loop", "Done"],
       ["Rev 17/18", "14 Nov", "pilot100-rev17-prereg, pilot100-rev18-prereg", "Arm P on Gemini; two fresh replicates and greedy check", "Done"],
       ["Rev 19", "15 Nov", "pilot100-rev19-prereg, pilot100-rev19-gemma-prereg", "Arm P in the deployed prompt format on gpt-oss and Gemma", "Done"]]
table(["Revision", "Date (2026)", "Git tag", "Question", "Status"], pre, [1.5, 1.6, 4.6, 6.2, 3.0], caption="Pre-registration index (PILOT50_PROTOCOL.md; each revision was written and tagged before any model call it describes).", size=7.4, aligns=["l"] * 5)

# ---------------------------------------------------------------- 3. SCOREBOARD
H1("3. Master Comparative Scoreboard: Progression Across the Study")
P("Table 5 consolidates the main results in the layout of Report 17's Table 1. Costs are total token spend at Groq list prices divided by the number of tasks; Gemma runs used the free tier, so no cost is recorded. All counts are tasks resolved in the official harness. Rows from the design set are discovery numbers; rows from the blind set are the confirmatory ones.")
c20, c120 = V["t0_cost"]["cost20"], V["t0_cost"]["cost120"]
rows = [["Pilot-100, T=0: gpt-oss-20b plain", "99 design", "One-shot, exact-match apply", "31 / 99", "31.3%", f"${c20/99:.5f}", "1.00"],
        ["Pilot-100: gpt-oss-20b + Argus apply", "99 design", "One-shot, Argus tiers 1 to 3 + AST gate", "38 / 99", "38.4%", f"${c20/99:.5f}", "1.00"],
        ["Pilot-100: gpt-oss-120b plain", "99 design", "One-shot, exact-match apply", "44 / 99", "44.4%", f"${c120/99:.5f}", "1.00"],
        ["Pilot-100: gpt-oss-120b + Argus apply", "99 design", "One-shot, Argus apply", "46 / 99", "46.5%", f"${c120/99:.5f}", "1.00"],
        ["Rev 7: 120B, arm R", "100 design", "Test-gated re-draws, up to 3", f"{AS['120B R']['solved']} / 100", f"{AS['120B R']['solved']:.1f}%", usd(AS['120B R']['usd'], 100), fmt(AS['120B R']['attempts'], 2)],
        ["Rev 7: 120B, arm F", "100 design", "Test-failure feedback, up to 3", f"{AS['120B F']['solved']} / 100", f"{AS['120B F']['solved']:.1f}%", usd(AS['120B F']['usd'], 100), fmt(AS['120B F']['attempts'], 2)],
        ["Rev 9: 20B, arm R", "100 design", "Test-gated re-draws, up to 3", f"{AS['20B R']['solved']} / 100", f"{AS['20B R']['solved']:.1f}%", usd(AS['20B R']['usd'], 100), fmt(AS['20B R']['attempts'], 2)],
        ["Rev 9: 20B, arm F", "100 design", "Test-failure feedback, up to 3", f"{AS['20B F']['solved']} / 100", f"{AS['20B F']['solved']:.1f}%", usd(AS['20B F']['usd'], 100), fmt(AS['20B F']['attempts'], 2)],
        ["Rev 19: 120B, arm P", "100 design", "Feedback + previous patch", f"{AS['120B P19']['solved']} / 100", f"{AS['120B P19']['solved']:.1f}%", usd(AS['120B P19']['usd'], 100), fmt(AS['120B P19']['attempts'], 2)],
        ["Rev 19: 20B, arm P", "100 design", "Feedback + previous patch", f"{AS['20B P19']['solved']} / 100", f"{AS['20B P19']['solved']:.1f}%", usd(AS['20B P19']['usd'], 100), fmt(AS['20B P19']['attempts'], 2)],
        ["Rev 19: Gemma 26B, arm P", "99 design", "Feedback + previous patch", f"{LP_['Gemma P19']} / 99", f"{100*LP_['Gemma P19']/99:.1f}%", "free tier", "n/a"]]
for m, nm in (("gpt-oss-20b", "gpt-oss-20b"), ("gpt-oss-120b", "gpt-oss-120b"), ("gemma-4-26b-a4b-it", "Gemma 26B")):
    for a, an in (("R", "R re-draws"), ("F", "F test feedback")):
        x = BS[f"{m}:{a}"]
        rows.append([f"BLIND: {nm}, {an}", "198 sealed", "Up to 3 attempts, test-gated", f"{x['solved']} / 198", f"{100*x['solved']/198:.1f}%", usd(x["usd"], 198) if x["usd"] else "free tier", fmt(x["attempts"], 2)])
table(["Phase / System", "Target", "Primary mechanism", "Solved / Total", "Pass rate", "Mean cost / task", "Avg attempts"], rows, [4.4, 1.9, 4.2, 1.9, 1.5, 1.9, 1.5],
      caption="Master progression across the study (file-given setting; not leaderboard scores).", size=7.4, aligns=["l", "l", "l", "c", "c", "c", "c"], hl={11: "EAF1F8", 12: "EAF1F8", 13: "EAF1F8", 14: "EAF1F8", 15: "EAF1F8", 16: "EAF1F8"})

# ---------------------------------------------------------------- 4. FAILURE ANATOMY
H1("4. Where a Small Model Fails: Failure Anatomy (Pilot-100, no Argus)")
P("The first phase generated once per model (temperature 0, seed 1000, medium reasoning, 8,000-token cap) and graded every patch in the official harness. Nothing here uses Argus's retry or test loops.")
n20, n120 = V["t0_plain_applied"]["gpt-oss-20b"], V["t0_plain_applied"]["gpt-oss-120b"]
table(["Stage reached (plain arm, 99 tasks)", "gpt-oss-20b", "gpt-oss-120b"],
      [["Model produced an answer (not one of the 21 no-output truncations)", f"{99-21} (21 truncated with no answer)", "99"],
       ["SEARCH text applied to the file (exact, line-aligned)", str(n20), str(n120)],
       ["Resolved by the full F2P and P2P suites", "31", "44"],
       ["Pass rate given the patch applied", f"{100*31/n20:.1f}% ({31}/{n20})", f"{100*44/n120:.1f}% ({44}/{n120})"],
       ["Paired outcome (McNemar, exact)", "both 27, only 20B 4, only 120B 17, neither 51", f"p = {S['paired_plain']['p_exact_two_sided']}"]],
      [8.0, 4.5, 4.3], caption="The stages of the plain arm. Once a patch lands the two models are indistinguishable (53.4% vs 53.7%).", size=8, aligns=["l", "c", "c"])
lab20, lab120 = S["gpt-oss-20b"]["plain"]["labels"], S["gpt-oss-120b"]["plain"]["labels"]
names = [("PASS", "Resolved"), ("F1_budget_truncation", "F1 budget truncation (8,000 tokens, no answer)"), ("F2_format", "F2 unparseable or empty edit"), ("F3_wrong_file", "F3 wrong file"),
         ("F4_search_not_found", "F4 SEARCH text not found"), ("F4_ambiguous", "F4 SEARCH text ambiguous"), ("F5_syntax", "F5 applied but syntax error"), ("F6_crash_all_tests", "F6 applied, suite crashes"),
         ("F7_wrong_fix", "F7 wrong fix (target tests fail)"), ("F8_regression", "F8 target passes, other tests break"), ("F78_both", "F7 + F8")]
la, lb = S["gpt-oss-20b"]["argus"]["labels"], S["gpt-oss-120b"]["argus"]["labels"]
rows = [[nm, lab20.get(k, 0), la.get(k, 0), lab120.get(k, 0), lb.get(k, 0)] for k, nm in names]
rows.append(["F4 refused by Argus (other reasons)", 0, la.get("F4_refused_other", 0), 0, lb.get("F4_refused_other", 0)])
table(["Failure label (mechanically assigned, in order)", "20B plain", "20B + Argus", "120B plain", "120B + Argus"], rows, [7.6, 2.3, 2.5, 2.3, 2.5],
      caption="Failure labels over 99 valid tasks (results/analysis/summary.json).", size=8, aligns=["l", "c", "c", "c", "c"])
figure(FIGS["fig3_funnel"], "Where each task ends under plain and Argus apply. The 120B never truncates; the 20B loses 21 tasks to budget truncation, which no apply layer can touch.", 13.2)
H3("Budget truncation is a repetition loop, not long thinking")
P(f"21 of 99 gpt-oss-20b runs end at the 8,000-token cap with no answer (22 hit the cap; one had partial content); the 120B never does. The 20B writes {D['tokens_gpt-oss-20b']['mean_completion']:,} completion tokens per task on average against {D['tokens_gpt-oss-120b']['mean_completion']:,} for the 120B, 2.3 times as many, while the prompts are the same size ({D['tokens_gpt-oss-20b']['mean_prompt']:,} tokens). Report 3 found all 21 traces highly repetitive (compression ratio 0.03 to 0.15 against a finished-run median of 0.28; one line repeated more than 200 times). Rerunning at temperature 1.0 broke most loops, but only 3 of the 22 length-capped tasks then resolved (Report 3, not re-run here), consistent with the 120B solving only 2 of the same 21. At temperature 1.0 the 20B loop rate falls from {T1['loop']['gpt-oss-20b']['t0_pct']}% (22 of 99) to {T1['loop']['gpt-oss-20b']['t1_pct']}% (22 of 297), and loops are {T1['loop']['gpt-oss-20b']['t1_loop_tokens_share_of_spend_pct']:.0f}% of the 20B's spend (46% at temperature 0); 10 of the 22 tasks that looped at T=0 loop again on some T=1 draw, so some tasks are loop-prone regardless of temperature.")
H3("Edits that do not land")
P("When a model writes a SEARCH/REPLACE edit, the SEARCH text must be found in the file. The plain arm requires line-exact, unique matches, which is stricter than a normal str_replace tool. In the cases Argus later recovered, the SEARCH text was a correct copy of the code with a trivial difference (a dropped leading indentation on the first line, or drifted indentation inside the block). 15 (20B) and 14 (120B) tasks end with 'not found'; 3 and 2 are ambiguous. This is partly a tool-strictness effect, so the apply-failure numbers should not be read as 'the model cannot copy code' (Report 1).")
H3("Wrong fixes: the real reasoning failures")
P("Of the 20B's 28 wrong or broken applied patches (25 plain plus 3 that only apply under Argus), one annotator read each next to the gold patch and issue (Report 1, single unblinded reader, not re-run): partial fix in the right place 8; wrong location or mechanism 8; over-broad change that breaks other tests 5; near-miss on a single fact (a wrong name, spelling or message) 5; logic inversion 1; a fuzzy edit applied in the wrong function 1. The dominant pattern is 'patches the symptom the issue describes rather than the cause' and 'fixes one of several sites', i.e. under-exploration of the code, not syntax. Five of the wrong fixes are single-token factual errors in an otherwise correct patch, the kind a failing test names directly, which is what the feedback arms later address.")
cf, cn, cz = S["gpt-oss-20b"]["cov_fully_covered"], S["gpt-oss-20b"]["cov_not_fully"], S["gpt-oss-20b"]["cov_zero_cov"]
cf2, cn2, cz2 = S["gpt-oss-120b"]["cov_fully_covered"], S["gpt-oss-120b"]["cov_not_fully"], S["gpt-oss-120b"]["cov_zero_cov"]
table(["Context coverage of the gold edit region (99 tasks)", "Tasks", "20B plain", "20B Argus", "120B plain", "120B Argus"],
      [["Whole gold region inside the prompt", cf["n"], cf["plain_pass"], cf["argus_pass"], cf2["plain_pass"], cf2["argus_pass"]],
       ["Not fully inside (includes the zero-coverage tasks below)", cn["n"], cn["plain_pass"], cn["argus_pass"], cn2["plain_pass"], cn2["argus_pass"]],
       ["Of which: none of it inside the prompt", cz["n"], cz["plain_pass"], cz["argus_pass"], cz2["plain_pass"], cz2["argus_pass"]]],
      [7.0, 1.6, 2.0, 2.0, 2.0, 2.2], caption="Resolved tasks by what the model could see. Zero-coverage tasks are context failures, a floor on any one-shot arm.", size=8, aligns=["l", "c", "c", "c", "c", "c"])
P("**Reading.** (1) The 20B's deficit against the 120B is concentrated before the tests run: truncation loops, then non-matching edits. (2) 'Equal conditional pass rate' is descriptive, not proof of equal reasoning, because the tasks where a weaker model lands a patch are probably the easier ones. (3) 18% of tasks give the model none of the edit region, and neither model solves more than one of them without Argus.")

# ---------------------------------------------------------------- 5. APPLY LAYER
H1("5. What the Argus Patch-Apply Layer Recovers")
figure(FIGS["fig2_design_resolved"], "Plain exact-match versus Argus v0.2.0b1 apply on the same frozen outputs; no model was called again.", 10.6)
m1, m2, m3, m4 = D["mcnemar_20argus_vs_20plain"], D["mcnemar_120argus_vs_120plain"], D["mcnemar_20argus_vs_120plain"], D["mcnemar_20argus_vs_120argus"]
P(f"On the same 99 frozen outputs Argus turns 20B from 31 to 38 resolved (7 gained, 0 lost; exact McNemar p = {m1['p']}) and 120B from 44 to 46 (2 gained, 0 lost; p = {m2['p']}). It adds no tokens and no calls. 20B + Argus against 120B plain is still 6 tasks apart (p = {m3['p']}); against 120B + Argus it is 8 (p = {m4['p']}). The gain is a few percentage points, not a headline.")
lad20, lad120 = D["baseline_ladder_gpt-oss-20b"], D["baseline_ladder_gpt-oss-120b"]
table(["Apply rule (cumulative)", "20B resolved", "120B resolved"],
      [["Line-exact, unique (the plain arm)", lad20["plain_line_exact"]["pass_"], lad120["plain_line_exact"]["pass_"]],
       ["+ exact substring match (a normal str_replace)", lad20["substring_exact"]["pass_"], lad120["substring_exact"]["pass_"]],
       ["+ whitespace / indentation normalization (Aider-style)", lad20["plus_whitespace_norm"]["pass_"], lad120["plus_whitespace_norm"]["pass_"]],
       ["+ Argus Tier 3 fuzzy sliding window (full Argus)", lad20["argus_all_tiers"]["pass_"], lad120["argus_all_tiers"]["pass_"]]],
      [9.0, 3.5, 3.5], caption="Baseline ladder: how much of the apply gain any competent edit tool already has. Because tiers 1 and 2 put the same text in the same place, graded results are identical, so the ladder is derived without re-grading (identical-diff argument, Report 2).", size=8, aligns=["l", "c", "c"])
figure(FIGS["fig4_ladder"], "Six of the 20B's seven extra solves, and both of the 120B's, come from tiers that any edit tool has; only one solve (pytest-5262) needs true fuzzy matching.", 13.0)
P(f"**Safety, the Argus-specific part.** Across both models 12 non-exact applications occurred; 7 resolved and 5 were wrong fixes (Report 2). The AST gate stopped 3 patches that would have been syntax errors; the ambiguity guards refused 5 matches that were genuinely ambiguous and no passing patch was lost to a refusal. There is one confirmed false positive: sympy__sympy-24539 (gpt-oss-20b). With none of the target region in the prompt the model guessed a one-line SEARCH; Tier 3 matched it to a different method (similarity 0.8235, Report 2) and applied it, introducing an undefined name that parses fine; 13 other tests broke (the graded label is F78 in the ladder data). Of the 20B's 66 Argus-applied patches, {D['argus_tiers_gpt-oss-20b']['1']} applied at Tier 1, {D['argus_tiers_gpt-oss-20b']['2']} at Tier 2 and {D['argus_tiers_gpt-oss-20b']['3']} at Tier 3.")
P(f"**Replication at temperature 1.0.** Over 3 draws per task the paired Argus effect is {sgn(T1['resolve']['argus_minus_plain:gpt-oss-20b']['mean_pp'])} points for the 20B (CI {T1['resolve']['argus_minus_plain:gpt-oss-20b']['ci95_pp'][0]} to {T1['resolve']['argus_minus_plain:gpt-oss-20b']['ci95_pp'][1]}) and {sgn(T1['resolve']['argus_minus_plain:gpt-oss-120b']['mean_pp'])} for the 120B (CI {T1['resolve']['argus_minus_plain:gpt-oss-120b']['ci95_pp'][0]} to {T1['resolve']['argus_minus_plain:gpt-oss-120b']['ci95_pp'][1]}), reproducing the T=0 gain (+7 and +2) with intervals that exclude zero. Argus applied {T1['apply_layer']['gpt-oss-20b']['argus_only_applied_draws']} 20B draws that plain could not; {T1['apply_layer']['gpt-oss-20b']['argus_only_applied_and_resolved']} of them resolved. Apply rate (Argus arm) is {T1['apply_rate_pct']['gpt-oss-20b']}% for the 20B and {T1['apply_rate_pct']['gpt-oss-120b']}% for the 120B; the conditional pass rate given an applied patch is {T1['conditional_pass_given_applied']['gpt-oss-20b']}% and {T1['conditional_pass_given_applied']['gpt-oss-120b']}%.")
H3("The patches the layer rescues are mostly real fixes")
P("An audit of every resolved patch that exists only because of the apply layer (38 unique patches, 26 tasks; one reader, not blind, nothing executed except where stated) found 29 correct (4 identical to the gold patch), 5 partial, 3 fragile and 1 junk-but-equivalent; 9 of 38 (24%) are not clean fixes (E3 review). Over all 265 unique resolved patches from the 20B, 120B and Gemma, the non-clean share is 8 of 38 (21%) for rescued patches against 61 of 227 (27%) for the rest, so the apply layer does not inflate the score by lowering the bar. The three 'fragile' sphinx-11445 patches were confirmed by execution: all three insert the prolog before a bare :orphan: line, a regression the test suite does not catch.")

# ---------------------------------------------------------------- 6. T=1, COST, ROUTING
H1("6. Temperature 1.0, Cost, Routing and Stop Rules")
P("Pilot-100 ran at temperature 0, which is not the vendor-recommended setting and a known trigger for repetition loops. Revision 4 re-measured both models at temperature 1.0 with three draws per task (seeds 1000 to 1002), grading all 447 distinct patches. Everything in this section is a discovery number, and the verifier in the retry simulations is the Docker result, a perfect hidden-test verifier, so the numbers are upper bounds for a real test-based gate.")
rs = T1["resolve"]
table(["Arm (99 tasks)", "Draw 1", "Draw 2", "Draw 3", "Mean %", "95% CI", "T=0 single draw"],
      [["20B plain", *rs["plain:gpt-oss-20b"]["per_draw"], rs["plain:gpt-oss-20b"]["mean_pct"], f"{rs['plain:gpt-oss-20b']['ci95'][0]} to {rs['plain:gpt-oss-20b']['ci95'][1]}", T1["t0_reference"]["gpt-oss-20b"]["plain"]],
       ["20B Argus", *rs["argus:gpt-oss-20b"]["per_draw"], rs["argus:gpt-oss-20b"]["mean_pct"], f"{rs['argus:gpt-oss-20b']['ci95'][0]} to {rs['argus:gpt-oss-20b']['ci95'][1]}", T1["t0_reference"]["gpt-oss-20b"]["argus"]],
       ["120B plain", *rs["plain:gpt-oss-120b"]["per_draw"], rs["plain:gpt-oss-120b"]["mean_pct"], f"{rs['plain:gpt-oss-120b']['ci95'][0]} to {rs['plain:gpt-oss-120b']['ci95'][1]}", T1["t0_reference"]["gpt-oss-120b"]["plain"]],
       ["120B Argus", *rs["argus:gpt-oss-120b"]["per_draw"], rs["argus:gpt-oss-120b"]["mean_pct"], f"{rs['argus:gpt-oss-120b']['ci95'][0]} to {rs['argus:gpt-oss-120b']['ci95'][1]}", T1["t0_reference"]["gpt-oss-120b"]["argus"]]],
      [3.0, 1.5, 1.5, 1.5, 1.7, 2.8, 2.6], caption="Temperature 1.0, three draws (resolved tasks of 99; 95% task-clustered bootstrap CI). Temperature does not change the resolve rate; the 120B spans 41 to 52 solved depending on the draw.", size=8, aligns=["l", "c", "c", "c", "c", "c", "c"])
pt = T1["per_task"]
P(f"**Per-task difficulty.** With Argus, the 20B solves {pt['gpt-oss-20b']['hist_k_of_3']['3']} tasks on all three draws, {pt['gpt-oss-20b']['hist_k_of_3']['2']} on two, {pt['gpt-oss-20b']['hist_k_of_3']['1']} on one and never solves {pt['gpt-oss-20b']['hist_k_of_3']['0']}; the 120B {pt['gpt-oss-120b']['hist_k_of_3']['3']} / {pt['gpt-oss-120b']['hist_k_of_3']['2']} / {pt['gpt-oss-120b']['hist_k_of_3']['1']} / {pt['gpt-oss-120b']['hist_k_of_3']['0']}. {pt['solved_by_neither_at_t0']['solved_by_some_t1_draw_any_model']} of the {pt['solved_by_neither_at_t0']['n']} tasks solved by neither model at T=0 are solved by some T=1 draw (partly pass@k selection with the hidden test as verifier). {pt['solvable_by_any_model_any_draw_t1']} tasks are solvable by some model on some draw. **Every task the 20B ever solves, the 120B also solves on some draw** ({pt['solved_by_20b_not_by_120b_any_draw']} 20B-only against {pt['solved_by_120b_not_by_20b_any_draw']} 120B-only), so the cheaper model adds no coverage, only a lower price per attempt.")
so = T1["oracle"]["single_draw_each"]
casc = T1["cascades"]
table(["Policy (mean over 3 draw orders)", "Solved", "Spend ($)", "$ per solve"],
      [["20B alone", so["always_gpt-oss-20b"]["mean_solves"], so["always_gpt-oss-20b"]["mean_spend"], so["always_gpt-oss-20b"]["usd_per_solve"]],
       ["120B alone", so["always_gpt-oss-120b"]["mean_solves"], so["always_gpt-oss-120b"]["mean_spend"], so["always_gpt-oss-120b"]["usd_per_solve"]],
       ["Oracle O1: perfect model per task, every task still attempted", so["O1_model_choice_only"]["mean_solves"], so["O1_model_choice_only"]["mean_spend"], so["O1_model_choice_only"]["usd_per_solve"]],
       ["Oracle O3: O1 plus skipping tasks nobody solves", so["O3_skip_hopeless"]["mean_solves"], so["O3_skip_hopeless"]["mean_spend"], so["O3_skip_hopeless"]["usd_per_solve"]],
       ["20B then 120B cascade, test-gated", so["cascade_test_gated"]["mean_solves"], so["cascade_test_gated"]["mean_spend"], so["cascade_test_gated"]["usd_per_solve"]],
       ["20B then 120B cascade, observable-only (accept first applied patch)", so["cascade_observable_only"]["mean_solves"], so["cascade_observable_only"]["mean_spend"], so["cascade_observable_only"]["usd_per_solve"]]],
      [9.0, 2.2, 2.6, 2.4], caption="Oracle router and cascades on Pilot-100 at T=1.0 (Revision 4; Docker result as a perfect verifier).", size=8, aligns=["l", "c", "c", "c"])
figure(FIGS["fig7_pareto"], "Retrying the large model dominates the realizable cascades: the test-gated cascade solves 51.0 for $0.222, below the 120B retry frontier (56.7 for $0.242); the observable-only cascade is dominated by the 120B alone. Oracle points are not achievable policies.", 12.0)
sr = T1["stop_rules"]
P(f"**Reading.** (1) Perfect knowledge would roughly halve spend, but half of the oracle's spend advantage is knowing which tasks are hopeless (O1 minus O3 = ${T1['oracle']['spend_O1_minus_O3']}), which no observable signal tested here recovers. (2) At this model pair and these prices the allocation problem collapses toward how many times to retry the big model: 120B x2 solves {sr['gpt-oss-120b']['retry to K=2']['solves']} for ${sr['gpt-oss-120b']['retry to K=2']['spend']}, while the test-gated cascade solves {so['cascade_test_gated']['mean_solves']} for ${so['cascade_test_gated']['mean_spend']}. (3) No stop rule saves money for free: each rule that saves spend loses solves, at roughly $0.009 to $0.022 per solve lost against an average of $0.003 to $0.005 per solve. (4) An early-abort token cap tuned on draws 1 and 2 and scored on draw 3 is a null result: the largest resolved 20B run used 7,780 of 8,000 tokens, so token count alone does not separate a long reasoning run from a loop.")
H3("Cost per solved task")
P(f"At Groq list prices the price ratio between the two models is 0.5 per token, but the 20B writes 2.3 times more tokens, so the per-task cost ratio is 0.83. Cost per solved task on the T=0 pilot is ${V['t0_cost_per_solve']['120B plain']:.5f} (120B plain), ${V['t0_cost_per_solve']['120B Argus']:.5f} (120B + Argus), ${V['t0_cost_per_solve']['20B plain']:.5f} (20B plain) and ${V['t0_cost_per_solve']['20B Argus']:.5f} (20B + Argus); the 20B's first-pass loops took 46% of its spend at T=0 ($0.059 of $0.128). Report 3's tally of all-in 20B stages (31, 38, 40 with prototype apply fixes, 43 with a temperature-1.0 retry of the length-capped tasks, against 46 for 120B + Argus) was not re-run here and is a discovery number. In the cross-family sweep (Table 12) 120B costs ${SW['cost']['gpt-oss-120b']['usd_per_solve']:.4f} per solve against ${SW['cost']['gemini-3.1-flash-lite']['usd_per_solve']:.4f} for Gemini 3.1 and ${SW['cost']['gemini-3.5-flash-lite']['usd_per_solve']:.4f} for 3.5.")

# ---------------------------------------------------------------- 7. FAMILIES
H1("7. Other Model Families: How the Apply Layer's Value Depends on the Model")
P("Revisions 6, 10, 11, 12 and 14 added Gemini 3.1 and 3.5 Flash-Lite (3 draws on 100 tasks, Revision 6), Gemma 4 26B (3 draws), Qwen3.5 2B, 4B and 9B (one draw, thinking off, Docker graded) and Qwen3.8-27B (3 draws, reasoning off). Only the apply layer is exercised here: one call per draw, no loop. Counts are mean resolved tasks per 100 (task-clustered bootstrap, 5,000 resamples).")
sv = SW["resolved"]
rows = []
for k, nm in (("gpt-oss-20b", "gpt-oss-20b"), ("gpt-oss-120b", "gpt-oss-120b"), ("gemini-3.1-flash-lite", "Gemini 3.1 Flash-Lite"), ("gemini-3.5-flash-lite", "Gemini 3.5 Flash-Lite")):
    r = sv[k]
    rows.append([nm, f"{r['plain']['mean']} ({r['plain']['ci95'][0]} to {r['plain']['ci95'][1]})", f"{r['argus']['mean']} ({r['argus']['ci95'][0]} to {r['argus']['ci95'][1]})", f"{sgn(r['argus_minus_plain']['mean'])} ({r['argus_minus_plain']['ci95'][0]} to {r['argus_minus_plain']['ci95'][1]})",
                 f"{r['rescued_draws']} / {r['rescued_resolved']}", SW["cost"][k]["usd_per_solve"]])
g = NR["gemma-4-26b-a4b-it"]
rows.append(["Gemma 4 26B-A4B", f"{g['plain_resolved_per100']} ({g['plain_ci'][0]} to {g['plain_ci'][1]})", f"{g['argus_resolved_per100']} ({g['argus_ci'][0]} to {g['argus_ci'][1]})", f"{sgn(g['delta_per100'])} ({g['delta_ci'][0]} to {g['delta_ci'][1]})", "n/a", "free tier"])
q38 = LF["qwen38|all"]
rows.append(["Qwen3.8-27B (reasoning off)", f"{q38['plain']}", f"{q38['argus']}", f"{sgn(q38['argus'] - q38['plain'])}", "n/a", "not priced"])
for k in ("Qwen3.5-9B", "Qwen3.5-4B", "Qwen3.5-2B"):
    r = NR[k]
    rows.append([f"{k} (1 draw)", f"{r['plain_resolved_per100']} ({r['plain_ci'][0]} to {r['plain_ci'][1]})", f"{r['argus_resolved_per100']} ({r['argus_ci'][0]} to {r['argus_ci'][1]})", f"{sgn(r['delta_per100'])} ({r['delta_ci'][0]} to {r['delta_ci'][1]})", "n/a", "not priced"])
table(["Model", "Plain apply", "Argus apply", "Argus minus plain", "Rescued draws / resolved", "$ per solve (Argus)"], rows, [3.6, 3.0, 3.0, 3.0, 2.0, 2.2],
      caption="Cross-family apply-layer results on the 100 design tasks (resolved per 100). Qwen3.8 plain and Argus are means of 3 draws read from analyze_loop_f.py; the 100-task Qwen3.5 rows are 1 draw.", size=7.6, aligns=["l", "c", "c", "c", "c", "c"])
P(f"**Reading.** (1) The apply-layer gain tracks how often a model's plain edits fail to match: Spearman {V['spearman']['tie_corrected']:.2f} across eight models (CLAIM_STATUS recorded 0.71; recomputed from the eight pairs in the protocol with tie-corrected ranks, it is {V['spearman']['tie_corrected']:.2f}; the simple 1 - 6*sum(d^2) formula gives {V['spearman']['simple_formula']:.2f}), with families and sizes confounded and n = 8, so descriptive only (Figure 7). Gemma 26B gains most (+6.0, CI 2.7 to 10.0), Qwen3.8 and Gemini almost nothing. (2) Rescue quality differs: Gemini 3.1's 9 rescued draws resolve 1 time, the gpt-oss rescues 53% to 61% (Report 6). (3) Gemini 3.5 is not clearly better than gpt-oss-120b (51.7 vs 47.7, overlapping intervals) and costs about eight times more per solve because hidden thinking tokens are billed as output (Figure 8). (4) Which Argus tier does the rescuing is family-specific: Tier 2 (whitespace) for gpt-oss, Tier 3 (fuzzy) for Gemini and Qwen (Report 10 Qwen, 30-task probe, not re-run).")
figure(FIGS["fig5_scatter"], "Argus's gain in applied edits against the plain not-applied rate, eight models (design-set values listed in PILOT50_PROTOCOL.md Revision 13).", 11.0)
figure(FIGS["fig6_cost"], "Cost per solved task, Argus arm, one call per draw (Revision 6 price book; Gemini thinking tokens billed as output).", 11.0)
rm = SW["routing_replay"]["mean"]
P(f"**Cross-family routing replay (Revision 6, perfect verifier).** The pre-registered four-model oracle solves {rm['oracle_solved']:.1f} per 100 for ${rm['oracle_usd']:.3f}; the cheapest-first four-rung cascade reaches the same {rm['cascade_solved']:.1f} for ${rm['cascade_usd']:.2f}: the gap is the price of not knowing which model will pass. 120B best-of-3 reaches 61 for $0.47. Post hoc subsets: 20B to 120B {SW['cascade_subsets_post_hoc']['gpt-oss-20b->gpt-oss-120b']['solved']} solved for ${SW['cascade_subsets_post_hoc']['gpt-oss-20b->gpt-oss-120b']['usd']}; 120B to Gemini 3.1 {SW['cascade_subsets_post_hoc']['gpt-oss-120b->gemini-3.1-flash-lite']['solved']} for ${SW['cascade_subsets_post_hoc']['gpt-oss-120b->gemini-3.1-flash-lite']['usd']}; 120B to Gemini 3.5 {SW['cascade_subsets_post_hoc']['gpt-oss-120b->gemini-3.5-flash-lite']['solved']} for ${SW['cascade_subsets_post_hoc']['gpt-oss-120b->gemini-3.5-flash-lite']['usd']}. These cascades use up to 4 attempts against 3 for best-of-3, so the comparison is not budget-matched and is not a deployable result.")

# ---------------------------------------------------------------- 8. FEEDBACK
H1("8. Does Test Feedback Beat Drawing Again? Revisions 5 to 9 on gpt-oss")
P("Report 17's central mechanism claim was that execution feedback gives 'directed corrective gradients' that parallel sampling cannot replicate. Under the corrected design this became a clean experiment: same tasks, same attempts, same stop rule, only the information in the retry differs.")
b4 = L5["by_turn"]["4"]
P(f"**Revision 5 (Argus-style 4-turn ladder, 99 tasks).** Test-fed loop (turn 1 20B medium, turn 2 20B high, turns 3 and 4 120B high) resolved {L5['headline']['L_B_resolved']} against {L5['headline']['redraw_ladder_resolved_mean']} for independent re-draws on the same ladder (L-B minus re-draw {b4['L_B_minus_redraw_ladder_pp']:+.1f} points, CI {b4['ci95_pp'][0]} to {b4['ci95_pp'][1]}) at 2.2 times the spend; at matched spend it sits below re-drawing at mid budgets ({L5['matched_spend'][6]['L_B_minus_ladder_pp']:+.1f}, CI {L5['matched_spend'][6]['ci95_pp'][0]} to {L5['matched_spend'][6]['ci95_pp'][1]} at $0.004 per task). The comparison was confounded: turns 2 to 4 ran at high effort and {L5['loop_rate_by_turn']['turn2_gpt-oss-20b_high']['pct']}% of turn-2 calls hit the 8,000-token cap with no answer, so the ladder mostly tested the cap. Test feedback was worth +8 solves over the observable-only loop (53 vs 45), but the gain came from escalating to the 120B, not from feedback. 7 of the 60 patches that passed all FAIL_TO_PASS tests broke other tests.")
H3("The clean test: Revisions 7, 8 and 9")
rows = [["Rev 7: 120B", "F test feedback vs R re-draws", f"F {L2['within_3_attempts']['F_solved']} / R {L2['within_3_attempts']['R_solved']}", f"{L2['within_3_attempts']['F_minus_R']['diff']:+d} ({L2['within_3_attempts']['F_minus_R']['ci95'][0]:+d} to {L2['within_3_attempts']['F_minus_R']['ci95'][1]:+d})", f"${L2['F_total']['usd']:.3f} / ${L2['R_total']['usd']:.3f}"],
        ["Rev 8: 120B", "P (multi-turn, previous answer) vs R", f"P {L3['within_3_attempts']['P']['solved']} / R {L3['within_3_attempts']['R']['solved']}", f"{L3['within_3_attempts']['P_minus_R']['diff']:+d} ({L3['within_3_attempts']['P_minus_R']['ci95'][0]:+d} to {L3['within_3_attempts']['P_minus_R']['ci95'][1]:+d})", f"${L3['P_total']['usd']:.3f} / ${L3['R_total']['usd']:.3f}"],
        ["Rev 8: 120B", "P vs F", f"P {L3['within_3_attempts']['P']['solved']} / F {L3['within_3_attempts']['F']['solved']}", f"{L3['within_3_attempts']['P_minus_F']['diff']:+d} ({L3['within_3_attempts']['P_minus_F']['ci95'][0]:+d} to {L3['within_3_attempts']['P_minus_F']['ci95'][1]:+d})", "-"],
        ["Rev 9: 20B", "F test feedback vs R re-draws (primary)", f"F {L2b['within_3_attempts']['F_solved']} / R {L2b['within_3_attempts']['R_solved']}", f"{L2b['within_3_attempts']['F_minus_R']['diff']:+d} ({L2b['within_3_attempts']['F_minus_R']['ci95'][0]:+d} to {L2b['within_3_attempts']['F_minus_R']['ci95'][1]:+d})", f"${L2b['F_total']['usd']:.3f} / ${L2b['R_total']['usd']:.3f}"],
        ["Rev 9: 20B", "P vs R", f"P {L3b['within_3_attempts']['P']['solved']} / R {L3b['within_3_attempts']['R']['solved']}", f"{L3b['within_3_attempts']['P_minus_R']['diff']:+d} ({L3b['within_3_attempts']['P_minus_R']['ci95'][0]:+d} to {L3b['within_3_attempts']['P_minus_R']['ci95'][1]:+d})", f"${L3b['P_total']['usd']:.3f} / ${L3b['R_total']['usd']:.3f}"],
        ["Rev 9: 20B", "P vs F", f"P {L3b['within_3_attempts']['P']['solved']} / F {L3b['within_3_attempts']['F']['solved']}", f"{L3b['within_3_attempts']['P_minus_F']['diff']:+d} ({L3b['within_3_attempts']['P_minus_F']['ci95'][0]:+d} to {L3b['within_3_attempts']['P_minus_F']['ci95'][1]:+d})", "-"]]
table(["Revision / model", "Comparison", "Solved of 100 (3 attempts)", "Difference (95% CI)", "Spend (first / second arm)"], rows, [2.6, 5.2, 3.2, 3.2, 2.6],
      caption="Revisions 7, 8 and 9 on the design set (gpt-oss, 100 tasks, medium effort, T=1.0). Revision 8 and 9 'P' arms lost 6 tasks each to Groq's free-tier 8,000-token-per-minute limit (counted unsolved).", size=7.8, aligns=["l", "l", "c", "c", "c"])
pa2 = L2b["per_attempt"]["attempt_2"]
P(f"**Reading.** (1) For the 120B, test feedback did not beat drawing again ({L2['within_3_attempts']['F_minus_R']['diff']:+d}, CI {L2['within_3_attempts']['F_minus_R']['ci95'][0]} to {L2['within_3_attempts']['F_minus_R']['ci95'][1]}); among the 54 tasks that failed attempt 1, F resolved 10 at attempt 2 against 14 for R. (2) For the 20B, feedback beat re-draws (+8, CI +2 to +14): among the 59 tasks failing attempt 1, attempt-2 resolve rate was F {100*pa2['F']['resolve_rate']:.1f}% against R {100*pa2['R']['resolve_rate']:.1f}%. Part of that may be F's prompt: after a cut-off answer F's retry includes a sentence telling the model to keep reasoning short, and R's identical re-draw ran out of tokens at attempt 2 on {pa2['R']['truncated']} of 59 tasks against {pa2['F']['truncated']} for F. After a failing-test traceback 13 of 59 F attempts resolved (22%) against about 8% for a fresh re-draw, the clearest sign that information helped the 20B. (3) Showing the previous answer (P) did not add to F in either model.")
H2("8.1 Other families (Revisions 15 to 18)")
P("The same F-versus-R test was repeated on Gemma 26B and Qwen3.8-27B (Revision 15), then on both Gemini models (Revision 16), with R replayed from stored independent draws. F attempt 2 and 3 calls are new, so each F-versus-R difference mixes the effect with draw-to-draw variation, which Revision 18 later measured directly.")
rows = []
for key, nm in (("gemma26|all", "Gemma 26B (Rev 15)"), ("qwen38|all", "Qwen3.8-27B (Rev 15)"), ("gemini31|all", "Gemini 3.1 FL (Rev 16)"), ("gemini35|all", "Gemini 3.5 FL (Rev 16)")):
    r = LF[key]
    rows.append([nm, r["tasks"], r["R"], r["F"], f"{r['diff']:+.1f} ({r['ci'][0]:+.1f} to {r['ci'][1]:+.1f})", f"{r['fonly']} / {r['ronly']}"])
table(["Model (revision)", "Tasks", "R loop (per 100)", "F loop (per 100)", "F minus R (95% CI)", "F-only / R-only tasks"], rows, [4.4, 1.3, 2.4, 2.4, 3.8, 2.6],
      caption="Feedback versus replayed re-draws on other families (design set, up to 3 attempts; stdout of scripts/analyze_loop_f.py with bootstrap seed 0).", size=8, aligns=["l", "c", "c", "c", "c", "c"])
P("The Qwen3.8 F arm lost 15 of 100 tasks to the Groq input-token limit (api_error) and Gemma lost 7; excluding those tasks, Qwen3.8 F minus R is +3.5 (CI -3.5 to +11.8, 85 tasks) and Gemma +0.0 (92 tasks). Pre-registered predictions: Gemma F minus R in +2 to +10 (**missed**: -1.0), Qwen3.8 in -4 to +4 (held), both Gemini models in -4 to +4 (held).")
figure(FIGS["fig9_forest"], "F minus R across models. Only gpt-oss-20b excludes zero on both the design set (+8) and the sealed blind set (+6.6). The wide intervals mean 'no effect' and 'small effect' cannot be told apart for the other models.", 14.2)

# ---------------------------------------------------------------- 9. BLIND
H1("9. Confirmatory Evidence: the Sealed 200-Task Blind Test (Revision 13/16)")
P("The blind set was fixed before any model ran on it (seed 20261113; ids SHA-256 5527183c...c1e5d; tag blind200-sealed) and run once with the settings of Revisions 7 and 9, the stock Arms R and F, and Argus v0.2.0b1. Gemma was added in Revision 16 as an exploratory arm. Two tasks (psf__requests-1724 and -1921) failed the gold-patch control and are excluded, leaving 198. Task-clustered bootstrap, 5,000 resamples, seed 20261113. The analysis script was debugged on a partial snapshot (about 119 tasks) before the run finished; no setting of the run was changed because of it.")
rows = []
for m, nm in (("gpt-oss-20b", "gpt-oss-20b"), ("gpt-oss-120b", "gpt-oss-120b"), ("gemma-4-26b-a4b-it", "Gemma 26B (exploratory)")):
    r = BR[m][BRL]
    rr = BR[m]["excluding tasks with infra failures"]
    rows.append([nm, f"{BS[m + ':R']['solved']} ({r['R']})", f"{BS[m + ':F']['solved']} ({r['F']})", f"{sgn(r['diff'])} ({r['ci'][0]} to {r['ci'][1]})", f"{r['F_only']} / {r['R_only']}", f"{sgn(rr['diff'])} (n={rr['n']})"])
table(["Model", "R solved of 198 (%)", "F solved of 198 (%)", "F minus R (95% CI)", "F-only / R-only", "Without infra losses"], rows, [3.6, 2.8, 2.8, 3.4, 2.2, 2.6],
      caption="Blind-test results, solved within 3 attempts. Gemma had 19 F-arm and 8 R-arm api_error tasks (counted unsolved).", size=8, aligns=["l", "c", "c", "c", "c", "c"])
figure(FIGS["fig10_blind"], "Blind-test results: feedback beats re-draws for the 20B with the interval above zero, is smaller and borderline for the 120B, and is not visible for Gemma.", 11.6)
ids3 = None
h4 = V["blind_report"]["h4"]
hyp = [["H1 (confirmatory): 20B, F beats R, CI above 0", f"F minus R = {sgn(BR['gpt-oss-20b'][BRL]['diff'])}, CI {BR['gpt-oss-20b'][BRL]['ci'][0]} to {BR['gpt-oss-20b'][BRL]['ci'][1]}; design estimate was +8 (+2 to +14)", "**CONFIRMED**"],
       ["H2: 120B F minus R has upper 95% bound at most +5", f"{sgn(BR['gpt-oss-120b'][BRL]['diff'])}, CI {BR['gpt-oss-120b'][BRL]['ci'][0]} to {BR['gpt-oss-120b'][BRL]['ci'][1]}; design set suggested about 0", "**DOES NOT HOLD** (point estimate under 5, upper bound 9.1)"],
       ["H3: cascade (20B F up to 2, then 120B R up to 2) beats 120B R up to 3 at no more than 1.2x spend", "59.6 vs 54.5 solved (+5.1, CI 1.0 to 9.1) at 1.10x spend (n = 198; offline replay of stored attempts)", "**SUPPORTED** (replay, not a live cascade)"],
       ["H4: apply-layer gain in applied edits larger for 20B than 120B, positive for both", f"20B +{h4['gpt-oss-20b']['gain']} pp (plain {h4['gpt-oss-20b']['plain']}% to Argus {h4['gpt-oss-20b']['argus']}%); 120B +{h4['gpt-oss-120b']['gain']} pp ({h4['gpt-oss-120b']['plain']}% to {h4['gpt-oss-120b']['argus']}%); Gemma +{h4['gemma-4-26b-a4b-it']['gain']} pp", "**HOLDS** (applied-edit part; resolved-task ordering not computed)"],
       ["H5: Spearman of not-applied rate vs Argus gain at least 0.5 across 6 to 8 models on the blind set", "Not run. The design-set value (0.73 recomputed) is not a blind-set result", "NOT RUN"]]
table(["Pre-registered hypothesis (Revision 13)", "Result", "Verdict"], hyp, [6.2, 6.6, 4.0], caption="Hypothesis verdicts. H1 is the only confirmatory test; H2 to H5 were secondary with no multiplicity correction.", size=7.8, aligns=["l", "l", "l"])
P(f"**What it changes.** (1) The main finding stands on unseen tasks: test-failure feedback beats blind re-draws for the weakest gpt-oss model. (2) 'Feedback does not help the strong model' is not supported: the 120B effect is smaller but plausibly positive ({sgn(BR['gpt-oss-120b'][BRL]['diff'])}, CI {BR['gpt-oss-120b'][BRL]['ci'][0]} to {BR['gpt-oss-120b'][BRL]['ci'][1]}; repo-clustered CI {BR['gpt-oss-120b'][BRL]['ci_repo'][0]} to {BR['gpt-oss-120b'][BRL]['ci_repo'][1]}). (3) Gemma gets almost nothing from feedback, while the apply layer helps it most (+{h4['gemma-4-26b-a4b-it']['gain']} pp). (4) Cost per solve is lowest for the 20B with F (${BS['gpt-oss-20b:F']['usd']/BS['gpt-oss-20b:F']['solved']:.4f}) against ${BS['gpt-oss-120b:F']['usd']/BS['gpt-oss-120b:F']['solved']:.4f} and ${BS['gpt-oss-120b:R']['usd']/BS['gpt-oss-120b:R']['solved']:.4f} for the 120B (F and R). (5) The cascade result supports 'cheap model with feedback first, larger model only for what is left', with the caveat that the gain is mostly the 20B feedback loop's gain over 120B re-draws.")
P("**Limits.** Single sealed set and one seed per arm; per-repo splits are underpowered and repo-clustered intervals are degenerate for single-repo subsets (Django only: F minus R +4.6 in all three models, CI -3.1 to +12.3); task order was not randomised (this does not bias the paired comparison); the first-attempt solved counts are 75 (20B), 92 (120B) and 63 (Gemma) of 198.")

# ---------------------------------------------------------------- 10. REV 19
H1("10. Revisions 17 to 19: Showing the Previous Patch (Arm P)")
P("Revisions 5 to 16 tested only arm F, in which the previous answer is not shown. The deployed Argus repair prompt does show it (patch_builder.build_repair_prompt), so F does not measure the deployed design. Arm P matches it: the previous patch (at most 3,000 characters) and the result block go into one prompt with the instruction to rewrite corrected blocks against the original file.")
H3("Revisions 17 and 18: Gemini")
P(f"Revision 17 ran arm P once on both Gemini models and found P minus R of {LP17['gemini31|all']['diff']:+.1f} (CI {LP17['gemini31|all']['ci'][0]:+.1f} to {LP17['gemini31|all']['ci'][1]:+.1f}) for 3.1, above the pre-registered -2 to +6, and {LP17['gemini35|all']['diff']:+.1f} for 3.5. Because R had been replayed from an earlier session, Revision 18 re-ran all three arms in the same session with fresh calls, twice, plus a greedy check.")
rows = []
for m, nm in (("gemini31", "Gemini 3.1 Flash-Lite"), ("gemini35", "Gemini 3.5 Flash-Lite")):
    rm_ = V["rev18_means"]
    rows.append([nm, f"{sum(rm_[m + ':r'])/2:.1f} {rm_[m + ':r']}", f"{sum(rm_[m + ':f'])/2:.1f} {rm_[m + ':f']}", f"{sum(rm_[m + ':p'])/2:.1f} {rm_[m + ':p']}",
                 f"{R18[m + ':P-R']['diff']:+.1f} ({R18[m + ':P-R']['ci'][0]:+.1f}, {R18[m + ':P-R']['ci'][1]:+.1f})", f"{R18[m + ':P-F']['diff']:+.1f} ({R18[m + ':P-F']['ci'][0]:+.1f}, {R18[m + ':P-F']['ci'][1]:+.1f})", f"{R18[m + ':F-R']['diff']:+.1f}"])
table(["Model", "R mean [rep1, rep2]", "F mean [rep1, rep2]", "P mean [rep1, rep2]", "P minus R (CI)", "P minus F (CI)", "F minus R"], rows, [3.0, 2.4, 2.4, 2.4, 2.8, 2.8, 1.4],
      caption="Revision 18: two fresh replicates of each arm on the 100 design tasks (solved of 100 within 3 attempts).", size=7.6, aligns=["l", "c", "c", "c", "c", "c", "c"])
P(f"Fresh replicates changed the Gemini 3.1 picture (P minus R +9.0 in one session, {R18['gemini31:P-R']['diff']:+.1f} over two replicates) and moved Gemini 3.5 the other way ({LP17['gemini35|all']['diff']:+.1f} to {R18['gemini35:P-R']['diff']:+.1f}, CI {R18['gemini35:P-R']['ci'][0]} to {R18['gemini35:P-R']['ci'][1]}). For Gemini 3.1 the Revision 17 arm values were R {LP17['gemini31|all']['R']} (replayed from an earlier session) and P {LP17['gemini31|all']['F']}; fresh replicates gave R {sum(V['rev18_means']['gemini31:r'])/2:.1f} and P {sum(V['rev18_means']['gemini31:p'])/2:.1f}, so most of the shift is the replayed R being low. Within-arm replicate noise is small (arms flip on 3 to 7 tasks), but which session was unusual was not isolated. Greedy (temperature 0) P minus F: Gemini 3.1 {R18['gemini31:Pg-Fg']['diff']:+.1f} (CI {R18['gemini31:Pg-Fg']['ci'][0]} to {R18['gemini31:Pg-Fg']['ci'][1]}), Gemini 3.5 {R18['gemini35:Pg-Fg']['diff']:+.1f}. Three of eight Revision 18 predictions were missed.")
figure(FIGS["fig14_regression"], "The same P minus R comparison measured in one session (Revision 17) and over two fresh replicates (Revision 18): single-session estimates are not stable at 100 tasks.", 10.0)
H3("Revision 19: the deployed prompt on gpt-oss and Gemma")
P("Revision 19 ran arm P in exactly the deployed prompt format (one user message; previous patch up to 3,000 characters in a 'Previous Attempt (FAILED)' block, then the result block, then the instruction to include all necessary changes) on gpt-oss-20b and 120B (same 100 design tasks, same seeds for attempt 1, fresh seeds 9000 + turn for attempts 2 and 3, medium effort, T=1.0, cap 8,000), and, in the same image pulls, on Gemma 26B (attempt 1 = stored draw 0, attempts 2 and 3 new calls). Comparators R and F are the Revision 7 and 9 arms (not re-run); the Gemma comparator F is the Revision 15 arm. Infrastructure losses count as unsolved.")
rows = []
for k, nm, n in (("120b", "gpt-oss-120b", 100), ("20b", "gpt-oss-20b", 100)):
    ptag = {"120b": "120B P19", "20b": "20B P19"}[k]
    ftag = {"120b": "120B F", "20b": "20B F"}[k]
    rtag = {"120b": "120B R", "20b": "20B R"}[k]
    a, b2, c = PR(f"{k}:P-F"), PR(f"{k}:P-R"), PR(f"{k}:F-R")
    rows.append([nm, n, LP_[ptag], LP_[ftag], LP_[rtag], f"{a['diff']:+.1f} ({a['ci'][0]:+.1f}, {a['ci'][1]:+.1f}); without losses {a['without_losses']['diff']:+.1f}", f"{b2['diff']:+.1f} ({b2['ci'][0]:+.1f}, {b2['ci'][1]:+.1f})", f"[{a['pred'][0]}, {a['pred'][1]}] / [{b2['pred'][0]}, {b2['pred'][1]}]: held"])
g_ = PR("gemma:P-F")
rows.append(["Gemma 26B", 99, LP_["Gemma P19"], LP_["Gemma F"], f"{round(LF['gemma26|all']['R']*0.99)} (replay)", f"{g_['diff']:+.1f} ({g_['ci'][0]:+.1f}, {g_['ci'][1]:+.1f}); without losses {g_['without_losses']['diff']:+.1f}", f"{V['gemma_P_minus_Rreplay']:+.1f} (point estimate; unmatched draws)", f"[{g_['pred'][0]}, {g_['pred'][1]}] on P minus F: **MISSED**"])
table(["Model", "Tasks", "P solved", "F solved", "R solved", "P minus F (95% CI)", "P minus R (95% CI)", "Pre-registered range: P-F / P-R"], rows, [2.3, 1.1, 1.2, 1.2, 1.5, 3.6, 3.0, 3.4],
      caption="Revision 19 results (solved within 3 attempts). Infrastructure losses: 20B 1 P grade_error and 1 F api_error; Gemma 4 P and 7 F api_error; 120B none. Gemma's R replay is the stored independent draws scored with the same stop rule.", size=7.2, aligns=["l", "c", "c", "c", "c", "c", "c", "l"])
figure(FIGS["fig11_rev19"], "Revision 19. Left: solved of 100 by arm. Right: P minus F and P minus R with 95% CIs; the grey band is the pre-registered range. Only Gemma's P minus F lies outside its range (red).", 15.4)
P(f"**Reading.** On both gpt-oss models P is statistically indistinguishable from F ({PR('120b:P-F')['diff']:+.1f} and {PR('20b:P-F')['diff']:+.1f}) and from R for the 120B; for the 20B P recovers about the same gain over R as F does ({PR('20b:P-R')['diff']:+.1f} against F minus R {PR('20b:F-R')['diff']:+.1f}) but the P minus R interval touches zero ({PR('20b:P-R')['ci'][0]:+.1f} to {PR('20b:P-R')['ci'][1]:+.1f}). Gemma is the one model where P looks better than F ({g_['diff']:+.1f}, CI {g_['ci'][0]} to {g_['ci'][1]}; 8 tasks only P solves against 2 only F solves). That comparison is weak: the Gemma F arm is from an earlier run with its own draws, so P minus F mixes the prompt with draw noise, and one task (django-13406) has no Gemma record because the stored draw 0 does not exist (the Google endpoint closed the connection without a response on every draw-0 try in the sweep) and it is absent from both arms. Treat the Gemma result as a lead.")
H3("Why does feedback help the small model more? Three offline checks")
P("After Revision 19 three exploratory, post-hoc checks were run on the stored attempts (scripts/analyze_why19.py; nothing re-run, not pre-registered). Each tests one explanation of why a retry with the failure shown does not beat a blind re-draw for the 120B.")
why = V["why_parsed"]
txt = open(os.path.join(OUT, "verify", "analyze_why19.out"), encoding="utf-8").read()
ident = {}
for blk in re.split(r"######## ", txt)[1:]:
    mname = blk.split()[0]
    for g2 in re.finditer(r"   ([PFR]): (\d+) tasks with attempt 2; identical patch to attempt 1: (\d+) \((\d+)%\)", blk):
        ident[(mname, g2.group(1))] = (int(g2.group(2)), int(g2.group(3)), int(g2.group(4)))
trunc = {}
for blk in re.split(r"######## ", txt)[1:]:
    mname = blk.split()[0]
    for g2 in re.finditer(r"   (no truncated runs|only truncated-run tasks)\s+n=\s*(\d+)\s+F-R ([+\-][\d.]+) \(([\-\d.]+), ([\-\d.]+)\)\s+P-R ([+\-][\d.]+) \(([\-\d.]+), ([\-\d.]+)\)", blk):
        trunc[(mname, g2.group(1))] = (int(g2.group(2)), g2.group(3), g2.group(4), g2.group(5), g2.group(6), g2.group(7), g2.group(8))
    sh = re.search(r"share of R attempts that hit the output limit: ([\d.]+)%\s+F: ([\d.]+)%", blk)
    if sh:
        trunc[(mname, "share")] = (sh.group(1), sh.group(2))
rows = [["1. Anchoring: does the model repeat its previous patch? (identical attempt-2 patch, tasks with attempt 2)", f"120B: P {ident[('120b','P')][1]} of {ident[('120b','P')][0]} ({ident[('120b','P')][2]}%), F {ident[('120b','F')][1]}, R {ident[('120b','R')][1]}", f"20B: P {ident[('20b','P')][1]} of {ident[('20b','P')][0]}, F {ident[('20b','F')][1]}, R {ident[('20b','R')][1]}", "Not supported: P rarely repeats itself"],
        ["2. Is the gain in tasks where the patch applied but tests fail? (eventually solved)", "120B: P 11, F 12, R 13 of 37", "20B: P 12, F 15, R 8 of 37", "Partly: the 20B gain sits here; edit-not-applied failures are recovered rarely under every arm"],
        ["3. Is the 20B gain just breaking repetition loops? (F minus R without tasks with a truncated run)", f"120B: no truncated runs at all ({trunc[('120b','share')][0]}%)", f"20B: n={trunc[('20b','no truncated runs')][0]}, F-R {trunc[('20b','no truncated runs')][1]} (CI {trunc[('20b','no truncated runs')][2]} to {trunc[('20b','no truncated runs')][3]}), P-R {trunc[('20b','no truncated runs')][4]}", "Not supported: gain survives removing the 21 truncated-run tasks"]]
table(["Check", "gpt-oss-120b", "gpt-oss-20b", "Verdict"], rows, [5.4, 3.6, 4.0, 3.8], caption="Offline checks on why feedback helps the 20B (scripts/analyze_why19.py; exploratory).", size=7.6, aligns=["l", "l", "l", "l"])
figure(FIGS["fig12_why"], "Recovery by why attempt 1 failed (tasks eventually solved, % of tasks failing attempt 1). The recovery that exists is in tasks where the patch applied but tests still failed; the 20B gain is concentrated there.", 14.0)
P(f"After a failed first attempt only about a quarter to a third of tasks are fixed under any arm (120B: P 14, F 15, R 17 of 54; 20B: P 15, F 17, R 9 of 59). About {trunc[('20b','share')][0]}% of 20B re-draw attempts and {trunc[('20b','share')][1]}% of F attempts hit the output limit. The surviving explanation (a hypothesis, not tested) is that most remaining failures are semantic: the patch applies, the failing test names a symptom but not why the model's theory of the bug is wrong, and a fresh draw is already a different guess.")

# ---------------------------------------------------------------- 11. VERIFIER QUALITY
H1("11. Verifier Quality: What 'Resolved' and 'Accepted' Do and Do Not Guarantee")
fa = V["false_accept"]
rows = [[m, fa[k]["applied"], fa[k]["target_test_pass"], fa[k]["false_accepts"], f"{100*fa[k]['false_accept_rate']:.1f}%", f"{100*fa[k]['resolved_rate_given_applied']:.1f}%"]
        for k, m in (("gpt-oss-20b", "gpt-oss-20b"), ("gpt-oss-120b", "gpt-oss-120b"), ("gemini-3.1-flash-lite", "Gemini 3.1 Flash-Lite"), ("gemini-3.5-flash-lite", "Gemini 3.5 Flash-Lite"))]
table(["Model (Argus arm, 300 draws)", "Applied", "Target test passes", "...but other tests break", "False-accept rate", "Resolved given applied"], rows, [4.0, 1.6, 2.4, 3.0, 2.4, 3.0],
      caption="A gate that stops at the first passing target test would ship these (Revision 7 policy analysis).", size=8, aligns=["l", "c", "c", "c", "c", "c"])
P("A test-gated loop has a false-accept rate by construction: 6.6% to 12.0% of target-passing patches break other tests, and in the Revision 7, 9 and 19 loops 4 to 9 tasks per arm end accepted-but-regressed. Beyond regressions, an audit of all 342 resolved Argus-arm rows (265 unique task-patch pairs from 20B, 120B and Gemma) judged 194 (73%) correct, 20 partial (8%), 49 wrong or fragile (18%) and 2 junk-but-equivalent (1%). Of the 216 patches read by five parallel reviewer agents, 154 were judged correct, 15 partial, 46 wrong or fragile and 1 junk-but-equivalent (only 15 of the 46 wrong calls were high confidence). All verdicts are reader judgements of diffs, not executions, except the three sphinx-11445 patches, whose regression was confirmed by execution.")
figure(FIGS["fig15_e3"], "Reader-judged quality of patches the harness marks resolved (E3 review). About one resolved patch in five to six is not a clean fix.", 11.4)
P("**Consequence.** 'Resolved' is a necessary condition, not a guarantee, for these small models. Any headline 'rate' should state its verifier, and a deployed loop that stops at the first passing visible test needs a regression gate (run the touched test files) rather than the target test alone.")

# ---------------------------------------------------------------- 12. PREDICTIONS
H1("12. Pre-Registered Predictions Against Outcomes")
P(f"From Revision 14 on, every revision wrote numeric predictions before any call. Figure 15 plots the {V['pred_counts']['total']} predictions that concern a difference in solved-per-100; the three Revision 14 predictions about Qwen3.8 (plain not-applied 8% to 20%: held at 18.3%; Argus gain at most +3: held at +0.3; plain at least 25 per 100: held at 26.0) are stated here. **{V['pred_counts']['held']} of the {V['pred_counts']['total']} difference predictions held and {V['pred_counts']['total'] - V['pred_counts']['held']} were missed** (22 numeric predictions in all, 16 held).")
miss = [["Rev 15", "Gemma F minus R in +2 to +10", f"{LF['gemma26|all']['diff']:+.1f}", "Feedback helped no more than re-drawing on Gemma"],
        ["Rev 17", "Gemini 3.1 P minus R in -2 to +6", f"{LP17['gemini31|all']['diff']:+.1f}", "Above range; not reproduced on fresh replicates (Rev 18: +2.0)"],
        ["Rev 18", "Gemini 3.1 P minus R in +3 to +10", f"{R18['gemini31:P-R']['diff']:+.1f}", "Below range: the Rev 17 estimate regressed"],
        ["Rev 18", "Gemini 3.1 P minus F in +2 to +10", f"{R18['gemini31:P-F']['diff']:+.1f}", "Below range"],
        ["Rev 18", "Gemini 3.5 P minus R in -3 to +5", f"{R18['gemini35:P-R']['diff']:+.1f}", "Above range (CI +1.0 to +12.5)"],
        ["Rev 19", "Gemma P minus F in -5 to +5", f"{PR('gemma:P-F')['diff']:+.1f}", "Above range (CI 0.0 to +12.1); weak comparison"]]
table(["Revision", "Prediction", "Outcome", "Note"], miss, [1.7, 5.8, 1.8, 7.5], caption="The six missed predictions. Pre-registered predictions that held are plotted in Figure 15; the other revisions' hypotheses are in Tables 4 and 16.", size=7.8, aligns=["l", "l", "c", "l"])
figure(FIGS["fig13_predictions"], "Pre-registered ranges (grey) against outcomes. The greedy Gemini 3.1 prediction was open-ended ('at least +2') and is drawn to +12. Misses are red crosses.", 13.8)
P("The misses are informative. Two overestimated feedback on a new family (Gemma F, Gemini 3.1 P in Revision 18); three underestimated a P effect (Gemini 3.1 in Revision 17, Gemini 3.5 and Gemma). The pattern that P helps Gemini 3.5 and Gemma but not gpt-oss is exploratory (several comparisons, intervals at or near zero) and has not been confirmed on the blind set.")

# ---------------------------------------------------------------- 13. FINDINGS
H1("13. Results and Discussion: Seven Empirical Findings")
B(f"**Finding 1 (the small model's deficit is mostly pipeline loss).** Given an applied patch, gpt-oss-20b and 120B pass at {100*31/V['t0_plain_applied']['gpt-oss-20b']:.1f}% and {100*44/V['t0_plain_applied']['gpt-oss-120b']:.1f}%. The 20B loses 21 of 99 tasks to repetition loops and many to non-matching edits; genuine wrong fixes (symptom-patching, partial fixes) are real but smaller than the 31% vs 44% headline suggests. This is descriptive: the tasks where the weaker model lands a patch are probably the easier ones.")
B(f"**Finding 2 (the apply layer is a conditional robustness layer).** Gain {sgn(T1['resolve']['argus_minus_plain:gpt-oss-20b']['mean_pp'])} / {sgn(T1['resolve']['argus_minus_plain:gpt-oss-120b']['mean_pp'])} points for 20B / 120B at T=1 and +{h4['gpt-oss-20b']['gain']} / +{h4['gpt-oss-120b']['gain']} points in applied edits on the blind set; it follows how often a model's edits fail to match (Spearman {V['spearman']['tie_corrected']:.2f}, n = 8) and shrinks with model strength. Most of it is indentation tolerance; true fuzzy matching contributed about one solve and one confirmed false-positive apply.")
B(f"**Finding 3 (test feedback helps the weakest gpt-oss model, and is uncertain or absent elsewhere).** 20B: F minus R +8 (design) and {sgn(BR['gpt-oss-20b'][BRL]['diff'])} (blind, H1 confirmed); 120B: -2 and {sgn(BR['gpt-oss-120b'][BRL]['diff'])} (CI {BR['gpt-oss-120b'][BRL]['ci'][0]} to {BR['gpt-oss-120b'][BRL]['ci'][1]}); Gemma, Qwen3.8 and Gemini within a few points of zero.")
B(f"**Finding 4 (the previous patch adds nothing on gpt-oss).** P minus F is {PR('120b:P-F')['diff']:+.1f} (120B) and {PR('20b:P-F')['diff']:+.1f} (20B) in the deployed format, matching the earlier multi-turn format (0 and -3). Gemini 3.5 and Gemma lean positive; unconfirmed.")
B(f"**Finding 5 (cost: parity at best, cheapest with the small model plus feedback).** Cost per solve is ${BS['gpt-oss-20b:F']['usd']/BS['gpt-oss-20b:F']['solved']:.4f} for 20B + F against ${BS['gpt-oss-120b:R']['usd']/BS['gpt-oss-120b:R']['solved']:.4f} for 120B + R on the blind set; the replayed cascade '20B with feedback, then 120B' solves 59.6 against 54.5 at 1.10x spend. With a perfect verifier, retrying the 120B on the design set beats escalating from the 20B.")
B("**Finding 6 (verification is the weak link).** A first-passing-test stop rule ships regressed patches in 4 to 9 tasks per arm of 100 (Revisions 7, 9 and 19); 6.6% to 12.0% of target-passing patches break other tests; about 18% of resolved patches are wrong or fragile on a reader audit.")
B(f"**Finding 7 (single-run differences at 100 tasks are unstable).** {V['pred_counts']['total'] - V['pred_counts']['held']} of {V['pred_counts']['total']} difference predictions missed; a +9.0 became +2.0 on fresh replicates; the 120B resolves 41 to 52 tasks depending on the draw. Effects under about 5 points should not be called real at this size.")
H2("13.1 What is not claimed")
for t in ["No leaderboard result. The file is given; Report 17's SWE-bench figures are not comparable and are not repeated.",
          "No claim that Argus 'routes adaptively'. Routing in the shipped default is a keyword regex over one model (audit); the allocation results here are offline replays and fixed ladders.",
          "No claim that the findings transfer to agentic scaffolds, multi-file tasks, or tasks where the model must localize.",
          "No claim about algorithmic tasks, or that routing principles generalize from them to repository tasks: that half of the original research question is untested.",
          "No claim that feedback 'does nothing' for the 120B or Gemini: intervals at 100 to 198 tasks do not exclude effects of a few points.",
          "No causal split of the 20B's feedback gain into test information versus the 'keep reasoning short' sentence in F's cut-off prompt; that control was not run.",
          "No claim that 'resolved' means the patch is correct (Section 11)."]:
    B(t)
H2("13.2 Limitations")
for t in ["Design-set results are discovery numbers: all design decisions were made on the same 99 or 100 tasks. Only the blind set (198 tasks, one seed per arm) supports confirmatory statements, and only for H1 to H4.",
          "Draws are unseeded for Gemma and Gemini; stored outputs, not re-runs, are the ground truth. Comparators in several revisions use draws from different sessions, so F-versus-R and P-versus-R differences mix the effect with draw variation (Revision 18 measured this for Gemini only).",
          "Infrastructure losses (Groq's token-per-minute limit, Google connection closes, image-pull failures) are counted unsolved and reported with and without them; they hit F and P arms harder than R.",
          "Prices are Groq list prices of undated docs and a one-off Gemini price book; Docker compute is excluded.",
          "The apply-layer ladder (Table 9) and the Report 3 stage tally were derived or taken from earlier reports and not re-graded.",
          "Contamination of public SWE-bench Verified tasks cannot be excluded, especially for Gemini and the Qwen3.8 model released after most of the benchmark.",
          "Qwen runs use thinking-off and 4,000 tokens; gpt-oss ran at medium reasoning. Qwen solve rates are not a like-for-like capability ranking, and series and size are confounded (Qwen3.5 vs Qwen3.8).",
          "Gemma 31B has 294 of 300 draws generated (data/gemma_sweep/raw.jsonl) but they were not graded or analysed; H5 was not run; one Gemma task (django-13406) has no draw 0."]:
    B(t)

# ---------------------------------------------------------------- 14. TOOL
H1("14. From Research to Software Engineering Tool: Implications for the argus Package")
P("These are recommendations that follow from the evidence, not changes that have been implemented or tested in this report.")
for t in ["**Make failing-test text (F) the default retry format and do not carry the previous patch (P)** for gpt-oss-class models: P adds tokens and no measurable benefit.",
          "**Keep Tiers 1 and 2 as the default and report which tier fired** in telemetry; make Tier 3 stricter (refuse one- or two-line SEARCH blocks, require an enclosing-function match, add an undefined-name check to the AST gate); the one confirmed Tier-3 false positive was a one-line SEARCH landing in a different method.",
          "**Detect truncated or looping output** (finish at the length limit) and retry at temperature 1.0 or with a shorter instruction; 10% to 13% of 20B attempts hit the cap, none for the 120B.",
          "**Add a regression gate**: run the touched test files before accepting a patch; the target test alone accepted regressed patches in 4 to 9 tasks per arm of 100.",
          "**Record per-attempt cost, state, patch hash and grade in the trajectory.** This is what made every offline analysis here possible, and it is what a per-task budget cap needs.",
          "**Describe the product accurately:** a recovery runtime with a test-gated retry loop, not 'adaptive routing'."]:
    B(t)
P("**Open experiments.** The agent-scaffold pilot (a mini-SWE-agent-style baseline on the same tasks, not file-given) and the algorithmic-task arm under the same arms, held-out tests and grading are planned and not yet run; they are needed before any claim about harness effects or generalization across task families.")

# ---------------------------------------------------------------- 15. VERIFICATION
H1("15. Data Reconciliation and Verification")
P("Every headline number in this report was either recomputed from raw stored data by scripts/report18_data.py (apply outputs joined with Docker grades, trajectories, trajectory-level counts) or taken from a committed analysis JSON that the corresponding script reproduces when re-run (scripts listed in Table 23). No model was called and no Docker container was run to produce this report. Table 22 lists each recomputed quantity; Table 23 lists scripts re-run against committed outputs; Table 24 lists discrepancies found. To reproduce: python -X utf8 scripts/report18_data.py (recompute and verify), then python -X utf8 scripts/make_report18.py (figures, Report18.docx, Report18.pdf); raw data and per-revision analysis scripts are in the Argus-pilot50 repository.")
rows = [[c["what"], c["quoted"], c["recomputed"], c["source"], c["status"]] for c in CHK]
table(["Quantity", "Quoted", "Recomputed", "Raw source", "Status"], rows, [6.3, 1.5, 1.8, 5.6, 1.8], caption="Ground-truth reconciliation: each quantity as quoted in project reports, recomputed from raw data by scripts/report18_data.py (verified_numbers.json).", size=6.8, aligns=["l", "c", "c", "l", "l"])
rr = [["scripts/analyze.py and deep_dive.py", "results/analysis/summary.json, deep.json, records.jsonl", "Unchanged on re-run (31 / 38 / 44 / 46; labels; ladder)"],
      ["scripts/analyze_t1.py", "t1_summary.json", "Unchanged"],
      ["scripts/analyze_sweep.py", "sweep_summary.json", "Unchanged"],
      ["scripts/analyze_loop.py (Rev 5)", "loop_summary.json", "Unchanged"],
      ["scripts/analyze_loop2.py, analyze_loop3.py (+ '_20b')", "loop2/3 summaries (120B and 20B)", "Unchanged except set-ordering of the infra-task list in loop3 summaries (no numeric change)"],
      ["scripts/analyze_failures.py, analyze_policies.py", "failures_summary.json, policies_summary.json", "Unchanged"],
      ["scripts/analyze_blind.py", "blind_report_data.json, BLIND_REPORT.md", "Unchanged; stdout matches every blind number quoted"],
      ["scripts/analyze_rev18.py, analyze_rev19.py, analyze_why19.py", "rev18_results.json, rev19_results.json", "Unchanged"],
      ["scripts/analyze_loop_f.py (F and ARM=P)", "stdout, saved in reports/Report18/verify/", "Revision 15 to 17 numbers (Table 14 and Section 8.1)"],
      ["scripts/loc_recall.py", "data/loc/recall_summary.json", "Unchanged (BM25 27, Argus 21 at recall@1)"],
      ["scripts/analyze_new_runs.py", "new_runs_summary.json (untracked file)", "Re-run stdout matches stored values (Gemma 25.5 / 31.5; Qwen3.5 rows)"],
      ["scripts/analyze_qwen_probe.py", "qwen_probe_summary.json", "Not re-run (hung); committed JSON used only for the Rev 10 probe statements"]]
table(["Script re-run on 15 Nov 2026", "Output compared", "Result"], rr, [5.6, 5.4, 6.0], caption="Re-run scripts and their agreement with committed outputs (stdout in reports/Report18/verify/).", size=7.4, aligns=["l", "l", "l"])
disc = [["CLAIM_STATUS.md row 'Spearman 0.71'", "0.71", f"{V['spearman']['tie_corrected']:.2f} (both the tie-corrected and the simple formula)", "Minor; recomputed from the eight value pairs in the protocol"],
        ["CLAIM_STATUS.md rows 5, 8, 11 (dated 14 Nov, draft)", "Feedback 'NOT SUPPORTED'; cascade 'WEAKENED'; blind 'UNTESTED'", "Blind run finished: H1 confirmed, H3 supported", "Stale: the table predates the blind results and Revisions 17 to 19"],
        ["REPORT10_ARM_P_ARGUS_FORMAT.md: 'The 120B pass logged one grade_error (sympy__sympy-18698) ... stored as continue'", "120B grade_error", f"The 120B P arm has no grade_error; the logged line belongs to the 20B pass (20B stops: grade_error 1)", "Wrong attribution in that report"],
        ["REPORT10_ARM_P_ARGUS_FORMAT.md Gemma table: R = 'none'", "no Gemma R", f"An R replay from the stored sweep draws exists ({round(LF['gemma26|all']['R']*0.99)} of 99, unmatched); P minus R is {V['gemma_P_minus_Rreplay']:+.1f}", "Incomplete in that report"],
        ["Two files named REPORT10_*", "-", "REPORT10_QWEN_SIZE_LADDER.md and REPORT10_ARM_P_ARGUS_FORMAT.md", "Numbering collision; this report calls them 'Report 10 Qwen' and Revision 19"],
        ["Report 3: '46% of the 20B's first-pass spend' on loops", "46%", "46% counts the 21 no-output runs; counting the 22nd length-capped run gives 48%", "Definition, not an error"]]
table(["Where", "Stated", "Found", "Note"], disc, [4.8, 3.2, 5.8, 3.4], caption="Discrepancies found while verifying (none changes a conclusion).", size=7.4, aligns=["l", "l", "l", "l"])


# footer page numbers
for s_ in doc.sections:
    fp = s_.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = fp.add_run("Report 18 | page ")
    r.font.size = Pt(8)
    r.font.color.rgb = GREYC
    for kind, txt_ in (("begin", None), ("instr", " PAGE "), ("end", None)):
        run = fp.add_run()
        run.font.size = Pt(8)
        if kind == "instr":
            it = OxmlElement("w:instrText")
            it.set(qn("xml:space"), "preserve")
            it.text = txt_
            run._r.append(it)
        else:
            fc = OxmlElement("w:fldChar")
            fc.set(qn("w:fldCharType"), kind)
            run._r.append(fc)

os.makedirs(OUT, exist_ok=True)
docx_path = os.path.join(OUT, "Report18.docx")
doc.save(docx_path)
print("saved", docx_path, "tables", TN[0], "figures", FN[0])

pdf_path = os.path.join(OUT, "Report18.pdf")
ps = ("$w = New-Object -ComObject Word.Application; $w.Visible = $false; "
      f"$d = $w.Documents.Open('{docx_path}'); $d.Fields.Update() | Out-Null; $d.ExportAsFixedFormat('{pdf_path}', 17); $d.Close($false); $w.Quit()")
subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
print("pdf", pdf_path)
