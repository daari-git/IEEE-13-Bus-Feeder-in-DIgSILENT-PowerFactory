"""
Coordination diagrams: the existing scheme (R2 with one setting) against R2 as a dual-setting
directional recloser (DSDR), for the faults of the study's figures and for the faults where the
dual setting decides.  PowerFactory is not needed (results/studies.json, results/settings.json).

Both panels of every diagram use the SAME fuse sizes (the final design), so the only difference
between them is R2's setting:
  single setting   R2 non-directional, forward setting for every fault (also for the DG's reverse current)
  dual setting     forward setting for faults below R2, reverse setting (eq. 12) for faults above it

Each diagram carries its fault table: fault, fault impedance Zf, fault-path current, current through
R1 and R2 with direction, the setting R2 applies, the operating times and the verdict.

Outputs in results/coordination_diagrams/: one PNG per case, 00_Summary.png, 00_Grids.png,
Fault_table.csv, Coordination_Diagrams.pdf.
"""

import copy
import csv
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

import sequence_check as SQ
import step3_design_and_evaluate as m
from curves import INF, _loglog
from protection_data import NODES, NODE_ORDER, FAULT_TYPES

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results", "coordination_diagrams")
os.makedirs(OUT, exist_ok=True)

SET = json.load(open(os.path.join(HERE, "results", "settings.json")))
CONV, DS = SET["conventional"], SET["dsdr"]


def open_csv(path):
    """Open a csv for writing; if it is open in Excel write <name>_new.csv instead."""
    try:
        return open(path, "w", newline="")
    except PermissionError:
        print("locked, writing", os.path.basename(path).replace(".csv", "_new.csv"))
        return open(path.replace(".csv", "_new.csv"), "w", newline="")


def scheme(fuses, dual):
    s = copy.deepcopy(DS)
    s["fuses"] = dict(fuses)
    if not dual:
        s["R2fw"] = copy.deepcopy(CONV["R2fw"])
    return s


S_SINGLE, S_DUAL = scheme(DS["fuses"], False), scheme(DS["fuses"], True)
A_SINGLE, A_DUAL = scheme(CONV["fuses"], False), scheme(CONV["fuses"], True)     # fuse sizes of the no-DG design
BLUE, ORANGE, AQUA, VIOLET = "#2a78d6", "#eb6834", "#1baf7a", "#4a3aa7"
GOOD, BAD, INK, INK2, GRID, SURF = "#0ca30c", "#d03b3b", "#0b0b0b", "#52514e", "#d9d8d4", "#fcfcfb"
plt.rcParams.update({"font.size": 8.5, "axes.edgecolor": INK2, "axes.labelcolor": INK, "text.color": INK,
                     "xtick.color": INK2, "ytick.color": INK2, "figure.facecolor": SURF, "axes.facecolor": SURF,
                     "savefig.facecolor": SURF})


LOCKED = []


def save_fig(fig, path, dpi):
    """Save a figure; a file that is open in a viewer is locked on Windows, so the new version then
    goes to <name>_new.png and the caller uses that."""
    try:
        fig.savefig(path, dpi=dpi)
        return path
    except OSError:
        alt = path[:-4] + "_new.png"
        fig.savefig(alt, dpi=dpi)
        LOCKED.append(os.path.basename(path))
        return alt


def figrec(case):
    return [r for r in m.FAULTS if r["case"] == case][0]


def nodefault(node, ftype, phases):
    return [r for r in m.faults("max", 1.0, node, ftype) if r["phases"] == phases][0]


# id, title, record, node used for the zone / fuse path, fault impedance (ohm), paper figure
CASES = [
    ("01", "LG fault at 611", figrec("Fig8"), "611", 0.0, "Fig. 8"),
    ("02", "LLG fault at the middle of 692-675", figrec("Fig9"), "675", 1.0, "Fig. 9"),
    ("03", "LL fault at 646", figrec("Fig11"), "646", 1.0, "Fig. 11"),
    ("04", "LL fault at 645", figrec("Fig12"), "645", 1.5, "Fig. 12"),
    ("05", "3-phase fault at 10 % of 632-633", figrec("Fig13"), "633", 0.0, "Fig. 13"),
    ("06", "LL fault at 646", figrec("Fig15"), "646", 0.0, "Figs. 15, 16"),
    ("07", "LG fault at 646 (phase c)", nodefault("646", "LG", "C"), "646", 0.0, "Fig. 14 / 17 cell"),
    ("08", "LG fault at 633 (phase b)", nodefault("633", "LG", "B"), "633", 0.0, "Fig. 14 / 17 cell"),
    ("09", "LG fault at 692 (phase a)", nodefault("692", "LG", "A"), "692", 0.0, "Fig. 14 / 17 cell"),
]


def evaluate(rec, node, s, dual):
    r = dict(rec)
    r["where"] = node
    return m.evaluate(r, s, dual)


def tt(x):
    return "no trip" if x == INF else "%.3f s" % x


def r2_unit(node, dual):
    return "R2fw" if (NODES[node]["zone"] == "R2" or not dual) else "R2rv"


def draw_panel(ax, rec, node, s, dual, title):
    ii = [10 ** (2 + k / 200.0) for k in range(461)]
    zone = NODES[node]["zone"]
    path = NODES[node]["path"]
    i1, i2 = m.imax(rec, "R1"), m.imax(rec, "R2")
    unit = r2_unit(node, dual)
    opts = []
    for name, col, fun, i_dev in (("R1", BLUE, lambda i, md: m.t_r1(i, s, md), i1),
                                  ("R2", ORANGE, lambda i, md, u=unit: m.t_r2(i, s, u, md), i2)):
        opts.append(("R2rv" if (name == "R2" and unit == "R2rv") else name, i_dev,
                     [fun(i_dev, "f"), fun(i_dev, "d")], col))
        for md, ls in (("f", "-"), ("d", "--")):
            pts = [(i, fun(i, md)) for i in ii if fun(i, md) < 100]
            if pts:
                ax.plot(*zip(*pts), color=col, lw=1.7, ls=ls)
            t = fun(i_dev, md)
            if t < INF:
                ax.plot([i_dev], [t], marker="o", ms=6.5, color=col, mec=SURF, mew=1.4, zorder=6)
        ax.axvline(i_dev, color=col, lw=0.9, alpha=0.75)
    for f, col in zip(path[:2], (AQUA, VIOLET)):
        fz = m.FTYPE[s["fuses"][f]]
        lo = [(i, fz.mmt(i)) for i in ii if fz.mmt(i) < 100]
        hi = [(i, fz.tct(i)) for i in ii if fz.tct(i) < 100]
        ax.plot(*zip(*lo), color=col, lw=1.2)
        ax.plot(*zip(*hi), color=col, lw=1.2)
        ax.fill_betweenx([p[1] for p in lo], [p[0] for p in lo],
                         [_loglog(p[1], sorted((b, a) for a, b in fz.clear)) or p[0] for p in lo], color=col, alpha=0.2, lw=0)
        i_f = m.imax(rec, f)
        ax.axvline(i_f, color=col, lw=0.9, alpha=0.75)
        for t in (fz.mmt(i_f), fz.tct(i_f)):
            if t < INF:
                ax.plot([i_f], [t], marker="s", ms=5.5, color=col, mec=SURF, mew=1.2, zorder=6)
        opts.append((f, i_f, [fz.mmt(i_f), fz.tct(i_f)], col))
    e = evaluate(rec, node, s, dual)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(100, 2e4)
    ax.set_ylim(0.01, 100)
    m.annotate_times(ax, opts)
    ax.grid(True, which="major", color=GRID, lw=0.8)
    ax.grid(True, which="minor", color=GRID, lw=0.3, alpha=0.6)
    ax.set_xlabel("Current (A at 4.16 kV)")
    ax.set_title(title, fontsize=9.5, loc="left")
    ax.text(0.98, 0.97, "coordination HELD" if e["held"] else "coordination LOST", transform=ax.transAxes, ha="right",
            va="top", fontsize=10, fontweight="bold", color=GOOD if e["held"] else BAD,
            bbox=dict(boxstyle="round,pad=0.3", fc=SURF, ec=GOOD if e["held"] else BAD, lw=1.2))
    return e


def fault_rows(rec, node, zf, paper):
    """Rows of the fault table: quantity, single setting, dual setting."""
    path = NODES[node]["path"]
    zone = NODES[node]["zone"]
    i1, i2 = m.imax(rec, "R1"), m.imax(rec, "R2")
    up = zone == "R1"
    rows = [("Fault", None),
            ("Fault impedance Zf", "%.1f ohm" % zf if zf else "0 ohm (bolted)"),
            ("Fault-path current (%s)" % path[0] if path else "Fault current at the node",
             "%.0f A" % (m.imax(rec, path[0]) if path else max(rec["ifault"]))),
            ("Current through R1, direction", "%.0f A, forward (RG60 -> 632), grid contribution" % i1),
            ("Current through R2, direction", "%.0f A, %s" % (i2, "REVERSE (671 -> 632), DG contribution only" if up
                                                                else "forward (632 -> 671), grid contribution"))]
    both = []
    for s, dual in ((S_SINGLE, False), (S_DUAL, True)):
        u = r2_unit(node, dual)
        e = evaluate(rec, node, s, dual)
        col = ["%s: plug %.0f/%.0f A, starts %.0f/%.0f A, TMS %.1f/%.1f" % (
            "FORWARD" if u == "R2fw" else "REVERSE", s[u]["is_f"], s[u]["is_d"], 2 * s[u]["is_f"],
            2 * s[u]["is_d"], s[u]["tms_f"], s[u]["tms_d"]),
            "%s / %s" % (tt(m.t_r1(i1, s, "f")), tt(m.t_r1(i1, s, "d"))),
            "%s / %s" % (tt(m.t_r2(i2, s, u, "f")), tt(m.t_r2(i2, s, u, "d")))]
        if path:
            fz = m.FTYPE[s["fuses"][path[0]]]
            i_f = m.imax(rec, path[0])
            col.append("%s %s: %s / %s" % (path[0], s["fuses"][path[0]].replace("A055C", ""), tt(fz.mmt(i_f)), tt(fz.tct(i_f))))
            if len(path) > 1:
                fb = m.FTYPE[s["fuses"][path[1]]]
                col.append("%s %s: %s" % (path[1], s["fuses"][path[1]].replace("A055C", ""), tt(fb.mmt(m.imax(rec, path[1])))))
            else:
                col.append("-")
        else:
            col += ["no fuse in the fault path", "-"]
        col.append(("HELD" if e["held"] else "LOST") + ("" if e["held"] else ": " + e["reason"].split(";")[0]))
        both.append((col, e))
    labels = ["R2 setting applied (fast / delayed)", "R1 fast / delayed", "R2 fast / delayed",
              "Primary fuse melts / clears", "Backup fuse melts", "Fuse saving"]
    return rows, labels, both


def case_figure(cid, title, rec, node, zf, paper):
    """Two TCC panels (single / dual setting).  The numbers of the case go to Case_NN_table.csv, which the
    report prints as a table under the figure."""
    fig = plt.figure(figsize=(11.4, 5.4))
    gs = fig.add_gridspec(1, 2, wspace=0.12, left=0.06, right=0.985, top=0.94, bottom=0.1)
    ax1, ax2 = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1])
    e1 = draw_panel(ax1, rec, node, S_SINGLE, False, "Single setting: R2 non-directional, forward setting only")
    e2 = draw_panel(ax2, rec, node, S_DUAL, True, "Dual setting: R2 as DSDR")
    ax1.set_ylabel("Time (s)")
    ax2.set_yticklabels([])
    path = NODES[node]["path"]
    handles = [Line2D([], [], color=BLUE, lw=1.7, label="R1 (fast solid, delayed dashed)"),
               Line2D([], [], color=ORANGE, lw=1.7, label="R2 (fast solid, delayed dashed)")]
    for f, col in zip(path[:2], (AQUA, VIOLET)):
        handles.append(Line2D([], [], color=col, lw=5, alpha=0.4, label="%s %s (melting - clearing band)" % (
            f, S_DUAL["fuses"][f].replace("A055C", ""))))
    handles.append(Line2D([], [], color=INK2, lw=0.9, label="vertical lines: current through each device"))
    ax1.legend(handles=handles, loc="lower left", fontsize=7.2, frameon=True, framealpha=0.92)

    rows, labels, both = fault_rows(rec, node, zf, paper)
    cell = [[title if a.startswith("Fault") and b is None else a, "" if b is None else b, "same"] for a, b in rows]
    cell[0] = ["Fault", "%s, %s, phases %s" % (title, rec["type"], rec["phases"] or "a-b-c"), "same"]
    for k, lab in enumerate(labels):
        cell.append([lab, both[0][0][k], both[1][0][k]])
    with open_csv(os.path.join(OUT, "Case_%s_table.csv" % cid)) as f:
        w = csv.writer(f)
        w.writerow(["Quantity", "Single setting", "Dual setting (DSDR)"])
        w.writerows(cell)
    path_png = os.path.join(OUT, "Case_%s_%s.png" % (cid, title.replace(" ", "_").replace("%", "pct").replace("(", "").replace(")", "")))
    path_png = save_fig(fig, path_png, 150)
    plt.close(fig)
    return path_png, rows, labels, both, e1, e2


# ---------------------------------------------------------------------------------------------
# Summary figures
# ---------------------------------------------------------------------------------------------
def summary():
    combos = [("no-DG design fuses", CONV["fuses"]), ("final fuses", DS["fuses"])]
    res = {}
    for lab, fz in combos:
        for dual in (False, True):
            g, _ = m.classify(scheme(fz, dual), dual, 1.0)
            res[(lab, dual)] = g
    fig, ax = plt.subplots(figsize=(6.4, 3.3))
    x = [0, 1]
    w = 0.36
    single = [m.count(res[(lab, False)])[0] for lab, _ in combos]
    dual = [m.count(res[(lab, True)])[0] for lab, _ in combos]
    b1 = ax.bar([v - w / 2 for v in x], single, w * 0.94, color=BLUE, label="single setting on R2")
    b2 = ax.bar([v + w / 2 for v in x], dual, w * 0.94, color=ORANGE, label="dual setting on R2 (DSDR)")
    for bars in (b1, b2):
        for b in bars:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.5, "%d" % b.get_height(), ha="center", fontsize=9,
                    fontweight="bold")
    ax.axhline(39, color=INK2, lw=0.8, ls=":")
    ax.text(1.48, 39.3, "39 cells", fontsize=7.5, color=INK2, ha="right")
    ax.set_xticks(x)
    ax.set_xticklabels(["fuse sizes of the no-DG design", "fuse sizes after the method's revision (step 9)"])
    ax.set_ylabel("node / fault-type cells held (of 39)")
    ax.set_ylim(0, 44)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.set_title("Fuse-saving coordination with the DG connected", fontsize=10, loc="left")
    fig.tight_layout()
    p1 = save_fig(fig, os.path.join(OUT, "00_Summary.png"), 170)
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(8.6, 5.6))
    for ax, dual, title in ((axes[0], False, "Single setting on R2 (final fuse sizes)"),
                            (axes[1], True, "Dual setting on R2 - DSDR (final fuse sizes)")):
        g = res[("final fuses", dual)]
        other = res[("final fuses", not dual)]
        for xk, node in enumerate(NODE_ORDER):
            for yk, ft in enumerate(FAULT_TYPES[::-1]):
                st = g[(node, ft)]
                if st == "n/a":
                    ax.text(xk, yk, "-", ha="center", va="center", fontsize=12, color=INK2)
                    continue
                c = GOOD if st == "held" else BAD
                ax.add_patch(plt.Circle((xk, yk), 0.36, facecolor="none", edgecolor=c, lw=1.6))
                ax.text(xk, yk, "✓" if st == "held" else "✗", ha="center", va="center", fontsize=12, color=c,
                        fontweight="bold")
                if dual and other[(node, ft)] != st:
                    ax.add_patch(plt.Rectangle((xk - 0.46, yk - 0.46), 0.92, 0.92, fill=False, lw=1.3, edgecolor=ORANGE))
        ax.set_xticks(range(len(NODE_ORDER)))
        ax.set_xticklabels(NODE_ORDER)
        ax.set_yticks(range(4))
        ax.set_yticklabels(FAULT_TYPES[::-1])
        ax.set_xlim(-0.6, len(NODE_ORDER) - 0.4)
        ax.set_ylim(-0.6, 3.6)
        ax.set_aspect("equal")
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.tick_params(length=0)
        ax.set_title("%s: %d of %d held" % ((title,) + m.count(g)), fontsize=10, loc="left")
    axes[1].set_xlabel("Faulted node   (✓ held, ✗ lost, - not applicable; orange box = restored by the dual setting)")
    fig.tight_layout()
    p2 = save_fig(fig, os.path.join(OUT, "00_Grids.png"), 170)
    plt.close(fig)
    return res, p1, p2


def cells(pairs):
    out = []
    for n in NODE_ORDER:
        t = [ft for ft in FAULT_TYPES if (n, ft) in pairs]
        if t:
            out.append("%s %s" % (n, "/".join(t)))
    return ", ".join(out) or "none"


# ---------------------------------------------------------------------------------------------
def main():
    res, p_sum, p_grid = summary()
    results = []
    table = []
    for cid, title, rec, node, zf, paper in CASES:
        png, rows, labels, both, e1, e2 = case_figure(cid, title, rec, node, zf, paper)
        a1, a2 = evaluate(rec, node, A_SINGLE, False), evaluate(rec, node, A_DUAL, True)
        results.append((cid, title, zf, paper, png, e1, e2, rec, node, a1, a2))
        path = NODES[node]["path"]
        i1, i2 = m.imax(rec, "R1"), m.imax(rec, "R2")
        up = NODES[node]["zone"] == "R1"
        table.append([cid, paper, title, rec["type"], rec["phases"] or "ABC", "%g" % zf,
                      "%.0f" % (m.imax(rec, path[0]) if path else max(rec["ifault"])),
                      "%.0f" % i1, "forward", "%.0f" % i2, "reverse" if up else "forward",
                      both[0][0][1], both[0][0][2], both[1][0][2], both[1][0][3], both[0][0][5].split(":")[0],
                      both[1][0][5].split(":")[0], e1["reason"].split(";")[0], e2["reason"].split(";")[0],
                      "HELD" if a1["held"] else "LOST", "HELD" if a2["held"] else "LOST"])
        print("Case %s  %-36s Zf %-4g R1 %5.0f A fwd  R2 %5.0f A %-7s single: %-4s dual: %-4s" % (
            cid, title, zf, i1, i2, "reverse" if up else "forward", "held" if e1["held"] else "LOST",
            "held" if e2["held"] else "LOST"))
    with open_csv(os.path.join(OUT, "Fault_table.csv")) as f:
        w = csv.writer(f)
        w.writerow(["Case", "Figure", "Fault", "Type", "Phases", "Zf (ohm)", "Fault-path current (A)", "I R1 (A)",
                    "R1 direction", "I R2 (A)", "R2 direction", "R1 fast / delayed", "R2 fast / delayed, single setting",
                    "R2 fast / delayed, dual setting", "Primary fuse melts / clears", "Fuse saving, single setting",
                    "Fuse saving, dual setting", "Reason if lost, single", "Reason if lost, dual",
                    "Fuse saving with the no-DG-design fuses, single setting",
                    "Fuse saving with the no-DG-design fuses, dual setting"])
        w.writerows(table)

    # ---- PDF ------------------------------------------------------------------------------------
    n = {k: m.count(v)[0] for k, v in res.items()}
    a_s, a_d = n[("no-DG design fuses", False)], n[("no-DG design fuses", True)]
    f_s, f_d = n[("final fuses", False)], n[("final fuses", True)]
    gs, gd = res[("final fuses", False)], res[("final fuses", True)]
    restored = {k for k in gs if gs[k] == "lost" and gd[k] == "held"}
    still = {k for k in gd if gd[k] == "lost"}
    ss = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontSize=15, spaceAfter=6, textColor=colors.HexColor("#1b4f93"))
    H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=11.5, spaceBefore=6, spaceAfter=3, textColor=colors.HexColor("#1b4f93"))
    BODY = ParagraphStyle("B", parent=ss["BodyText"], fontSize=9.5, leading=12.8)
    CELL = ParagraphStyle("C", parent=BODY, fontSize=8, leading=9.6)
    HEAD = ParagraphStyle("h", parent=CELL, textColor=colors.white, fontName="Helvetica-Bold")

    def img(path, width):
        im = Image(path)
        return Image(path, width=width, height=width * im.imageHeight / float(im.imageWidth))

    def tbl(data, widths, colour=None):
        data = [[Paragraph(str(c), HEAD if r == 0 else CELL) for c in row] for r, row in enumerate(data)]
        t = Table(data, colWidths=widths, repeatRows=1)
        st = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b9b8b3")), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1b4f93")),
              ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
        for c, r, col in (colour or []):
            st.append(("BACKGROUND", (c, r), (c, r), col))
        t.setStyle(TableStyle(st))
        return t

    fw, rv = DS["R2fw"], DS["R2rv"]
    story = [Paragraph("Coordination diagrams: single setting vs dual setting on R2", ParagraphStyle("T", parent=H1, fontSize=19, leading=23)),
             Paragraph("IEEE 13-node feeder, 4.05 MVA DG at node 692 - DSDR recloser-fuse coordination study", H2),
             Paragraph("<b>What is compared.</b> The existing scheme has one setting on the mid-line recloser R2: it is "
                       "non-directional and uses its forward setting for every fault, including the DG's reverse current for "
                       "faults above it. As a dual-setting directional recloser (DSDR) R2 keeps the forward setting for faults "
                       "below it and uses a second, reverse setting (eq. 12) for faults above it. "
                       "<b>Both panels of every diagram use the same fuse sizes (the final design)</b>, so the only "
                       "difference between left and right is R2's setting.", BODY),
             Spacer(1, 0.15 * cm),
             tbl([["Device", "Setting", "Pickup / curve start", "Time dial (fast / delayed)"],
                  ["R1 (GE IAC77, at RG60)", "one setting, forward", "720 A; curve from 1080 A", "0.5 / 10"],
                  ["R2 forward (CDG34, at 671)", "used by both schemes", "plug %.0f / %.0f A; curve from %.0f / %.0f A" % (
                      fw["is_f"], fw["is_d"], 2 * fw["is_f"], 2 * fw["is_d"]), "%.1f / %.1f" % (fw["tms_f"], fw["tms_d"])],
                  ["R2 reverse (CDG34 curve)", "dual setting only", "plug %.0f / %.0f A; curve from %.0f / %.0f A  (eq. 12: 1.25 x %.1f A = %.0f A)" % (
                      rv["is_f"], rv["is_d"], 2 * rv["is_f"], 2 * rv["is_d"], rv["i_nom_rv"], rv["ip_eq12"]),
                   "%.1f / %.1f" % (rv["tms_f"], rv["tms_d"])]],
                 [5.5 * cm, 4.2 * cm, 11.5 * cm, 4.3 * cm]),
             Spacer(1, 0.15 * cm),
             Paragraph("<b>Fault impedance.</b> Each case states its fault impedance Zf: 0 ohm (bolted) or the value used "
                       "for that figure (1.0 ohm for Figs. 9 and 11, 1.5 ohm for Fig. 12). Currents are "
                       "initial symmetrical short-circuit currents from PowerFactory (complete method), largest phase. "
                       "Direction: + forward = away from the grid; for faults above R2 the current through R2 is the "
                       "DG's contribution and flows in reverse (confirmed for all 48 bolted faults above R2 in the "
                       "short-circuit database).", BODY),
             Paragraph("<b>Fuse saving holds</b> when every recloser that feeds the fault trips on its fast curve before the "
                       "primary fuse melts, the fuse clears before the recloser's delayed trip, and the backup fuse keeps the "
                       "75 % margin of eq. (8). No breaker time or safety margin is added.", BODY),
             Paragraph("Fault table", H2)]
    data = [["Case", "Figure", "Fault", "Zf (ohm)", "Fault-path current", "R1 current, direction", "R2 current, direction",
             "R2 fast: single -> dual", "Fuse melts", "Single setting", "Dual setting", "No-DG-design fuses: single / dual"]]
    colr = []
    for k, (cid, title, zf, paper, png, e1, e2, rec, node, a1, a2) in enumerate(results, 1):
        row = table[k - 1]
        data.append([cid, paper, "%s (%s %s)" % (title, row[3], row[4]), row[5], row[6] + " A", row[7] + " A, forward",
                     "%s A, %s" % (row[9], row[10]), "%s -> %s" % (row[12].split(" / ")[0], row[13].split(" / ")[0]),
                     row[14].split(": ")[-1].split(" / ")[0] if ":" in row[14] else "-",
                     "held" if e1["held"] else "LOST", "held" if e2["held"] else "LOST",
                     "%s / %s" % ("held" if a1["held"] else "LOST", "held" if a2["held"] else "LOST")])
        colr += [(9, k, colors.HexColor("#dff3df" if e1["held"] else "#fbe0e0")),
                 (10, k, colors.HexColor("#dff3df" if e2["held"] else "#fbe0e0"))]
    lost_both = [r for r in results if not r[5]["held"] and not r[6]["held"]]
    story += [tbl(data, [1.0 * cm, 1.9 * cm, 4.6 * cm, 1.1 * cm, 2.0 * cm, 2.6 * cm, 2.7 * cm, 2.9 * cm, 1.6 * cm, 1.5 * cm, 1.5 * cm, 2.7 * cm],
                  colour=colr),
              Paragraph("Single / dual setting columns: final fuse sizes (as in the diagrams). Last column: the same faults with the "
                        "fuse sizes of the no-DG design. " + ("Cases lost under both settings: " + "; ".join(
                            "%s - %s" % (r[0], r[6]["reason"].split(";")[0]) for r in lost_both) + "." if lost_both else ""),
                        ParagraphStyle("n", parent=BODY, fontSize=8, leading=10, textColor=colors.HexColor("#52514e"))),
              PageBreak(),
              Paragraph("All 39 node / fault-type cells", H1),
              Table([[img(p_grid, 15.5 * cm), img(p_sum, 10.2 * cm)]], colWidths=[15.8 * cm, 10.4 * cm]),
              Paragraph("Restored by the dual setting (final fuses): %s. Still lost: %s." % (cells(restored), cells(still)), BODY),
              PageBreak()]
    for r_ in results:
        story += [img(r_[4], 23.4 * cm), PageBreak()]

    # ---- time-sequence check of all 39 cells ----------------------------------------------------
    sq_grids, sq_rows = SQ.run()
    p_seq = SQ.figure(sq_grids, os.path.join(OUT, "10_Sequence_check.png"))
    sq = SQ.summary(sq_grids)
    s_up, d_up, s_dn = sq[(False, "above")], sq[(True, "above")], sq[(False, "below")]
    strict_only = {k for k in restored if k in s_up["held"]}
    genuine = {k for k in restored if k not in s_up["held"]}
    story += [Paragraph("Time-sequence check of all 39 cells", H1),
              Paragraph("The strict rule of Figs. 14 and 17 compares every recloser's fast time with the fuse's melting time at "
                        "the full fault current. Here each fault is followed in time: the fuse carries the full current until "
                        "the first recloser opens, then only the other source's contribution; the fuse is saved if its heat "
                        "stays below 100 % of melting when the fault is cut off. The delayed-trip and series-fuse conditions "
                        "are unchanged. Assumption: after one recloser opens, the other source's current stays at its "
                        "contribution during the fault; nothing is simulated.", BODY),
              img(p_seq, 16.2 * cm),
              Paragraph("<b>Faults above R2 (%d cells).</b> Strict rule: %d held with one setting, %d with the dual setting. "
                        "Time sequence: %d and %d. Of the %d cells the strict rule shows as restored, %d are restored in the "
                        "time sequence as well (%s): there the single-setting R2 does not trip on the DG's reverse current at "
                        "all and the DG keeps feeding the fault. In the other %d (%s) the fuse survives with one setting too "
                        "(fuse heat 32-71 %%): R1 opens first and the DG's remaining current is too small to melt the fuse "
                        "before R2 opens. There the dual setting shortens the time the DG feeds the fault and lowers the fuse heat."
                        % (s_up["n"], s_up["strict"], d_up["strict"], len(s_up["held"]), len(d_up["held"]), len(restored),
                           len(genuine), cells(genuine), len(strict_only), cells(strict_only)), BODY),
              Paragraph("<b>Faults below R2 (%d cells).</b> In all of them the DG at 692 feeds the fault directly: no recloser "
                        "lies between the DG and the fault, so after R2 has opened the fault stays energised under either "
                        "setting. The strict rule does not look at this. Fuse saving below R2 therefore "
                        "relies on the DG's own protection disconnecting it during the dead time, which this model does "
                        "not include." % s_dn["n"], BODY),
              PageBreak()]

    imp = [r for r in results if r[2] > 0 and NODES[r[8]]["zone"] == "R1"]
    story += [Paragraph("Conclusion: how the DSDR improves coordination", H1)]
    for s_ in [
        "<b>1. The problem is the direction and size of the current through R2.</b> For a fault above R2 (632, 633, 645, "
        "646, DL) the fuse carries the grid's and the DG's current together (3-6 kA), but R2 carries only the DG's share, "
        "in reverse (0.5-2.0 kA). With one setting R2 measures that small reverse current against a forward setting sized for "
        "its 470 A forward load: its fast curve only starts at %.0f A and its delayed curve at %.0f A." % (2 * fw["is_f"], 2 * fw["is_d"]),
        "<b>2. With one setting R2 is blind or slow for the DG infeed.</b> For ground faults the DG's reverse current is "
        "470-650 A, at or below the start of the forward curve: R2 does not pick up (case 07) or needs about 1 s (case 08), "
        "so the DG keeps feeding a temporary fault and the fuse is lost.",
        "<b>3. The reverse setting matches the reverse duty.</b> Its pickup follows eq. (12) from the reverse load current "
        "(1.25 x %.1f A = %.0f A; curve from %.0f A), half the forward value. The same DG currents are then cleared in "
        "0.2-0.4 s for ground faults and in under 0.1 s for phase faults (case 06: %s -> %s), before the fuse melts." % (
            rv["i_nom_rv"], rv["ip_eq12"], 2 * rv["is_f"],
            tt(m.t_r2(m.imax(figrec("Fig15"), "R2"), S_SINGLE, "R2fw", "f")), tt(m.t_r2(m.imax(figrec("Fig15"), "R2"), S_DUAL, "R2rv", "f"))),
        "<b>4. Nothing is given up in the forward direction.</b> For faults below R2 (cases 01, 02, 09) both schemes use the "
        "same forward setting and give the same times; the two settings are independent.",
        "<b>5. In numbers.</b> With the DG connected and the same fuses, fuse saving holds in %d of 39 cells with one "
        "setting and in %d of 39 with the dual setting. The %d restored cells (%s) are all faults above R2, where R2 "
        "sees reverse current." % (f_s, f_d, len(restored), cells(restored)),
        "<b>6. The limit of the claim.</b> The dual setting only acts on R2. It cannot speed up R1, which is at its minimum "
        "dial, and it cannot help where a fuse melts faster than any recloser curve. With the fuse sizes of the no-DG design "
        "the dual setting restores only %d cell (%d -> %d of 39); the method's fuse revision (step 9) is needed as well "
        "(%d -> %d with one setting, %d with the dual setting). The remaining lost cell (%s) is a fault below R2 on the "
        "forward setting, which the DSDR does not change." % (a_d - a_s, a_s, a_d, a_s, f_s, f_d, cells(still)),
        "<b>7. Faults through a fault impedance.</b> " + " ".join(
            "Case %s (%s, Zf %.1f ohm): R2's fast trip improves from %s to %s, but fuse saving is %s with the final fuses "
            "(%s) and %s with the no-DG-design fuses." % (
                r[0], r[1], r[2], tt(m.t_r2(m.imax(r[7], "R2"), S_SINGLE, "R2fw", "f")),
                tt(m.t_r2(m.imax(r[7], "R2"), S_DUAL, "R2rv", "f")), "held" if r[6]["held"] else "lost",
                r[6]["reason"].split(";")[0] if not r[6]["held"] else "all conditions met",
                "held" if r[10]["held"] else "lost") for r in imp) +
        " The fuse revision was judged on bolted faults, as Figs. 14 and 17 are; at the lower currents of resistive faults the "
        "larger fuses clear slowly. This is a limit of the fuse sizes, not of the dual setting.",
        "<b>8. Time-sequence check.</b> Followed in time, fuse saving above R2 holds in %d of %d cells with one setting and "
        "in %d with the dual setting. The cells that are restored beyond doubt are the ground faults %s, where the "
        "single-setting R2 never trips on the DG's reverse current. For the phase faults at 633 and the ground fault at DL "
        "the strict rule overstates the loss: the fuse would survive with one setting too, and the dual setting adds margin. "
        "Below R2 the DG feeds every fault directly, whatever R2's setting." % (
            len(s_up["held"]), s_up["n"], len(d_up["held"]), cells(genuine)),
        "<b>Conclusion.</b> The DSDR improves coordination because it lets R2 detect and interrupt the DG's reverse fault "
        "contribution with a setting sized for that contribution, instead of a forward setting sized for the grid. That "
        "restores the fuse-saving scheme for every fault above R2 without touching the forward coordination. It is a "
        "necessary part of the solution in this feeder, but not sufficient alone: it works together with the fuse revision.",
    ]:
        story.append(Paragraph(s_, BODY))
        story.append(Spacer(1, 0.12 * cm))

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#52514e"))
        canvas.drawString(1.5 * cm, 0.8 * cm, "Coordination diagrams - single vs dual setting on R2, IEEE 13-node feeder")
        canvas.drawRightString(landscape(A4)[0] - 1.5 * cm, 0.8 * cm, "page %d" % doc.page)
        canvas.restoreState()

    pdf = os.path.join(OUT, "Coordination_Diagrams.pdf")
    try:
        open(pdf, "ab").close()
    except OSError:
        LOCKED.append(os.path.basename(pdf))
        pdf = pdf[:-4] + "_new.pdf"
    SimpleDocTemplate(pdf, pagesize=landscape(A4), leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.2 * cm,
                      bottomMargin=1.3 * cm, title="Coordination diagrams - single vs dual setting").build(
        story, onFirstPage=on_page, onLaterPages=on_page)
    if LOCKED:
        print("NOTE: open in another program, new version written as *_new: " + ", ".join(LOCKED))
    print("PDF:", pdf)
    print("cells held with DG: no-DG fuses %d -> %d, final fuses %d -> %d (single -> dual)" % (a_s, a_d, f_s, f_d))
    print("restored:", cells(restored), "| still lost:", cells(still))
    print("Saved", OUT)


if __name__ == "__main__":
    main()
