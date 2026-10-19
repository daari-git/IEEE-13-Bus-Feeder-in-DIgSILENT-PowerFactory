"""
Load flow on all buses and all branches of the IEEE 13-node feeder, DG disconnected and connected.
No relay, fuse or network setting is changed (the DG is switched and restored).

  Branch table   one row per branch, written "From node -> To node" in the direction away from the
                 grid: current per phase, P and Q entering the branch at the From node, losses, and
                 the direction in which the active power actually flows.
                 + = from the From node to the To node,  - = from the To node to the From node.
  Bus table      voltage per phase (pu, kV, angle), load, capacitor and generation at every bus.
  Check          active and reactive power balance at every bus (sum of all connected elements).

The three single-phase regulators 650 -> RG60 are shown as one branch.  The concentric-neutral and
cable-shield conductors (LC684-652N, LC692-675 Shield) are return paths, not feeder branches, and
are not listed.  nDL1 ... nDL5 are the tapping points of the distributed load along 632-671.

Outputs: results/database/7 ... 10_*.csv and LoadFlow_AllBuses_Report.txt (also printed).
Run inside PowerFactory (through show_progress.py / "Final(1)") or with python.exe when the
PowerFactory window is closed.
"""

import csv
import os

import pf_setup
from pf_setup import activate, attr, RESULTS, dg_units, clean_variation

out = pf_setup.out
OUT = os.path.join(RESULTS, "database")
os.makedirs(OUT, exist_ok=True)
REPORT = []
SIDES = ("bus1", "bus2", "bushv", "buslv")
RETURN_PATHS = ("LC684-652N", "LC692-675 Shield")       # neutral / shield conductors

app = activate()
ldf = app.GetFromStudyCase("ComLdf")
sym = dg_units()[0]


def say(s=""):
    REPORT.append(s)
    out(s)


def heading(s):
    say("")
    say("=" * 118)
    say(s)
    say("=" * 118)


def table(head, rows, name=None):
    rows = [["" if c is None else str(c) for c in r] for r in rows]
    w = [max(len(x) for x in col) for col in zip(head, *rows)] if rows else [len(h) for h in head]
    line = lambda r: "  " + " | ".join(c.ljust(n) for c, n in zip(r, w))
    say(line(head))
    say("  " + "-+-".join("-" * n for n in w))
    for r in rows:
        say(line(r))
    if name:
        with open(os.path.join(OUT, name), "w", newline="") as f:
            wr = csv.writer(f)
            wr.writerow(head)
            wr.writerows(rows)


def val(o, name):
    """Result variable or None (a phase the element does not have gives None)."""
    try:
        return o.GetAttribute(name)
    except Exception:
        return None


def term_of(el, side):
    cub = attr(el, side)
    return attr(cub, "cterm").loc_name if cub is not None else None


# ---------------------------------------------------------------------------------------------
# network: branches, orientation away from the grid, elements at each bus
# ---------------------------------------------------------------------------------------------
TERMS = {t.loc_name: t for t in app.GetCalcRelevantObjects("*.ElmTerm")}
RAW = []                                               # (element, side a, terminal a, side b, terminal b)
for cls in ("ElmLne", "ElmTr2", "ElmCoup"):
    for o in app.GetCalcRelevantObjects("*." + cls):
        if o.loc_name in RETURN_PATHS or attr(o, "outserv", 0):
            continue
        ends = [(s, term_of(o, s)) for s in SIDES if attr(o, s) is not None]
        if len(ends) == 2 and ends[0][1] != ends[1][1]:
            RAW.append((o, ends[0][0], ends[0][1], ends[1][0], ends[1][1]))

GRID = app.GetCalcRelevantObjects("*.ElmXnet")[0]
START = term_of(GRID, "bus1")
DEPTH, ORDER, todo = {START: 0}, [START], [START]      # breadth-first from the grid
while todo:
    a = todo.pop(0)
    for o, sa, ta, sb, tb in RAW:
        for x, y in ((ta, tb), (tb, ta)):
            if x == a and y not in DEPTH:
                DEPTH[y] = DEPTH[a] + 1
                ORDER.append(y)
                todo.append(y)

BRANCHES = []                                          # oriented: from = nearer to the grid
for o, sa, ta, sb, tb in RAW:
    if ta not in DEPTH or tb not in DEPTH:
        continue
    if DEPTH[ta] > DEPTH[tb]:
        sa, ta, sb, tb = sb, tb, sa, ta
    BRANCHES.append(dict(el=o, s_from=sa, frm=ta, s_to=sb, to=tb))
BRANCHES.sort(key=lambda b: (ORDER.index(b["frm"]), ORDER.index(b["to"]), b["el"].loc_name))

KIND = {"ElmLne": "line", "ElmTr2": "transformer", "ElmCoup": "switch"}
INJECT = [("ElmLod", "load"), ("ElmShnt", "capacitor"), ("ElmSym", "DG"), ("ElmXnet", "grid")]


def phase_values(el, side, var):
    """[A, B, C] of a per-phase result; None where the element has no such phase."""
    v = [val(el, "%s:%s:%s" % (var, side, p)) for p in "ABC"]
    if all(x is None for x in v):                       # single-phase element without phase names
        one = val(el, "%s:%s" % (var, side))
        ph = el.loc_name[-1].upper()
        if one is not None and ph in "ABC":
            v["ABC".index(ph)] = one
    return v


def sums(el, side):
    return (val(el, "m:Psum:" + side) or 0.0, val(el, "m:Qsum:" + side) or 0.0)


def fmt_i(i, p):
    if i is None:
        return "-"
    if abs(i) < 0.05:
        return "0.0"
    return "%s%.1f" % ("-" if (p is not None and p < 0) else "+", abs(i))


# ---------------------------------------------------------------------------------------------
def loadflow(dg_on, tag, n_branch, n_bus):
    sym.SetAttribute("outserv", 0 if dg_on else 1)
    if ldf.Execute() != 0:
        raise RuntimeError("load flow failed (DG %s)" % ("in" if dg_on else "out"))
    title = "DG %s" % ("CONNECTED (4.05 MVA at 692)" if dg_on else "DISCONNECTED")

    # ---- branches: merge the three single-phase regulators into one row ------------------------
    merged, rows = {}, []
    for b in BRANCHES:
        el = b["el"]
        i = phase_values(el, b["s_from"], "m:I")
        pp = phase_values(el, b["s_from"], "m:P")
        p, q = sums(el, b["s_from"])
        p2, q2 = sums(el, b["s_to"])
        rec = dict(frm=b["frm"], to=b["to"], name=el.loc_name, kind=KIND[el.GetClassName()], I=i, Pp=pp,
                   P=p, Q=q, loss=p + p2, qloss=q + q2)
        key = (b["frm"], b["to"]) if el.loc_name.lower().startswith("vreg") else None
        if key and key in merged:
            m = merged[key]
            for k in range(3):
                if i[k] is not None:
                    m["I"][k], m["Pp"][k] = i[k], pp[k]
            for f in ("P", "Q", "loss", "qloss"):
                m[f] += rec[f]
            m["name"] = "Vreg A+B+C"
            m["kind"] = "regulator"
            continue
        if key:
            merged[key] = rec
            rec["kind"] = "regulator"
        rows.append(rec)

    heading("LOAD FLOW, %s  -  BRANCH FLOWS  (From node -> To node, away from the grid)" % title)
    say("Values at the From node.  + : power / current flows From -> To;  - : it flows To -> From.")
    out_rows, reversed_ = [], []
    for r in rows:
        if abs(r["P"]) < 0.05 and abs(r["Q"]) < 0.05:
            flow = "no flow"
        else:
            a, c = (r["frm"], r["to"]) if r["P"] >= 0 else (r["to"], r["frm"])
            flow = "%s -> %s" % (a, c)
            if r["P"] < -0.05:
                reversed_.append("%s -> %s" % (r["frm"], r["to"]))
        out_rows.append([r["frm"], r["to"], "%s (%s)" % (r["name"], r["kind"]),
                         fmt_i(r["I"][0], r["Pp"][0]), fmt_i(r["I"][1], r["Pp"][1]), fmt_i(r["I"][2], r["Pp"][2]),
                         "%+.1f" % r["P"], "%+.1f" % r["Q"], "%.2f" % r["loss"], flow])
    table(["From node", "To node", "Branch", "I a (A)", "I b (A)", "I c (A)", "P (kW)", "Q (kvar)",
           "Loss (kW)", "Active power flows"], out_rows, "%d_BranchFlow_%s.csv" % (n_branch, tag))
    say("")
    say("Total branch losses: %.1f kW.  Branches where the active power flows towards the grid: %s." % (
        sum(r["loss"] for r in rows), ", ".join(reversed_) if reversed_ else "none"))

    # ---- buses -----------------------------------------------------------------------------------
    heading("LOAD FLOW, %s  -  BUSES  (voltage per phase; load, capacitor and generation at the bus)" % title)
    inj = {}                                             # terminal -> {kind: [P, Q]}
    for cls, kind in INJECT:
        for o in app.GetCalcRelevantObjects("*." + cls):
            if attr(o, "outserv", 0):
                continue
            t = term_of(o, "bus1")
            p, q = sums(o, "bus1")
            e = inj.setdefault(t, {}).setdefault(kind, [0.0, 0.0])
            e[0] += p
            e[1] += q
    bus_rows = []
    vmin, vmax = (9.0, ""), (0.0, "")
    for n in ORDER:
        t = TERMS[n]
        cells = []
        for p in "ABC":
            u = val(t, "m:u:" + p)
            if u is None or u < 0.01:
                cells += ["-", "-", "-"]
                continue
            cells += ["%.4f" % u, "%.4f" % (val(t, "m:U:" + p) or 0.0), "%.2f" % (val(t, "m:phiu:" + p) or 0.0)]
            if attr(t, "uknom", 0.0) > 1.0 and n in DEPTH and DEPTH[n] > 1:      # feeder buses
                if u < vmin[0]:
                    vmin = (u, "%s phase %s" % (n, p.lower()))
                if u > vmax[0]:
                    vmax = (u, "%s phase %s" % (n, p.lower()))
        d = inj.get(n, {})
        load, cap = d.get("load", [0, 0]), d.get("capacitor", [0, 0])
        # PowerFactory gives a source's output as positive, a load's / capacitor's intake as positive
        gen = [d.get("DG", [0, 0])[k] + d.get("grid", [0, 0])[k] for k in (0, 1)]
        bus_rows.append([n, "%.2f" % attr(t, "uknom", 0.0)] + cells + [
            "%.1f" % load[0] if "load" in d else "-", "%.1f" % load[1] if "load" in d else "-",
            "%.1f" % -cap[1] if "capacitor" in d else "-",
            "%.1f" % gen[0] if ("DG" in d or "grid" in d) else "-",
            "%.1f" % gen[1] if ("DG" in d or "grid" in d) else "-"])
    table(["Bus", "Un (kV)", "Va (pu)", "Va (kV)", "ang a", "Vb (pu)", "Vb (kV)", "ang b", "Vc (pu)", "Vc (kV)",
           "ang c", "Load P (kW)", "Load Q (kvar)", "Cap Q supplied (kvar)", "Source P (kW)", "Source Q (kvar)"],
          bus_rows, "%d_BusLoadFlow_%s.csv" % (n_bus, tag))
    say("")
    say("Voltages are phase-to-neutral.  Lowest feeder voltage %.4f pu at %s, highest %.4f pu at %s." % (
        vmin[0], vmin[1], vmax[0], vmax[1]))
    tl = [sum(v.get("load", [0, 0])[k] for v in inj.values()) for k in (0, 1)]
    say("Total load %.1f kW / %.1f kvar; total branch losses %.1f kW." % (tl[0], tl[1], sum(r["loss"] for r in rows)))
    for kind, lab in (("grid", "Grid"), ("DG", "DG")):
        e = [sum(v.get(kind, [0, 0])[k] for v in inj.values()) for k in (0, 1)]
        if any(kind in v for v in inj.values()):
            say("%s supplies P %.1f kW, Q %.1f kvar." % (lab, e[0], e[1]))

    # ---- power balance at every bus ------------------------------------------------------------------
    bal = {n: [0.0, 0.0] for n in ORDER}
    for b in BRANCHES:
        for side, n in ((b["s_from"], b["frm"]), (b["s_to"], b["to"])):
            p, q = sums(b["el"], side)
            bal[n][0] += p
            bal[n][1] += q
    worst = (0.0, "")
    for n in ORDER:
        d = inj.get(n, {})
        # into branches + into loads and capacitors - output of sources = 0
        sgn = lambda k: -1.0 if k in ("DG", "grid") else 1.0
        p = bal[n][0] + sum(sgn(k) * v[0] for k, v in d.items())
        q = bal[n][1] + sum(sgn(k) * v[1] for k, v in d.items())
        m = max(abs(p), abs(q))
        if m > worst[0]:
            worst = (m, n)
    say("Power balance at every bus (branches + loads + capacitors - sources): largest mismatch "
        "%.2f kW/kvar at %s%s." % (worst[0], worst[1] or "-",
                                    "" if worst[0] < 5 else "  <-- CHECK: an element at this bus is not in the tables"))
    return rows


def close_open_breakers():
    """A load flow with an open switch in the feeder is a different network (everything behind it
    is dead, or an island with the DG).  Open switches in the cubicles of the branches are closed,
    as database_study.py does for the reclosers, and reported."""
    notes = []
    for b in BRANCHES:
        for side, node in ((b["s_from"], b["frm"]), (b["s_to"], b["to"])):
            for sw in attr(b["el"], side).GetContents("*.StaSwitch"):
                if attr(sw, "on_off") == 0:
                    sw.SetAttribute("on_off", 1)
                    notes.append("NOTE: the switch at %s of %s (%s -> %s) was OPEN in the model and has been closed."
                                 % (node, b["el"].loc_name, b["frm"], b["to"]))
        if b["el"].GetClassName() == "ElmCoup" and attr(b["el"], "on_off", 1) == 0:
            b["el"].SetAttribute("on_off", 1)
            notes.append("NOTE: the switch %s (%s -> %s) was OPEN in the model and has been closed."
                         % (b["el"].loc_name, b["frm"], b["to"]))
    return notes


def main():
    dg_state = sym.GetAttribute("outserv")
    heading("LOAD FLOW ON ALL BUSES AND BRANCHES")
    for n in close_open_breakers():
        say(n)
    say("Project: %s   Study case: %s" % (app.GetActiveProject().loc_name, app.GetActiveStudyCase().loc_name))
    say("AC load flow, unbalanced 3-phase (ABC).  Grid at bus %s.  %d buses, %d branch elements." % (
        START, len(ORDER), len(BRANCHES)))
    try:
        a = loadflow(False, "DG_out", 7, 9)
        b = loadflow(True, "DG_in", 8, 10)
    finally:
        sym.SetAttribute("outserv", dg_state)
        clean_variation()

    heading("EFFECT OF THE DG ON THE BRANCH FLOWS  (P at the From node, kW)")
    rows = []
    for x, y in zip(a, b):
        note = ""
        if x["P"] > 0.05 and y["P"] < -0.05:
            note = "REVERSED by the DG"
        elif abs(x["P"]) < 0.05 and abs(y["P"]) > 0.05:
            note = "carries the DG output" if y["P"] < 0 else ""
        rows.append([x["frm"], x["to"], "%+.1f" % x["P"], "%+.1f" % y["P"], "%+.1f" % (y["P"] - x["P"]), note])
    table(["From node", "To node", "P DG out (kW)", "P DG in (kW)", "Change (kW)", "Note"], rows,
          "LoadFlow_BranchFlow_DG_effect.csv")
    with open(os.path.join(OUT, "LoadFlow_AllBuses_Report.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(REPORT) + "\n")
    say("")
    say("Saved: " + OUT + "  (7_/8_BranchFlow_*.csv, 9_/10_BusLoadFlow_*.csv, LoadFlow_AllBuses_Report.txt)")


if __name__ == "__main__":
    main()
