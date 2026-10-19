"""
Step 2 - load flows and short circuits in PowerFactory (complete method, unbalanced).

Saves results/studies.json with, for every case, the phase currents (A) through R1, R2, every
fuse and every Table II branch.  The currents do not depend on the protection settings, so the
design (step 3) can be iterated in Python without re-running PowerFactory.

Cases
  loadflow   DG out / DG in                              -> Inom (Table II), reverse current at R2
  max        all nodes x LG/LL/LLG/LLL x phases, Rf = 0, DG out and DG in (100 %)
  min        LG through 3 ohm at all nodes, DG out        -> If,min (Table II)
  pen        LLL at 633 and 671, DG penetration 0-100 %   (kept in studies.json; Fig. 7 is not produced)
  figures    the faults of Figs. 8-13, 15, 16 and Fig. 10 (DG in)
"""

import json
import os

from pf_setup import activate, attr, out, obj, lib_type, RESULTS, dg_units, clean_variation, save_table1
from protection_data import FUSES, RECLOSERS, NODES, NODE_ORDER, PF_FAULT, TABLE2_BRANCHES

app = activate()
ldf = app.GetFromStudyCase("ComLdf")
shc = app.GetFromStudyCase("ComShc")
shc.SetAttribute("iopt_mde", 3)          # complete method (prefault load flow)
shc.SetAttribute("iopt_allbus", 0)

# ---- measuring points ------------------------------------------------------------------------
POINTS = {}
for name, cfg in RECLOSERS.items():
    POINTS[name] = cfg["loc"]
for name, (loc, _, _) in FUSES.items():
    POINTS[name] = loc
for frm, to, br, side, _ in TABLE2_BRANCHES:
    POINTS["%s-%s" % (frm, to)] = ("line", br, side)


def element(loc):
    if loc[0] == "load":
        return obj(loc[1], "ElmLod"), "bus1"
    for cls in ("ElmLne", "ElmTr2", "ElmCoup"):
        hits = app.GetCalcRelevantObjects("%s.%s" % (loc[1], cls))
        if hits:
            return hits[0], loc[2]
    raise KeyError(loc)


ELEMENTS = {k: element(v) for k, v in POINTS.items()}
TERMS = {t.loc_name: t for t in app.GetCalcRelevantObjects("*.ElmTerm")}


def currents(var, scale=1000.0):
    """Phase currents in A (short-circuit results are in kA, load-flow results in A)."""
    res = {}
    for k, (e, side) in ELEMENTS.items():
        res[k] = [round(scale * abs(attr(e, "%s:%s:%s" % (var, side, p), 0.0)), 2) for p in "ABC"]
    return res


# ---- DG penetration ---------------------------------------------------------------------------
sym = dg_units()[0]
dg_tr = obj("2-Winding Transformer", "ElmTr2")
BASE = dict(sgn=attr(sym.typ_id, "sgn"), strn=attr(dg_tr.typ_id, "strn"),
            pgini=attr(sym, "pgini"), qgini=attr(sym, "qgini"))
save_table1()                            # Table I as it is in the model (results/Table_I_model.json)


def set_penetration(p):
    """p = DG rating / 4.05 MVA (4.05 MVA = total feeder load, so 1.0 = 100 %)."""
    if p <= 0:
        sym.SetAttribute("outserv", 1)
        return
    sym.SetAttribute("outserv", 0)
    sym.typ_id.SetAttribute("sgn", BASE["sgn"] * p)
    dg_tr.typ_id.SetAttribute("strn", BASE["strn"] * p)
    sym.SetAttribute("pgini", BASE["pgini"] * p)
    sym.SetAttribute("qgini", BASE["qgini"] * p)


# ---- short circuits ---------------------------------------------------------------------------
PH_ATTR = {"spgf": "i_pspgf", "2psc": "i_p2psc", "2pgf": "i_p2pgf"}


def run_fault(where, ftype, index=0, rf=0.0, xf=0.0, dist=None):
    """where: terminal name, or line name with dist = % from bus1. Returns dict or None."""
    code = PF_FAULT[ftype]
    if dist is None:
        shc.SetAttribute("shcobj", TERMS[where])
    else:
        shc.SetAttribute("shcobj", obj(where, "ElmLne"))
        shc.SetAttribute("ppro", float(dist))
    shc.SetAttribute("iopt_shc", code)
    if code in PH_ATTR:
        shc.SetAttribute(PH_ATTR[code], index)
    shc.SetAttribute("Rf", rf)
    shc.SetAttribute("Xf", xf)
    if shc.Execute() != 0:
        return None
    if dist is None:
        t = TERMS[where]
        ifault = [round(1000.0 * abs(attr(t, "m:Ikss:" + p, 0.0)), 2) for p in "ABC"]
    else:
        ifault = None
    faulted = None
    if ifault:
        big = max(ifault)
        faulted = "".join(p for p, i in zip("ABC", ifault) if big > 0 and i > 0.2 * big)
    return dict(where=where, type=ftype, index=index, rf=rf, dist=dist, phases=faulted,
                ifault=ifault, I=currents("m:Ikss"))


def sweep(dg, rf=0.0, types=("LG", "LL", "LLG", "LLL"), nodes=NODE_ORDER, tag="max"):
    res = []
    for node in nodes:
        for ft in types:
            seen = set()
            for idx in ([0] if ft == "LLL" else [0, 1, 2]):
                r = run_fault(node, ft, idx, rf)
                if r is None or not r["phases"]:
                    continue
                key = r["phases"]
                if ft != "LLL" and (key in seen or len(key) != (1 if ft == "LG" else 2)):
                    continue
                if not set(key) <= set(NODES[node]["phases"]):
                    continue
                seen.add(key)
                r.update(case=tag, dg=dg)
                res.append(r)
    return res


def loadflow(dg_on):
    set_penetration(1.0 if dg_on else 0.0)
    if ldf.Execute() != 0:
        raise RuntimeError("load flow failed")
    res = currents("m:I", 1.0)
    e, side = ELEMENTS["R2"]
    res["R2_P_kW"] = round(attr(e, "m:Psum:%s" % side, 0.0), 1)
    res["DG_P_MW"] = round(attr(sym, "m:Psum:bus1", 0.0) / 1000.0, 3) if dg_on else 0.0
    return res


data = dict(points={k: list(v) for k, v in POINTS.items()})
data["loadflow"] = {"dg_out": loadflow(False), "dg_in": loadflow(True)}
out("Load flow: R2 %.0f kW (DG out) / %.0f kW (DG in)" % (
    data["loadflow"]["dg_out"]["R2_P_kW"], data["loadflow"]["dg_in"]["R2_P_kW"]))

faults = []
set_penetration(0.0)
faults += sweep(0.0, tag="max")
faults += sweep(0.0, rf=3.0, types=("LG",), tag="min")
set_penetration(1.0)
faults += sweep(1.0, tag="max")
faults += sweep(1.0, rf=3.0, types=("LG",), tag="min")
out("Node sweeps: %d faults" % len(faults))

for p in (0.0, 0.10, 0.25, 0.37, 0.50, 0.75, 1.0):
    set_penetration(p)
    for r in sweep(p, types=("LLL",), nodes=["633", "671"], tag="pen"):
        faults.append(r)

# Figure faults (DG in service).  Fig. 9: LLG at the middle of 692-675 through 1 ohm;
# Fig. 13: 3-phase at 10 % of 632-633; Fig. 10: LL (a-c) at 684 through 0.2 ohm.
set_penetration(1.0)
FIG = [("Fig8", "611", "LG", None, 0.0, None), ("Fig9", "LC692-675", "LLG", None, 1.0, 50.0),
       ("Fig10", "684", "LL", "AC", 0.2, None), ("Fig11", "646", "LL", "BC", 1.0, None),
       ("Fig12", "645", "LL", "BC", 1.5, None), ("Fig13", "LOHL632-633", "LLL", None, 0.0, 10.0),
       ("Fig15", "646", "LL", "BC", 0.0, None)]
for fig, where, ft, want, rf, dist in FIG:
    for idx in ([0] if ft in ("LLL",) else [0, 1, 2]):
        r = run_fault(where, ft, idx, rf, dist=dist)
        if r is None:
            continue
        if want and r["phases"] != want:
            continue
        if dist is not None and ft == "LLG" and idx != 1:      # b-c on the 3-phase cable
            continue
        r.update(case=fig, dg=1.0)
        faults.append(r)
        out("  %s: %s %s at %s%s, Rf %.1f -> R1 %.0f A, R2 %.0f A" % (
            fig, ft, r["phases"] or "", where, "" if dist is None else " (%.0f %%)" % dist, rf,
            max(r["I"]["R1"]), max(r["I"]["R2"])))
        break

data["faults"] = faults

# ---- curve data used by the Python analysis (identical to the PowerFactory types) -------------
curves = {"fuses": {}}
for name, (loc, tname, _) in FUSES.items():
    t = obj(name, "RelFuse").typ_id         # keyed by the installed type: step 4 may have revised the size
    curves["fuses"][t.loc_name] = dict(irat=attr(t, "irat"), vmat=[list(r) for r in t.GetAttribute("vmat")])
a055c = lib_type("A055C200E.TypFuse", "ProtFuse").GetParent()
for t in a055c.GetContents("A055C*.TypFuse"):                 # every size, for fuse revision
    curves["fuses"].setdefault(t.loc_name, dict(irat=attr(t, "irat"),
                                                vmat=[list(r) for r in t.GetAttribute("vmat")]))
cdg = obj("R2 Fast", "ElmRelay").GetContents("*.RelToc")[0]
ch = attr(cdg, "pcharac")
curves["cdg"] = dict(name=ch.loc_name, imin=attr(ch, "imin"), imax=attr(ch, "imax"),
                     tmin=attr(ch, "tmin"), vmat=[list(r) for r in ch.GetAttribute("vmat")])
iac = attr(obj("R1 Fast", "ElmRelay").GetContents("Toc.RelToc")[0], "pcharac")
curves["iac"] = dict(name=iac.loc_name, expr=attr(iac, "expr"), imin=attr(iac, "imin"),
                     imax=attr(iac, "imax"))
data["curves"] = curves
set_penetration(1.0)
ldf.Execute()
with open(os.path.join(RESULTS, "studies.json"), "w") as f:
    json.dump(data, f, indent=1)
clean_variation()                       # DG switching above was recorded in the study case's variation
out("Saved %d fault cases to results/studies.json" % len(faults))
