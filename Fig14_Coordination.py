"""
Fig. 14 of Yousaf et al. (2022) in the PowerFactory Output Window: recloser-fuse
coordination for every node and fault type, DG in service, conventional R2.

For each node and fault type (LG, LL, LLG, LLL) a bolted fault is calculated (Complete
method). Coordination is "held" when every recloser feeding the fault trips fast before the
primary fuse melts, and the fuse clears before the recloser's delayed trip:
  upstream of R2 (632, 633, 645, 646, DL): R1 (grid) and R2 (DG, reverse direction)
  downstream of R2: R2
Curves are the model's: GE IAC extremely inverse for R1/R2, eq. (6) with Table III b_i for
the fuses (melting), clearing at K_TCT x the melting current. Same rules as make_figures.py.

DSDR = True gives Fig. 17 instead: R2 uses its reverse (dual-setting) curve for faults
upstream of R2.

Run: Python Script (ComPython) in the study case -> Execute.
"""

import powerfactory as pf

DSDR = False                 # False: Fig. 14 (conventional R2); True: Fig. 17 (DSDR)

IAC_EI = (0.0040, 0.6379, 0.6200, 1.7872, 0.2461)
A_FUSE = -1.8
K_TCT = 1.21
# name: (pickup A, TDS fast, TDS delayed)
R1 = ("R1", 720.0, 0.5, 10.0)
R2 = ("R2", 600.0, 0.8, 4.0)
R2_RV = ("R2 rev", 322.2, 0.276, 4.582)       # from make_figures.py (eq. 12 + step 8)
B = {"F632": 6.38, "F633": 6.83, "F634": 8.32, "F645": 6.65, "F646": 6.67, "F-DL": 6.54,
     "F671": 6.08, "F671-1": 5.85, "F692": 6.13, "F692-R": 6.14, "F675": 6.19,
     "F671-2": 5.87, "F684": 6.15, "F611": 6.19, "F652": 6.17}

NODES = ["632", "633", "634", "645", "646", "671", "692", "675", "680", "684", "652", "611",
         "nDL"]
LABEL = {"nDL": "DL"}
UPSTREAM_OF_R2 = {"632", "633", "634", "645", "646", "nDL"}
PRIMARY_FUSE = {"633": "F633", "645": "F632", "646": "F646", "nDL": "F-DL", "680": "F671",
                "692": "F671-1", "675": "F692-R", "684": "F671-2", "611": "F684",
                "652": "F652"}               # 632, 671: no fuse; 634: LV fuse, not coordinated
FAULTS = ["LG", "LL", "LLG", "LLL"]
KIND = {"LG": ("spgf", "i_pspgf"), "LL": ("2psc", "i_p2psc"),
        "LLG": ("2pgf", "i_p2pgf"), "LLL": ("3rst", None)}
RECLOSER_AT = {"R1": "RG60", "R2": "671"}

# the paper's Figs. 14 and 17, columns in NODES order: v exist, x doesn't exist, - N/A
PAPER_GRID = {
    "Fig14": {"LG": "vv-xvvvvvvvvv", "LL": "vv-xxvvvvv--v",
              "LLG": "vx-xxvvxvv--v", "LLL": "vx---vvxv---v"},
    "Fig17": {"LG": "vv-vvvvvvvvvv", "LL": "vv-vvvvvvv--v",
              "LLG": "vv-vvvvvvv--v", "LLL": "vv---vvvv---v"},
}
SYMBOL = {"OK": "v", "X": "x", "-": "-"}
CUBICLE_KEYS = ("bus1", "bus2", "bushv", "buslv")
PHASES = ("A", "B", "C")

try:
    app            # one shared Application when loaded by Show_Progress.py
except NameError:
    app = pf.GetApplication()


def out(s=""):
    app.PrintPlain(s)


def attr(obj, name, default=None):
    try:
        v = obj.GetAttribute(name)
        return default if v is None else v
    except Exception:
        return default


def iac(m):
    a, b, c, d, e = IAC_EI
    x = m - c
    return a + b / x + d / x ** 2 + e / x ** 3 if m > 1.0 else float("inf")


def rec_times(rec, i):
    name, ip, tf, td = rec
    k = iac(i / ip)
    return tf * k, td * k


def mmt(f, i):
    return 10.0 ** B[f] * i ** A_FUSE if i > 0 else float("inf")


def tct(f, i):
    return mmt(f, i / K_TCT)


def measuring_point(cub):
    el = attr(cub, "obj_id")
    for k in CUBICLE_KEYS:
        if el is not None and attr(el, k) == cub:
            return el, k
    return None


def points():
    """Measuring points (element, cubicle key) of R1, R2 and the fuses."""
    pts = {}
    for name, term in RECLOSER_AT.items():
        for r in app.GetCalcRelevantObjects("%s.ElmRelay" % name):
            cub = r.GetParent()
            if attr(attr(cub, "cterm"), "loc_name") == term:
                pts[name] = measuring_point(cub)
                for sw in cub.GetContents("*.StaSwitch"):
                    if attr(sw, "on_off") == 0:
                        sw.on_off = 1
                        out("Breaker in the %s cubicle was OPEN - closed" % name)
    for f in app.GetCalcRelevantObjects("*.RelFuse"):
        pts[f.loc_name] = measuring_point(f.GetParent())
    return pts


def current(pt):
    el, k = pt
    return 1000.0 * max(abs(attr(el, "m:Ikss:%s:%s" % (k, p), 0.0)) for p in PHASES)


def fault(term, ftype, pts, shc):
    """Bolted fault, each phase (pair) tried; the trial with the largest current through any
    device is kept (same rule as Fault_Study.py). None = not possible."""
    kind, sel = KIND[ftype]
    shc.iopt_mde = 3
    shc.iopt_allbus = 0
    shc.shcobj = term
    shc.iopt_shc = kind
    shc.Rf = 0.0
    shc.Xf = 0.0
    best = None
    for p in ([None] if sel is None else range(3)):
        if sel is not None:
            shc.SetAttribute(sel, p)
        if shc.Execute() != 0:
            continue
        res = {n: current(pt) for n, pt in pts.items() if pt}
        if best is None or max(res.values()) > max(best.values()):
            best = res
    return best


def classify(node, res):
    """('OK' | 'X' | '-', reason)."""
    f = PRIMARY_FUSE.get(node)
    if res is None:
        return "-", "fault type does not exist at this node"
    if f is None:
        return "-", "no fuse in the faulted path" if node != "634" else \
            "LV-side fuse, not coordinated with the reclosers"
    i_f = res["R1"] + res["R2"] if f == "F-DL" else res.get(f, 0.0)
    melt, clear = mmt(f, i_f), tct(f, i_f)
    feeders = [(R1, res["R1"])]
    feeders.append(((R2_RV if DSDR else R2) if node in UPSTREAM_OF_R2 else R2, res["R2"]))
    if node not in UPSTREAM_OF_R2:
        feeders = feeders[1:]
    for rec, i in feeders:
        if i <= rec[1]:
            continue
        t_f, t_d = rec_times(rec, i)
        if t_f >= melt:
            return "X", "%s fast %.3f s at %.0f A is not before %s melting %.3f s at %.0f A" % (
                rec[0], t_f, i, f, melt, i_f)
        if clear >= t_d:
            return "X", "%s clears %.3f s at %.0f A, after %s delayed %.3f s at %.0f A" % (
                f, clear, i_f, rec[0], t_d, i)
    return "OK", ""


def chart(heading, cells, compare=None):
    """Grid drawn like the paper's figure: fault types top to bottom (LG ... LLL), faulted
    nodes left to right along an arrow, one circled symbol per cell, cells joined by lines.
    With 'compare', nodes with any cell different from it are marked '*' under the axis."""
    pre = "   %-4s   "                   # row label, then the grid
    width = 6 * len(NODES)
    out("")
    out("   " + heading)
    out("   " + " " * 18 + "(v) Exist     (x) Doesn't Exist     (-) Not Applicable")
    out("   Fault Type")
    for r, ft in enumerate(FAULTS):
        cellrow = "-".join("-(%s)-" % cells[(n, ft)] for n in NODES)
        out(pre % ft + "|-" + cellrow)
        link = " ".join("  |  " for _ in NODES)
        out(pre % "" + "| " + link)
    out(pre % "" + "+-" + "-" * (width + 1) + ">")
    out(pre % "" + "  " + "".join("%-6s" % (" " + LABEL.get(n, n)) for n in NODES))
    if compare:
        out(pre % "" + "  " + "".join("%-6s" % ("  *" if any(
            compare[(n, ft)] != cells[(n, ft)] for ft in FAULTS) else "") for n in NODES))
    out(pre % "" + " " * (width // 2 - 4) + "Faulted Node")


def main(clear=True, dsdr=None):
    """clear: empty the Output Window first; dsdr: override DSDR (Show_Progress.py)."""
    global DSDR
    if dsdr is not None:
        DSDR = dsdr
    if clear:
        try:
            app.GetOutputWindow().Clear()
        except Exception:
            pass
    shc = app.GetFromStudyCase("ComShc")
    terms = {t.loc_name: t for t in app.GetCalcRelevantObjects("*.ElmTerm")}
    pts = points()
    dgs = app.GetCalcRelevantObjects("*.ElmSym")
    state = [g.outserv for g in dgs]
    grid, notes = {}, []
    app.EchoOff()
    try:
        for g in dgs:
            g.outserv = 0
        for node in NODES:
            for ft in FAULTS:
                s, why = classify(node, fault(terms[node], ft, pts, shc))
                grid[(node, ft)] = s
                if s == "X":
                    notes.append("%-3s %-4s %s" % (LABEL.get(node, node), ft, why))
    finally:
        app.EchoOn()
        for g, st in zip(dgs, state):
            g.outserv = st

    title = ("Fig. 17. Classification of the protection coordination for all the nodes "
             "against different fault types by utilizing the proposed protection strategy "
             "with DSDR." if DSDR else
             "Fig. 14. Classification of the protection coordination for all the nodes "
             "against different fault types without the DSDR.")
    paper = PAPER_GRID["Fig17" if DSDR else "Fig14"]
    model = {k: SYMBOL[v] for k, v in grid.items()}
    chart("MODEL (PowerFactory, DG in service)", model)
    chart("PAPER (Yousaf et al. 2022)", {(n, ft): paper[ft][c]
                                         for c, n in enumerate(NODES) for ft in FAULTS},
          model)
    out(title)
    held = sum(1 for v in grid.values() if v == "OK")
    lost = sum(1 for v in grid.values() if v == "X")
    both = [(n, ft) for n in NODES for ft in FAULTS
            if model[(n, ft)] != "-" and paper[ft][NODES.index(n)] != "-"]
    diff = [(n, ft) for n, ft in both if model[(n, ft)] != paper[ft][NODES.index(n)]]
    out("")
    out("Model: exist %d, doesn't exist %d." % (held, lost))
    out("Against the paper, cells rated in both: %d agree, %d differ%s" % (
        len(both) - len(diff), len(diff), (" (" + ", ".join(
            "%s %s" % (LABEL.get(n, n), ft) for n, ft in diff) + ")") if diff else ""))
    out("The paper also rates 632 and 671, which have no fuse in the faulted path; the")
    out("model marks them not applicable (no recloser-fuse pair to check).")
    if notes:
        out("")
        out("Why coordination doesn't exist (model):")
        for n in notes:
            out("  " + n)


if __name__ == "__main__":
    main()
