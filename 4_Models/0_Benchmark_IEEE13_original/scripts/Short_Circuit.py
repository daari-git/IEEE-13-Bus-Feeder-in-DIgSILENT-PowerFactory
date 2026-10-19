"""
Short circuits at every node of the IEEE 13-node feeder: bolted 3-phase (LLL), two-phase to
ground (LLG), line-line (LL) and single line-to-ground (LG) faults.

Complete method (phase domain), maximum short-circuit currents. For each fault the fault current
at the node and the currents through R1 (RG60 end of 650-632) and R2 (671 end of 632-671) are
reported (largest phase, A) and saved in Result/ShortCircuit_DG_out.csv (DG_in when
DG_IN_SERVICE = True). One- and two-phase nodes only get the faults their phases allow; every
phase (pair) is tried and the largest current kept.

Run: inside PowerFactory as a Python Script (ComPython) -> Execute,
     or from a terminal with PowerFactory closed:  py -3.9 Short_Circuit.py
"""

import csv
import os
import sys

sys.path.append(r"C:\Program Files\DIgSILENT\PowerFactory 2021 SP2\Python\3.9")
import powerfactory as pf

DIR = r"C:\Users\Rabin\Desktop\Digsilent_project"
OUT_DIR = os.path.join(DIR, "Result")
PROJECT = "IEEE 13 Node Feeder"
DG_IN_SERVICE = False                     # False: DG disconnected for this run (restored after)
CUR_MAX = 0                               # ComShc iopt_cur: maximum short-circuit currents

NODES = ["650", "RG60", "632", "633", "634", "645", "646", "nDL", "671", "692", "675", "680",
         "684", "611", "652"]
# fault: (ComShc iopt_shc, phase selection attribute, phases needed)
FAULTS = [("LLL", "3rst", None, 3), ("LLG", "2pgf", "i_p2pgf", 2),
          ("LL", "2psc", "i_p2psc", 2), ("LG", "spgf", "i_pspgf", 1)]
RECLOSERS = [("R1", "LOHL650-632", "bus1"), ("R2", "LOHL632-671end", "bus2")]
PHASES = ("A", "B", "C")

try:
    app                                   # one shared Application when loaded by another script
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


def main(clear=True, dg=DG_IN_SERVICE):
    if clear:
        try:
            app.GetOutputWindow().Clear()
        except Exception:
            pass
    if app.GetActiveProject() is None:
        if app.ActivateProject(PROJECT) != 0:
            raise RuntimeError("Could not activate project '%s'" % PROJECT)

    shc = app.GetFromStudyCase("ComShc")
    dgs = app.GetCalcRelevantObjects("*.ElmSym")
    saved = [(s, s.outserv) for s in dgs]
    cur_state = shc.iopt_cur
    try:
        for s in dgs:
            s.outserv = 0 if dg else 1
        run(shc, dg)
    finally:
        app.EchoOn()
        shc.iopt_cur = cur_state
        for s, state in saved:
            s.outserv = state


def run(shc, dg):
    terms = {t.loc_name: t for t in app.GetCalcRelevantObjects("*.ElmTerm")}
    lines = {l.loc_name: l for l in app.GetCalcRelevantObjects("*.ElmLne")}

    # phases present at each node, from a load flow
    ldf = app.GetFromStudyCase("ComLdf")
    ldf.iopt_net = 1
    if ldf.Execute() != 0:
        raise RuntimeError("Load flow did not converge")
    nph = {n: sum(1 for p in PHASES if attr(terms[n], "m:u:%s" % p, 0.0) > 0.05)
           for n in NODES if n in terms}

    def amps(obj, key=None):
        var = "m:Ikss:%s:%%s" % key if key else "m:Ikss:%s"
        return max(abs(attr(obj, var % p, 0.0)) for p in PHASES) * 1000.0     # kA -> A

    def fault(bus, kind, sel):
        shc.iopt_mde = 3                  # complete method
        shc.iopt_cur = CUR_MAX
        shc.iopt_allbus = 0
        shc.shcobj = bus
        shc.iopt_shc = kind
        shc.Rf = 0.0
        shc.Xf = 0.0
        best = None
        for ph in ([None] if sel is None else range(3)):
            if sel is not None:
                try:
                    shc.SetAttribute(sel, ph)
                except Exception:
                    pass
            if shc.Execute() != 0:
                continue
            res = [amps(bus)] + [amps(lines[ln], key) if ln in lines else None
                                 for _, ln, key in RECLOSERS]
            if res[0] > 1.0 and (best is None or res[0] > best[0]):
                best = res
        return best

    rows = []
    app.EchoOff()                         # hide "calculation not possible" for absent phases
    for n in NODES:
        if n not in terms or not nph.get(n):
            continue
        for name, kind, sel, need in FAULTS:
            if nph[n] < need:
                continue
            res = fault(terms[n], kind, sel)
            if res is not None:
                rows.append([n, attr(terms[n], "uknom", 0.0), nph[n], name] + res)
    app.EchoOn()

    out()
    out("#" * 90)
    out("#  SHORT CIRCUIT  -  IEEE 13-node feeder, Complete method, max. currents, bolted, DG %s"
        % ("in service" if dg else "DISCONNECTED"))
    out("#" * 90)
    out()
    out("   FAULT CURRENT AT THE NODE (A, largest phase)")
    out("   " + "-" * 64)
    out("   %-6s %6s %4s %9s %9s %9s %9s" % ("Node", "kV", "ph", "LLL", "LLG", "LL", "LG"))
    out("   " + "-" * 64)
    table = {}
    for r in rows:
        table.setdefault((r[0], r[1], r[2]), {})[r[3]] = r
    for (n, kv, ph), f in table.items():
        out("   %-6s %6.2f %4d %s %s %s %s" % (n, kv, ph, *[
            fmt(f[k][4] if k in f else None, "9.0f") for k in ("LLL", "LLG", "LL", "LG")]))

    out()
    out("   CURRENT THROUGH THE RECLOSERS (A, largest phase)")
    out("   " + "-" * 74)
    out("   %-6s %-5s %10s %10s %10s" % ("Node", "Fault", "I_fault", "I_R1", "I_R2"))
    out("   " + "-" * 74)
    for r in rows:
        out("   %-6s %-5s %10.0f %s %s" % (r[0], r[3], r[4], fmt(r[5], "10.0f"), fmt(r[6], "10.0f")))

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "ShortCircuit_%s.csv" % ("DG_in" if dg else "DG_out"))
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Node", "kV", "Phases", "Fault", "I_fault (A)", "I_R1 (A)", "I_R2 (A)"])
        w.writerows([["%.1f" % c if isinstance(c, float) else c for c in r] for r in rows])
    out()
    out("   Saved: %s" % path)


if __name__ == "__main__":
    main()
