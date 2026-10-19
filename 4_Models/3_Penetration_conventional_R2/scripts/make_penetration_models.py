"""
DG penetration study (Fig. 7 of Yousaf et al. 2022) in separate PowerFactory models.

For every penetration level p (0, 10, 25, 37, 50, 75, 100 % of the 4.05 MVA DG):
  * the main project "IEEE13 DSDR Fuse Coordination" is COPIED to a new project
    "IEEE13 DG penetration <p> %"; the original project is only read, never changed;
  * in the copy the DG at 692 is set to p x 4.05 MVA (machine, its 0.69/4.16 kV transformer and its
    active / reactive power scaled together; per-unit impedances unchanged; p = 0: DG out of service);
  * the copy gets the CONVENTIONAL protection of the replication (no DSDR: the reverse units of R2
    out of service, fuse sizes of the design without DG) - Fig. 7 shows the preset scheme degrading;
  * load flow and short circuits are run and PowerFactory's own relay and fuse elements give the
    operating times (c:Ttrip);
  * the copy is exported to pfd/IEEE13_DG_penetration_<p>.pfd.

Faults (complete method, bolted):
  633  "internal" (R1's zone): fault at node 633, below fuse F633;   pair F633 - R1 fast
  671  "external" (R2's zone): fault on the lateral that leaves node 671 through its fuse F671-2,
       at node 684 (the lateral is 300 ft long; PowerFactory does not accept a fault inside this
       two-phase line);  pair F671-2 - R2 fast.  The lateral has phases a and c only.
Both fuses carry the grid share AND the DG share; the recloser carries only the grid share.

Output: results/penetration_results.json.  PowerFactory must be closed.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPL = os.path.join(os.path.dirname(HERE), "DSDR_Study")
sys.path.insert(0, REPL)
from pf_setup import get_app, attr, PROJECT, STUDY_CASE, BUILD_CASE   # noqa: E402

LEVELS = [0, 10, 25, 37, 50, 75, 100]
S_DG = 4.05                                      # MVA, rating of the DG of the study
PFD = os.path.join(HERE, "pfd")
RES = os.path.join(HERE, "results")
os.makedirs(PFD, exist_ok=True)
os.makedirs(RES, exist_ok=True)
CONV = json.load(open(os.path.join(REPL, "results", "settings.json")))["conventional"]

app = get_app()
user = app.GetCurrentUser()
if app.GetActiveProject() is not None:
    app.GetActiveProject().Deactivate()
orig = user.GetContents(PROJECT + ".IntPrj")[0]


def say(msg):
    print(msg, flush=True)


def one(name, cls):
    hits = app.GetCalcRelevantObjects("%s.%s" % (name, cls))
    if not hits:
        raise KeyError(name + "." + cls)
    return hits[0]


def case(name):
    c = app.GetProjectFolder("study").GetContents(name + ".IntCase", 1)[0]
    c.Activate()
    return c


def lib_fuse(tname):
    hits = [h for h in app.GetGlobalLibrary().GetContents(tname + ".TypFuse", 1)
            if "ProtFuse" in h.GetFullName() and "\\Arch\\" not in h.GetFullName()]
    return hits[0]


def trip(o):
    """PowerFactory's operating time of a relay (fastest active time-overcurrent element) or a fuse."""
    objs = [t for t in o.GetContents("*.RelToc") if not attr(t, "outserv")] if o.GetClassName() == "ElmRelay" else [o]
    best = float("inf")
    for x in objs:
        v = attr(x, "c:Ttrip")
        for y in (v if isinstance(v, list) else [v]):
            if y is not None and 0 < y < 9999:
                best = min(best, y)
    return best


def i_max(el, side, var="m:Ikss", scale=1000.0):
    return max(scale * abs(attr(el, "%s:%s:%s" % (var, side, p), 0.0) or 0.0) for p in "ABC")


results = {}
for p in LEVELS:
    name = "IEEE13 DG penetration %03d %%" % p
    for old in user.GetContents(name + ".IntPrj"):          # a copy from an earlier run of THIS script
        old.Delete()
    prj = user.AddCopy(orig, name)
    prj.Activate()

    # ---- model changes in the base network (study case without variation) -----------------------
    case(BUILD_CASE)
    sym = one("Synchronous Machine", "ElmSym")
    tr = one("2-Winding Transformer", "ElmTr2")
    if p == 0:
        sym.SetAttribute("outserv", 1)
    else:
        k = p / 100.0
        sym.SetAttribute("outserv", 0)
        sym.typ_id.SetAttribute("sgn", S_DG * k)
        tr.typ_id.SetAttribute("strn", S_DG * k)
        sym.SetAttribute("pgini", 3.24 * k)                  # 0.8 x rating, as in the replication
        sym.SetAttribute("qgini", 2.43 * k)
    for fname, tname in CONV["fuses"].items():               # conventional scheme: no-DG fuse sizes
        one(fname, "RelFuse").typ_id = lib_fuse(tname)
    for u in ("R2 Rev Fast", "R2 Rev Delayed"):                # no reverse setting group
        one(u, "ElmRelay").SetAttribute("outserv", 1)

    # ---- calculations in the study case with the substation transformer -------------------------
    case(STUDY_CASE)
    ldf = app.GetFromStudyCase("ComLdf")
    ldf.SetAttribute("iopt_net", 1)
    if ldf.Execute() != 0:
        raise RuntimeError("load flow failed at %d %%" % p)
    r1_line, r2_line = one("LOHL650-632", "ElmLne"), one("LOHL632-671end", "ElmLne")
    lf = dict(
        dg_rating_MVA=round(S_DG * p / 100.0, 3),
        dg_P_MW=round(attr(sym, "m:Psum:bus1", 0.0) / 1000.0, 3) if p else 0.0,
        R1_A=round(i_max(r1_line, "bus1", "m:I", 1.0), 1),
        R1_P_kW=round(attr(r1_line, "m:Psum:bus1", 0.0), 1),
        R2_A=round(i_max(r2_line, "bus2", "m:I", 1.0), 1),
        R2_P_kW=round(-attr(r2_line, "m:Psum:bus2", 0.0), 1),       # + = towards 671 (forward)
        V={b: [round(attr(one(b, "ElmTerm"), "m:u:" + ph, 0.0), 4) for ph in "ABC"] for b in ("632", "633", "671", "692", "684")})

    shc = app.GetFromStudyCase("ComShc")
    shc.SetAttribute("iopt_mde", 3)
    shc.SetAttribute("iopt_allbus", 0)
    shc.SetAttribute("Rf", 0.0)
    shc.SetAttribute("Xf", 0.0)
    f633_line, lat = one("LOHL632-633", "ElmLne"), one("LOHL671-684", "ElmLne")
    faults = {}
    for key, where, dist, ftype, idx in (("633 LLL", one("633", "ElmTerm"), None, "3rst", 0),
                                         ("633 LL", one("633", "ElmTerm"), None, "2psc", 2),
                                         ("671 LL", one("684", "ElmTerm"), None, "2psc", 2),
                                         ("671 LG", one("684", "ElmTerm"), None, "spgf", 0)):
        shc.SetAttribute("shcobj", where)
        if dist is not None:
            shc.SetAttribute("ppro", dist)
        shc.SetAttribute("iopt_shc", ftype)
        fuse_el, fuse_side, rec, rec_unit = ((f633_line, "bus1", "R1", "R1 Fast") if key.startswith("633")
                                             else (lat, "bus1", "R2", "R2 Fast"))
        # phase selection: try every index, keep the one with the largest fuse current (the lateral
        # 671-684 has phases a and c only, so some indices are not possible there)
        best = None
        for k_ in ([0] if ftype == "3rst" else [0, 1, 2]):
            if ftype == "2psc":
                shc.SetAttribute("i_p2psc", k_)
            if ftype == "spgf":
                shc.SetAttribute("i_pspgf", k_)
            if shc.Execute() == 0:
                v = i_max(fuse_el, fuse_side)
                if best is None or v > best[1]:
                    best = (k_, v)
        if best is None:
            raise RuntimeError("short circuit failed: %s at %d %%" % (key, p))
        if ftype == "2psc":
            shc.SetAttribute("i_p2psc", best[0])
        if ftype == "spgf":
            shc.SetAttribute("i_pspgf", best[0])
        shc.Execute()
        faults[key] = dict(
            I_R1=round(i_max(r1_line, "bus1"), 1), I_R2=round(i_max(r2_line, "bus2"), 1),
            I_fuse=round(i_max(fuse_el, fuse_side), 1),
            I_DG=round(i_max(tr, "bushv"), 1) if p else 0.0,
            fuse="F633" if key.startswith("633") else "F671-2",
            recloser=rec,
            t_fuse_MMT=trip(one("F633" if key.startswith("633") else "F671-2", "RelFuse")),
            t_R1_fast=trip(one("R1 Fast", "ElmRelay")), t_R2_fast=trip(one("R2 Fast", "ElmRelay")),
            t_R1_delayed=trip(one("R1 Delayed", "ElmRelay")), t_R2_delayed=trip(one("R2 Delayed", "ElmRelay")))
        f = faults[key]
        f["t_rec_fast"] = f["t_R1_fast"] if rec == "R1" else f["t_R2_fast"]
        f["CTI_s"] = f["t_fuse_MMT"] - f["t_rec_fast"]
    results[p] = dict(project=name, loadflow=lf, faults=faults)
    f1, f2 = faults["633 LLL"], faults["671 LL"]
    say("%3d %%  DG %.2f MVA | 633 LLL: F633 %5.0f A %.3f s, R1 %5.0f A %.3f s, CTI %+.3f s | "
        "671 LL: F671-2 %5.0f A %.3f s, R2 %5.0f A %.3f s, CTI %+.3f s" % (
            p, S_DG * p / 100, f1["I_fuse"], f1["t_fuse_MMT"], f1["I_R1"], f1["t_rec_fast"], f1["CTI_s"],
            f2["I_fuse"], f2["t_fuse_MMT"], f2["I_R2"], f2["t_rec_fast"], f2["CTI_s"]))

    # ---- save the copy as its own .pfd file -----------------------------------------------------
    prj.Deactivate()
    path = os.path.join(PFD, "IEEE13_DG_penetration_%03d.pfd" % p)
    if os.path.exists(path):
        os.remove(path)
    exp = user.CreateObject("CompfdExport", "export")
    exp.SetAttribute("g_objects", [prj])
    for a in ("e:g_file", "g_file"):
        try:
            exp.SetAttribute(a, path)
            break
        except Exception:
            pass
    exp.Execute()
    exp.Delete()
    results[p]["pfd"] = os.path.basename(path) if os.path.exists(path) else None
    say("      saved %s" % (path if os.path.exists(path) else "-- EXPORT FAILED"))

json.dump(results, open(os.path.join(RES, "penetration_results.json"), "w"), indent=1)
say("results/penetration_results.json written; original project '%s' not modified" % PROJECT)
