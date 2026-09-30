"""
Fault currents for Table IV and Figs. 7-17 of Yousaf et al. (2022), IEEE 13-node feeder.

PowerFactory only supplies the currents. Operating times (R1, R2, fuses) and the figures
are computed from them outside PowerFactory (make_figures.py), with the same curves as
the model: GE IAC extremely inverse for R1/R2, eq. (6) with Table III b_i for the fuses.

Studies (Complete method, DG at 692 in service unless stated):
  cases  : the faults of Figs. 8-13, 15, 16 (location, type and fault resistance as in
           the captions; a line fault is placed at the given % of the line)
  sweep  : bolted LG, LL, LLG and 3-phase faults at every node (Table IV, Figs. 14, 17)
  dg     : bolted 3-phase faults at 633 and 671 for DG ratings 0-100 % (Fig. 7)
  loadflow: currents through R1 and R2 with and without the DG (R2 reverse pickup)

For each fault the current through R1, R2 and every fuse is saved (largest phase, A),
in Fault_Study.csv. The DG rating and in-service state are restored at the end.

Run: Python Script (ComPython) in the study case -> Execute.
"""

import os

import powerfactory as pf

OUT_DIR = r"D:\Protection and co-ordination\Result"
OUT_CSV = os.path.join(OUT_DIR, "Fault_Study.csv")
OUT_TXT = os.path.join(OUT_DIR, "Logs", "Fault_Study.txt")
os.makedirs(os.path.dirname(OUT_TXT), exist_ok=True)

# name, location (node, or (line, % from its bus1 end)), fault type, Rf (ohm)
CASES = [
    ("Fig8", "611", "LG", 0.0),
    ("Fig9", ("LC692-675", 50.0), "LLG", 1.0),
    ("Fig10", "684", "LL", 0.2),
    ("Fig11", "646", "LL", 1.0),
    ("Fig12", "645", "LL", 1.5),
    ("Fig13", ("LOHL632-633", 10.0), "LLL", 0.0),
    ("Fig15-16", "646", "LL", 0.0),
]
NODES = ["632", "633", "634", "645", "646", "nDL", "671", "692", "675", "680", "684",
         "611", "652"]
FAULTS = ["LG", "LL", "LLG", "LLL"]
DG_LEVELS = [0, 10, 25, 37, 50, 75, 100]       # % of the rated DG (Fig. 7)
DG_NODES = ["633", "671"]

KIND = {"LG": ("spgf", "i_pspgf"), "LL": ("2psc", "i_p2psc"),
        "LLG": ("2pgf", "i_p2pgf"), "LLL": ("3rst", None)}
RECLOSERS = {"R1": ("RG60", "632"), "R2": ("671", "632")}   # terminal, towards
CUBICLE_KEYS = ("bus1", "bus2", "bushv", "buslv")
PHASES = ("A", "B", "C")

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


TERMS = {t.loc_name: t for t in app.GetCalcRelevantObjects("*.ElmTerm")}
LINES = {l.loc_name: l for l in app.GetCalcRelevantObjects("*.ElmLne")}
SHC = app.GetFromStudyCase("ComShc")
LDF = app.GetFromStudyCase("ComLdf")


def cub_branch(cub):
    """Element and cubicle key (bus1, bus2, ...) of the element connected at cubicle."""
    el = attr(cub, "obj_id")
    for k in CUBICLE_KEYS:
        if el is not None and attr(el, k) == cub:
            return el, k
    return el, None


def devices():
    """(name, element, key) for R1, R2 and every fuse."""
    res = []
    for name, (term, towards) in RECLOSERS.items():
        for r in app.GetCalcRelevantObjects("%s.ElmRelay" % name):
            cub = r.GetParent()
            if attr(cub, "cterm") is not None and attr(cub, "cterm").loc_name == term:
                el, k = cub_branch(cub)
                res.append((name, el, k))
                break
        else:
            out("WARNING: recloser %s at %s not found" % (name, term))
    for f in sorted(app.GetCalcRelevantObjects("*.RelFuse"), key=lambda x: x.loc_name):
        el, k = cub_branch(f.GetParent())
        res.append((f.loc_name, el, k))
    return res


def current(el, key, var):
    """Largest phase current at the cubicle (A)."""
    v = max(abs(attr(el, "%s:%s:%s" % (var, key, p), 0.0)) for p in PHASES)
    return 1000.0 * v


def close_feeder_breaker():
    for name, (term, towards) in RECLOSERS.items():
        for r in app.GetCalcRelevantObjects("%s.ElmRelay" % name):
            for sw in r.GetParent().GetContents("*.StaSwitch"):
                if attr(sw, "on_off") == 0:
                    sw.on_off = 1
                    out("Breaker in the %s cubicle at %s was OPEN - closed" % (
                        name, attr(r.GetParent(), "cterm").loc_name))


def fault(loc, ftype, rf, devs):
    """Apply the fault, trying each phase (pair); keep the trial with the largest device
    current. Returns {device: current A} or None if no trial solved."""
    kind, sel = KIND[ftype]
    SHC.iopt_mde = 3
    SHC.iopt_allbus = 0
    if isinstance(loc, tuple):
        SHC.shcobj = LINES[loc[0]]
        SHC.ppro = loc[1]
    else:
        SHC.shcobj = TERMS[loc]
    SHC.iopt_shc = kind
    SHC.Rf = rf
    SHC.Xf = 0.0
    best = None
    for p in ([None] if sel is None else range(3)):
        if sel is not None:
            try:
                SHC.SetAttribute(sel, p)
            except Exception:
                pass
        if SHC.Execute() != 0:
            continue
        res = {n: current(el, k, "m:Ikss") for n, el, k in devs}
        if best is None or max(res.values()) > max(best.values()):
            best = res
    return best


def label(loc):
    return "%s@%g%%" % loc if isinstance(loc, tuple) else loc


def main():
    try:
        app.GetOutputWindow().Clear()
    except Exception:
        pass
    close_feeder_breaker()
    devs = devices()
    names = [d[0] for d in devs]
    out("Devices: " + ", ".join(names))

    dgs = app.GetCalcRelevantObjects("*.ElmSym")
    dg_state = [g.outserv for g in dgs]
    dg_typ = attr(dgs[0], "typ_id") if dgs else None
    dg_sgn = attr(dg_typ, "sgn")
    rows = []
    try:
        # ---- load flow: nominal currents through the reclosers --------------------------
        for dg_on in (0, 1):
            for g in dgs:
                g.outserv = 0 if dg_on else 1
            LDF.iopt_net = 1
            if LDF.Execute() == 0:
                for n, el, k in devs:
                    if n in RECLOSERS:
                        i = current(el, k, "m:I") / 1000.0     # load flow m:I is in A

                        p = sum(attr(el, "m:P:%s:%s" % (k, ph), 0.0) for ph in PHASES) / 1000.0
                        rows.append(("loadflow", "", "", "", 0.0, dg_on, 100, n, i))
                        out("Load flow, DG %s: %s %.1f A, P %.3f MW at its cubicle" % (
                            "in" if dg_on else "out", n, i, p))

        for g in dgs:
            g.outserv = 0
        app.EchoOff()
        # ---- figure cases ---------------------------------------------------------------
        for name, loc, ftype, rf in CASES:
            res = fault(loc, ftype, rf, devs)
            out("%-9s %-6s %-16s Rf %.1f: %s" % (name, ftype, label(loc), rf,
                "FAILED" if res is None else "OK"))
            for n in names:
                rows.append(("case", name, label(loc), ftype, rf, 1, 100, n,
                             None if res is None else res[n]))

        # ---- sweep: every node and fault type, DG in and out ------------------------------
        for dg_on in (1, 0):
            for g in dgs:
                g.outserv = 0 if dg_on else 1
            for node in NODES:
                for ftype in FAULTS:
                    res = fault(node, ftype, 0.0, devs)
                    for n in names:
                        rows.append(("sweep", "", node, ftype, 0.0, dg_on, 100, n,
                                     None if res is None else res[n]))

        # ---- DG penetration (Fig. 7) --------------------------------------------------
        if dg_typ is not None and dg_sgn:
            for pct in DG_LEVELS:
                for g in dgs:
                    g.outserv = 0 if pct > 0 else 1
                if pct > 0:
                    dg_typ.sgn = dg_sgn * pct / 100.0
                for node in DG_NODES:
                    res = fault(node, "LLL", 0.0, devs)
                    for n in names:
                        rows.append(("dg", "", node, "LLL", 0.0, int(pct > 0), pct, n,
                                     None if res is None else res[n]))
        else:
            out("DG type rating not found - Fig. 7 study skipped")
    finally:
        app.EchoOn()
        if dg_typ is not None and dg_sgn:
            dg_typ.sgn = dg_sgn
        for g, s in zip(dgs, dg_state):
            g.outserv = s

    with open(OUT_CSV, "w") as fh:
        fh.write("study,case,location,fault,Rf,DG,DG_pct,device,I_A\n")
        for r in rows:
            fh.write("%s,%s,%s,%s,%.2f,%d,%d,%s,%s\n" % (
                r[:8] + ("" if r[8] is None else "%.1f" % r[8],)))
    failed = sum(1 for r in rows if r[8] is None and r[7] == names[0])
    out("Saved %d rows to %s (%d faults did not solve)" % (len(rows), OUT_CSV, failed))
    out("DG rating restored: %s MVA" % attr(dg_typ, "sgn"))


try:
    main()
except Exception:
    import traceback
    out("SCRIPT STOPPED WITH AN ERROR:")
    for s in traceback.format_exc().splitlines():
        out("  " + s)
    raise
finally:
    with open(OUT_TXT, "w") as fh:
        fh.write("\n".join(lines) + "\n")
