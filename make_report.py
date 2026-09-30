"""
Builds Result/Progress_Report.pdf from the files in Result/ (tables, fault study,
figures and PowerFactory plots). Run with Python 3 (reportlab, matplotlib) after
Show_Progress.py and make_figures.py.
"""

import csv
import os
import subprocess
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

PROJ = r"D:\Protection and co-ordination"
RES = os.path.join(PROJ, "Result")
FIG = os.path.join(RES, "Figures")
OUT = os.path.join(RES, "Progress_Report.pdf")

INK, INK2, RULE, HEAD, BAND = (colors.HexColor(c) for c in
                               ("#0b0b0b", "#52514e", "#d9d8d3", "#eef3fb", "#f6f6f4"))
GOOD, BAD, ACCENT = colors.HexColor("#0c7a0c"), colors.HexColor("#b83232"), colors.HexColor("#2a78d6")

ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=15,
                    textColor=INK, spaceBefore=4, spaceAfter=6)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=11.5,
                    textColor=INK, spaceBefore=8, spaceAfter=4)
BODY = ParagraphStyle("B", parent=ss["BodyText"], fontName="Helvetica", fontSize=9.5,
                      leading=13, textColor=INK, spaceAfter=4, alignment=TA_LEFT)
SMALL = ParagraphStyle("S", parent=BODY, fontSize=8, leading=10.5, textColor=INK2)
CELL = ParagraphStyle("C", parent=BODY, fontSize=8, leading=10, spaceAfter=0)
BUL = ParagraphStyle("BL", parent=BODY, leftIndent=12, bulletIndent=2)


def p(t, st=BODY):
    return Paragraph(t, st)


def bullets(items):
    return [Paragraph(t, BUL, bulletText="\u2022") for t in items]


def table(rows, widths, header_rows=1, align_right_from=1, zebra=True, extra=None):
    data = [[c if not isinstance(c, str) else Paragraph(c, CELL) for c in r] for r in rows]
    t = Table(data, colWidths=widths, repeatRows=header_rows)
    st = [("FONT", (0, 0), (-1, -1), "Helvetica", 8),
          ("BACKGROUND", (0, 0), (-1, header_rows - 1), HEAD),
          ("LINEBELOW", (0, header_rows - 1), (-1, header_rows - 1), 0.8, INK2),
          ("LINEBELOW", (0, -1), (-1, -1), 0.8, INK2),
          ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]
    if zebra:
        for i in range(header_rows, len(rows)):
            if (i - header_rows) % 2:
                st.append(("BACKGROUND", (0, i), (-1, i), BAND))
    st += extra or []
    t.setStyle(TableStyle(st))
    return t


def rcsv(name):
    with open(os.path.join(RES, name)) as fh:
        return list(csv.DictReader(fh))


def fig(name, w):
    path = os.path.join(FIG, name)
    from reportlab.lib.utils import ImageReader
    iw, ih = ImageReader(path).getSize()
    return Image(path, width=w, height=w * ih / iw)


def match(model, paper):
    return max(0.0, 100.0 - abs(model - paper) / paper * 100.0) if paper else None


def colour_pct(v):
    if v is None:
        return "---"
    c = "#0c7a0c" if v >= 90 else ("#9a6700" if v >= 75 else "#b83232")
    return '<font color="%s">%.0f %%</font>' % (c, v)


# ---- data ----------------------------------------------------------------------------------
PAPER_T2 = [("RG60", "632", 587.1, 1.24, 5.41), ("632", "633", 81.1, 0.72, 6.73),
            ("632", "645", 143.3, 0.93, 4.25), ("632", "671", 478.2, 1.08, 4.52),
            ("XFM1-HV", "side", 81.1, 0.73, 6.48), ("XFM1-LV", "side", 704.7, 0.59, 18.76),
            ("645", "646", 64.9, 0.84, 3.64), ("671", "692", 229.3, 0.78, 3.69),
            ("671", "684", 70.9, 0.69, 3.47), ("671", "680", 0.0, 0.59, 6.25),
            ("692", "675", 205.9, 0.71, 7.83), ("684", "611", 70.8, 0.63, 1.93),
            ("684", "652", 63.1, 0.66, 2.67)]
t2 = rcsv("Table_II.csv")
t3 = rcsv("Table_III.csv")
t4 = rcsv("Table_IV_model.csv")
ops = rcsv("Paper_comparison_operating_points.csv")

# make_figures.py summary (coordination agreement, DSDR settings, series fuses)
mf = subprocess.run([sys.executable, os.path.join(PROJ, "make_figures.py")], capture_output=True,
                    text=True, encoding="utf-8", env=dict(os.environ, PYTHONIOENCODING="utf-8")).stdout
agree = {}
for line in mf.splitlines():
    if "agree" in line and "differ" in line:
        k = "14" if "14" in line else "17"
        a = line.split(":")[1].split(",")
        agree[k] = (int(a[0].split()[0]), int(a[1].split()[0]))
dsdr = [l for l in mf.splitlines() if l.startswith("DSDR reverse")][0]
ip_rv = [l for l in mf.splitlines() if l.startswith("Load flow with DG")][0]

# ---- document -----------------------------------------------------------------------------
doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                        topMargin=16 * mm, bottomMargin=16 * mm,
                        title="Progress report - IEEE 13-node replication",
                        author="Protection and co-ordination project")
W = A4[0] - 36 * mm


def footer(c, d):
    c.saveState()
    c.setFont("Helvetica", 7.5)
    c.setFillColor(INK2)
    c.drawString(18 * mm, 10 * mm, "Replication of Yousaf et al. (2022), IEEE 13-node feeder "
                 "- progress report, 30 September 2026")
    c.drawRightString(A4[0] - 18 * mm, 10 * mm, "Page %d" % d.page)
    c.restoreState()


S = []
# ---- page 1 -----------------------------------------------------------------------------
S.append(p("Progress report", ParagraphStyle("k", parent=SMALL, fontSize=9, textColor=ACCENT)))
S.append(p("Replication of an adaptive recloser&#8211;fuse protection scheme on the IEEE "
           "13-node feeder in DIgSILENT PowerFactory", ParagraphStyle(
               "T", parent=H1, fontSize=17, leading=21)))
S.append(p("Reference paper: M. Yousaf, A. Jalilian, K. M. Muttaqi, D. Sutanto, <i>An Adaptive "
           "Overcurrent Protection Scheme for Dual-Setting Directional Recloser and Fuse "
           "Coordination in Unbalanced Distribution Networks With Distributed Generation</i>, "
           "IEEE Trans. Ind. Appl., vol. 58, no. 2, pp. 1831&#8211;1842, 2022.", SMALL))
S.append(p("Tool: DIgSILENT PowerFactory 2021 SP2 (Python scripting). Date: 30 September 2026. "
           "All results below come from the PowerFactory model: load flow and short-circuit "
           "(Complete method) results, and the operating times of the protective devices "
           "computed from those currents.", SMALL))
S.append(Spacer(1, 6))
S.append(p("Status at a glance", H2))
status = [["Paper item", "Status", "Result file / script"],
          ["Table I &#8211; DG short-circuit data", "In the model; not yet re-checked", "IEEE 13 Node Feeder.pfd"],
          ["Table II &#8211; rated / min / max branch currents", '<font color="#0c7a0c"><b>Done</b></font>', "Result\\Table_II.csv (IEEE13_Tables.py)"],
          ["Table III &#8211; fuse coefficients b<sub>i</sub>", '<font color="#0c7a0c"><b>Done</b></font>', "Result\\Table_III.csv (IEEE13_Tables.py)"],
          ["Table IV &#8211; R1, R2, fuse operating times", '<font color="#0c7a0c"><b>Done</b></font>', "Result\\Table_IV_model.csv (Table_IV.py)"],
          ["Fig. 6 &#8211; feeder with protective devices", "Reclosers and 15 fuses placed; diagram not redrawn", "Add_Fuses.py, Configure_Reclosers.py"],
          ["Fig. 7 &#8211; CTI vs DG penetration", '<font color="#0c7a0c"><b>Done</b></font>', "Figures\\Fig07"],
          ["Figs. 8, 9, 11&#8211;13, 15, 16 &#8211; operation sequences", '<font color="#0c7a0c"><b>Done</b></font>', "Figures\\Fig08 ... Fig16"],
          ["Fig. 10 &#8211; time-domain fault current", '<font color="#b83232"><b>Not started</b></font>', "needs RMS/EMT simulation"],
          ["Figs. 14, 17 &#8211; coordination maps", '<font color="#0c7a0c"><b>Done</b></font>', "Figures\\Fig14, Fig17 (Fig14_Coordination.py)"],
          ["Figs. 18&#8211;21, Table V &#8211; IEEE 34-node", "Out of scope so far", ""]]
S.append(table(status, [0.40 * W, 0.28 * W, 0.32 * W], zebra=True))
S.append(Spacer(1, 6))
S.append(p("Key findings", H2))
S += bullets([
    "The feeder model reproduces the paper's load flow (rated currents within 1 % of Table II "
    "on every branch) and most fault currents within 20 %; I<sub>f,max</sub> differs by "
    "28&#8211;46 % on four branches (section 2).",
    "Recloser R1 (GE IAC77B801A extremely inverse, pickup 720 A, TDS 0.5 / 10) reproduces "
    "every R1 time given in the paper within 1&#8211;4 %.",
    "The coordination maps reproduce the paper's main result: without the dual-setting "
    "directional recloser (DSDR) coordination is lost for faults upstream of R2; with the DSDR it "
    "is restored. Fig. 14: %d of %d comparable cells agree; Fig. 17: %d of %d." % (
        agree["14"][0], sum(agree["14"]), agree["17"][0], sum(agree["17"])),
    "Fuse and R2 times differ from the paper's figures. The paper's plotted fuse times cannot "
    "be obtained from its own eq. (6) with its Table III b<sub>i</sub>; the model follows the "
    "equations (decision taken with the method, not the plots).",
])
S.append(PageBreak())

# ---- page 2: model ------------------------------------------------------------------------
S.append(p("1. Model and protection settings", H1))
S.append(p("IEEE 13-node test feeder (4.16 kV, 60 Hz) with a 4.05 MVA / 0.69 kV synchronous DG "
           "connected at node 692 through a 0.69/4.16 kV transformer (Table I data). Short "
           "circuits use the Complete method; the IEC/ANSI methods cannot represent the "
           "feeder's single-phase regulators and one- and two-phase laterals.", BODY))
S.append(p("Reclosers", H2))
S.append(table([
    ["Device", "Location", "Relay / curve", "Pickup", "TDS fast / delayed", "Source of setting"],
    ["R1", "RG60 end of line 650&#8211;632", "GE IAC77B801A, extremely inverse", "720 A (CT 900/5, tap 4 A)", "0.5 / 10", "Paper (Ip = 1.25 &#215; 587.6 A)"],
    ["R2 forward", "671 end of line 632&#8211;671", "GE IAC77B801A, extremely inverse", "600 A (CT 1000/5, tap 3 A)", "0.8 / 4.0", "Fitted to Table III (not given in the paper)"],
    ["R2 reverse (DSDR)", "same", "GE IAC extremely inverse", "322 A", "%s / %s" % tuple(
        dsdr.split("fast ")[1].split(", delayed ")[i].split(" ")[0] for i in (0, 1)),
     "Eq. (12): 1.25 &#215; 257.8 A reverse load current with DG; TDS by step 8 of the method"],
], [0.12 * W, 0.17 * W, 0.19 * W, 0.16 * W, 0.12 * W, 0.24 * W]))
S.append(p("Fuses", H2))
S.append(p("15 fuses placed as in Fig. 6 of the paper (19 objects: the distributed load is split "
           "into five sections in the model, each with an F-DL fuse). Each fuse has its own fuse "
           "type: minimum melting time from eq. (6), log<sub>10</sub>(t) = &#8722;1.8 "
           "log<sub>10</sub>(I) + b<sub>i</sub> with the paper's Table III b<sub>i</sub>; total "
           "clearing at 1.21 &#215; the melting current (band width of a tested DIgSILENT "
           "library fuse, Gould-Shawmut A055B, used as the template).", BODY))
fuse_loc = {"F632": "632 end of 632&#8211;645", "F633": "632 end of 632&#8211;633",
            "F634": "XFM-1 LV side", "F645": "load at 645", "F646": "645 end of 645&#8211;646",
            "F-DL": "distributed load", "F671": "671 end of 671&#8211;680",
            "F671-1": "671 end of switch 671&#8211;692", "F692": "load at 692",
            "F692-R": "692 end of 692&#8211;675", "F675": "load at 675",
            "F671-2": "671 end of 671&#8211;684", "F684": "684 end of 684&#8211;611",
            "F611": "load at 611", "F652": "684 end of 684&#8211;652"}
rows = [["Fuse", "Location", "b<sub>i</sub>", "Fuse", "Location", "b<sub>i</sub>"]]
fl = list(fuse_loc.items())
paper_b = {r["Fuse"]: r["b_i paper"] for r in t3}
half = (len(fl) + 1) // 2
for i in range(half):
    a = fl[i]
    b = fl[i + half] if i + half < len(fl) else ("", "")
    rows.append([a[0], a[1], paper_b.get(a[0], ""), b[0], b[1], paper_b.get(b[0], "")])
S.append(table(rows, [0.11 * W, 0.28 * W, 0.08 * W, 0.11 * W, 0.34 * W, 0.08 * W]))
S.append(PageBreak())

# ---- page 3: tables II, III ---------------------------------------------------------------
S.append(p("2. Table II &#8211; maximum, minimum and rated branch currents", H1))
S.append(p("Rated current I<sub>nom</sub>: unbalanced load flow, largest phase current at the "
           "device end. I<sub>f,max</sub>: bolted three-phase fault at the downstream node, "
           "maximum short-circuit currents; at 645, 646 and 684 (two phases) and 611, 652 (one "
           "phase) a three-phase fault cannot exist, so the largest fault that can (line-line or "
           "line-to-ground) is used. I<sub>f,min</sub>: single line-to-ground fault through 3 ohm "
           "at the farthest node, minimum short-circuit currents. DG out of service. "
           "Match = 100 % &#8722; |model &#8722; paper| / paper.", SMALL))
rows = [["From", "To", "I<sub>nom</sub> model (A)", "paper", "match",
         "I<sub>f,min</sub> model (kA)", "paper", "match", "I<sub>f,max</sub> model (kA)",
         "paper", "match"]]
sums = [[], [], []]
for m, (f, t, pn, pmin, pmax) in zip(t2, PAPER_T2):
    vals = [float(m["I_nom (A)"]), float(m["I_f_min (kA)"]), float(m["I_f_max (kA)"])]
    ms = [100.0 if pn == 0 and vals[0] == 0 else match(vals[0], pn), match(vals[1], pmin),
          match(vals[2], pmax)]
    for k in range(3):
        sums[k].append(ms[k])
    rows.append([f, t, "%.1f" % vals[0], "%.1f" % pn, colour_pct(ms[0]), "%.2f" % vals[1],
                 "%.2f" % pmin, colour_pct(ms[1]), "%.2f" % vals[2], "%.2f" % pmax,
                 colour_pct(ms[2])])
rows.append(["<b>Average</b>", "", "", "", colour_pct(sum(sums[0]) / len(sums[0])), "", "",
             colour_pct(sum(sums[1]) / len(sums[1])), "", "",
             colour_pct(sum(sums[2]) / len(sums[2]))])
S.append(table(rows, [0.115 * W, 0.06 * W] + [0.09 * W, 0.08 * W, 0.072 * W] * 3))
S.append(p("Rated currents match the paper within 1 % on every branch, and I<sub>f,min</sub> "
           "within 20 %. I<sub>f,max</sub> differs by more than 20 % on four branches: "
           "RG60&#8211;632 (model 46 % higher), 671&#8211;692 (28 % higher), and 671&#8211;680 and "
           "692&#8211;675 (model 38 % and 46 % lower). The paper's 6.25 and 7.83 kA at 680 and "
           "675 exceed its own 5.41 kA for the feeder-head branch RG60&#8211;632, which a radial "
           "feeder without DG cannot produce; the paper does not state the source impedance or "
           "DG state it used.", SMALL))
S.append(Spacer(1, 4))
S.append(p("3. Table III &#8211; fuse coefficients b<sub>i</sub>", H1))
S.append(p("b<sub>i</sub> = log<sub>10</sub>(t<sub>F</sub> + i/(z+1)&#183;(t<sub>D</sub> &#8722; "
           "t<sub>F</sub>)) + 1.8&#183;log<sub>10</sub>(I<sub>f</sub>) (eqs. 7, 9), with the "
           "recloser fast and delayed times at a bolted fault below each fuse.", SMALL))
rows = [["Fuse", "Recloser", "i / z", "I<sub>fuse</sub> (A)", "t<sub>F</sub> (s)",
         "t<sub>D</sub> (s)", "b<sub>i</sub> model", "b<sub>i</sub> paper", "difference"]]
ex = []
for k, r in enumerate(t3, start=1):
    d = float(r["b_i"]) - float(r["b_i paper"])
    rows.append([r["Fuse"], r["Recloser"], "%s / %s" % (r["i"], r["z"]), r["I_fuse (A)"],
                 r["t_F (s)"], r["t_D (s)"], r["b_i"], r["b_i paper"], "%+.2f" % d])
    if abs(d) > 0.1:
        ex.append(("TEXTCOLOR", (8, k), (8, k), BAD))
S.append(table(rows, [0.1 * W, 0.1 * W, 0.08 * W, 0.11 * W, 0.1 * W, 0.1 * W, 0.11 * W,
                      0.11 * W, 0.11 * W], extra=ex))
S.append(p("11 of 15 b<sub>i</sub> within 0.1 of the paper; F633 (&#8722;0.38), F684 "
           "(&#8722;0.19), F652 (&#8722;0.14) and F611 (&#8722;0.11) differ most. The fuses in the "
           "model use the paper's b<sub>i</sub>.", SMALL))
S.append(PageBreak())

# ---- page 4: table IV -----------------------------------------------------------------------
S.append(p("4. Table IV &#8211; operating times for a fault at each node", H1))
S.append(p("Largest bolted fault that exists at the node, DG in service. R2 uses its reverse "
           "(DSDR) setting for nodes upstream of R2. Fuse: melting time of the primary fuse in "
           "the faulted path. Times in seconds; model on the left, paper on the right. Fault "
           "currents from the fault study (study-case short-circuit setting: minimum currents).",
           SMALL))
rows = [["", "", "Model", "", "", "", "", "", "Paper", "", "", "", ""],
        ["Node", "Fault", "R1 fast", "R1 del.", "R2 fast", "R2 del.", "Fuse", "Fuse MMT",
         "R1 fast", "R1 del.", "R2 fast", "R2 del.", "Fuse MMT"]]
for r in t4:
    rows.append([r["Node"], r["Fault"], r["R1 fast (s)"], r["R1 delayed (s)"], r["R2 fast (s)"],
                 r["R2 delayed (s)"], r["Primary fuse"], r["Fuse MMT (s)"],
                 r["Paper R1 fast"], r["Paper R1 delayed"], r["Paper R2 fast"],
                 r["Paper R2 delayed"], r["Paper fuse MMT"]])
w = [0.07, 0.07, 0.072, 0.072, 0.072, 0.072, 0.09, 0.08, 0.072, 0.075, 0.072, 0.072, 0.08]
S.append(table(rows, [x * W for x in w], header_rows=2, extra=[
    ("SPAN", (2, 0), (7, 0)), ("SPAN", (8, 0), (12, 0)), ("ALIGN", (2, 0), (-1, 0), "CENTER"),
    ("LINEAFTER", (7, 0), (7, -1), 0.8, INK2)]))
S.append(Spacer(1, 4))
S += bullets([
    "R1: the model's delayed/fast ratio is 20 at every node, exactly as in the paper (TDS 0.5 / "
    "10 on one curve). Absolute R1 times agree within 5&#8211;45 % (closest at 680, 684 and "
    "611); the paper does not state the fault type used for Table IV.",
    "R2: the paper's delayed/fast ratio varies from 11 to 65 between nodes, so its fast and "
    "delayed stages must use different curves or pickups. These settings are not published; "
    "the model's R2 uses one curve (ratio 5 forward).",
    "Fuses: the model's melting times are 0.9&#8211;7 times the paper's, because the fuses follow "
    "eq. (6) with the Table III b<sub>i</sub> (see section 7).",
])
S.append(Spacer(1, 6))
S.append(p("Recloser R1 at the paper's own operating points", H2))
rows = [["Paper source", "Device", "Current (A)", "Paper (s)", "Model (s)", "Model / paper"]]
for r in ops:
    if r["Device"].startswith("R1"):
        rows.append([r["Source"], r["Device"], r["Current (A)"], r["t paper (s)"],
                     r["t model (s)"], r["model/paper"]])
S.append(table(rows, [0.3 * W, 0.14 * W, 0.13 * W, 0.13 * W, 0.13 * W, 0.17 * W]))
S.append(PageBreak())

# ---- page 5: figs 14, 17 --------------------------------------------------------------------
S.append(p("5. Figs. 14 and 17 &#8211; recloser&#8211;fuse coordination maps", H1))
S.append(p("Coordination holds when every recloser feeding the fault trips on its fast curve "
           "before the primary fuse melts, and the fuse clears before the recloser's delayed "
           "trip. Upstream of R2 both R1 (grid) and R2 (DG, reverse direction) feed the fault. "
           "Node 634 (fuse on the transformer LV side) is not coordinated, as in the paper; 632 "
           "and 671 have no fuse in the faulted path.", SMALL))
S.append(fig("Fig14_coordination_conventional.png", W))
S.append(p("Model vs paper, cells rated in both: <b>%d agree, %d differ</b> (633 LG, LL; 645 LG; "
           "675 LLG, LLL; DL LL, LLG, LLL)." % agree["14"], SMALL))
S.append(Spacer(1, 6))
S.append(fig("Fig17_coordination_DSDR.png", W))
S.append(p("Model vs paper: <b>%d agree, %d differ</b> (633 LG and LL: R1's delayed trip comes "
           "before F633 clears, a consequence of the paper's b<sub>i</sub> = 6.83 for F633)."
           % agree["17"], SMALL))
S.append(p("With the DSDR, R2's separate reverse setting restores coordination at 645, 646 and "
           "DL for all fault types and at 633 for LLG and LLL, which is the paper's central "
           "result.", BODY))
S.append(PageBreak())

# ---- pages 6-7: TCC figures -----------------------------------------------------------------
S.append(p("6. Operation sequences (time&#8211;current plots)", H1))
S.append(p("Figs. 8, 9, 11, 12, 13 and 16 are drawn by PowerFactory itself "
           "(Figure_Plots.py): each page has the figure's reclosers and fuses, and the figure's "
           "fault is applied with the DG in service, so the vertical lines are PowerFactory's "
           "fault currents and the labels its trip times. At the fault study's currents these "
           "labels equal the model's calculated times exactly (Fig. 16: R1 0.129 / 2.572 s, "
           "F646 1.406 s, F632 0.712 s), confirming that the fuse curves in PowerFactory follow "
           "eq. (6). The plots below use maximum short-circuit currents, so their currents are "
           "5&#8211;10 % higher and their times shorter than in Table IV (minimum currents). "
           "Fig. 15 needs R2's reverse (DSDR) setting, which is not yet a relay in the "
           "model, and Fig. 7 is not a time-current plot; both are calculated in Python from "
           "PowerFactory's fault currents.", SMALL))
PAPER_NOTE = {"08": "SLG fault at 611. Paper: R2 fast 0.207 s, F684 0.476 s, F671-2 1.456 s, "
                    "R2 delayed 2.472 s.",
              "11": "LL fault at 646, Rf 1 ohm. Paper: R1 fast 0.134 s, F646 0.202 s, F632 "
                    "1.096 s, R1 delayed 2.690 s.",
              "13": "3-phase fault at 10 % of 632&#8211;633. Paper: R2 fast 0.079 s, delayed "
                    "1.556 s, F633 0.022 s.",
              "16": "Solid LL fault at 646. Paper: R1 fast 0.128 s, F646 0.181 s, F632 0.411 s, "
                    "R1 delayed 2.555 s.",
              "12": "LL fault at 645, Rf 1.5 ohm, conventional R2. Paper: R2 fast 0.419 s, "
                    "delayed 16.683 s, F632 25.440 s.",
              "09": "LLG fault at mid 692&#8211;675, Rf 1 ohm. Paper: R2 fast 0.141 s, fuses "
                    "0.217 / 0.546 s, R2 delayed 1.483 s."}
PFDIR = os.path.join(RES, "PF_Figures")


def pf_fig(num, w):
    from reportlab.lib.utils import ImageReader
    path = os.path.join(PFDIR, "Fig%s.png" % num)
    iw, ih = ImageReader(path).getSize()
    return [Image(path, width=w, height=w * ih / iw),
            Paragraph("<b>Fig. %d</b> (PowerFactory). %s" % (int(num), PAPER_NOTE[num]), SMALL)]


pairs = [(pf_fig("08", 0.495 * W), pf_fig("11", 0.495 * W)),
         (pf_fig("13", 0.495 * W), pf_fig("16", 0.495 * W)),
         (pf_fig("12", 0.495 * W), pf_fig("09", 0.495 * W)),
         ([fig("Fig15_LL_646_DSDR_R2.png", 0.495 * W)], [fig("Fig07_CTI_vs_DG.png", 0.495 * W)])]
for a, b in pairs:
    S.append(Table([[a, b]], colWidths=[0.5 * W, 0.5 * W],
                   style=[("VALIGN", (0, 0), (-1, -1), "TOP"),
                          ("LEFTPADDING", (0, 0), (-1, -1), 0),
                          ("RIGHTPADDING", (0, 0), (-1, -1), 2)]))
    S.append(Spacer(1, 4))
S.append(p("Fig. 7: the recloser&#8211;fuse CTI shrinks as the DG grows, by 29 % at node 633 and "
           "77 % at node 671 at full DG rating (penetration taken as % of the 4.05 MVA rating; "
           "the paper does not define it).", SMALL))
S.append(Spacer(1, 10))

# ---- page 8: differences, next steps --------------------------------------------------------
S.append(p("7. Differences from the paper and their causes", H1))
rows = [["Paper source", "Device", "Current (A)", "Paper (s)", "Model (s)", "Model / paper"]]
for r in ops:
    if not r["Device"].startswith("R1"):
        rows.append([r["Source"], r["Device"], r["Current (A)"], r["t paper (s)"],
                     r["t model (s)"], r["model/paper"]])
S.append(table(rows, [0.3 * W, 0.14 * W, 0.13 * W, 0.13 * W, 0.13 * W, 0.17 * W]))
S.append(Spacer(1, 4))
S += bullets([
    "<b>Fuse curves.</b> Working back from the paper's figures, its fuses are faster than its "
    "Table III b<sub>i</sub> allow (e.g. F646: 5.67 from the figures against 6.67 in Table III; "
    "F633: 5.42 against 6.83), and they are drawn as curved manufacturer-style bands, not the "
    "straight lines of eq. (6). The paper's PowerFactory figures most likely used library fuse "
    "types. The model follows eq. (6) and Table III.",
    "<b>Series fuses.</b> With the Table III b<sub>i</sub>, the upstream fuse melts before the "
    "downstream fuse in all four series pairs (F632&#8211;F646, F671-1&#8211;F692-R, "
    "F671-2&#8211;F684, F671-2&#8211;F652), which violates the paper's own 75 % rule, eq. (8). "
    "The paper's figures show the correct order.",
    "<b>R2 settings.</b> The paper names the relay (GE Alstom CDG34) but gives no pickup or TDS "
    "for R2, forward or reverse. The model's forward setting is fitted to Table III; the "
    "reverse (DSDR) setting is derived with eq. (12) and step 8 of the paper's method.",
    "<b>Fault levels.</b> The paper's I<sub>f,max</sub> at 680 and 675 (6.25, 7.83 kA) exceed "
    "its own 5.41 kA at the feeder head (RG60&#8211;632); the source impedance and DG state "
    "used for Table II are not given (section 2).",
])
S.append(p("8. Next steps", H1))
S += bullets([
    "Fig. 10: time-domain (RMS/EMT) simulation of two fast reclosing attempts of R2 before the "
    "fuse clears an LL fault at 684.",
    "Fig. 6 and Table I: redraw the single-line diagram with the protective devices and check "
    "the DG data in the model against Table I.",
    "Discuss with the supervisor whether to keep the eq. (6) fuses or fit fuse curves to the "
    "paper's figures (reproduces the plots, but departs from Table III).",
    "Optional: IEEE 34-node system (Figs. 18&#8211;21, Table V).",
])
S.append(Spacer(1, 6))
S.append(p("How to reproduce: in PowerFactory run <b>Show_Progress.py</b> (Tables II&#8211;IV, "
           "Figs. 14 and 17 in the Output Window, saved to Result\\Show_Progress_output.txt); "
           "for the plots run Fault_Study.py in PowerFactory, then make_figures.py in Python.",
           SMALL))

doc.build(S, onFirstPage=footer, onLaterPages=footer)
print("saved", OUT)
