"""
Shared PowerFactory helpers for the replication of

  M. Yousaf, A. Jalilian, K. M. Muttaqi, D. Sutanto, "An Adaptive Overcurrent Protection Scheme
  for Dual-Setting Directional Recloser and Fuse Coordination in Unbalanced Distribution Networks
  With Distributed Generation", IEEE Trans. Ind. Appl., 58(2), 1831-1842, 2022.

Runs either inside PowerFactory (ComPython) or from a normal Python 3.9 shell (engine mode).
"""

import os
import sys

def _find_pf_dir():
    """Folder of PowerFactory 2021 on this computer (the newest installed 2021 version)."""
    cands = [os.environ.get("POWERFACTORY_DIR", "")]
    for base in (r"C:\Program Files\DIgSILENT", r"C:\Program Files (x86)\DIgSILENT"):
        if os.path.isdir(base):
            cands += sorted((os.path.join(base, d) for d in os.listdir(base) if d.startswith("PowerFactory 2021")),
                            reverse=True)
    for c in cands:
        if c and os.path.isfile(os.path.join(c, "PowerFactory.exe")):
            return c
    return r"C:\Program Files\DIgSILENT\PowerFactory 2021 SP2"


PF_DIR = _find_pf_dir()
PROJECT = "IEEE13 DSDR Fuse Coordination"
# The ready model (01_MAIN_model_STANDIN_copy_DSDR_DG100pct.pfd) imports under this name (guide, section 3).
READY_PROJECT = "IEEE13 DSDR penetration 100 %"
PFD_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "IEEE 13 Node Feeder.pfd")
# The IEEE short-circuit benchmark (Kersting & Shirek 2012, used in ref. [8]) includes the
# 115/4.16 kV 5 MVA substation transformer; this study case reproduces it within ~2 %.
STUDY_CASE = "Study with Substation Transformer"
# Protection devices are built in the base network (this case has no active variation), so they
# exist in every study case; the substation transformer case then adds only its variation.
BUILD_CASE = "Study Detailed Network Model"

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
os.makedirs(RESULTS, exist_ok=True)

_app = None


def get_app():
    global _app
    if _app is not None:
        return _app
    try:
        import powerfactory as pf                  # inside PowerFactory
    except ImportError:
        os.environ["PATH"] = PF_DIR + ";" + os.environ["PATH"]
        sys.path.append(os.path.join(PF_DIR, "Python", "%d.%d" % sys.version_info[:2]))
        import powerfactory as pf
    _app = pf.GetApplication()
    if _app is None:
        raise RuntimeError("Could not start PowerFactory")
    return _app


def attr(obj, name, default=None):
    try:
        v = obj.GetAttribute(name)
        return default if v is None else v
    except Exception:
        return default


def out(msg=""):
    print(msg)
    try:
        get_app().PrintPlain(msg)
    except Exception:
        pass


def activate(build=False):
    """Activate the replication project (importing the .pfd the first time) and the study case
    (BUILD_CASE for model changes, STUDY_CASE for calculations)."""
    app = get_app()
    user = app.GetCurrentUser()
    prj = user.GetContents(PROJECT + ".IntPrj")
    if not prj:
        # the model the user imported and activated (guide, section 3), whatever its name ...
        act = app.GetActiveProject()
        if act is not None and act.GetContents("R1 Fast.ElmRelay", 1):
            prj = [act]
    if not prj:
        # ... or the ready model imported but not active (engine mode)
        prj = user.GetContents(READY_PROJECT + ".IntPrj")
    if not prj:
        # otherwise start from the network without the final protection
        before = {p.loc_name for p in user.GetContents("*.IntPrj")}
        imp = user.CreateObject("CompfdImport", "import")
        imp.SetAttribute("e:g_file", PFD_FILE)
        imp.SetAttribute("g_target", user)
        imp.Execute()
        imp.Delete()
        new = [p for p in user.GetContents("*.IntPrj") if p.loc_name not in before]
        new[0].SetAttribute("loc_name", PROJECT)
        prj = [new[0]]
    prj[0].Activate()
    clean_variation()
    name = BUILD_CASE if build else STUDY_CASE
    case = app.GetProjectFolder("study").GetContents(name + ".IntCase", 1)[0]
    case.Activate()
    ldf = app.GetFromStudyCase("ComLdf")
    ldf.SetAttribute("iopt_net", 1)                # unbalanced 3-phase load flow
    return app


# The "Substation Transformer" variation as delivered in the .pfd: 13 objects.  Anything else in its
# stage was recorded by a script (or a click) that changed the network while STUDY_CASE was active -
# DG in / out, relay or fuse settings, a breaker closed - and overrides the base network from then on.
_ORIGINAL_STAGE = {"Substation Transformer": {
    "Terminal", "2-Winding Transformer", "Cub_1", "Switch", "Cub_5", "Switch(1)", "External Grid(1)", "Cub_2",
    "Switch(2)", "Cub_4", "External Grid", "GND611(1)", "Cub_6"}}


def clean_variation():
    """Restore the variation stage to its original objects, so that the base network applies."""
    app = get_app()
    n = 0
    for st in app.GetActiveProject().GetContents("*.IntSstage", 1):
        keep = _ORIGINAL_STAGE.get(st.loc_name)
        if keep is None:
            continue
        for o in st.GetContents():
            if o.loc_name not in keep:
                o.Delete()
                n += 1
    return n


def obj(name, cls):
    hits = get_app().GetCalcRelevantObjects("%s.%s" % (name, cls))
    if not hits:
        raise KeyError("%s.%s not found" % (name, cls))
    return hits[0]


def lib_type(pattern, must_contain=""):
    hits = [h for h in get_app().GetGlobalLibrary().GetContents(pattern, 1)
            if must_contain in h.GetFullName() and "\\Arch\\" not in h.GetFullName()
            and "\\v001\\" not in h.GetFullName()]
    if not hits:
        raise KeyError("library type %s (%s) not found" % (pattern, must_contain))
    return hits[0]


def dg_units():
    return get_app().GetCalcRelevantObjects("*.ElmSym")


def save_table1():
    """Read the DG and its transformer back from the model -> results/Table_I_model.json (Table I)."""
    import json
    sym = dg_units()[0]
    typ = sym.typ_id
    tr = obj("2-Winding Transformer", "ElmTr2").typ_id
    keys = ("sgn", "ugn", "iturbo", "xl", "rstr", "xd", "xq", "xds", "xqs", "xdss", "xqss", "tds0", "tdss0", "tqs0",
            "tqss0", "h")
    data = {k: round(float(attr(typ, k, float("nan"))), 5) for k in keys}
    data.update(tr_strn=round(attr(tr, "strn"), 4), tr_hv=round(attr(tr, "utrn_h"), 4), tr_lv=round(attr(tr, "utrn_l"), 4),
                tr_uk=round(attr(tr, "uktr"), 4), node=sym.bus1.cterm.loc_name, type=typ.loc_name)
    with open(os.path.join(RESULTS, "Table_I_model.json"), "w") as fh:
        json.dump(data, fh, indent=1)
    return data


def set_dg(in_service):
    for g in dg_units():
        g.SetAttribute("outserv", 0 if in_service else 1)
