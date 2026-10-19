"""
Step 3 - protection design by the paper's method (Section II, Fig. 5) and coordination analysis.
Pure Python on results/studies.json (no PowerFactory needed).

The paper's workflow, in three stages:

 A  Design without DG (conventional fuse-saving scheme)
      step 1  load flow -> Inom (Table II)
      step 3  pickups by eq. (3), Ip = OLF x Inom, realised with the relay's CT and taps
              R1  IAC77B801A, TDS 0.5 (fast) / 10 (delayed) - paper
              R2  CDG34 (CDG14 table, curve from 2 x plug).  Fast plug = Ip/2 (curve starts at Ip,
                  as in Figs. 8 and 13), delayed plug = Ip.  Fast TMS = lowest dial 0.1; delayed
                  TMS = highest dial that stays 10 cycles below R1's delayed curve.
      step 4  fuse coefficients b_i, eqs. (6)-(9) -> Table III (i = 1 closest to the fault, [25])
      step 5  fault study; steps 8-10 until every fault is coordinated without DG
 B  DG added (4.05 MVA at 692), settings unchanged -> Fig. 14, Figs. 8-13
 C  R2 as DSDR: reverse pickup eq. (12), TMS revised by If,Rec / If,Fuse (step 8);
    fuse revision (step 9) where a dial limit is reached -> Fig. 17, Table IV, Figs. 15-16

Coordination of one fault ("held"):
  * every recloser that interrupts a source feeding the fault (R1 for the grid in R1's zone,
    R2 for the grid in R2's zone, R2 in reverse for the DG in R1's zone) picks up, trips on its
    fast curve before the primary fuse melts (MMT), and on its delayed curve after the fuse clears
    (TCT);
  * series fuses: TCT(primary) < 0.75 MMT(backup), eq. (8);
  * R2-zone faults: R2 fast before R1 fast and R2 delayed >= 10 cycles before R1 delayed.
A cell of Figs. 14 / 17 is held only if every phase combination of that fault type holds.
"""

import copy
import csv
import json
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from curves import IAC, CDG, Fuse, INF, _loglog
from protection_data import (FUSES, NODES, NODE_ORDER, FAULT_TYPES, TABLE2_BRANCHES, PAPER_TABLE2,
                             PAPER_TABLE3, PAPER_TABLE4, PAPER_FIG14_LOST, OLF, A_FUSE, T_RECL_MIN)

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
FIG = os.path.join(RES, "figures")
os.makedirs(FIG, exist_ok=True)

D = json.load(open(os.path.join(RES, "studies.json")))
IACC, CDGC = IAC(D["curves"]["iac"]), CDG(D["curves"]["cdg"])
FTYPE = {t: Fuse(v) for t, v in D["curves"]["fuses"].items()}
A055C = sorted([t for t in FTYPE if t.startswith("A055C")], key=lambda t: FTYPE[t].irat)
FAULTS = D["faults"]
LF = D["loadflow"]
REPORT = []

CDG_TAPS = [1.0, 1.2, 1.5, 2.0, 2.4, 3.0, 4.0]                     # CDG34-5A (1-4), secondary A
IAC_TAPS = [0.5, 0.6, 0.7, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5, 3.0, 4.0]   # IAC77B801A, secondary A
CT_R1, CT_R2, CT_R2RV = 900.0, 1000.0, 500.0
TMS_MIN, TMS_MAX = 0.1, 1.0            # CDG34 dial range
# The DSDR keeps the CDG34 extremely-inverse curve (paper, Section IV-A).  That curve is a table
# for TMS 0.1-1.0 whose times are not proportional to TMS, so the dial is not extended below 0.1
# (PowerFactory's linear extrapolation below 0.1 even gives negative times at low multiples).
DSDR_TMS_MIN = TMS_MIN


def say(s=""):
    print(s)
    REPORT.append(s)


def imax(rec, point):
    return max(rec["I"][point])


def fmt(t, nd=3):
    return "no trip" if t == INF else ("%.*f" % (nd, t))


def save_png(fig, fname):
    """Save a figure; if the file is open in a viewer (locked on Windows) write <name>_new.png."""
    path = os.path.join(FIG, fname)
    alt = path[:-4] + "_new.png"
    try:
        fig.savefig(path, dpi=160)
        if os.path.isfile(alt):
            os.remove(alt)
    except OSError:
        fig.savefig(alt, dpi=160)
        print("NOTE: %s is open in another program; the new figure is %s" % (fname, os.path.basename(alt)))


CMP = os.path.join(RES, "comparison")             # values of the reference paper, for the comparison only
os.makedirs(CMP, exist_ok=True)


def write_csv(name, header, rows):
    path = os.path.join(RES, name)
    try:
        f = open(path, "w", newline="")
    except PermissionError:                      # open in Excel: the old file stays, the new one goes beside it
        f = open(path[:-4] + "_new.csv", "w", newline="")
        print("NOTE: %s is open in another program; the new table is %s_new.csv" % (name, name[:-4]))
    with f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def faults(case="max", dg=None, node=None, ftype=None, zone=None):
    return [r for r in FAULTS if r["case"] == case and (dg is None or r["dg"] == dg)
            and (node is None or r["where"] == node) and (ftype is None or r["type"] == ftype)
            and (zone is None or (r["where"] in NODES and NODES[r["where"]]["zone"] == zone
                                  and not NODES[r["where"]].get("lv")))]


# =============================================================================================
# Operating times
# =============================================================================================
def t_r1(i, s, mode):
    return IACC.t(i, s["R1"]["ip"], s["R1"]["tds_" + mode])


def t_r2(i, s, unit, mode):
    u = s[unit]
    return CDGC.t(i, u["is_" + mode], u["tms_" + mode])


def fuse(s, name):
    return FTYPE[s["fuses"][name]]


# =============================================================================================
# Coordination of one fault
# =============================================================================================
def evaluate(r, s, dsdr):
    node = r["where"]
    info = NODES[node]
    i1, i2 = imax(r, "R1"), imax(r, "R2")
    reasons, reclosers = [], []                       # reclosers: (name, unit, I, t_fast, t_delayed)
    if info["zone"] == "R2":
        reclosers.append(("R2", "R2fw", i2, t_r2(i2, s, "R2fw", "f"), t_r2(i2, s, "R2fw", "d")))
        t1f, t1d = t_r1(i1, s, "f"), t_r1(i1, s, "d")
        if reclosers[0][3] < INF and not reclosers[0][3] < t1f:
            reasons.append("R2 fast (%.3f s) not before R1 fast (%s s)" % (reclosers[0][3], fmt(t1f)))
        if reclosers[0][4] < INF and t1d < INF and not t1d - reclosers[0][4] >= T_RECL_MIN:
            reasons.append("R2/R1 delayed margin %.3f s < 10 cycles" % (t1d - reclosers[0][4]))
    else:
        reclosers.append(("R1", "R1", i1, t_r1(i1, s, "f"), t_r1(i1, s, "d")))
        if r["dg"] > 0 and i2 >= s["dg_infeed"]:        # DG infeed above the eq. (12) pickup
            unit = "R2rv" if dsdr else "R2fw"
            reclosers.append(("R2 rev" if dsdr else "R2", unit, i2, t_r2(i2, s, unit, "f"),
                              t_r2(i2, s, unit, "d")))
    res = dict(node=node, type=r["type"], phases=r["phases"], dg=r["dg"], reclosers=reclosers,
               fuse=None, cti_f=None, cti_d=None, flags=set())
    for name, unit, i, tf, td in reclosers:
        if tf == INF:
            reasons.append("%s does not pick up (%.0f A)" % (name, i))
            res["flags"].add(("nopickup", unit))
    path = info["path"]
    if path:
        p = path[0]
        ip_ = imax(r, p)
        f = fuse(s, p)
        mmt, tct = f.mmt(ip_), f.tct(ip_)
        tf = max(x[3] for x in reclosers)
        td = min(x[4] for x in reclosers)
        res.update(fuse=p, i_fuse=ip_, mmt=mmt, tct=tct, cti_f=mmt - tf, cti_d=td - tct)
        for name, unit, i, tfk, tdk in reclosers:
            if tfk < INF and not tfk < mmt:
                reasons.append("%s melts (%.3f s) before %s fast (%.3f s)" % (p, mmt, name, tfk))
                res["flags"].add(("fast", unit))
            if tdk < INF and not tct < tdk:
                reasons.append("%s delayed (%.3f s) before %s clears (%.3f s)" % (name, tdk, p, tct))
                res["flags"].add(("delayed", unit))
        for b in path[1:]:
            mb = fuse(s, b).mmt(imax(r, b))
            if not tct < 0.75 * mb:
                reasons.append("series %s/%s: TCT %.3f > 0.75 x MMT %.3f" % (p, b, tct, 0.75 * mb))
                res["flags"].add(("series", b))
    res["held"] = not reasons
    res["reason"] = "; ".join(reasons)
    return res


def classify(s, dsdr, dg):
    grid, detail = {}, []
    for node in NODE_ORDER:
        for ft in FAULT_TYPES:
            recs = faults("max", dg, node, ft)
            if NODES[node].get("lv") or not recs:
                grid[(node, ft)] = "n/a"
                continue
            ev = [evaluate(r, s, dsdr) for r in recs]
            detail += ev
            grid[(node, ft)] = "held" if all(e["held"] for e in ev) else "lost"
    return grid, detail


def count(grid):
    return sum(v == "held" for v in grid.values()), sum(v != "n/a" for v in grid.values())


# =============================================================================================
# Steps 8-10 - revise the recloser dials, then the fuse sizes
# =============================================================================================
def step8(s, dsdr, dg, units, log):
    """Revise TMS of the given R2 units by If,Rec / If,Fuse until held or at a limit."""
    for _ in range(40):
        changed = False
        ev = [e for e in classify(s, dsdr, dg)[1] if not e["held"]]
        for unit in units:
            fast = [e for e in ev if ("fast", unit) in e["flags"]]
            slow = [e for e in ev if ("delayed", unit) in e["flags"]]
            if fast and s[unit]["tms_f"] > s[unit]["tms_min"]:
                k = min(next(x[2] for x in e["reclosers"] if x[1] == unit) / e["i_fuse"] for e in fast)
                new = max(s[unit]["tms_min"], round(s[unit]["tms_f"] * k, 3))
                log.append("step 8: %s fast TMS %.3f x If,Rec/If,Fuse (%.3f) -> %.3f" % (unit, s[unit]["tms_f"], k, new))
                s[unit]["tms_f"], changed = new, True
            if slow and s[unit]["tms_d"] < s[unit]["tms_d_max"]:
                k = max(e["i_fuse"] / next(x[2] for x in e["reclosers"] if x[1] == unit) for e in slow)
                new = min(s[unit]["tms_d_max"], round(s[unit]["tms_d"] * max(k, 1.05), 3))
                log.append("step 8: %s delayed TMS %.3f x If,Fuse/If,Rec (%.3f) -> %.3f" % (unit, s[unit]["tms_d"], k, new))
                s[unit]["tms_d"], changed = new, True
        if not changed:
            return


def resize(s, name, step, log, why):
    t = s["fuses"][name]
    if t not in A055C:
        return False
    k = A055C.index(t) + step
    if not 0 <= k < len(A055C) or FTYPE[A055C[k]].irat < 100:
        return False
    s["fuses"][name] = A055C[k]
    log.append("step 9/10: %s %s -> %s (%s)" % (name, t, A055C[k], why))
    return True


def n_lost(s, dsdr, dgs):
    return sum(not e["held"] for dg in dgs for e in classify(s, dsdr, dg)[1])


def step9(s, dsdr, dgs, log):
    """Fuse revision (step 9) and series-fuse revision (step 10).  Candidate moves from the
    failures: primary fuse one A055C size up (melts before a recloser's fast curve at its dial
    limit) or down (clears after the delayed curve), or for eq. (8) the backup one size up or the
    primary one size down.  The move that removes most lost cases is applied; repeat."""
    for _ in range(30):
        base = n_lost(s, dsdr, dgs)
        if base == 0:
            return
        moves = set()
        for dg in dgs:
            for e in classify(s, dsdr, dg)[1]:
                path = NODES[e["node"]]["path"]
                for kind, what in e["flags"]:
                    where = "%s %s" % (e["node"], e["type"])
                    for k in (1, 2, 3):
                        if kind == "fast":
                            moves.add(((e["fuse"], k),))
                            for k2 in (1, 2, 3):
                                moves.add(((e["fuse"], k),) + tuple((b, k2) for b in path[1:]))
                        elif kind == "delayed":
                            moves.add(((e["fuse"], -k),))
                        elif kind == "series":
                            moves.add(((what, k),))
                            moves.add(((e["fuse"], -k),))
        best = None
        for mv in sorted(moves):
            trial = copy.deepcopy(s)
            if not all(resize(trial, name, k, [], "") for name, k in mv):
                continue
            n = n_lost(trial, dsdr, dgs)
            size = sum(abs(k) for _, k in mv)
            if n < base and (best is None or (n, size) < (best[0], best[1])):
                best = (n, size, mv)
        if best is None:
            return
        for name, k in best[2]:
            resize(s, name, k, log, "lost cases %d -> %d" % (base, best[0]))



# =============================================================================================
# Stage A - settings without DG
# =============================================================================================
def nearest_tap(target, taps, ratio):
    return min(taps, key=lambda t: abs(t * ratio - target))


def table2():
    rows = []
    for frm, to, br, side, nodes in TABLE2_BRANCHES:
        key = "%s-%s" % (frm, to)
        inom = max(LF["dg_out"][key])
        fmax = [imax(r, key) for r in faults("max", 0.0) if r["where"] in nodes]
        fmin = [imax(r, key) for r in faults("min", 0.0) if r["where"] in nodes]
        rows.append([frm, to, round(inom, 1), round(min(fmin) / 1e3, 2), round(max(fmax) / 1e3, 2)])
    write_csv("Table_II.csv", ["From", "To", "Inom (A)", "If,min (kA)", "If,max (kA)"], rows)
    write_csv(os.path.join("comparison", "Table_II_vs_paper.csv"),
              ["From", "To", "Inom (A)", "If,min (kA)", "If,max (kA)", "paper Inom (A)", "paper If,min (kA)",
               "paper If,max (kA)"], [r + list(PAPER_TABLE2[(r[0], r[1])]) for r in rows])
    say("\nTABLE II - rated (load flow), minimum (LG through 3 ohm, farthest node) and maximum "
        "(bolted, nearest node) branch current, DG out")
    say("  %-8s %-5s %8s | %8s | %8s" % ("from", "to", "Inom A", "Ifmin kA", "Ifmax kA"))
    for r in rows:
        say("  %-8s %-5s %8.1f | %8.2f | %8.2f" % (r[0], r[1], r[2], r[3], r[4]))
    return {"%s-%s" % (r[0], r[1]): r for r in rows}


def design_reclosers(t2):
    s = {"fuses": {n: t for n, (_, t, _) in FUSES.items()}}
    inom1 = t2["RG60-632"][2]
    tap = nearest_tap(OLF * inom1, IAC_TAPS, CT_R1 / 5)
    s["R1"] = dict(ct=CT_R1, tap=tap, ip=tap * CT_R1 / 5, ip_eq3=OLF * inom1, tds_f=0.5, tds_d=10.0)
    inom2 = t2["632-671"][2]
    ip = OLF * inom2
    tf, td = nearest_tap(ip / 2, CDG_TAPS, CT_R2 / 5), nearest_tap(ip, CDG_TAPS, CT_R2 / 5)
    fw = dict(ct=CT_R2, ip_eq3=ip, tap_f=tf, tap_d=td, is_f=tf * CT_R2 / 5, is_d=td * CT_R2 / 5,
              tms_f=TMS_MIN, tms_d=None, tms_min=TMS_MIN)
    for k in range(int(TMS_MAX * 100), 4, -1):            # highest delayed dial below R1 - 10 cycles
        fw["tms_d"] = k / 100.0
        if all(t_r2(imax(r, "R2"), {"R2fw": fw}, "R2fw", "d") == INF or
               t_r1(imax(r, "R1"), s, "d") - t_r2(imax(r, "R2"), {"R2fw": fw}, "R2fw", "d") >= T_RECL_MIN
               for dg in (0.0, 1.0) for r in faults("max", dg, zone="R2")):
            break
    fw["tms_d_max"] = fw["tms_d"]
    s["R2fw"] = fw
    # a DG infeed through R2 counts as a fault contribution above the eq. (12) pickup
    s["dg_infeed"] = OLF * max(LF["dg_in"]["R2"])
    say("\nSTAGE A - SETTINGS WITHOUT DG (step 3)")
    say("  R1  GE IAC77B801A: Inom %.1f A -> Ip = 1.25 Inom = %.1f A -> CT 900/5, tap %.1f A = %.0f A; "
        "TDS 0.5 (fast) / 10 (delayed)" % (inom1, OLF * inom1, s["R1"]["tap"], s["R1"]["ip"]))
    say("  R2  GE/Alstom CDG34 (forward): Inom %.1f A -> Ip = %.1f A -> CT 1000/5; fast plug %.1f A = %.0f A "
        "(curve from %.0f A), delayed plug %.1f A = %.0f A (curve from %.0f A); TMS %.2f / %.2f" % (
            inom2, ip, tf, fw["is_f"], 2 * fw["is_f"], td, fw["is_d"], 2 * fw["is_d"], fw["tms_f"], fw["tms_d"]))
    say("      delayed TMS %.2f = highest dial keeping R2 >= 10 cycles below R1 for all R2-zone faults" % fw["tms_d"])
    return s


# =============================================================================================
# Table III
# =============================================================================================
FUSE_PATHS = {   # longest series path through each fuse (fault first), node below the fuse
    "F632": ("645", ["F646", "F632"]), "F633": ("633", ["F633"]), "F634": ("634", ["F634", "F633"]),
    "F645": ("645", ["F645", "F632"]), "F646": ("646", ["F646", "F632"]), "F-DL": ("DL", ["F-DL"]),
    "F671": ("671", ["F671"]), "F671-1": ("692", ["F675", "F692-R", "F671-1"]),
    "F692": ("692", ["F692", "F671-1"]), "F692-R": ("675", ["F675", "F692-R", "F671-1"]),
    "F675": ("675", ["F675", "F692-R", "F671-1"]), "F671-2": ("684", ["F611", "F684", "F671-2"]),
    "F684": ("611", ["F611", "F684", "F671-2"]), "F611": ("611", ["F611", "F684", "F671-2"]),
    "F652": ("652", ["F652", "F671-2"]),
}


def table3(s):
    rows = []
    say("\nTABLE III - fuse coefficient b_i, eq. (9), a_i = -1.8, at the maximum fault current below the fuse (DG out)")
    say("  %-7s %7s %4s %7s %7s %8s | %6s | %s" % ("fuse", "If A", "i/z", "t_F s", "t_D s", "t_fuse",
                                                 "b_i", "b_i of the installed fuse"))
    cmp_rows = []
    for f, (node, path) in FUSE_PATHS.items():
        recs = faults("max", 0.0, node)
        i = max(max(r["ifault"]) for r in recs)
        i_rel = i * (0.48 / 4.16) if NODES[node].get("lv") else i          # F634: recloser sees HV current
        if NODES[node]["zone"] == "R1":
            tf, td = t_r1(i_rel, s, "f"), t_r1(i_rel, s, "d")
        else:
            tf, td = t_r2(i_rel, s, "R2fw", "f"), t_r2(i_rel, s, "R2fw", "d")
        z, idx = len(path), path.index(f) + 1
        tgt = tf + idx / (z + 1.0) * (td - tf)
        tgt_rev = tf + (z + 1 - idx) / (z + 1.0) * (td - tf)
        b = math.log10(tgt) - A_FUSE * math.log10(i)
        b_rev = math.log10(tgt_rev) - A_FUSE * math.log10(i)
        mmt = fuse(s, f).mmt(i)
        b_fit = math.log10(mmt) - A_FUSE * math.log10(i) if 0 < mmt < INF else float("nan")
        base = [f, round(i), "%d/%d" % (idx, z), round(tf, 3), round(td, 3), round(tgt, 3), round(b, 2)]
        rows.append(base + [round(b_fit, 2), s["fuses"][f], fmt(mmt), fmt(fuse(s, f).tct(i))])
        cmp_rows.append(base + [round(b_rev, 2), PAPER_TABLE3[f]] + rows[-1][7:])
        say("  %-7s %7.0f %4s %7.3f %7.3f %8.3f | %6.2f | %.2f  (%s)" % (*rows[-1][:8], s["fuses"][f]))
    write_csv("Table_III.csv", ["Fuse", "If (A)", "i/z", "t_fast (s)", "t_delayed (s)", "t_fuse eq.(9) (s)",
                                "b_i (eq. 9, i=1 closest to fault)", "b_i of installed fuse at If", "installed fuse",
                                "t_MMT of installed fuse at If (s)", "t_TCT of installed fuse at If (s)"], rows)
    write_csv(os.path.join("comparison", "Table_III_vs_paper.csv"),
              ["Fuse", "If (A)", "i/z", "t_fast (s)", "t_delayed (s)", "t_fuse eq.(9) (s)",
               "b_i (i=1 closest to fault, ref. [25])", "b_i (i counted from source)", "paper b_i",
               "b_i of installed fuse at If", "installed fuse", "t_MMT of installed fuse at If (s)",
               "t_TCT of installed fuse at If (s)"], cmp_rows)
    return rows


# =============================================================================================
# Figures
# =============================================================================================
PAL = dict(blue="#2a78d6", orange="#eb6834", aqua="#1baf7a", violet="#4a3aa7", magenta="#e87ba4",
           green="#008300", good="#0ca30c", critical="#d03b3b", ink="#0b0b0b", ink2="#52514e",
           grid="#d9d8d4", surface="#fcfcfb")
plt.rcParams.update({"font.size": 9, "axes.edgecolor": PAL["ink2"], "axes.labelcolor": PAL["ink"],
                     "text.color": PAL["ink"], "xtick.color": PAL["ink2"], "ytick.color": PAL["ink2"],
                     "figure.facecolor": PAL["surface"], "axes.facecolor": PAL["surface"],
                     "savefig.facecolor": PAL["surface"], "font.family": "DejaVu Sans"})


def coord_grid(grid, title, fname):
    fig, ax = plt.subplots(figsize=(8.6, 3.1))
    for x, node in enumerate(NODE_ORDER):
        for y, ft in enumerate(FAULT_TYPES[::-1]):
            st = grid[(node, ft)]
            if st == "n/a":
                ax.text(x, y, "–", ha="center", va="center", fontsize=13, color=PAL["ink2"])
            else:
                c = PAL["good"] if st == "held" else PAL["critical"]
                ax.add_patch(plt.Circle((x, y), 0.36, facecolor="none", edgecolor=c, lw=1.6))
                ax.text(x, y, "✓" if st == "held" else "✗", ha="center", va="center", fontsize=12,
                        color=c, fontweight="bold")
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
    ax.set_xlabel("Faulted node")
    ax.set_title(title, fontsize=10, loc="left")
    handles = [Line2D([], [], marker="$✓$", color=PAL["good"], ls="", ms=9, label="coordination held"),
               Line2D([], [], marker="$✗$", color=PAL["critical"], ls="", ms=9, label="coordination lost"),
               Line2D([], [], marker="$–$", color=PAL["ink2"], ls="", ms=9, label="not applicable")]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.3), ncol=3, frameon=False)
    fig.tight_layout()
    save_png(fig, fname)
    plt.close(fig)


def annotate_times(ax, opts, x_left=100.0):
    """Operating times on a TCC: a dotted line from each operating point to the time axis with its value,
    and the coordination margins as arrows at the primary fuse current:
      CTI = t_MMT(primary fuse) - t_fast(recloser)        (fast trip before the fuse melts)
      t_delayed(recloser) - t_TCT(primary fuse)            (fuse clears before the delayed trip)
    opts: [(device, current, [t1, t2], colour)] - for a recloser t1/t2 = fast/delayed, for a fuse MMT/TCT."""
    import math
    labels = []
    for dev, i_dev, ops, c in opts:
        names = ("melts", "clears") if dev in FUSES else ("fast", "delayed")
        short = dev.replace("R2rv", "R2 rev").replace("R2fw", "R2")
        for t, nm in zip(ops, names):
            if t < INF and 0.01 < t < 1000:
                ax.plot([x_left, i_dev], [t, t], color=c, lw=0.7, ls=":", alpha=0.9, zorder=2)
                labels.append([t, "%s %s %.3f s" % (short, nm, t), c])
    # labels at the left edge, spread so that they do not overlap (log axis)
    labels.sort(key=lambda x: x[0])
    ys = []
    for t, _, _ in labels:
        y = math.log10(t)
        if ys and y - ys[-1] < 0.13:
            y = ys[-1] + 0.13
        ys.append(y)
    for (t, txt, c), y in zip(labels, ys):
        ax.text(x_left * 1.08, 10 ** y, txt, fontsize=6.4, color=c, va="bottom", ha="left",
                bbox=dict(boxstyle="square,pad=0.08", fc="white", ec="none", alpha=0.75), zorder=7)
    recs = [o for o in opts if o[0] not in FUSES]
    fuses = [o for o in opts if o[0] in FUSES]
    if not recs or not fuses:
        return
    # a recloser that carries current but does not pick up
    lo_y, hi_y = ax.get_ylim()
    for dev, i_dev, (tf, _), c in recs:
        if tf == INF and i_dev > 1.0:
            ax.text(i_dev * 1.05, (lo_y * hi_y) ** 0.5 / 3, "%s: %.0f A, does not trip" % (
                dev.replace("R2rv", "R2 rev").replace("R2fw", "R2"), i_dev), rotation=90, fontsize=7.4,
                color="#c62828", fontweight="bold", va="center", ha="left", zorder=8,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="#c62828", lw=0.6, alpha=0.9))
    # the recloser that decides: the one with the latest fast trip (it must still beat the fuse)
    live = [r for r in recs if r[2][0] < INF]
    if not live:
        return
    _, i_rec, (tf, td), _ = max(live, key=lambda r: r[2][0])
    _, i_fu, (mmt, tct), _ = fuses[0]
    x = i_fu * 1.35
    for lo, hi, name in ((tf, mmt, "CTI"), (tct, td, "t$_D$ − t$_{TCT}$")):
        if not (lo < INF and hi < INF and 0.01 < min(lo, hi) and max(lo, hi) < 1000):
            continue
        ok = hi > lo
        col = "#2e7d32" if ok else "#c62828"
        d = hi - lo
        val = ("%+.0f ms" % (1000 * d)) if abs(d) < 1 else ("%+.2f s" % d)
        ax.annotate("", xy=(x, hi), xytext=(x, lo), arrowprops=dict(arrowstyle="<->", color=col, lw=1.3), zorder=8)
        right = x * 4.5 < ax.get_xlim()[1]                    # room for the label right of the arrow?
        ax.text(x * 1.06 if right else x / 1.06, (lo * hi) ** 0.5, "%s = %s" % (name, val.replace("-", "−")),
                fontsize=7.2, color=col, fontweight="bold", va="center", ha="left" if right else "right", zorder=8,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=col, lw=0.6, alpha=0.9))


def tcc(fig_id, rec, s, devices, title, fname, dsdr):
    fig, ax = plt.subplots(figsize=(6.6, 4.8))
    ii = [10 ** (2 + k / 200.0) for k in range(601)]
    colors = [PAL["blue"], PAL["orange"], PAL["aqua"], PAL["violet"]]
    handles = []
    opts = []
    for n, dev in enumerate(devices):
        c = colors[n]
        if dev in FUSES:
            f = fuse(s, dev)
            i_dev = imax(rec, dev)
            lo = [(i, f.mmt(i)) for i in ii if f.mmt(i) < 1000]
            hi = [(i, f.tct(i)) for i in ii if f.tct(i) < 1000]
            ax.plot(*zip(*lo), color=c, lw=1.3)
            ax.plot(*zip(*hi), color=c, lw=1.3)
            ax.fill_betweenx([p[1] for p in lo], [p[0] for p in lo],
                             [_loglog(p[1], sorted((b, a) for a, b in f.clear)) or p[0] for p in lo],
                             color=c, alpha=0.2, lw=0)
            ops = [f.mmt(i_dev), f.tct(i_dev)]
            label = ("%s %s  %.0f A: melts %.3f s, clears %.3f s" % (dev, s["fuses"][dev], i_dev, ops[0], ops[1])
                     if ops[1] < INF else "%s %s  %.0f A: does not melt" % (dev, s["fuses"][dev], i_dev))
        else:
            i_dev = imax(rec, "R1" if dev == "R1" else "R2")
            if dev == "R1":
                fun = lambda i, m: t_r1(i, s, m)
                name = "R1"
            else:
                unit = "R2rv" if dev == "R2rv" else "R2fw"
                fun = lambda i, m, u=unit: t_r2(i, s, u, m)
                name = "R2 reverse (DSDR)" if dev == "R2rv" else "R2"
            for m, ls in (("f", "-"), ("d", "--")):
                pts = [(i, fun(i, m)) for i in ii if fun(i, m) < 1000]
                ax.plot(*zip(*pts), color=c, lw=1.7, ls=ls)
            ops = [fun(i_dev, "f"), fun(i_dev, "d")]
            label = "%s  %.0f A: fast %s, delayed %s" % (name, i_dev, *(("%.3f s" % x) if x < INF else "no trip"
                                                                       for x in ops))
        ax.axvline(i_dev, color=c, lw=0.8, alpha=0.7)
        for t in ops:
            if t < INF:
                ax.plot([i_dev], [t], marker="o", ms=6, color=c, mec=PAL["surface"], mew=1.5, zorder=5)
        handles.append(Line2D([], [], color=c, lw=1.7, label=label))
        opts.append((dev, i_dev, ops, c))
    handles.append(Line2D([], [], color=PAL["ink2"], lw=1.2, ls="--", label="dashed: recloser delayed curve"))
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(100, 1e5)
    ax.set_ylim(0.01, 1000)
    annotate_times(ax, opts)
    ax.grid(True, which="major", color=PAL["grid"], lw=0.8)
    ax.grid(True, which="minor", color=PAL["grid"], lw=0.3, alpha=0.6)
    ax.set_xlabel("Current (A at 4.16 kV)")
    ax.set_ylabel("Time (s)")
    status = evaluate(rec, s, dsdr) if rec["where"] in NODES else None
    extra = "" if status is None else ("  -  coordination held" if status["held"] else "  -  coordination LOST")
    ax.set_title("%s%s" % (title, extra), fontsize=9.5, loc="left")      # the figure number is in the caption
    ax.legend(handles=handles, loc="upper right", fontsize=7.3, frameon=True, framealpha=0.92)
    fig.tight_layout()
    save_png(fig, fname)
    plt.close(fig)


# =============================================================================================
# main
# =============================================================================================
def main():
    t2 = table2()
    s = design_reclosers(t2)

    # ---------------- stage A: conventional scheme without DG ----------------------------------
    g, _ = classify(s, False, 0.0)
    say("\n  published fuse sizes, no DG: %d of %d cells held" % count(g))
    for e in classify(s, False, 0.0)[1]:
        if not e["held"]:
            say("    lost  %-4s %-3s %-3s  %s" % (e["node"], e["type"], e["phases"], e["reason"]))
    log_a = []
    step8(s, False, 0.0, ["R2fw"], log_a)
    step9(s, False, [0.0], log_a)
    for l in log_a:
        say("  " + l)
    gA, dA = classify(s, False, 0.0)
    say("  after steps 8-10, no DG: %d of %d cells held" % count(gA))
    for e in dA:
        if not e["held"]:
            say("    lost  %-4s %-3s %-3s  %s" % (e["node"], e["type"], e["phases"], e["reason"]))
    t3 = table3(s)
    s_conv = copy.deepcopy(s)

    # ---------------- stage B: DG added, conventional R2 -----------------------------------------
    g14, d14 = classify(s_conv, False, 1.0)
    say("\nSTAGE B - DG 4.05 MVA at 692, conventional (non-directional) R2 -> Fig. 14: %d of %d cells held" % count(g14))
    for e in d14:
        if not e["held"]:
            say("    lost  %-4s %-3s %-3s  %s" % (e["node"], e["type"], e["phases"], e["reason"]))
    coord_grid(g14, "Coordination without DSDR, DG 4.05 MVA at 692", "Fig14_without_DSDR.png")

    # ---------------- stage C: R2 as DSDR -------------------------------------------------------
    i_rv = max(LF["dg_in"]["R2"])
    ip_rv = OLF * i_rv
    tf, td = nearest_tap(ip_rv / 2, CDG_TAPS, CT_R2RV / 5), nearest_tap(ip_rv, CDG_TAPS, CT_R2RV / 5)
    s["R2rv"] = dict(ct=CT_R2RV, ip_eq12=ip_rv, i_nom_rv=i_rv, tap_f=tf, tap_d=td, is_f=tf * CT_R2RV / 5,
                     is_d=td * CT_R2RV / 5, tms_f=s["R2fw"]["tms_f"], tms_d=s["R2fw"]["tms_d"],
                     tms_d_max=TMS_MAX, tms_min=DSDR_TMS_MIN)
    s["R2fw"]["tms_min"] = DSDR_TMS_MIN
    say("\nSTAGE C - R2 AS DUAL-SETTING DIRECTIONAL RECLOSER")
    say("  reverse load current with DG %.1f A (%.0f kW towards 632) -> Ip,rv = 1.25 x %.1f = %.1f A (eq. 12)" % (
        i_rv, LF["dg_in"]["R2_P_kW"], i_rv, ip_rv))
    say("  DSDR: CDG34 extremely-inverse curve in both directions, TMS %.1f-%.1f; reverse setting group on CT 500/5" % (
        DSDR_TMS_MIN, TMS_MAX))
    say("  reverse fast plug %.1f A = %.0f A (curve from %.0f A), delayed plug %.1f A = %.0f A (curve from %.0f A)" % (
        tf, s["R2rv"]["is_f"], 2 * s["R2rv"]["is_f"], td, s["R2rv"]["is_d"], 2 * s["R2rv"]["is_d"]))
    log_c = []
    step8(s, True, 1.0, ["R2rv", "R2fw"], log_c)
    step9(s, True, [1.0, 0.0], log_c)
    step8(s, True, 1.0, ["R2rv", "R2fw"], log_c)
    for l in log_c:
        say("  " + l)
    say("  final: reverse TMS %.3f (fast) / %.3f (delayed); forward TMS %.3f / %.3f" % (
        s["R2rv"]["tms_f"], s["R2rv"]["tms_d"], s["R2fw"]["tms_f"], s["R2fw"]["tms_d"]))
    g17, d17 = classify(s, True, 1.0)
    g17_0, _ = classify(s, True, 0.0)
    say("  Fig. 17: %d of %d cells held with DG;  %d of %d without DG" % (count(g17) + count(g17_0)))
    for e in d17:
        if not e["held"]:
            say("    lost  %-4s %-3s %-3s  %s" % (e["node"], e["type"], e["phases"], e["reason"]))
    coord_grid(g17, "Coordination with DSDR, DG 4.05 MVA at 692", "Fig17_with_DSDR.png")

    # the same fuse sizes with the conventional R2 (to separate the DSDR's effect from step 9)
    s_mix = copy.deepcopy(s)
    s_mix["R2fw"] = copy.deepcopy(s_conv["R2fw"])
    g14b, _ = classify(s_mix, False, 1.0)
    say("  check: final fuse sizes but conventional R2 -> %d of %d cells held" % count(g14b))

    rows = [[n, ft, g14[(n, ft)], g17[(n, ft)], g14b[(n, ft)]] for n in NODE_ORDER for ft in FAULT_TYPES]
    write_csv("Fig14_Fig17_classification.csv", ["node", "fault", "without DSDR (Fig14)", "with DSDR (Fig17)",
                                                 "revised fuses, conventional R2"], rows)
    write_csv(os.path.join("comparison", "Fig14_Fig17_vs_paper.csv"),
              ["node", "fault", "Fig14 model", "Fig14 paper", "Fig17 model", "final fuses, conventional R2"],
              [[r[0], r[1], r[2], "n/a" if r[2] == "n/a" else ("lost" if (r[0], r[1]) in PAPER_FIG14_LOST else "held"),
                r[3], r[4]] for r in rows])
    comp = [r for r in rows if r[2] != "n/a"]
    say("  Fig. 14: %d of %d cells held;  Fig. 17: %d of %d" % (
        sum(r[2] == "held" for r in comp), len(comp), sum(r[3] == "held" for r in comp), len(comp)))

    det = []
    for tag, dd in (("conventional (Fig. 14)", d14), ("DSDR (Fig. 17)", d17)):
        for e in dd:
            det.append([tag, e["node"], e["type"], e["phases"], e["fuse"] or "", round(e.get("i_fuse", 0)),
                        fmt(e["mmt"]) if e["fuse"] else "", fmt(e["tct"]) if e["fuse"] else "",
                        " | ".join("%s %.0f A: %s / %s s" % (x[0], x[2], fmt(x[3]), fmt(x[4])) for x in e["reclosers"]),
                        "held" if e["held"] else "lost", e["reason"]])
    write_csv("Coordination_detail.csv", ["scheme", "node", "fault", "phases", "primary fuse", "I fuse (A)", "MMT (s)",
                                          "TCT (s)", "reclosers: fast / delayed", "status", "reason"], det)

    # sympathetic operation of F671-1 (DG current flows up through it for faults outside its zone)
    say("\nSYMPATHETIC CHECK - F671-1 carries the DG current for faults outside its zone (DSDR, DG in)")
    for node in ("632", "633", "645", "646", "DL", "671", "680", "684", "611", "652"):
        worst = None
        for r in faults("max", 1.0, node):
            e = evaluate(r, s, True)
            t_clear = max((x[3] for x in e["reclosers"] if x[0].startswith("R2")), default=None)
            m = fuse(s, "F671-1").mmt(imax(r, "F671-1"))
            ref = t_clear if t_clear is not None else None
            if worst is None or m < worst[0]:
                worst = (m, r["type"], r["phases"], imax(r, "F671-1"), ref)
        m, ft, ph, i, ref = worst
        say("  fault %-4s worst %-3s %-3s: F671-1 %5.0f A melts %s s; %s" % (
            node, ft, ph, i, fmt(m), ("R2 reverse fast %s s -> %s" % (fmt(ref), "ok" if ref < m else "F671-1 melts first"))
            if ref is not None else "no recloser between the DG and the fault"))

    # ---------------- Table IV ------------------------------------------------------------------
    rep = {"632": "LLL", "633": "LLL", "645": "LL", "646": "LL", "DL": "LLL", "671": "LLL", "692": "LLL",
           "675": "LLL", "684": "LL", "680": "LLL", "611": "LG", "652": "LG"}
    say("\nTABLE IV - operating times with the DSDR, DG in; bolted LLL (LL at 2-phase nodes, LG at 1-phase nodes)")
    say("  %-4s %-3s | %-17s | %-22s | %-7s %-15s" % ("node", "flt", "R1 fast / delayed", "R2 unit fast / delayed",
                                                      "fuse", "MMT / TCT"))
    rows4 = []
    for node, ft in rep.items():
        r = max(faults("max", 1.0, node, ft), key=lambda x: imax(x, "R1"))
        e = evaluate(r, s, True)
        i1, i2 = imax(r, "R1"), imax(r, "R2")
        unit = "R2fw" if NODES[node]["zone"] == "R2" else "R2rv"
        r1 = (t_r1(i1, s, "f"), t_r1(i1, s, "d"))
        r2 = (t_r2(i2, s, unit, "f"), t_r2(i2, s, unit, "d"))
        rows4.append([node, ft, r["phases"], round(i1), fmt(r1[0]), fmt(r1[1]), round(i2), "fwd" if unit == "R2fw" else "rev",
                      fmt(r2[0]), fmt(r2[1]), e["fuse"] or "---", round(e.get("i_fuse", 0)) if e["fuse"] else "",
                      fmt(e["mmt"]) if e["fuse"] else "---", fmt(e["tct"]) if e["fuse"] else "---",
                      "held" if e["held"] else "lost"])
        say("  %-4s %-3s | %7s / %-7s | %s %7s / %-7s | %-7s %6s / %-6s%s" % (
            node, ft, fmt(r1[0]), fmt(r1[1]), rows4[-1][7], fmt(r2[0]), fmt(r2[1]), e["fuse"] or "---",
            rows4[-1][12], rows4[-1][13], "" if e["held"] else "   LOST: " + e["reason"]))
    head4 = ["node", "fault", "phases", "I R1 (A)", "R1 fast (s)", "R1 delayed (s)", "I R2 (A)", "R2 unit", "R2 fast (s)",
             "R2 delayed (s)", "fuse", "I fuse (A)", "fuse MMT (s)", "fuse TCT (s)", "status"]
    write_csv("Table_IV.csv", head4, rows4)
    write_csv(os.path.join("comparison", "Table_IV_vs_paper.csv"),
              head4 + ["paper R1 fast", "paper R1 delayed", "paper R2 fast", "paper R2 delayed", "paper fuse MMT"],
              [r + [x if x is not None else "---" for x in PAPER_TABLE4[r[0]]] for r in rows4])

    # ---------------- time-current figures ------------------------------------------------------
    fr = {c: [r for r in FAULTS if r["case"] == c][0] for c in ("Fig8", "Fig9", "Fig11", "Fig12", "Fig13", "Fig15")}
    tcc("Fig. 8", fr["Fig8"], s_conv, ["R2", "F684", "F671-2"], "LG fault at 611", "Fig08_LG_611.png", False)
    tcc("Fig. 9", fr["Fig9"], s_conv, ["R2", "F692-R", "F671-1"], "LLG fault mid 692-675, 1 ohm",
        "Fig09_LLG_692-675.png", False)
    tcc("Fig. 11", fr["Fig11"], s_conv, ["R1", "F646", "F632"], "LL fault at 646, 1 ohm", "Fig11_LL_646_R1.png", False)
    tcc("Fig. 12", fr["Fig12"], s_conv, ["R2", "F646", "F632"], "LL at 645, 1.5 ohm, conventional R2",
        "Fig12_LL_645_conventional_R2.png", False)
    tcc("Fig. 13", fr["Fig13"], s_conv, ["R2", "F633"], "3-ph fault at 10 % of 632-633, conventional R2",
        "Fig13_LLL_632-633_conventional_R2.png", False)
    tcc("Fig. 15", fr["Fig15"], s, ["R2rv", "F646", "F632"], "solid LL at 646, R2 as DSDR",
        "Fig15_LL_646_DSDR.png", True)
    tcc("Fig. 16", fr["Fig15"], s, ["R1", "F646", "F632"], "solid LL at 646, R1", "Fig16_LL_646_R1.png", True)

    out = {"conventional": s_conv, "dsdr": s}
    json.dump(out, open(os.path.join(RES, "settings.json"), "w"), indent=1)
    with open(os.path.join(RES, "summary.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(REPORT))


if __name__ == "__main__":
    main()
