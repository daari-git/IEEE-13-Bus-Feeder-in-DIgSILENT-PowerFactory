"""
Builds results/Penetration_Defence.pdf: the DG penetration study (Fig. 7), how it reproduces the paper,
and prepared answers to the questions a panel is likely to ask, each with the result that supports it.

Needs: results of make_penetration_models.py, sc_levels_penetration.py, analyse_penetration.py,
compare_penetration.py, tcc_penetration.py.  No PowerFactory.
"""

import json
import os
import sys

import matplotlib
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

HERE = os.path.dirname(os.path.abspath(__file__))
REPL = os.path.join(os.path.dirname(HERE), "DSDR_Study")
sys.path.insert(0, REPL)
import step3_design_and_evaluate as S3          # noqa: E402  (curves only)

RES = os.path.join(HERE, "results")
OUT = os.path.join(HERE, "comparison", "Penetration_Defence.pdf")
D = {int(k): v for k, v in json.load(open(os.path.join(RES, "penetration_results.json"))).items()}
SC = {int(k): v for k, v in json.load(open(os.path.join(RES, "sc_levels.json"))).items()}
CONV = json.load(open(os.path.join(REPL, "results", "settings.json")))["conventional"]
P = sorted(D)
PAPER = {"633": [30, 23, 14, 6, -4, -9, -16], "671": [36, 22, 12, 6, 0, -8, -14]}
KEY = {"633": "633 LLL", "671": "671 LL"}

# ---- styles -----------------------------------------------------------------------------------
FONTS = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
for n, f in (("DV", "DejaVuSans.ttf"), ("DV-B", "DejaVuSans-Bold.ttf"), ("DV-I", "DejaVuSans-Oblique.ttf"),
             ("DV-BI", "DejaVuSans-BoldOblique.ttf")):
    pdfmetrics.registerFont(TTFont(n, os.path.join(FONTS, f)))
pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B", italic="DV-I", boldItalic="DV-BI")
INK, INK2, RULE = colors.HexColor("#1a1a1a"), colors.HexColor("#55534e"), colors.HexColor("#cfcdc7")
ACCENT, KEYC, QBG = colors.HexColor("#1f5fa8"), colors.HexColor("#fff6dc"), colors.HexColor("#eef2f7")
BODY = ParagraphStyle("b", fontName="DV", fontSize=9.4, leading=13.3, textColor=INK, spaceAfter=5)
NOTE = ParagraphStyle("n", parent=BODY, fontSize=8.4, leading=11.6, textColor=INK2)
CELL = ParagraphStyle("c", parent=BODY, fontSize=8.1, leading=10.6, spaceAfter=0)
HEAD = ParagraphStyle("h", parent=CELL, fontName="DV-B", textColor=colors.white)
H1 = ParagraphStyle("h1", parent=BODY, fontName="DV-B", fontSize=13.5, leading=18, textColor=ACCENT, spaceBefore=8,
                    spaceAfter=6, keepWithNext=True)
QST = ParagraphStyle("q", parent=BODY, fontName="DV-B", fontSize=10, leading=13.5, textColor=ACCENT, spaceBefore=8,
                     spaceAfter=3, keepWithNext=True)
TITLE = ParagraphStyle("t", parent=BODY, fontName="DV-B", fontSize=18, leading=23)
SUB = ParagraphStyle("s", parent=BODY, fontSize=9.6, textColor=INK2, spaceAfter=10)
CAP = ParagraphStyle("cap", parent=NOTE, alignment=1, spaceAfter=8)
W = A4[0] - 3.4 * cm


def p(t, s=BODY):
    return Paragraph(t, s)


def table(rows, widths, keys=()):
    data = [[Paragraph(str(c), HEAD if i == 0 else CELL) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1)
    st = [("BACKGROUND", (0, 0), (-1, 0), ACCENT), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE), ("TOPPADDING", (0, 0), (-1, -1), 2.5),
          ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
    st += [("BACKGROUND", (0, k), (-1, k), KEYC) for k in keys]
    t.setStyle(TableStyle(st))
    return t


def img(name, width=W):
    path = os.path.join(RES, name)
    im = Image(path)
    r = im.imageHeight / float(im.imageWidth)
    return Image(path, width=width, height=width * r)


QN = [0]


def answer(q, parts):
    QN[0] += 1
    return [p("Q%d. %s" % (QN[0], q), QST)] + parts


f = lambda pp, node: D[pp]["faults"][KEY[node]]
cti = {n: [f(pp, n)["CTI_s"] for pp in P] for n in KEY}
ring = {n: [100.0 * c / sum(abs(x) for x in cti[n]) for c in cti[n]] for n in KEY}
F633, F6712 = S3.FTYPE[CONV["fuses"]["F633"]], S3.FTYPE[CONV["fuses"]["F671-2"]]


def sc_best(pp, node, case="max"):
    rows = [r for r in SC[pp] if r["node"] == node and r["case"] == case]
    return max(rows, key=lambda r: r["I_fault"])


story = [p("DG penetration and recloser–fuse coordination", TITLE),
         p("DG penetration study (Fig. 7) in DIgSILENT PowerFactory, IEEE 13-node feeder — "
           "results, how they match the paper, and prepared answers to the panel's questions", SUB)]

# ---- 1 claim -------------------------------------------------------------------------------------
f0, f100 = f(0, "633"), f(100, "633")
story += [p("1. The claim in one paragraph", H1), p(
    "When a synchronous DG is added downstream of the recloser, the fault current through a lateral fuse rises "
    "(grid share + DG share) while the current through the recloser stays the same or falls (grid share only). "
    "The fuse therefore melts faster, the recloser does not trip faster, and the coordination time interval "
    "CTI = t<sub>MMT</sub>(fuse) − t<sub>fast</sub>(recloser) <b>decreases</b> with penetration until the fuse melts "
    "first and fuse saving is lost. This is what Fig. 7 of the paper shows, and the seven PowerFactory models "
    "reproduce it: at node 633 the fuse current rises from %.0f A to %.0f A (+%.0f %%) while R1's current falls from "
    "%.0f A to %.0f A (−%.0f %%), and the CTI falls from %+.0f ms to %+.0f ms." % (
        f0["I_fuse"], f100["I_fuse"], 100 * (f100["I_fuse"] / f0["I_fuse"] - 1), f0["I_R1"], f100["I_R1"],
        100 * (1 - f100["I_R1"] / f0["I_R1"]), 1000 * f0["CTI_s"], 1000 * f100["CTI_s"]))]

# ---- 2 what was done ----------------------------------------------------------------------------
story += [p("2. What was modelled", H1), table([
    ["Item", "In this study"],
    ["Models", "Seven separate PowerFactory projects (and .pfd files), copies of the replication model; the original is unchanged"],
    ["Penetration", "DG rating / 4.05 MVA (the paper's DG): 0, 10, 25, 37, 50, 75, 100 %. Machine, its 0.69/4.16 kV "
                    "transformer and its P, Q are scaled together; per-unit impedances (Table I) unchanged; 0 % = DG out"],
    ["Protection", "The conventional (preset) scheme, unchanged at every level: R1 IAC77B801A 720 A TDS 0.5/10; R2 CDG34 "
                   "300/600 A TMS 0.1/1.0, no reverse group; fuses of the design without DG"],
    ["Times", "PowerFactory's own relay and fuse elements (c:Ttrip); fuse time = minimum melting"],
    ["Node 633 (internal, R1's zone)", "Three-phase bolted fault at 633; fuse F633 (250E) against R1 fast"],
    ["Node 671 (external, R2's zone)", "Line-to-line fault at 684, on the lateral that leaves 671 through fuse F671-2 "
                                       "(300E), against R2 fast"],
    ["Percentages", "As in the paper's doughnut chart each ring adds up to 100 %: CTI % = 100 × CTI / Σ|CTI| (sign kept)"],
], [4.2 * cm, W - 4.2 * cm])]

# ---- 3 results -----------------------------------------------------------------------------------
rows = [["DG", "633: fuse / R1 (A)", "633 CTI", "633 %: ours / paper", "671: fuse / R2 (A)", "671 CTI", "671 %: ours / paper"]]
for k, pp in enumerate(P):
    a, b = f(pp, "633"), f(pp, "671")
    rows.append(["%d %%" % pp, "%.0f / %.0f" % (a["I_fuse"], a["I_R1"]), "%+.0f ms" % (1000 * a["CTI_s"]),
                 "%+.1f / %+d" % (ring["633"][k], PAPER["633"][k]), "%.0f / %.0f" % (b["I_fuse"], b["I_R2"]),
                 "%+.0f ms" % (1000 * b["CTI_s"]), "%+.1f / %+d" % (ring["671"][k], PAPER["671"][k])])
story += [PageBreak(), p("3. Results against the paper", H1), img("../comparison/Fig07_penetration_vs_paper.png"),
          p("Fig. 7 replicated (left) beside the paper's values (right). Outer ring 671, inner ring 633.", CAP),
          table(rows, [1.3 * cm, 2.9 * cm, 1.8 * cm, 2.9 * cm, 2.9 * cm, 1.8 * cm, W - 13.6 * cm]),
          Spacer(1, 6),
          p("<b>What agrees:</b> the direction of the effect — at both nodes the CTI falls monotonically as penetration rises; "
            "at 671 the shares of the first four levels are close to the paper's (26 / 22 / 16 / 13 %% against 36 / 22 / 12 / 6 %%). "
            "<b>What differs:</b> where the CTI crosses zero. 633 starts with only 4 ms of margin and is negative from about "
            "4 %%; 671 starts with 403 ms and stays positive (75 ms at 100 %%). The paper crosses zero at about 40–50 %% at "
            "both nodes. The reasons are in Q4 and Q5."),
          PageBreak(), img("TCC_penetration_overview.png"),
          p("TCC of both cases with all levels: the curves are fixed (settings unchanged); the recloser's operating point "
            "(circle) stays where it is, the fuse's point (square) moves to higher current and shorter time.", CAP),
          img("Fig07_penetration_currents.png"),
          p("Currents through the fuse (grid + DG), the recloser (grid only) and from the DG, and the resulting CTI.", CAP)]

# ---- 4 questions -------------------------------------------------------------------------------
story += [PageBreak(), p("4. Questions the panel may ask, with answers", H1)]

# Q1 -- the key one
r1 = [["DG", "Total at fault 633 (A)", "Grid share = R1 (A)", "DG share (A)", "Fuse F633 (A)", "R1 fast (s)", "F633 melts (s)",
       "CTI (ms)", "CTI if the fuse saw only the grid share (ms)"]]
for pp in P:
    a = f(pp, "633")
    tot = sc_best(pp, "633")["I_fault"]
    r1.append(["%d %%" % pp, "%.0f" % tot, "%.0f" % a["I_R1"], "%.0f" % a["I_DG"], "%.0f" % a["I_fuse"], "%.3f" % a["t_rec_fast"],
               "%.3f" % a["t_fuse_MMT"], "%+.0f" % (1000 * a["CTI_s"]), "%+.1f" % (1000 * (F633.mmt(a["I_R1"]) - a["t_rec_fast"]))])
story += answer(
    "With DG the short-circuit contribution from the source decreases, so the recloser and the fuse should both see less "
    "current and the CTI should increase. Why do you get a decreasing CTI?", [
        p("The first half is correct and the model shows it: the <b>source (grid) contribution falls</b> — R1 carries "
          "%.0f A at 0 %% and %.0f A at 100 %%, because the DG holds up the voltage at the common part of the network during "
          "the fault (infeed effect). If the fuse also carried only the grid share, the CTI would indeed <b>increase</b> "
          "slightly: last column of the table, %+.1f ms to %+.1f ms." % (
              f0["I_R1"], f100["I_R1"], 1000 * (F633.mmt(f0["I_R1"]) - f0["t_rec_fast"]),
              1000 * (F633.mmt(f100["I_R1"]) - f100["t_rec_fast"]))),
        p("But the fuse is <b>between the fault and both sources</b>. It carries the grid share and the DG share together, "
          "so its current <b>rises</b> (%.0f → %.0f A) while the recloser's falls. The total fault level at 633 rises from %.0f A "
          "to %.0f A (+%.0f %%). A fuse curve is steep, so the extra current shortens its melting time much more than the "
          "slightly lower current lengthens R1's time: F633 melts at %.3f s instead of %.3f s, R1 trips at %.3f s instead of "
          "%.3f s. The CTI is the difference of the two, so it decreases." % (
              f0["I_fuse"], f100["I_fuse"], sc_best(0, "633")["I_fault"], sc_best(100, "633")["I_fault"],
              100 * (sc_best(100, "633")["I_fault"] / sc_best(0, "633")["I_fault"] - 1),
              f100["t_fuse_MMT"], f0["t_fuse_MMT"], f100["t_rec_fast"], f0["t_rec_fast"])),
        table(r1, [1.4 * cm, 1.7 * cm, 1.7 * cm, 1.3 * cm, 1.6 * cm, 1.4 * cm, 1.6 * cm, 1.3 * cm, W - 12.0 * cm], keys=(1, 7)),
        p("The fuse current is the phasor sum of the two shares, so it is slightly less than the arithmetic sum. "
          "This is exactly the mechanism the paper states (Section II): the DG's contribution flows through the fuse but not "
          "through the upstream recloser.", NOTE)])

story += answer("How did you define the penetration level, and why that way?", [p(
    "As the DG rating relative to the paper's DG of 4.05 MVA, which equals the total feeder load of the IEEE 13-node "
    "feeder. The paper gives the levels but not its formula; this definition makes 100 % the case of the paper's main "
    "study, so the 100 % model reproduces the replication exactly (same currents and times). The machine, its step-up "
    "transformer and its power output are scaled together, so the per-unit impedances of Table I stay as published and "
    "the DG's fault contribution scales with its size (183 A at 10 %, 1580 A at 100 % for the fault at 633).")])

story += answer("Why are the relay settings and fuse sizes kept the same at every level?", [p(
    "Because that is what Fig. 7 tests: how a scheme designed without DG degrades when DG is added. Changing the settings "
    "with each level would hide the effect. Adapting the settings is the paper's proposal (the DSDR), and its result is "
    "shown separately in the replication (Q12).")])

story += answer("Why does node 633 become negative already at about 4 % penetration, while the paper reaches zero at 40–50 %?", [p(
    "Because the margin without DG is already very small in this model: F633 (250E) melts in %.3f s and R1 trips in %.3f s, "
    "only 4 ms apart. Any extra current through the fuse removes that margin. The paper's starting margin is about 30 %% of "
    "the ring, so it needs much more DG to cross zero. The paper does not publish the fuse sizes and settings behind Fig. 7; "
    "a larger fuse at 633 (e.g. the 400E chosen by the method's fuse revision) would move the crossing to a higher "
    "penetration. The trend is the same; the crossing point depends on the starting margin." % (
        f0["t_fuse_MMT"], f0["t_rec_fast"]))])

f671_0, f671_100 = f(0, "671"), f(100, "671")
story += answer("Why does node 671 never become negative?", [p(
    "F671-2 (300E) starts with a large margin: %.3f s against R2's %.3f s (CTI %+.0f ms). The DG raises the fuse current "
    "from %.0f A to %.0f A and the CTI falls by 81 %% to %+.0f ms, but 100 %% penetration is not enough to close the gap. "
    "With the paper's higher fault levels the fuse would sit further down its curve and reach zero earlier. The shares "
    "of the first levels (26 / 22 / 16 / 13 %%) are close to the paper's (36 / 22 / 12 / 6 %%)." % (
        f671_0["t_fuse_MMT"], f671_0["t_rec_fast"], 1000 * f671_0["CTI_s"], f671_0["I_fuse"], f671_100["I_fuse"],
        1000 * f671_100["CTI_s"]))])

story += answer("What do the percentages in Fig. 7 mean? Is that a percentage of the CTI?", [p(
    "The paper's Fig. 7 is a doughnut chart: the seven segments of each ring add up to 100 %, so each value is that level's "
    "share of the ring. It is computed here as CTI % = 100 × CTI / Σ|CTI| with the sign kept, which gives 100 % per ring "
    "(the paper's rings add up to 102 % and 98 % as read from the figure). The CTI in seconds is given beside it, "
    "because the share alone does not show the absolute margin.")])

story += answer("Why is the 671 case a fault at 684 and not at node 671 itself?", [p(
    "A fault on bus 671 is not downstream of any fuse, so there is no fuse–recloser pair to coordinate. The fuse located at "
    "671 whose current includes the DG share is F671-2, at the start of the 671–684 lateral. PowerFactory does not accept a "
    "fault inside that two-phase line, so the fault is at its end, node 684 (the lateral is 300 ft long). The fault is "
    "line-to-line because the lateral has only phases a and c.")])

# Q8 fault levels
r8 = [["Node", "0 %", "25 %", "50 %", "75 %", "100 %", "Change"]]
for n in ("632", "633", "645", "646", "DL", "671", "675", "680", "684", "652", "611"):
    v = [sc_best(pp, n)["I_fault"] for pp in (0, 25, 50, 75, 100)]
    r8.append([n] + ["%.0f" % x for x in v] + ["%+.0f %%" % (100 * (v[-1] / v[0] - 1))])
story += answer("How does the short-circuit level change with penetration, and where most?", [
    p("It rises at every node, most near the DG at 692 (671, 675: about +60 %) and least behind the 4.16/0.48 kV "
      "transformer (634: +12 %) and on the single-phase laterals (611, 652: about +20 %). Largest bolted fault at each node, A:"),
    table(r8, [1.6 * cm] + [2.3 * cm] * 5 + [W - 13.1 * cm]),
    p("At the same time the current through the reclosers stays the same or falls (R1 −0 to −21 %), so a larger fault does "
      "not mean a faster recloser — only a faster fuse.", NOTE)])

# Q9 R2 nuisance
r9 = [["DG", "R2 current, fault at 633 (A)", "R2 direction", "Conventional R2 fast trip (s)", "F633 melts (s)"]]
for pp in P:
    a = f(pp, "633")
    r9.append(["%d %%" % pp, "%.0f" % next(r for r in SC[pp] if r["node"] == "633" and r["type"] == "LLL")["I_R2"],
               "reverse" if pp else "-", "%.3f" % a["t_R2_fast"] if a["t_R2_fast"] < 1e6 else "does not trip", "%.3f" % a["t_fuse_MMT"]])
story += answer("What does R2 do for the fault at 633, which is outside its zone?", [
    p("With DG it carries the DG's current towards the fault, in the reverse direction (66 A at 0 % rising to 1500 A at 100 %). "
      "The conventional R2 is not directional, so from about 37 % this reverse current is large enough to start its fast curve, "
      "and its time falls to 0.160 s at 100 %. In these bolted cases F633 still melts first, but R2 is now racing the fuse for "
      "a fault outside its zone: with a slower fuse (for example the 400E that the fuse revision needs) or a fault through "
      "impedance, R2 trips first and disconnects the healthy part of the feeder beyond 671 together with the DG — a nuisance "
      "trip. Preventing this is the purpose of the paper's directional dual setting."),
    table(r9, [1.4 * cm, 4.0 * cm, 2.4 * cm, 4.2 * cm, W - 12.0 * cm])])

# Q10 pickups
pk = list(__import__("csv").DictReader(open(os.path.join(RES, "Pickup_vs_penetration.csv"))))
mn = list(__import__("csv").DictReader(open(os.path.join(RES, "Ifmin_vs_pickup.csv"))))
r10 = [["DG", "R1 1.25 × Inom (A)", "R1 lowest 3 Ω fault (A)", "R2 load flow", "R2 1.25 × Inom (A)", "R2 lowest 3 Ω fault (A)"]]
for a, b in zip(pk, mn):
    r10.append([a["DG penetration %"] + " %", a["R1 Ip = 1.25 Inom (A)"], "%.0f%s" % (float(b["lowest R1 current, LG 3 ohm (A)"]),
                "" if b["R1 sees it?"] == "yes" else " (missed)"), a["R2 load direction"], a["R2 Ip = 1.25 Inom (A)"],
                "%.0f%s" % (float(b["lowest R2 current in its zone, LG 3 ohm (A)"]), "" if b["R2 sees it?"] == "yes" else " (missed)")])
story += answer("Should the pickup currents change with penetration?", [
    p("By eq. (3) of the paper, yes: the DG supplies part of the load locally, so the load current through the reclosers falls "
      "and 1.25 × I<sub>nom</sub> falls with it (R1 734.6 → 356.1 A). R2's load flow reverses between 75 and 100 %, so a "
      "reverse pickup (eq. 12, 315 A) becomes necessary only at 100 %. With the fixed pickups the reclosers lose sensitivity: "
      "R2's fast curve (starting at 600 A) no longer sees the lowest 3 Ω fault in its zone above 50 %; R1 is marginal "
      "already without DG."),
    table(r10, [1.3 * cm, 2.9 * cm, 3.4 * cm, 2.3 * cm, 2.9 * cm, W - 12.8 * cm]),
    p("Settings set in the models: R1 720 A (curve from 1080 A), R2 300 / 600 A (fast curve from 600 A).", NOTE)])

story += answer("How reliable are these numbers?", [p(
    "The feeder reproduces the paper's rated branch currents within 2 % and the IEEE short-circuit benchmark within about 2 %. "
    "The 100 % model gives exactly the currents and times of the replication. All operating times in this study are "
    "PowerFactory's own relay and fuse calculations; the curves used for the plots agree with them within 1.2 % over 1896 "
    "operating times. The remaining differences to the paper come from data the paper does not publish: fuse sizes, R2's "
    "settings, the source impedance and the exact fault behind each point of Fig. 7.")])

story += answer("Does this support the paper's conclusion?", [p(
    "Yes, qualitatively and in mechanism: (1) the preset coordination degrades monotonically with DG penetration; (2) it is "
    "lost above a threshold; (3) the cause is the DG current that passes the fuse but not the recloser; (4) the mid-line "
    "recloser additionally sees reverse current and, without direction, trips for faults outside its zone. In the "
    "replication, making R2 a dual-setting directional recloser and revising the fuses restores coordination in 38 of 39 "
    "fault cells at 100 % penetration, against 24 with the conventional scheme (31 with the revised fuses alone). The "
    "threshold itself depends on the starting margin, which the paper does not give, so it is not reproduced exactly.")])

story += answer("What about other fault types?", [p(
    "The same trend holds. LL at 633: CTI %+.0f ms at 0 %% and %+.0f ms at 100 %%. LG at 684: %+.0f ms and %+.0f ms. "
    "Every fault type that passes the DG current through the fuse but not through the recloser shrinks the margin." % (
        1000 * D[0]["faults"]["633 LL"]["CTI_s"], 1000 * D[100]["faults"]["633 LL"]["CTI_s"],
        1000 * D[0]["faults"]["671 LG"]["CTI_s"], 1000 * D[100]["faults"]["671 LG"]["CTI_s"]))])

# ---- Fig. 10 question ------------------------------------------------------------------------
F10 = json.load(open(os.path.join(REPL, "results", "Fig10_summary.json")))["DG out"]
n632 = F10["node632"]
r10f = [["Time (s)", "What happens", "Current at 632 (RMS, phase a / c)"],
        ["0 - 0.30", "normal operation", "%.0f / %.0f A (load)" % (n632["prefault_rms_a"], n632["prefault_rms_c"])],
        ["0.30 - 0.42", "fault at 684, R2 fast shot 1", "%.0f / %.0f A (fault)" % (n632["fault_rms_a"], n632["fault_rms_c"])],
        ["0.42 - 0.62", "R2 open (dead time)", "%.0f / %.0f A (loads between 632 and R2 only)" % (
            n632["dead_time_rms_a"], n632["dead_time_rms_c"])],
        ["0.62 - 0.74", "R2 recloses, fault still there, fast shot 2", "fault current again"],
        ["0.74 - 0.94", "R2 open (dead time)", "small again"],
        ["0.94 - %.3f" % F10["t_clear"], "R2 recloses, permanent fault: fuse F671-2 melts at %.2f s and clears" % F10["t_melt"],
         "fault current until the fuse clears"],
        ["after %.3f" % F10["t_clear"], "lateral 671-684 isolated, rest of the feeder supplied", "load current again (without the lateral)"]]
story += answer("In Fig. 10 the fault is at node 684. Why is the current plotted at node 632?", [
    p("Because node 632 is on the path of the fault current - substation, 650, RG60, <b>632</b>, line 632-671 with R2, 671, "
      "fuse F671-2, <b>684</b> - and it is the point from which the whole protection sequence can be seen. The current at "
      "632 is R2's current plus the loads between 632 and R2 (633, 645, 646 and the distributed load), so it shows the fault "
      "being interrupted by each fast shot of R2, the reclosures, the fuse clearing the permanent fault, and - the purpose of "
      "the figure - the healthy feeder being supplied again afterwards. A measurement at 684 or at the fuse would only show "
      "the fault current switching off; once the fuse opens that point is disconnected, so the restoration of the rest of "
      "the feeder would not be visible. The same point is used in the published figure, so the two can be compared directly."),
    table(r10f, [2.4 * cm, 7.6 * cm, W - 10.0 * cm]),
    p("Fault: line-to-line a-c at 684 through 0.2 ohm, DG out of service, conventional settings; PowerFactory EMT "
      "simulation (Fig10_EMT_Study).", NOTE)])

# ---- 5 limitations -------------------------------------------------------------------------------
story += [p("5. Limitations to state openly", H1), p(
    "• The fuse and fault behind each node of Fig. 7 are not given in the paper; the pairs used here are the natural ones "
    "(the fuse at the node whose current includes the DG share).<br/>"
    "• Bolted faults; a fault impedance lowers all currents and shifts every point to the left on the TCC.<br/>"
    "• One DG location (692), as in the paper; the paper notes a similar effect for other locations.<br/>"
    "• Coordination judged on the start of melting with zero margin; a breaker time or a fuse margin makes the loss "
    "appear earlier.")]


def footer(c, doc):
    c.saveState()
    c.setFont("DV", 7.5)
    c.setFillColor(INK2)
    c.drawString(1.7 * cm, 1.0 * cm, "DG penetration study (Fig. 7) - Yousaf et al. 2022 replication, DIgSILENT PowerFactory")
    c.drawRightString(A4[0] - 1.7 * cm, 1.0 * cm, "page %d" % doc.page)
    c.restoreState()


SimpleDocTemplate(OUT, pagesize=A4, leftMargin=1.7 * cm, rightMargin=1.7 * cm, topMargin=1.5 * cm, bottomMargin=1.6 * cm,
                  title="DG penetration study - defence notes").build(story, onFirstPage=footer, onLaterPages=footer)
print("written", OUT)
