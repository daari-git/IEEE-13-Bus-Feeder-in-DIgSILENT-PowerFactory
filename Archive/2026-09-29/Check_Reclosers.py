"""
Check the recloser relays (R1, R2) added to the IEEE 13-node feeder.

For every relay (ElmRelay) in the project it reports where it sits (terminal, branch, line
end), its type, CT, and every protection element with its settings. It then applies a
bolted 3-phase fault (Complete method, DG out of service) just downstream of each recloser
and compares the relay's trip times with the GE IAC extremely inverse curve of the paper.

Run: Python Script (ComPython) -> Execute. The report is printed in the Output Window and
saved as Recloser_check.txt; PowerFactory's own messages go to PF_output_window.txt.
"""

import os

import powerfactory as pf

OUT_DIR = r"D:\Protection and co-ordination"
OUT_TXT = os.path.join(OUT_DIR, "Recloser_check.txt")
OUT_PF = os.path.join(OUT_DIR, "PF_output_window.txt")

# Expected settings: fault node for the check, pickup Ip = 1.25 x I_nom (A), time dials
EXPECTED = {
    "R1": dict(term="RG60", towards="632", fault="632", ip=734.5, tds_f=0.5, tds_d=10.0),
    "R2": dict(term="671", towards="632", fault="671", ip=598.8, tds_f=0.8, tds_d=4.0),
}
IAC_EI = (0.0040, 0.6379, 0.6200, 1.7872, 0.2461)   # GE IAC extremely inverse, TDS = 1

CUBICLE_KEYS = ("bus1", "bus2", "bushv", "buslv")
PHASES = ("A", "B", "C")

# Attributes worth reporting, per class (missing ones are skipped)
ATTRS = {
    "ElmRelay": ["outserv"],
    "StaCt": ["ptapset", "stapset", "iphase", "outserv"],
    "StaVt": ["ptapset", "stapset", "outserv"],
    "RelToc": ["outserv", "Ipset", "Ipsetr", "Tpset", "pcharac", "idir", "Iset"],
    "RelIoc": ["outserv", "Ipset", "Ipsetr", "Tset", "idir"],
    "RelDir": ["outserv", "idir", "mtau"],
    "RelRecl": ["outserv", "oper", "reclnum", "trecl"],
    "RelMeasure": ["outserv", "Unom", "Inom"],
}
# Result variables that may hold the trip time / measured current after a short circuit
TRIP_VARS = ["c:ttrip", "c:yt", "c:Tdelay", "c:tact"]
CURR_VARS = ["c:Iprim", "c:Isec", "c:I", "c:Ipu"]

app = pf.GetApplication()
lines = []


def out(s=""):
    lines.append(s)
    app.PrintPlain(s)


def attr(obj, name, default=None):
    try:
        v = obj.GetAttribute(name)
        return default if v is None else v
    except Exception:
        return default


def show(v):
    if hasattr(v, "loc_name"):
        return "%s (%s)" % (v.loc_name, v.GetClassName())
    if isinstance(v, float):
        return "%.4g" % v
    if isinstance(v, list):
        return "[" + ", ".join(show(x) for x in v) + "]"
    return str(v)


def iac_ei(m):
    a, b, c, d, e = IAC_EI
    x = m - c
    return a + b / x + d / x ** 2 + e / x ** 3 if m > 1.0 else float("nan")


def location(relay):
    """Cubicle holding the relay, its terminal, branch and the branch's far terminal."""
    cub = relay.GetParent()
    if cub is None or cub.GetClassName() != "StaCubic":
        return cub, None, None, None, None
    term, br = attr(cub, "cterm"), attr(cub, "obj_id")
    key, far = None, None
    if br is not None:
        for k in CUBICLE_KEYS:
            c = attr(br, k)
            if c is None:
                continue
            if c == cub:
                key = k
            elif attr(c, "cterm") is not None:
                far = attr(c, "cterm")
    return cub, term, br, key, far


def describe(relay):
    out("=" * 78)
    out("RELAY %s   (%s)" % (relay.loc_name, relay.GetFullName()))
    out("  out of service : %s" % attr(relay, "outserv"))
    typ = attr(relay, "typ_id")
    out("  relay type     : %s" % (typ.GetFullName() if typ else "NONE - no type selected"))

    cub, term, br, key, far = location(relay)
    if term is None:
        out("  location       : NOT in a line cubicle (parent: %s)" % show(cub))
    else:
        out("  location       : terminal %s, cubicle %s" % (term.loc_name, cub.loc_name))
        out("  branch         : %s, end %s, far end %s" % (
            show(br), key, far.loc_name if far else "?"))

    slots = attr(relay, "pdiselm")
    if slots:
        out("  slots          : %s" % show([s for s in slots if s is not None]))

    kids = relay.GetContents()
    out("  elements (%d):" % len(kids))
    for k in kids:
        cls = k.GetClassName()
        vals = ["%s=%s" % (a, show(attr(k, a))) for a in ATTRS.get(cls, ["outserv"])
                if attr(k, a) is not None]
        t = attr(k, "typ_id")
        out("    %-20s %-10s type=%s" % (k.loc_name, cls, t.loc_name if t else "-"))
        if vals:
            out("        " + "  ".join(vals))

    if cub is not None and cub.GetClassName() == "StaCubic":
        other = [c for c in cub.GetContents() if c != relay]
        if other:
            out("  also in the cubicle: %s" % show(other))
    return cub, term, br, key, far


def fault_check(relay, loc):
    exp = EXPECTED.get(relay.loc_name.upper())
    cub, term, br, key, far = loc
    if exp is None or br is None or key is None:
        return
    out("-" * 78)
    out("3-phase bolted fault at %s (Complete method, DG out of service)" % exp["fault"])
    ldf = app.GetFromStudyCase("ComLdf")
    ldf.iopt_net = 1                          # the Complete method needs an unbalanced load flow
    if ldf.Execute() != 0:
        out("  load flow FAILED")
        return
    terms = {t.loc_name: t for t in app.GetCalcRelevantObjects("*.ElmTerm")}
    bus = terms.get(exp["fault"])
    shc = app.GetFromStudyCase("ComShc")
    shc.iopt_mde = 3
    shc.iopt_allbus = 0
    shc.shcobj = bus
    shc.iopt_shc = "3rst"
    shc.Rf = 0.0
    shc.Xf = 0.0
    if shc.Execute() != 0:
        out("  short circuit FAILED")
        return
    i_a = 1000.0 * max(abs(attr(br, "m:Ikss:%s:%s" % (key, p), 0.0)) for p in PHASES)
    m = i_a / exp["ip"]
    out("  current through %s : %.0f A   (M = I / Ip = %.0f / %.1f = %.2f)" % (
        relay.loc_name, i_a, i_a, exp["ip"], m))
    out("  expected (GE IAC EI): fast %.3f s (TDS %.1f), delayed %.3f s (TDS %.1f)" % (
        exp["tds_f"] * iac_ei(m), exp["tds_f"], exp["tds_d"] * iac_ei(m), exp["tds_d"]))
    for obj in [relay] + list(relay.GetContents()):
        res = ["%s=%s" % (v, show(attr(obj, v))) for v in TRIP_VARS + CURR_VARS
               if attr(obj, v) is not None]
        if res:
            out("  %-20s %s" % (obj.loc_name, "  ".join(res)))


def main():
    try:
        app.GetOutputWindow().Clear()
    except Exception:
        pass
    prj = app.GetActiveProject()
    if prj is None:
        out("No active project.")
        return
    out("Project: %s" % prj.loc_name)
    relays = prj.GetContents("*.ElmRelay", 1)
    active = {r.GetFullName() for r in app.GetCalcRelevantObjects("*.ElmRelay")}
    out("Relays found: %d  (%d in the active network)" % (len(relays), len(active)))
    fuses = prj.GetContents("*.RelFuse", 1)
    out("Fuses found : %d" % len(fuses))

    dgs = app.GetCalcRelevantObjects("*.ElmSym")
    dg_state = [g.outserv for g in dgs]
    try:
        for g in dgs:
            g.outserv = 1
        for r in relays:
            if r.GetFullName() not in active:
                out("=" * 78)
                out("RELAY %s is NOT in the active network: %s" % (r.loc_name, r.GetFullName()))
                continue
            loc = describe(r)
            try:
                fault_check(r, loc)
            except Exception as e:
                out("  fault check failed: %s" % e)
        out("=" * 78)
    finally:
        for g, s in zip(dgs, dg_state):
            g.outserv = s

    with open(OUT_TXT, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    app.PrintPlain("Saved: " + OUT_TXT)
    try:
        app.GetOutputWindow().Save(OUT_PF)
    except Exception:
        pass


main()
