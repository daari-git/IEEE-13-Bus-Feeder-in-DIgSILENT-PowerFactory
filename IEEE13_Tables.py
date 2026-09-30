"""
IEEE 13-node feeder - TABLE II and TABLE III of Yousaf et al., IEEE Trans. Ind. Appl., 2022

TABLE II: maximum / minimum / rated branch current
  I_nom   : unbalanced AC load flow (ABC), largest phase current at the PD (From) end  [A]
  I_f,max : bolted 3-phase fault at the downstream node, current through the PD       [kA]
            (maximum short-circuit conditions). Where that node has only two phases or
            one phase (645, 646, 684 / 611, 652) a 3-phase fault cannot exist; the
            largest fault that can (line-line / line-ground) is used instead.
  I_f,min : single line-to-ground fault through 3 ohm at the farthest downstream
            node(s), minimum short-circuit conditions                               [kA]

TABLE III: fuse coefficient b_i for recloser-fuse coordination (fuse-saving)
  Ip      = OLF * I_nom of the recloser branch                                   (3)
  t_F,t_D = TDS_F, TDS_D * GE IAC extremely inverse curve at M = I_rec / Ip      (1),(2)
  b_i     = log10(t_F + i/(z+1) * (t_D - t_F)) - a * log10(I_f,i)                (7),(9)
            I_f,i: bolted fault just below fuse i (as I_f,max), current through the fuse [A]
            z: fuses in series on the faulted path, i: position of fuse i counted from the
            recloser (z = 1 reduces (9) to (7)). Fuse placement as in Fig. 6 of the paper.

Settings: Complete short-circuit method, external grid as in the model, DG out of service
(the tables describe the base feeder). The DG in-service state is restored at the end.

Run: Python Script (ComPython) in the study case -> Execute  (Python 3.9 selected under
Tools > Configuration > Python). The tables appear in the Output Window and are saved as
Table_II.csv and Table_III.csv in the folder below.
"""

import os
from math import log10

import powerfactory as pf

OUT_DIR = r"D:\Protection and co-ordination\Result"
os.makedirs(OUT_DIR, exist_ok=True)
RF_MIN = 3.0      # fault resistance for I_f,min (ohm)
CUR_MAX, CUR_MIN = 0, 1   # ComShc "Max./Min. short-circuit currents" (iopt_cur)
DG_IN_SERVICE = False

# ---- Table III settings ------------------------------------------------------------------
OLF = 1.25        # overload factor for recloser pickup
A_FUSE = -1.8     # fuse slope a_i, same for all fuses

# Reclosers: branch (Table II row) whose I_nom sets Ip, and time dials for fast/delayed.
# R1 (GE IAC77B801A): TDS 0.5 / 10 as given in the paper.
# R2 (GE Alstom CDG34): TDS not given in the paper; 0.8 / 4.0 fits the paper's R2-side b_i.
RECLOSERS = {
    "R1": dict(row="RG60-632", tds_f=0.5, tds_d=10.0),
    "R2": dict(row="632-671", tds_f=0.8, tds_d=4.0),
}

# GE IAC extremely inverse: t = TDS * (A + B/(M-C) + D/(M-C)^2 + E/(M-C)^3)
IAC_EI = (0.0040, 0.6379, 0.6200, 1.7872, 0.2461)

# fuse, recloser, Table II row carrying the fuse current and whose I_f,max node is faulted,
# i (position from the recloser), z (fuses in series on the path), b_i in the paper
FUSES = [
    ("F632", "R1", "632-645", 1, 2, 6.38),
    ("F633", "R1", "632-633", 1, 2, 6.83),
    ("F634", "R1", "XFM1-LV-side", 2, 2, 8.32),
    ("F645", "R1", "632-645", 2, 2, 6.65),
    ("F646", "R1", "645-646", 2, 2, 6.67),
    ("F-DL", "R1", "632-671", 1, 1, 6.54),
    ("F671", "R2", "671-680", 1, 1, 6.08),
    ("F671-1", "R2", "671-692", 1, 3, 5.85),
    ("F692", "R2", "671-692", 2, 2, 6.13),
    ("F692-R", "R2", "692-675", 2, 3, 6.14),
    ("F675", "R2", "692-675", 3, 3, 6.19),
    ("F671-2", "R2", "671-684", 1, 3, 5.87),
    ("F684", "R2", "684-611", 2, 3, 6.15),
    ("F611", "R2", "684-611", 3, 3, 6.19),
    ("F652", "R2", "684-652", 2, 2, 6.17),
]

# label_from, label_to, PD branch (from/to terminals, or transformer + side),
# node for I_f,max, candidate farthest nodes for I_f,min
ROWS = [
    dict(lf="RG60", lt="632", frm="RG60", to="632", max_bus="632",
         min_buses=["611", "652", "675", "680", "646", "633"]),
    dict(lf="632", lt="633", frm="632", to="633", max_bus="633", min_buses=["633"]),
    dict(lf="632", lt="645", frm="632", to="645", max_bus="645", min_buses=["645", "646"]),
    dict(lf="632", lt="671", frm="632", to="671", max_bus="671",
         min_buses=["671", "680", "684", "611", "652", "692", "675"]),
    # HV side of XFM-1: fault at its HV terminal (633), total fault current
    dict(lf="XFM1-HV", lt="side", elem="XFM-1", side="bushv", max_bus="633",
         min_buses=["633"], measure="bus"),
    dict(lf="XFM1-LV", lt="side", elem="XFM-1", side="buslv", max_bus="634",
         min_buses=["634"]),
    dict(lf="645", lt="646", frm="645", to="646", max_bus="646", min_buses=["646"]),
    dict(lf="671", lt="692", frm="671", to="692", max_bus="692", min_buses=["692", "675"]),
    dict(lf="671", lt="684", frm="671", to="684", max_bus="684",
         min_buses=["684", "611", "652"]),
    dict(lf="671", lt="680", frm="671", to="680", max_bus="680", min_buses=["680"]),
    dict(lf="692", lt="675", frm="692", to="675", max_bus="675", min_buses=["675"]),
    dict(lf="684", lt="611", frm="684", to="611", max_bus="611", min_buses=["611"]),
    dict(lf="684", lt="652", frm="684", to="652", max_bus="652", min_buses=["652"]),
]

BRANCH_CLASSES = ("ElmLne", "ElmTr2", "ElmCoup", "ElmZpu", "ElmSind", "ElmVoltreg")
CUBICLE_KEYS = ("bus1", "bus2", "bushv", "buslv")
PHASES = ("A", "B", "C")
NAN = float("nan")

try:
    app            # one shared Application when loaded by Show_Progress.py
except NameError:
    app = pf.GetApplication()


def attr(obj, name, default=None):
    try:
        v = obj.GetAttribute(name)
        return default if v is None else v
    except Exception:
        return default


# ---- topology ----------------------------------------------------------------------------
TERMS = {t.loc_name: t for t in app.GetCalcRelevantObjects("*.ElmTerm")}


def branch_ends(br):
    ends = {}
    for k in CUBICLE_KEYS:
        cub = attr(br, k)
        t = attr(cub, "cterm") if cub is not None else None
        if t is not None:
            ends[k] = t
    return ends


def branches_at(t):
    return [e for e in t.GetConnectedElements() if e.GetClassName() in BRANCH_CLASSES]


def reaches(start, target, blocked):
    seen, queue = {blocked.GetFullName()}, list(start)
    while queue:
        t = queue.pop(0)
        if t.GetFullName() in seen:
            continue
        seen.add(t.GetFullName())
        if t == target:
            return True
        for br in branches_at(t):
            queue.extend(n for n in branch_ends(br).values() if n.GetFullName() not in seen)
    return False


def pd_branch(row):
    """Branch element at the PD location and its cubicle key on the From side."""
    if row.get("elem"):
        return app.GetCalcRelevantObjects(row["elem"] + ".ElmTr2")[0], row["side"]
    frm, to = TERMS[row["frm"]], TERMS[row["to"]]
    for br in branches_at(frm):
        ends = branch_ends(br)
        keys = [k for k, t in ends.items() if t == frm]
        others = [t for t in ends.values() if t != frm]
        if keys and others and reaches(others, to, frm):
            return br, keys[0]
    raise RuntimeError("No branch from %s towards %s" % (row["frm"], row["to"]))


# ---- results -----------------------------------------------------------------------------
def branch_current(br, key, var):
    """Largest phase current at cubicle 'key'; var = 'm:I' (load flow) or 'm:Ikss'."""
    return max(abs(attr(br, "%s:%s:%s" % (var, key, p), 0.0)) for p in PHASES)


def bus_current(t):
    return max(abs(attr(t, "m:Ikss:%s" % p, 0.0)) for p in PHASES)


# ---- calculations --------------------------------------------------------------------------
LDF = app.GetFromStudyCase("ComLdf")
SHC = app.GetFromStudyCase("ComShc")


def load_flow():
    LDF.iopt_net = 1                          # AC load flow, unbalanced 3-phase (ABC)
    if LDF.Execute() != 0:
        raise RuntimeError("Load flow did not converge")


def fault(bus, kind, rf=0.0, phase=0, cur=CUR_MAX):
    """Complete method. kind: '3rst' 3-phase, '2psc' line-line, 'spgf' line-ground.
    cur: CUR_MAX (maximum short-circuit currents) or CUR_MIN (minimum)."""
    SHC.iopt_mde = 3                          # complete method (phase domain)
    SHC.iopt_cur = cur
    SHC.iopt_allbus = 0
    SHC.shcobj = bus
    SHC.iopt_shc = kind
    SHC.Rf = rf
    SHC.Xf = 0.0
    sel = {"spgf": "i_pspgf", "2psc": "i_p2psc"}.get(kind)
    if sel:
        try:
            SHC.SetAttribute(sel, phase)
        except Exception:
            pass
    return SHC.Execute() == 0


def bolted_fault(name, points, phases):
    """Bolted fault at node 'name': 3-phase, line-line or line-ground depending on the
    phases present. Returns the Ikss (kA) at each point ((branch, key), or None for the
    total bus current) for the trial giving the largest current at the first point."""
    bus = TERMS[name]
    nph = len(phases[name])
    trials = ([("3rst", 0)] if nph == 3 else
              [("2psc", p) for p in range(3)] if nph == 2 else
              [("spgf", p) for p in phases[name]])
    best = [NAN] * len(points)
    for kind, ph in trials:
        if fault(bus, kind, 0.0, ph):
            vals = [bus_current(bus) if pt is None else branch_current(pt[0], pt[1], "m:Ikss")
                    for pt in points]
            if vals[0] > 1e-6 and not (best[0] >= vals[0]):
                best = vals
    return best


def iac_ei(m):
    """GE IAC extremely inverse curve at TDS = 1 (s)."""
    a, b, c, d, e = IAC_EI
    x = m - c
    return a + b / x + d / x ** 2 + e / x ** 3 if m > 1.0 else NAN


def save_csv(name, header, fmt, rows):
    path = os.path.join(OUT_DIR, name)
    try:
        with open(path, "w") as fh:
            fh.write(header + "\n")
            for r in rows:
                fh.write(fmt % r + "\n")
        app.PrintPlain("Saved: " + path)
    except IOError:
        app.PrintWarn("%s is open in Excel - close it to save the file." % name)


def main():
    cur_state = SHC.iopt_cur                  # study case setting, restored below
    dgs = app.GetCalcRelevantObjects("*.ElmSym")
    dg_state = [g.outserv for g in dgs]
    pds = [pd_branch(r) for r in ROWS]
    row_id = {"%s-%s" % (r["lf"], r["lt"]): k for k, r in enumerate(ROWS)}
    results, fuses = [], []
    try:
        for g in dgs:
            g.outserv = 0 if DG_IN_SERVICE else 1

        load_flow()
        inom = [branch_current(br, key, "m:I") for br, key in pds]
        if max(inom) < 5.0:                   # kA -> A
            inom = [1000.0 * v for v in inom]
        phases = {n: [i for i, p in enumerate(PHASES) if attr(t, "m:u:%s" % p, 0.0) > 0.05]
                  for n, t in TERMS.items()}
        phases = {n: ph or [0, 1, 2] for n, ph in phases.items()}

        # Line-line faults are tried for each phase pair; only the pair that exists
        # solves, so PowerFactory's messages are muted during the fault calculations.
        app.EchoOff()

        # ---- Table II ---------------------------------------------------------------------
        for row, (br, key), i_n in zip(ROWS, pds, inom):
            use_bus = row.get("measure") == "bus"
            point = None if use_bus else (br, key)

            # I_f,max
            i_max = bolted_fault(row["max_bus"], [point], phases)[0]

            # I_f,min
            i_min = float("inf")
            for name in row["min_buses"]:
                for ph in phases[name]:
                    if fault(TERMS[name], "spgf", RF_MIN, ph, CUR_MIN):
                        i = (bus_current(TERMS[name]) if use_bus
                             else branch_current(br, key, "m:Ikss"))
                        if i > 1e-6:
                            i_min = min(i_min, i)
            results.append((row["lf"], row["lt"], i_n,
                            i_min if i_min < float("inf") else NAN, i_max))

        # ---- Table III --------------------------------------------------------------------
        for fuse, rec, row, i, z, b_paper in FUSES:
            rc = RECLOSERS[rec]
            k_f, k_r = row_id[row], row_id[rc["row"]]
            i_f, i_r = bolted_fault(ROWS[k_f]["max_bus"], [pds[k_f], pds[k_r]], phases)
            i_f, i_r = 1000.0 * i_f, 1000.0 * i_r            # kA -> A
            ip = OLF * inom[k_r]
            k = iac_ei(i_r / ip)
            t_f, t_d = rc["tds_f"] * k, rc["tds_d"] * k
            b = log10(t_f + float(i) / (z + 1) * (t_d - t_f)) - A_FUSE * log10(i_f)
            fuses.append((fuse, rec, i, z, i_f, i_r, t_f, t_d, b, b_paper))
    finally:
        app.EchoOn()
        SHC.iopt_cur = cur_state
        for g, s in zip(dgs, dg_state):
            g.outserv = s

    dg = "in service" if DG_IN_SERVICE else "out of service"

    # ---- Output window: Table II ------------------------------------------------------------
    line = "-" * 54
    app.PrintPlain(line)
    app.PrintPlain("TABLE II   MAXIMUM / MINIMUM / RATED BRANCH CURRENT")
    app.PrintPlain("           IEEE 13-NODE RADIAL FEEDER")
    app.PrintPlain(line)
    app.PrintPlain("%-9s %-5s | %10s | %10s | %10s" % ("From", "To", "I_nom", "I_f,min", "I_f,max"))
    app.PrintPlain("%-9s %-5s | %10s | %10s | %10s" % ("", "", "(A)", "(kA)", "(kA)"))
    app.PrintPlain(line)
    for f, t, i_n, i_min, i_max in results:
        app.PrintPlain("%-9s %-5s | %10.1f | %10.2f | %10.2f" % (f, t, i_n, i_min, i_max))
    app.PrintPlain(line)
    app.PrintPlain("Load flow: AC unbalanced (ABC).  Short circuit: Complete method.")
    app.PrintPlain("I_f,max: bolted 3-phase fault at the downstream node, max. currents "
                   "(LL at 645, 646, 684 and LG at 611, 652: no 3-phase fault possible).")
    app.PrintPlain("I_f,min: single line-to-ground fault, Rf = %.0f ohm, farthest node, "
                   "min. currents.  DG %s." % (RF_MIN, dg))

    # ---- Output window: Table III -----------------------------------------------------------
    line = "-" * 80
    app.PrintPlain("")
    app.PrintPlain(line)
    app.PrintPlain("TABLE III  FUSE COEFFICIENTS (a_i, b_i) FOR RECLOSER-FUSE COORDINATION")
    app.PrintPlain(line)
    app.PrintPlain("%-7s %-3s %5s | %9s %9s | %7s %7s | %6s %6s" % (
        "Fuse", "Rec", "i/z", "I_fuse", "I_rec", "t_F", "t_D", "b_i", "paper"))
    app.PrintPlain("%-7s %-3s %5s | %9s %9s | %7s %7s | %6s %6s" % (
        "", "", "", "(A)", "(A)", "(s)", "(s)", "", ""))
    app.PrintPlain(line)
    for fuse, rec, i, z, i_f, i_r, t_f, t_d, b, b_paper in fuses:
        app.PrintPlain("%-7s %-3s %5s | %9.0f %9.0f | %7.3f %7.3f | %6.2f %6.2f" % (
            fuse, rec, "%d/%d" % (i, z), i_f, i_r, t_f, t_d, b, b_paper))
    app.PrintPlain(line)
    app.PrintPlain("a_i = %.1f.  Ip = %.2f x I_nom.  GE IAC extremely inverse.  %s.  DG %s." % (
        A_FUSE, OLF, ",  ".join("%s TDS %.2g/%.3g" % (r, c["tds_f"], c["tds_d"])
                                for r, c in sorted(RECLOSERS.items())), dg))

    # ---- CSV --------------------------------------------------------------------------------
    save_csv("Table_II.csv", "From,To,I_nom (A),I_f_min (kA),I_f_max (kA)",
             "%s,%s,%.1f,%.2f,%.2f", results)
    save_csv("Table_III.csv",
             "Fuse,Recloser,i,z,I_fuse (A),I_recloser (A),t_F (s),t_D (s),b_i,b_i paper",
             "%s,%s,%d,%d,%.0f,%.0f,%.3f,%.3f,%.2f,%.2f", fuses)


if __name__ == "__main__":
    main()
