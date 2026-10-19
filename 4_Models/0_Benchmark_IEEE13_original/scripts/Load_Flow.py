"""
Unbalanced three-phase (ABC) load flow of the IEEE 13-node feeder.

Prints per-phase bus voltages, branch currents and loading, the grid supply and the losses,
and saves them in Result/LoadFlow_buses_DG_out.csv and Result/LoadFlow_branches_DG_out.csv
(DG_in when DG_IN_SERVICE = True).

Run: inside PowerFactory as a Python Script (ComPython) -> Execute,
     or from a terminal with PowerFactory closed:  py -3.9 Load_Flow.py
"""

import csv
import os
import sys

sys.path.append(r"C:\Program Files\DIgSILENT\PowerFactory 2021 SP2\Python\3.9")
import powerfactory as pf

DIR = r"C:\Users\Rabin\Desktop\Digsilent_project"
OUT_DIR = os.path.join(DIR, "Result")
PROJECT = "IEEE 13 Node Feeder"
V_MIN, V_MAX = 0.95, 1.05                 # ANSI C84.1 range A, p.u.
DG_IN_SERVICE = False                     # False: DG disconnected for this run (restored after)

BRANCH_CLASSES = ("ElmLne", "ElmTr2", "ElmCoup", "ElmZpu", "ElmSind", "ElmVoltreg")
PHASES = ("A", "B", "C")

try:
    app                                   # one shared Application when loaded by Show_Progress.py
except NameError:
    app = pf.GetApplication()
if app is None:
    sys.exit("Could not start PowerFactory: close the PowerFactory window and try again.")


def attr(obj, name, default=None):
    try:
        v = obj.GetAttribute(name)
        return default if v is None else v
    except Exception:
        return default


def out(text=""):
    app.PrintPlain(text)
    print(text)


def fmt(v, spec):
    return format(v, spec) if v is not None else "-".rjust(len(format(0.0, spec)))


def phase_voltages(t):
    """Phase-to-neutral voltage magnitudes in p.u.; None for phases that do not exist."""
    return [v if v > 0.05 else None for v in (attr(t, "m:u:%s" % p, 0.0) for p in PHASES)]


def branch_ends(br):
    ends = []
    for k in ("bus1", "bus2", "bushv", "buslv"):
        cub = attr(br, k)
        t = attr(cub, "cterm") if cub is not None else None
        if t is not None:
            ends.append((k, t.loc_name))
    return ends


def main(clear=True, dg=DG_IN_SERVICE):
    if clear:
        try:
            app.GetOutputWindow().Clear()
        except Exception:
            pass
    if app.GetActiveProject() is None:
        if app.ActivateProject(PROJECT) != 0:
            raise RuntimeError("Could not activate project '%s'" % PROJECT)

    dgs = app.GetCalcRelevantObjects("*.ElmSym")
    saved = [(s, s.outserv) for s in dgs]
    try:
        for s in dgs:
            s.outserv = 0 if dg else 1
        run(dg)
    finally:
        for s, state in saved:
            s.outserv = state


def run(dg):
    ldf = app.GetFromStudyCase("ComLdf")
    ldf.iopt_net = 1                      # AC load flow, unbalanced 3-phase (ABC)
    if ldf.Execute() != 0:
        raise RuntimeError("Load flow did not converge")

    # ---- buses --------------------------------------------------------------------------
    bus_rows = []
    for t in sorted(app.GetCalcRelevantObjects("*.ElmTerm"), key=lambda t: t.loc_name):
        if not attr(t, "m:u", 0.0):
            continue                      # de-energised or internal node
        va, vb, vc = phase_voltages(t)
        present = [v for v in (va, vb, vc) if v]
        if not present:
            continue                      # grounded node (cable shield)
        vmin, vmax = min(present), max(present)
        flag = "LOW" if vmin < V_MIN else ("HIGH" if vmax > V_MAX else "")
        u1 = attr(t, "m:u1", 0.0)
        unbalance = attr(t, "m:u2", 0.0) / u1 * 100.0 if len(present) == 3 and u1 else None
        bus_rows.append([t.loc_name, attr(t, "uknom", 0.0), va, vb, vc, unbalance, flag])

    out()
    out("#" * 90)
    out("#  LOAD FLOW  -  IEEE 13-node feeder, unbalanced ABC, DG %s" % ("in service" if dg else "DISCONNECTED"))
    out("#" * 90)
    out()
    out("   BUS VOLTAGES (p.u., phase-to-neutral)      limits %.2f - %.2f" % (V_MIN, V_MAX))
    out("   " + "-" * 64)
    out("   %-12s %7s %8s %8s %8s %9s  %s" % ("Bus", "kV", "V_A", "V_B", "V_C", "VUF %", ""))
    out("   " + "-" * 64)
    for name, kv, va, vb, vc, vuf, flag in bus_rows:
        out("   %-12s %7.2f %s %s %s %s  %s" % (name, kv, fmt(va, "8.4f"), fmt(vb, "8.4f"),
                                             fmt(vc, "8.4f"), fmt(vuf, "9.2f"), flag))

    # ---- branches -----------------------------------------------------------------------
    br_rows = []
    for cls in BRANCH_CLASSES:
        for br in app.GetCalcRelevantObjects("*." + cls):
            if attr(br, "outserv", 0):
                continue
            ends = branch_ends(br)
            if not ends:
                continue
            key = ends[0][0]
            amps = [abs(attr(br, "m:I:%s:%s" % (key, p), 0.0)) for p in PHASES]
            p_kw = attr(br, "m:Psum:%s" % key, 0.0)
            q_kvar = attr(br, "m:Qsum:%s" % key, 0.0)
            loss_kw = attr(br, "c:Losses", 0.0)
            br_rows.append([br.loc_name, cls[3:], ends[0][1], ends[-1][1] if len(ends) > 1 else "",
                            amps[0], amps[1], amps[2], p_kw, q_kvar,
                            attr(br, "c:loading"), loss_kw])
    br_rows.sort(key=lambda r: (r[1], r[0]))

    out()
    out("   BRANCH FLOWS (from-end)")
    out("   " + "-" * 100)
    out("   %-14s %-7s %-8s %-8s %7s %7s %7s %9s %9s %8s" % (
        "Branch", "Type", "From", "To", "I_A A", "I_B A", "I_C A", "P kW", "Q kvar", "Load %"))
    out("   " + "-" * 100)
    for name, typ, f, t, ia, ib, ic, p, q, ld, _ in br_rows:
        out("   %-14s %-7s %-8s %-8s %7.1f %7.1f %7.1f %9.1f %9.1f %s" % (
            name[:14], typ, f[:8], t[:8], ia, ib, ic, p, q, fmt(ld, "8.1f")))

    # ---- summary ------------------------------------------------------------------------
    out()
    out("   SUMMARY")
    out("   " + "-" * 50)
    p_tot = q_tot = 0.0
    for g in app.GetCalcRelevantObjects("*.ElmXnet"):
        p, q = attr(g, "m:Psum:bus1", 0.0), attr(g, "m:Qsum:bus1", 0.0)
        p_tot, q_tot = p_tot + p, q_tot + q
        out("   Grid %-20s P = %8.1f kW   Q = %8.1f kvar" % (g.loc_name, p, q))
    for s in app.GetCalcRelevantObjects("*.ElmSym"):
        state = "out of service" if attr(s, "outserv", 0) else "P = %8.1f kW   Q = %8.1f kvar" % (
            attr(s, "m:Psum:bus1", 0.0), attr(s, "m:Qsum:bus1", 0.0))
        out("   DG   %-20s %s" % (s.loc_name, state))
    out("   Total branch losses          %8.1f kW" % sum(r[10] for r in br_rows))
    vmin_row = min(bus_rows, key=lambda r: min(v for v in r[2:5] if v))
    out("   Lowest voltage               %8.4f p.u. at %s" %
        (min(v for v in vmin_row[2:5] if v), vmin_row[0]))
    out("   Buses outside limits         %s" % (", ".join(r[0] for r in bus_rows if r[6]) or "none"))

    # ---- files --------------------------------------------------------------------------
    os.makedirs(OUT_DIR, exist_ok=True)
    tag = "DG_in" if dg else "DG_out"
    f_bus = os.path.join(OUT_DIR, "LoadFlow_buses_%s.csv" % tag)
    with open(f_bus, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Bus", "kV", "V_A (pu)", "V_B (pu)", "V_C (pu)", "VUF (%)", "Flag"])
        w.writerows([[c if c is not None else "" for c in r] for r in bus_rows])
    f_br = os.path.join(OUT_DIR, "LoadFlow_branches_%s.csv" % tag)
    with open(f_br, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Branch", "Type", "From", "To", "I_A (A)", "I_B (A)", "I_C (A)",
                    "P (kW)", "Q (kvar)", "Loading (%)", "Losses (kW)"])
        w.writerows([[c if c is not None else "" for c in r] for r in br_rows])
    out()
    out("   Saved: %s" % f_bus)
    out("   Saved: %s" % f_br)


if __name__ == "__main__":
    main()
