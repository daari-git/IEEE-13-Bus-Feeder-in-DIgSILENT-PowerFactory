"""
Reproduce TABLE II of Yousaf et al. (IEEE Trans. Ind. Appl., 2022):
"Maximum / Minimum / Rated branch current for IEEE 13-node radial feeder".

  I_nom    : unbalanced (ABC) load flow, largest phase current at the PD (From) end   [A]
  I_f,max  : bolted 3-phase fault (Rf = 0) at the downstream node                    [kA]
  I_f,min  : single-line-to-ground fault with Rf = 3 ohm at the farthest node(s)     [kA]

Fault currents are reported two ways:
  "branch" = current flowing through the PD location (From end of the branch)
  "bus"    = total fault current at the faulted node (sum of all infeeds)
The paper does not say which one it tabulates, so compare both with its values.

HOW TO RUN (inside PowerFactory 2021 SP2 - recommended)
  1. Install Python 3.9 (64-bit) and select it in
     Tools > Configuration > Python  (PowerFactory 2021 SP2 supports 3.6 - 3.9).
  2. Activate your project "Thesis" and its study case.
  3. In the Data Manager, inside the study case: New Object > Python Script (ComPython),
     point it to this file and click Execute.
  Results appear in the output window and are saved as CSV next to this file.

HOW TO RUN (externally, PowerFactory GUI must be closed - licence)
  "C:\\path\\to\\Python39\\python.exe" table2_generator.py
"""

import os
import sys

# --------------------------------------------------------------------------------------
# USER SETTINGS
# --------------------------------------------------------------------------------------
PROJECT_NAME = "IEEE 13 Node Feeder"   # only used when run externally
DG_IN_LOADFLOW = False           # paper I_nom = feeder loading without the DG at 692
DG_IN_SHORTCIRCUIT = True        # include the DG in the fault calculations
RF_MIN = 3.0                     # fault resistance for I_f,min (ohm), paper uses 3 ohm
# I_f,max fault type on nodes that do not have 3 phases. The paper quotes 3.64 kA for a
# "solid line-line fault at node 646", identical to its Table II value -> use '2psc'.
MAX_FAULT_2PH = "2psc"           # '2psc' (LL) or '2pgf' (LLG)
MAX_FAULT_1PH = "spgf"           # single-phase laterals 611 / 652

# Table I of the paper (SBDG short-circuit parameters), written to the generator type
# (TypSym) before the calculation. Set APPLY_TABLE_I = False to keep your own data.
APPLY_TABLE_I = True
TABLE_I = {"xd": 1.4, "xq": 1.372, "xds": 0.231, "xqs": 0.8, "xdss": 0.118, "xqss": 0.118,
           "xl": 0.05, "rstr": 0.0014}
OUT_DIR = r"D:\Protection and co-ordination"
OUT_CSV = os.path.join(OUT_DIR, "Table_II_results.csv")
OUT_LOG = os.path.join(OUT_DIR, "Table_II_log.txt")
OUT_PF = os.path.join(OUT_DIR, "PF_output_window.txt")   # PowerFactory's own messages

# Short-circuit methods of the ComShc "Method" drop-down (iopt_mde index, name).
# Only the Complete method works on this feeder. IEC 60909 / VDE 0102 / ANSI / IEC 61363
# are balanced (sequence-domain) methods: they cannot pass current through the three
# single-phase regulators VregA/B/C (vector group Ii0) or fault the 1-/2-phase laterals,
# so they return 0 kA at the feeder head, NaN and red errors. Tested 26-09-2026.
SC_METHODS = [
    (3, "Complete"),
    # (1, "IEC 60909"),
    # (0, "VDE 0102"),
    # (2, "ANSI C37"),
    # (4, "IEC 61363"),
]

# The paper does not give its external-grid data, and the fault levels depend on it.
# Every combination below is calculated and scored against the paper; the best one is
# reported. None = keep the value in your model. The model is restored afterwards.
GRID_SWEEP_MVA = [None, 25, 35, 50, 75, 100, 150, 300]
DG_SWEEP = [True, False]          # DG in service during the fault calculation

# Rows of Table II.
#   label_from, label_to : text printed in the table
#   frm, to              : terminal names in the PowerFactory model (ElmTerm loc_name)
#   elem                 : fixed element name (only for the transformer rows), else None
#   side                 : for the transformer rows, which side the PD is on ('bushv'/'buslv')
#   max_bus              : node for the 3-phase bolted fault
#   min_buses            : candidate farthest nodes for the SLG fault (minimum is taken)
#   paper                : (I_nom A, I_fmin kA, I_fmax kA) from the paper
ROWS = [
    dict(label_from="RG60", label_to="632", frm="RG60", to="632", max_bus="632",
         min_buses=["611", "652", "675", "680", "646", "633"], paper=(587.1, 1.24, 5.41)),
    dict(label_from="632", label_to="633", frm="632", to="633", max_bus="633",
         min_buses=["633"], paper=(81.1, 0.72, 6.73)),
    dict(label_from="632", label_to="645", frm="632", to="645", max_bus="645",
         min_buses=["645", "646"], paper=(143.3, 0.93, 4.25)),
    dict(label_from="632", label_to="671", frm="632", to="671", max_bus="671",
         min_buses=["671", "680", "684", "611", "652", "692", "675"], paper=(478.2, 1.08, 4.52)),
    # 6.48 kA cannot flow through a 0.5 MVA transformer (rated HV current 69 A): the
    # paper's value is the fault at the transformer HV terminal (node 633), so the
    # total bus fault current is compared for this row.
    dict(label_from="XFM1-HV", label_to="side", elem="XFM-1", side="bushv", max_bus="633",
         min_buses=["633"], measure="bus", paper=(81.1, 0.73, 6.48)),
    dict(label_from="XFM1-LV", label_to="side", elem="XFM-1", side="buslv", max_bus="634",
         min_buses=["634"], paper=(704.7, 0.59, 18.76)),
    dict(label_from="645", label_to="646", frm="645", to="646", max_bus="646",
         min_buses=["646"], paper=(64.9, 0.84, 3.64)),
    dict(label_from="671", label_to="692", frm="671", to="692", max_bus="692",
         min_buses=["692", "675"], paper=(229.3, 0.78, 3.69)),
    dict(label_from="671", label_to="684", frm="671", to="684", max_bus="684",
         min_buses=["684", "611", "652"], paper=(70.9, 0.69, 3.47)),
    dict(label_from="671", label_to="680", frm="671", to="680", max_bus="680",
         min_buses=["680"], paper=(0.0, 0.59, 6.25)),
    dict(label_from="692", label_to="675", frm="692", to="675", max_bus="675",
         min_buses=["675"], paper=(205.9, 0.71, 7.83)),
    dict(label_from="684", label_to="611", frm="684", to="611", max_bus="611",
         min_buses=["611"], paper=(70.8, 0.63, 1.93)),
    dict(label_from="684", label_to="652", frm="684", to="652", max_bus="652",
         min_buses=["652"], paper=(63.1, 0.66, 2.67)),
]

BRANCH_CLASSES = ("ElmLne", "ElmTr2", "ElmCoup", "ElmZpu", "ElmSind", "ElmVoltreg")
CUBICLE_KEYS = ("bus1", "bus2", "bushv", "buslv")
PHASES = ("A", "B", "C")


# --------------------------------------------------------------------------------------
# PowerFactory connection
# --------------------------------------------------------------------------------------
def get_app():
    try:
        import powerfactory as pf  # works when executed inside PowerFactory
    except ImportError:
        sys.path.append(r"C:\Program Files\DIgSILENT\PowerFactory 2021 SP2\Python\3.9")
        import powerfactory as pf
    app = pf.GetApplication()
    if app is None:
        raise RuntimeError("Could not start/connect to PowerFactory")
    if app.GetActiveProject() is None:
        if app.ActivateProject(PROJECT_NAME) != 0:
            raise RuntimeError("Could not activate project '%s'" % PROJECT_NAME)
    return app


app = get_app()


open(OUT_LOG, "w").close()


def log(msg=""):
    app.PrintPlain(str(msg))
    with open(OUT_LOG, "a") as fh:  # copy of the output window
        fh.write(str(msg) + "\n")


def attr(obj, name, default=None):
    try:
        v = obj.GetAttribute(name)
        return default if v is None else v
    except Exception:
        return default


def set_attr(obj, names, value):
    """Set the first attribute name that exists (attribute names vary between versions)."""
    for n in names:
        try:
            obj.SetAttribute(n, value)
            return True
        except Exception:
            continue
    log("  ! could not set any of %s on %s" % (names, obj.loc_name))
    return False


# --------------------------------------------------------------------------------------
# Topology helpers
# --------------------------------------------------------------------------------------
TERMS = {t.loc_name: t for t in app.GetCalcRelevantObjects("*.ElmTerm")}


def term(name):
    if name not in TERMS:
        raise KeyError("Terminal '%s' not found. Available: %s" % (name, sorted(TERMS)))
    return TERMS[name]


def is_branch(obj):
    return obj is not None and obj.GetClassName() in BRANCH_CLASSES


def branch_ends(br):
    """{cubicle_key: terminal} for a branch element."""
    ends = {}
    for k in CUBICLE_KEYS:
        cub = attr(br, k)
        if cub is not None:
            t = attr(cub, "cterm")
            if t is not None:
                ends[k] = t
    return ends


def branches_at(t):
    return [e for e in t.GetConnectedElements() if is_branch(e)]


def reaches(start_terms, target, blocked):
    """Breadth-first search through branches, never crossing the 'blocked' terminal."""
    seen = {blocked.GetFullName()}
    queue = list(start_terms)
    while queue:
        t = queue.pop(0)
        key = t.GetFullName()
        if key in seen:
            continue
        seen.add(key)
        if t == target:
            return True
        for br in branches_at(t):
            for nt in branch_ends(br).values():
                if nt.GetFullName() not in seen:
                    queue.append(nt)
    return False


def find_pd_branch(frm_name, to_name):
    """Branch element at terminal 'frm' that leads towards 'to', and its cubicle key at 'frm'."""
    frm, to = term(frm_name), term(to_name)
    for br in branches_at(frm):
        ends = branch_ends(br)
        key_at_from = [k for k, t in ends.items() if t == frm]
        others = [t for k, t in ends.items() if t != frm]
        if key_at_from and others and reaches(others, to, frm):
            return br, key_at_from[0]
    raise RuntimeError("No branch found from %s towards %s" % (frm_name, to_name))


def resolve_row(row):
    if row.get("elem"):
        objs = app.GetCalcRelevantObjects(row["elem"] + ".ElmTr2")
        if not objs:
            raise RuntimeError("Transformer '%s' not found" % row["elem"])
        return objs[0], row["side"]
    return find_pd_branch(row["frm"], row["to"])


# --------------------------------------------------------------------------------------
# Result read-out
# --------------------------------------------------------------------------------------
def branch_phase_current(br, key, calc):
    """Largest phase current magnitude (kA) at cubicle 'key' of branch 'br'."""
    names = (["m:I:%s:%s" % (key, p) for p in PHASES] if calc == "ldf" else
             ["m:Ikss:%s:%s" % (key, p) for p in PHASES] + ["m:I:%s:%s" % (key, p) for p in PHASES])
    vals = [abs(attr(br, n, 0.0) or 0.0) for n in names]
    best = max(vals) if vals else 0.0
    if best == 0.0:  # balanced/positive-sequence fallback
        best = abs(attr(br, "m:Ikss:%s" % key, 0.0) or attr(br, "m:I:%s" % key, 0.0) or 0.0)
    return best


def bus_fault_current(t):
    vals = [abs(attr(t, "m:Ikss:%s" % p, 0.0) or 0.0) for p in PHASES]
    best = max(vals)
    return best if best > 0 else abs(attr(t, "m:Ikss", 0.0) or 0.0)


# --------------------------------------------------------------------------------------
# Calculations
# --------------------------------------------------------------------------------------
DGS = app.GetCalcRelevantObjects("*.ElmSym")


def set_dg(in_service):
    for g in DGS:
        g.outserv = 0 if in_service else 1


def run_loadflow():
    ldf = app.GetFromStudyCase("ComLdf")
    ldf.iopt_net = 1                      # 1 = AC load flow, unbalanced 3-phase (ABC)
    if ldf.Execute() != 0:
        raise RuntimeError("Load flow did not converge")


SHC = app.GetFromStudyCase("ComShc")


def run_fault(bus, kind, rf=0.0, phase=0, quiet=False, method=3, minimum=False):
    """kind: '3psc'/'3rst' (3-phase), '2psc', '2pgf' or 'spgf'.
    phase: 0/1/2 selects the faulted phase (spgf) or phase pair (2psc/2pgf).
    minimum: IEC/VDE/ANSI 'minimum short-circuit current' (c_min) instead of maximum."""
    SHC.iopt_mde = method
    SHC.iopt_allbus = 0                   # user-selected location
    SHC.shcobj = bus
    SHC.iopt_shc = kind
    SHC.Rf = rf
    SHC.Xf = 0.0
    if method != 3:
        try:
            SHC.SetAttribute("iopt_cur", 1 if minimum else 0)
        except Exception:
            pass
    phase_attr = {"spgf": "i_pspgf", "2psc": "i_p2psc", "2pgf": "i_p2pgf"}.get(kind)
    if phase_attr:
        try:
            SHC.SetAttribute(phase_attr, phase)
        except Exception:
            pass
    err = SHC.Execute()
    if err != 0 and not quiet:
        log("  ! %s fault at %s failed (error %s)" % (kind, bus.loc_name, err))
    return err == 0


# '3psc' is the balanced 3-phase fault and is refused on this unbalanced feeder,
# '3rst' is the 3-phase fault evaluated in the phase (ABC) domain.
# Laterals 645/646/684 (2-phase) and 611/652 (1-phase) cannot have a 3-phase fault.
PHASES_AT = {}   # terminal name -> list of existing phase indices, filled after load flow


def detect_phases():
    for name, t in TERMS.items():
        ph = [i for i, p in enumerate(PHASES) if (attr(t, "m:u:%s" % p, 0.0) or 0.0) > 0.05]
        PHASES_AT[name] = ph or [0, 1, 2]


def run_max_fault(bus, br, key, method):
    """Returns (branch kA, bus kA, fault type) of the most severe bolted fault at 'bus'."""
    nph = len(PHASES_AT.get(bus.loc_name, [0, 1, 2]))
    if nph == 3:
        # '3psc' = balanced 3-phase fault (IEC/VDE/ANSI), '3rst' = ABC-domain 3-phase
        # fault (the complete method refuses '3psc' on this unbalanced feeder)
        kinds, phase_opts = (["3rst"] if method == 3 else ["3psc", "3rst"]), [0]
    elif nph == 2:
        kinds, phase_opts = [MAX_FAULT_2PH], [0, 1, 2]  # only the existing pair will solve
    else:
        kinds, phase_opts = [MAX_FAULT_1PH], PHASES_AT[bus.loc_name]
    best = (float("nan"), float("nan"), "none")
    for kind in kinds:
        for ph in phase_opts:
            if not run_fault(bus, kind, 0.0, ph, quiet=True, method=method):
                continue
            i_bus = bus_fault_current(bus)
            if i_bus > 1e-6 and not (best[1] >= i_bus):
                best = (branch_phase_current(br, key, "shc"), i_bus, kind)
        if nph == 3 and best[2] != "none":
            break
    return best


def apply_table_i():
    for g in DGS:
        typ = attr(g, "typ_id")
        if typ is None:
            continue
        for name, val in TABLE_I.items():
            old = attr(typ, name)
            try:
                typ.SetAttribute(name, val)
                log("Generator type %s: %s %s -> %s" % (typ.loc_name, name, old, val))
            except Exception:
                log("  ! generator type has no attribute '%s'" % name)


def log_source_data():
    """Source data that sets the fault levels - compare these with the paper's model."""
    for g in app.GetCalcRelevantObjects("*.ElmXnet"):
        log("External grid %-12s Sk''max=%s MVA  R/X max=%s  Sk''min=%s MVA  c=%s"
            % (g.loc_name, attr(g, "snss"), attr(g, "rntxn"), attr(g, "snssmin"),
               attr(g, "cfac")))
    for g in DGS:
        typ = attr(g, "typ_id")
        log("Generator %-16s S=%s MVA  x''d=%s pu  (out of service=%s)"
            % (g.loc_name, attr(typ, "sgn"), attr(typ, "xdss"), g.outserv))
    for t in app.GetCalcRelevantObjects("*.ElmTr2"):
        typ = attr(t, "typ_id")
        log("Transformer %-14s %s MVA  %s/%s kV  uk=%s %%  vector group=%s"
            % (t.loc_name, attr(typ, "strn"), attr(typ, "utrn_h"), attr(typ, "utrn_l"),
               attr(typ, "uktr"), attr(typ, "vecgrp")))


GRIDS = app.GetCalcRelevantObjects("*.ElmXnet")


def set_grid(mva):
    """mva=None keeps the model value; otherwise Sk''max and Sk''min are both set."""
    for g in GRIDS:
        if mva is not None:
            g.SetAttribute("snss", float(mva))
            g.SetAttribute("snssmin", float(mva))


def run_min_fault(r, br, key, method):
    """SLG fault through RF_MIN at the farthest node(s): (branch kA, bus kA), minimum taken."""
    best_br, best_bus = float("inf"), float("inf")
    for bname in r["min_buses"]:
        for ph in PHASES_AT.get(bname, [0, 1, 2]):
            if not run_fault(term(bname), "spgf", RF_MIN, ph, quiet=True, method=method,
                             minimum=True):
                continue
            i_bus = bus_fault_current(term(bname))
            if i_bus <= 1e-6:  # phase does not exist at this node
                continue
            best_bus = min(best_bus, i_bus)
            best_br = min(best_br, branch_phase_current(br, key, "shc"))
    nan = float("nan")
    return (best_br if best_br < float("inf") else nan,
            best_bus if best_bus < float("inf") else nan)


def match(mine, paper):
    """Agreement with the paper in % (100 = identical, 0 = off by 100 % or more)."""
    if mine != mine:  # nan
        return float("nan")
    if paper == 0:
        return 100.0 if abs(mine) < 0.5 else 0.0
    return max(0.0, 100.0 - abs(mine - paper) / abs(paper) * 100.0)


def fmt(v, spec, width):
    """Number formatted with 'spec', or 'n/a' when not calculated (nan)."""
    return ("%" + str(width) + "s") % "n/a" if v != v else ("%" + str(width) + spec) % v


def mean(vals):
    vals = [v for v in vals if v == v]
    return sum(vals) / len(vals) if vals else float("nan")


def save_output_window():
    """Copy PowerFactory's output window (including its red errors) to OUT_PF."""
    try:
        ow = app.GetOutputWindow()
        try:
            ow.Save(OUT_PF)
        except Exception:
            with open(OUT_PF, "w") as fh:
                fh.write("\n".join(str(x) for x in ow.GetContent()))
    except Exception as e:
        log("Could not save the output window: %s" % e)


def main():
    try:
        app.GetOutputWindow().Clear()
    except Exception:
        pass
    old_dg = [g.outserv for g in DGS]
    old_grid = [(attr(g, "snss"), attr(g, "snssmin")) for g in GRIDS]
    studies = []   # (method name, [row results])
    try:
        pd = {id(r): resolve_row(r) for r in ROWS}
        for r in ROWS:
            br, key = pd[id(r)]
            log("%-8s %-5s -> %s (%s) at %s" % (r["label_from"], r["label_to"],
                                               br.loc_name, br.GetClassName(), key))

        # ---- I_nom : unbalanced load flow --------------------------------------------
        set_dg(DG_IN_LOADFLOW)
        run_loadflow()
        detect_phases()
        if APPLY_TABLE_I:
            apply_table_i()
        log_source_data()
        app.EchoOff()   # hide PowerFactory's messages for fault types probed on missing phases
        inom = {id(r): branch_phase_current(*pd[id(r)], calc="ldf") for r in ROWS}
        if max(inom.values()) < 5.0:  # results came back in kA, convert to A
            inom = {k: 1000.0 * v for k, v in inom.items()}

        # ---- Fault currents: method x grid strength x DG in/out -----------------------
        variants = [(m, g, d) for m in SC_METHODS for g in GRID_SWEEP_MVA for d in DG_SWEEP]
        for (mde, mname), mva, dg in variants:
            set_dg(dg)
            set_grid(mva)
            gname = "model %.0f" % old_grid[0][0] if mva is None and old_grid else str(mva)
            study = "%s | grid Sk''=%s MVA | DG %s" % (mname, gname, "in" if dg else "out")
            log()
            log("=== %s ===" % study)
            rows = []
            for r in ROWS:
                br, key = pd[id(r)]
                mxb, mxbus, kind = run_max_fault(term(r["max_bus"]), br, key, mde)
                mnb, mnbus = run_min_fault(r, br, key, mde)
                log("  %-8s %-5s If,max at %-4s: %-4s branch %.3f bus %.3f | "
                    "If,min branch %.3f bus %.3f kA"
                    % (r["label_from"], r["label_to"], r["max_bus"], kind, mxb, mxbus,
                       mnb, mnbus))
                rows.append((r["label_from"], r["label_to"], inom[id(r)],
                             mnb, mnbus, mxb, mxbus, r["paper"], r.get("measure", "branch")))
            for g, (sn, snmin) in zip(GRIDS, old_grid):  # back to the model value
                g.SetAttribute("snss", sn)
                g.SetAttribute("snssmin", snmin)
            studies.append((study, rows))
    finally:
        app.EchoOn()
        for g, o in zip(DGS, old_dg):
            g.outserv = o
        for g, (sn, snmin) in zip(GRIDS, old_grid):
            g.SetAttribute("snss", sn)
            g.SetAttribute("snssmin", snmin)
        save_output_window()

    # ---- Score every study on the value the paper tabulates ------------------------------
    # "used" = branch current at the PD (Table II is "branch current"), or the total bus
    # fault current for rows marked measure="bus".
    scored = []
    for study, rows in studies:
        out = []
        for f, t, i_n, mnb, mnbus, mxb, mxbus, p, meas in rows:
            mn = mnbus if meas == "bus" else mnb
            mx = mxbus if meas == "bus" else mxb
            out.append((f, t, i_n, p[0], match(i_n, p[0]), mn, p[1], match(mn, p[1]),
                        mx, p[2], match(mx, p[2]), meas, mnb, mnbus, mxb, mxbus))
        a_in = mean([o[4] for o in out])
        a_mn = mean([o[7] for o in out])
        a_mx = mean([o[10] for o in out])
        scored.append((study, out, a_in, a_mn, a_mx, mean([a_in, a_mn, a_mx])))

    log()
    log("SUMMARY - average match with the paper (100 - |mine - paper| / paper x 100)")
    log("%-58s %7s %9s %9s %9s" % ("Study", "Inom", "If,min", "If,max", "Overall"))
    for study, out, a_in, a_mn, a_mx, a_all in sorted(scored, key=lambda x: -x[5]):
        log("%-58s %s%% %s%% %s%% %s%%" % (study, fmt(a_in, ".0f", 6), fmt(a_mn, ".0f", 8),
                                          fmt(a_mx, ".0f", 8), fmt(a_all, ".0f", 8)))

    best = max(scored, key=lambda x: x[5])
    log()
    log("BEST MATCH: %s" % best[0])
    log("-" * 96)
    log("%-8s %-5s | %7s %7s %6s | %6s %6s %6s | %6s %6s %6s | %s"
        % ("From", "To", "Inom A", "paper", "match", "If,min", "paper", "match",
           "If,max", "paper", "match", "value"))
    log("-" * 96)
    for o in best[1]:
        log("%-8s %-5s | %7.1f %7.1f %s | %s %6.2f %s | %s %6.2f %s | %s"
            % (o[0], o[1], o[2], o[3], fmt(o[4], ".0f", 5) + "%", fmt(o[5], ".2f", 6), o[6],
               fmt(o[7], ".0f", 5) + "%", fmt(o[8], ".2f", 6), o[9],
               fmt(o[10], ".0f", 5) + "%", o[11]))
    log("-" * 96)
    log("AVERAGE MATCH: Inom %.0f%% | If,min %.0f%% | If,max %.0f%% | overall %.0f%%"
        % best[2:6])

    # ---- CSV (all studies; the colour-coded Excel report is built from this) ------------
    try:
        with open(OUT_CSV, "w") as fh:
            fh.write("Study,From,To,Inom_A,Inom_paper_A,Inom_match_%,"
                     "Ifmin_kA,Ifmin_paper_kA,Ifmin_match_%,Ifmax_kA,Ifmax_paper_kA,"
                     "Ifmax_match_%,Compared_value,Ifmin_branch_kA,Ifmin_bus_kA,"
                     "Ifmax_branch_kA,Ifmax_bus_kA\n")
            for study, out, _, _, _, _ in scored:
                for o in out:
                    fh.write('"%s",%s,%s,%.1f,%.1f,%.1f,%.3f,%.2f,%.1f,%.3f,%.2f,%.1f,%s,'
                             '%.3f,%.3f,%.3f,%.3f\n' % ((study,) + tuple(o)))
        log("Saved: " + OUT_CSV)
    except Exception as e:
        log("Could not write CSV (close it in Excel first): %s" % e)


main()
