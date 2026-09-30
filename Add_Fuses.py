"""
Add the 15 fuses of Yousaf et al. (2022), Fig. 6, to the IEEE 13-node feeder.

Fuse curve, eq. (6):  log10(t) = a * log10(I) + b_i,  a = -1.8,  b_i from Table III
  minimum melting time (MMT) : t = 10^b_i * I^a
  total clearing time  (TCT) : same curve at K x the current, K = clearing/melting current
                               ratio of the library fuse used as the template (about 1.2)

Each fuse gets its own fuse type (TypFuse) and characteristic (TypChatoc) in the project
library folder "Fuse Types Yousaf 2022". Both are copies of a tested fuse of the DIgSILENT
library (a new characteristic lacks internal curve settings PowerFactory needs), with the
curve table replaced: one row per time value, [I_melt, t, I_clear, t], as in the library.

Placement (Fig. 6): a fuse on a line sits in the cubicle at the upstream end of the line,
a fuse on a load drop sits in the load's cubicle.

The script then applies a bolted fault below each line fuse (DG out of service) and compares
PowerFactory's fuse melting time with eq. (6). The report is printed in the Output Window and
saved as Fuse_setup.txt.

Run: Python Script (ComPython) in the study case -> Execute.
"""

import os
from math import log10

import powerfactory as pf

OUT_DIR = r"D:\Protection and co-ordination\Result\Logs"
OUT_TXT = os.path.join(OUT_DIR, "Fuse_setup.txt")
OUT_PF = os.path.join(OUT_DIR, "PF_output_window.txt")
os.makedirs(OUT_DIR, exist_ok=True)

A_FUSE = -1.8
F_HZ = 60.0
T_RANGE = (0.01, 1000.0)    # time range of the curve tables (s)
N_POINTS = 25
U_RATED = 4.16              # kV
I_RATED = 100.0             # A, rating written to each fuse type

TYPE_FOLDER = "Fuse Types Yousaf 2022"
K_TCT = [1.2]               # clearing / melting current ratio, taken from the template

# name, location, b_i (Table III of the paper)
#   ("line", from, to): upstream end of the branch from -> to
#   ("load", node):     cubicle of the load at node
#   ("trf_lv", trf):    LV side of the transformer
#   ("dl",):            distributed load(s) along 632-671
FUSES = [
    ("F632",   ("line", "632", "645"), 6.38),
    ("F633",   ("line", "632", "633"), 6.83),
    ("F634",   ("trf_lv", "XFM-1"),    8.32),
    ("F645",   ("load", "645"),        6.65),
    ("F646",   ("line", "645", "646"), 6.67),
    ("F-DL",   ("dl",),                6.54),
    ("F671",   ("line", "671", "680"), 6.08),
    ("F671-1", ("line", "671", "692"), 5.85),
    ("F692",   ("load", "692"),        6.13),
    ("F692-R", ("line", "692", "675"), 6.14),
    ("F675",   ("load", "675"),        6.19),
    ("F671-2", ("line", "671", "684"), 5.87),
    ("F684",   ("line", "684", "611"), 6.15),
    ("F611",   ("load", "611"),        6.19),
    ("F652",   ("line", "684", "652"), 6.17),
]

BRANCH_CLASSES = ("ElmLne", "ElmTr2", "ElmCoup", "ElmZpu", "ElmSind", "ElmVoltreg")
CUBICLE_KEYS = ("bus1", "bus2", "bushv", "buslv")
PHASES = ("A", "B", "C")
FUSE_VARS = ["c:ttrip", "c:tmelt", "c:tclear", "c:yt", "c:Ifuse", "c:Iprim", "c:I"]
TYPE_ATTRS = {"TypFuse": ["itype", "chartype", "interpol", "frq", "urat", "irat",
                          "Ibnom", "Ipnom", "pmelt"],
              "TypChatoc": ["i_use", "i_type", "i_multx", "i_curves", "i_drawt", "tresunit",
                            "imin", "imax", "tmin", "rTp", "rResetT", "expr"]}

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


def setattr_ok(obj, name, value, quiet=False):
    try:
        obj.SetAttribute(name, value)
        return True
    except Exception as e:
        if not quiet:
            out("    could not set %s.%s = %s (%s)" % (obj.loc_name, name, value, e))
        return False


def show(v):
    if hasattr(v, "loc_name"):
        return "%s (%s)" % (v.loc_name, v.GetClassName())
    if isinstance(v, float):
        return "%.4g" % v
    return str(v)


def mmt(b, i):
    return 10.0 ** b * i ** A_FUSE


def tct(b, i):
    return mmt(b, i / K_TCT[0])


# ---- curve tables ------------------------------------------------------------------------
def get_matrix(obj):
    """vmat as a list of rows (empty list if not set)."""
    v = attr(obj, "vmat")
    if not v:
        return []
    if not isinstance(v[0], (list, tuple)):
        return [list(v)]
    return [list(r) for r in v]


def dump_type(obj):
    out("  %s  [%s]" % (obj.GetFullName(), obj.GetClassName()))
    for a in TYPE_ATTRS[obj.GetClassName()]:
        out("    %-9s = %s" % (a, show(attr(obj, a))))
    try:
        shape = obj.GetAttributeShape("vmat")
    except Exception:
        shape = "?"
    m = get_matrix(obj)
    out("    vmat shape %s, %d rows" % (shape, len(m)))
    for r in m[:4] + (["..."] if len(m) > 6 else []) + (m[-2:] if len(m) > 6 else m[4:]):
        out("      %s" % (r if r == "..." else ", ".join("%.5g" % x for x in r)))


def layout(m, irat):
    """Library curve table: one row per point, columns in (current, time) pairs, e.g.
    S&C SMD-50: [I_melt, t_melt, I_clear, t_clear], unused cells -1. Current in A or in
    multiples of the rating."""
    if not m or len(m[0]) < 2 or len(m[0]) % 2:
        return None
    currents = [r[0] for r in m if r[0] > 0]
    if not currents:
        return None
    return dict(pairs=len(m[0]) // 2, multiples=min(currents) < 0.5 * irat)


def write_curve(obj, lay, b, irat):
    """Fuse b's curve in the library layout: one row per time value (falling), each
    (current, time) pair one curve - melting, then clearing at K x the current."""
    scale = irat if lay["multiples"] else 1.0
    m = []
    for k in range(N_POINTS):
        t = T_RANGE[1] * (T_RANGE[0] / T_RANGE[1]) ** (k / (N_POINTS - 1.0))
        i = (t / 10.0 ** b) ** (1.0 / A_FUSE)
        row = []
        for c in range(lay["pairs"]):
            row += [i * (K_TCT[0] if c else 1.0) / scale, t]
        m.append(row)
    try:
        obj.SetAttributeShape("vmat", [len(m), len(m[0])])
    except Exception:
        pass
    return setattr_ok(obj, "vmat", m) and m


def tct_ratio(ch):
    """Median clearing/melting current ratio of a library table [I1, t, I2, t]."""
    r = sorted(row[2] / row[0] for row in get_matrix(ch)
               if len(row) >= 4 and row[0] > 0 and row[2] > 0)
    return r[len(r) // 2] if r else None


def find_library_fuse():
    """Library fuse type to copy settings from: a melting curve table in (current, time)
    pairs, preferably tested (not in the 'Untested' folder) and with time settings (rTp)."""
    best, best_score = None, -1
    for t in app.GetGlobalLibrary().GetContents("*.TypFuse", 1):
        ch = attr(t, "pmelt")
        if ch is None or layout(get_matrix(ch), attr(t, "irat", I_RATED)) is None:
            continue
        score = ((0 if "untested" in t.GetFullName().lower() else 4) +
                 (2 if str(attr(ch, "rTp", "")).strip() else 0) +
                 (1 if attr(ch, "i_curves") == 2 else 0))
        if score > best_score:
            best, best_score = t, score
    return best


def remove_previous():
    """Delete fuses and fuse types made by an earlier run of this script."""
    names = [f[0] for f in FUSES]
    n = 0
    for fuse in app.GetCalcRelevantObjects("*.RelFuse"):
        if any(fuse.loc_name == x or fuse.loc_name.startswith(x + "-") for x in names):
            fuse.Delete()
            n += 1
    found = app.GetProjectFolder("equip").GetContents(TYPE_FOLDER + ".IntFolder")
    for f in found:
        f.Delete()
    if n or found:
        out("Removed %d fuses and the type folder of an earlier run." % n)


def type_folder():
    equip = app.GetProjectFolder("equip")
    found = equip.GetContents(TYPE_FOLDER + ".IntFolder")
    return found[0] if found else equip.CreateObject("IntFolder", TYPE_FOLDER)


def copy_from_library(folder, obj, name):
    found = folder.GetContents("%s.%s" % (name, obj.GetClassName()))
    if found:
        return found[0]
    new = folder.AddCopy(obj, name)
    if new is None:
        res = folder.PasteCopy(obj, 1)
        new = res[1] if isinstance(res, (list, tuple)) else None
        if new is not None:
            new.loc_name = name
    if new is None:
        raise RuntimeError("could not copy %s into %s" % (obj.GetFullName(), folder.loc_name))
    return new


def make_types(folder, name, b, lib):
    """TypFuse + TypChatoc for fuse 'name', copied from the library fuse 'lib' with the
    curve table replaced. Returns the TypFuse and a note on what was written."""
    tname = "Yousaf %s" % name              # no '=' or '.' allowed in object names
    typ = copy_from_library(folder, lib, tname)
    ch = copy_from_library(folder, attr(lib, "pmelt"), tname + " melt")
    setattr_ok(typ, "pmelt", ch)
    setattr_ok(typ, "desc", ["b_i = %.2f, a_i = %.1f (Yousaf et al. 2022, Table III)"
                             % (b, A_FUSE)], quiet=True)
    setattr_ok(typ, "frq", F_HZ, quiet=True)
    setattr_ok(typ, "urat", U_RATED, quiet=True)
    setattr_ok(typ, "irat", I_RATED, quiet=True)
    lay = layout(get_matrix(attr(lib, "pmelt")), attr(lib, "irat", I_RATED))
    m = write_curve(ch, lay, b, I_RATED)
    back = get_matrix(ch)
    same = bool(m) and len(back) == len(m) and all(
        abs(x - y) <= 1e-4 * abs(y) for r1, r2 in zip(back, m) for x, y in zip(r1, r2))
    if name == FUSES[0][0]:
        out("Curve written for %s:" % name)
        dump_type(ch)
    return typ, "%s curve table written%s" % (
        "melting + clearing" if lay["pairs"] >= 2 else "melting",
        "" if same else "  <-- TABLE READ BACK DIFFERENT, see dump")


# ---- network -----------------------------------------------------------------------------
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


def line_cubicle(frm, to):
    """Cubicle at 'frm' of the branch leading to 'to'. With parallel conductors (e.g. a
    separate neutral), the branch carrying the most load current is taken."""
    f, t = TERMS[frm], TERMS[to]
    best = None
    for br in branches_at(f):
        ends = branch_ends(br)
        keys = [k for k, n in ends.items() if n == f]
        others = [n for n in ends.values() if n != f]
        if keys and others and reaches(others, t, f):
            i = max(abs(attr(br, "m:I:%s:%s" % (keys[0], p), 0.0)) for p in PHASES)
            if best is None or i > best[0]:
                best = (i, br, keys[0])
    if best is None:
        return None, None, None
    return attr(best[1], best[2]), best[1], best[2]


def loads_at(node):
    res = []
    for ld in app.GetCalcRelevantObjects("*.ElmLod"):
        cub = attr(ld, "bus1")
        if cub is not None and attr(cub, "cterm") == TERMS[node]:
            res.append(ld)
    return res


def load_power(ld):
    return abs(attr(ld, "m:P:bus1", 0.0)) + abs(attr(ld, "plini", 0.0))


def distributed_loads():
    res = []
    for ld in app.GetCalcRelevantObjects("*.ElmLod"):
        cub = attr(ld, "bus1")
        t = attr(cub, "cterm") if cub is not None else None
        if "istrib" in ld.loc_name or (t is not None and t.loc_name.lower().startswith("ndl")):
            res.append(ld)
    return res


def locate(loc):
    """List of (cubicle, description, branch, key) for a fuse location."""
    kind = loc[0]
    if kind == "line":
        cub, br, key = line_cubicle(loc[1], loc[2])
        return [(cub, "%s end of %s (towards %s)" % (loc[1], br.loc_name, loc[2]), br, key)] \
            if cub else []
    if kind == "trf_lv":
        tr = app.GetCalcRelevantObjects(loc[1] + ".ElmTr2")
        return [(attr(tr[0], "buslv"), "LV side of %s" % loc[1], tr[0], "buslv")] if tr else []
    if kind == "load":
        lds = sorted(loads_at(loc[1]), key=load_power, reverse=True)
        return [(attr(lds[0], "bus1"), "load %s at %s" % (lds[0].loc_name, loc[1]),
                 lds[0], "bus1")] if lds else []
    if kind == "dl":
        return [(attr(ld, "bus1"), "load %s at %s" % (ld.loc_name,
                 attr(attr(ld, "bus1"), "cterm").loc_name), ld, "bus1")
                for ld in distributed_loads()]
    return []


def element_phases(elem):
    """Number of phases of the element the fuse protects (None = not known)."""
    cls = elem.GetClassName()
    if cls in ("ElmLne", "ElmLod"):
        return attr(attr(elem, "typ_id"), "nlnph")
    if cls == "ElmCoup":
        return attr(elem, "nphase")
    return 3


def cub_phases(cub, elem):
    """Phases of the fuse: count from the terminal and the element, which terminal
    phases from the cubicle's phase map (it2p1, it2p2)."""
    n = min([attr(t, "nphase", 3) or 3 for t in branch_ends(elem).values()] or [3])
    ne = element_phases(elem)
    if ne:
        n = min(n, int(ne))
    return [attr(cub, "it2p%d" % (k + 1), k) for k in range(n)]


def node_nphase(node):
    return attr(TERMS[node], "nphase", 3) or 3


def place(name, cub, typ, elem):
    found = cub.GetContents(name + ".RelFuse")
    fuse = found[0] if found else cub.CreateObject("RelFuse", name)
    fuse.typ_id = typ
    setattr_ok(fuse, "outserv", 0)
    setattr_ok(fuse, "on_off", 1)
    ph = cub_phases(cub, elem)
    setattr_ok(fuse, "nphase", len(ph), quiet=True)
    if len(ph) < 3:
        setattr_ok(fuse, "it2p1", ph[0], quiet=True)
        if len(ph) == 2:
            setattr_ok(fuse, "it2p2", ph[1], quiet=True)
    return fuse, ph, not found


# ---- check -------------------------------------------------------------------------------
SHC = app.GetFromStudyCase("ComShc")


def bolted_fault(node, prot=1):
    """Bolted fault at node: 3-phase, line-line or line-ground by phases present.
    Returns True if one of the trials solved (the last solved one stays in memory)."""
    n = node_nphase(node)
    trials = ([("3rst", 0)] if n >= 3 else
              [("2psc", p) for p in range(3)] if n == 2 else
              [("spgf", p) for p in range(3)])
    SHC.iopt_mde = 3
    SHC.iopt_allbus = 0
    SHC.shcobj = TERMS[node]
    SHC.Rf = 0.0
    SHC.Xf = 0.0
    setattr_ok(SHC, "iopt_prot", prot, quiet=True)
    ok = False
    for kind, p in trials:
        SHC.iopt_shc = kind
        sel = {"spgf": "i_pspgf", "2psc": "i_p2psc"}.get(kind)
        if sel:
            setattr_ok(SHC, sel, p, quiet=True)
        if SHC.Execute() == 0:
            ok = True
            if kind == "3rst":
                break
            # keep the phase (pair) that exists: non-zero fault current
            if max(abs(attr(TERMS[node], "m:Ikss:%s" % q, 0.0)) for q in PHASES) > 1e-6:
                break
    return ok


def check(placed):
    out("=" * 86)
    out("CHECK: bolted fault just below each line fuse, DG out of service")
    out("%-7s %-5s | %8s | %8s %8s | %s" % ("Fuse", "fault", "I_fuse", "MMT eq6", "TCT",
                                            "PowerFactory result variables"))
    out("%-7s %-5s | %8s | %8s %8s |" % ("", "at", "(A)", "(s)", "(s)"))
    out("-" * 86)
    try:
        for name, loc, b, fuse, br, key in placed:
            if loc[0] == "line":
                node = loc[2]
            elif loc[0] == "trf_lv":
                node = attr(attr(br, "buslv"), "cterm").loc_name
            else:
                continue
            if not bolted_fault(node):
                out("%-7s %-5s | short circuit failed" % (name, node))
                continue
            i = 1000.0 * max(abs(attr(br, "m:Ikss:%s:%s" % (key, p), 0.0)) for p in PHASES)
            res = ["%s=%s" % (v, show(attr(fuse, v))) for v in FUSE_VARS
                   if attr(fuse, v) is not None]
            out("%-7s %-5s | %8.0f | %8.3f %8.3f | %s" % (
                name, node, i, mmt(b, i), tct(b, i), "  ".join(res) or "none"))
    finally:
        pass
    out("-" * 86)
    out("Load fuses (F645, F692, F675, F611, F-DL) carry no current for a bus fault and are")
    out("not checked here; their curves are built the same way.")


def network_state():
    """Report what can de-energise part of the feeder: dead nodes after the load flow,
    open switches and out-of-service elements. Switches in the cubicles where fuses go
    are closed (as the recloser script does for R1/R2)."""
    dead = [n for n, t in sorted(TERMS.items())
            if max(abs(attr(t, "m:u:%s" % p, 0.0)) for p in PHASES) < 0.05]
    out("Network state after the load flow (DG out of service):")
    out("  de-energised nodes : %s" % (", ".join(dead) or "none"))
    opened = []
    for sw in (app.GetCalcRelevantObjects("*.StaSwitch") +
               app.GetCalcRelevantObjects("*.ElmCoup")):
        if attr(sw, "on_off") == 0:
            opened.append(sw)
            out("  OPEN switch        : %s" % sw.GetFullName())
    for cls in ("ElmLne", "ElmTr2", "ElmCoup", "ElmTerm", "ElmXnet", "ElmLod"):
        for e in app.GetCalcRelevantObjects("*." + cls):
            if attr(e, "outserv") == 1:
                out("  out of service     : %s (%s)" % (e.loc_name, cls))
    return dead, opened


def close_fuse_switches(where, opened):
    """Close open switches in the cubicles that get a fuse and in the recloser cubicles
    (an open R1 breaker at RG60 de-energises the whole feeder)."""
    cubs = {spot[0].GetFullName() for spots in where.values() for spot in spots}
    cubs |= {r.GetParent().GetFullName() for r in app.GetCalcRelevantObjects("*.ElmRelay")}
    n = 0
    for sw in opened:
        par = sw.GetParent()
        if sw.GetClassName() == "StaSwitch" and par is not None and par.GetFullName() in cubs:
            sw.on_off = 1
            n += 1
            out("  closed %s in %s (%s)" % (sw.loc_name, par.loc_name,
                                            attr(par, "cterm").loc_name))
    return n


def test_first_fuse(folder, lib, where):
    """Build F632 alone and run the short circuit below it in several variants, so the
    report shows which part of the fuse (if any) PowerFactory rejects."""
    name, loc, b = FUSES[0]
    cub, spot, br, key = where[name][0]
    node = loc[2]
    res = [("no fuse in the network", bolted_fault(node))]
    typ, _ = make_types(folder, name, b, lib)
    fuse, ph, _ = place(name, cub, typ, br)
    res.append(("%s in service (%d-phase)" % (name, len(ph)), bolted_fault(node)))
    setattr_ok(SHC, "iopt_prot", 0, quiet=True)
    res.append(("%s in service, protection not evaluated" % name, bolted_fault(node, prot=0)))
    setattr_ok(fuse, "outserv", 1)
    res.append(("%s out of service" % name, bolted_fault(node)))
    setattr_ok(fuse, "outserv", 0)
    setattr_ok(fuse, "nphase", 3)
    res.append(("%s set to 3-phase" % name, bolted_fault(node)))
    out("Short-circuit test at %s:" % node)
    for what, ok in res:
        out("  %-48s %s" % (what, "OK" if ok else "FAILED"))
    out("  %s settings: %s" % (name, ", ".join("%s=%s" % (a, show(attr(fuse, a))) for a in (
        "nphase", "it2p1", "it2p2", "on_off", "outserv", "calcuse", "iphauto", "nneutral"))))
    out("  type %s: %s" % (typ.loc_name, ", ".join("%s=%s" % (a, show(attr(typ, a))) for a in (
        "itype", "chartype", "interpol", "frq", "urat", "irat", "pmelt"))))
    fuse.Delete()


def main():
    try:
        app.GetOutputWindow().Clear()
    except Exception:
        pass

    lib = find_library_fuse()
    if lib is None:
        out("No fuse type with a curve table found in the DIgSILENT library - stopped.")
        return
    out("Library fuse used as the template:")
    dump_type(lib)
    dump_type(attr(lib, "pmelt"))
    K_TCT[0] = tct_ratio(attr(lib, "pmelt")) or K_TCT[0]
    out("Clearing / melting current ratio of the template: %.2f" % K_TCT[0])

    dgs = app.GetCalcRelevantObjects("*.ElmSym")
    dg_state = [g.outserv for g in dgs]
    placed = []
    try:
        remove_previous()
        for g in dgs:
            g.outserv = 1
        ldf = app.GetFromStudyCase("ComLdf")
        ldf.iopt_net = 1
        if ldf.Execute() != 0:
            out("Load flow failed - phases and parallel conductors cannot be checked.")

        where = {name: locate(loc) for name, loc, b in FUSES}   # needs load-flow currents
        dead, opened = network_state()
        if close_fuse_switches(where, opened):
            if ldf.Execute() == 0:
                network_state()
                where = {name: locate(loc) for name, loc, b in FUSES}

        folder = type_folder()
        out("=" * 86)
        out("FUSES  (MMT: log10 t = %.1f log10 I + b_i,  TCT at %.2f x the MMT current)" % (
            A_FUSE, K_TCT[0]))
        out("-" * 86)
        test_first_fuse(folder, lib, where)
        for name, loc, b in FUSES:
            spots = where[name]
            if not spots:
                out("%-7s b=%.2f  location %s NOT FOUND - not placed" % (name, b, loc))
                continue
            typ, note = make_types(folder, name, b, lib)
            for k, (cub, spot, br, key) in enumerate(spots):
                fname = name if k == 0 else "%s-%d" % (name, k + 1)
                fuse, ph, new = place(fname, cub, typ, br)
                out("%-7s b=%.2f  %-42s %d-phase (nphase %s, it2p1 %s, it2p2 %s)  %s" % (
                    fname, b, spot, len(ph), attr(fuse, "nphase"),
                    attr(fuse, "it2p1"), attr(fuse, "it2p2"), "added" if new else "updated"))
                placed.append((fname, loc, b, fuse, br, key))
            out("        type %s: %s" % (typ.loc_name, note))

        # Sample of the curve written, for comparison with the paper's plots
        out("-" * 86)
        out("Curve samples (MMT / TCT in s):")
        out("  %-7s %16s %16s %16s" % ("Fuse", "1 kA", "3 kA", "10 kA"))
        for name, loc, b in FUSES:
            out("  %-7s %16s %16s %16s" % (name, *("%.3f / %.3f" % (mmt(b, i), tct(b, i))
                                                   for i in (1000.0, 3000.0, 10000.0))))
        check(placed)
    finally:
        for g, s in zip(dgs, dg_state):
            g.outserv = s

    out("=" * 86)
    out("Fuses in the network: %d" % len(app.GetCalcRelevantObjects("*.RelFuse")))


def save():
    with open(OUT_TXT, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    app.PrintPlain("Saved: " + OUT_TXT)
    try:
        app.GetOutputWindow().Save(OUT_PF)
    except Exception:
        pass


try:
    main()
except Exception:
    import traceback
    out("SCRIPT STOPPED WITH AN ERROR:")
    for s in traceback.format_exc().splitlines():
        out("  " + s)
    raise
finally:
    save()
