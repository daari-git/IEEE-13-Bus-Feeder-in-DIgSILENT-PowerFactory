"""
Exports the PowerFactory projects of the study as .pfd files into  FINAL DELIVERABLES\\Models  (PowerFactory closed).

    python export_models.py check     -> only prints the state of each project
    python export_models.py export    -> writes the .pfd files

Projects (user database):
    IEEE13 DSDR Fuse Coordination      the model of the study (relays, fuses, DG, DSDR settings)
    IEEE13 Fig10 EMT - DG out / DG in  the time-domain projects (Curve plot page repaired)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pf_setup import get_app, PROJECT, STUDY_CASE          # noqa: E402

ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "FINAL DELIVERABLES", "Models")
PROJECTS = [(PROJECT, "01_MAIN_DSDR_Fuse_Coordination.pfd"),
            ("IEEE13 Fig10 EMT - DG out", "02_EMT_Fig10_DG_out.pfd"),
            ("IEEE13 Fig10 EMT - DG in", "03_EMT_Fig10_DG_in.pfd")]
mode = sys.argv[1] if len(sys.argv) > 1 else "check"

app = get_app()
user = app.GetCurrentUser()
os.makedirs(OUT, exist_ok=True)
for name, fname in PROJECTS:
    found = user.GetContents(name + ".IntPrj")
    if not found:
        print("%-36s NOT FOUND" % name)
        continue
    prj = found[0]
    prj.Activate()
    case = app.GetProjectFolder("study").GetContents(STUDY_CASE + ".IntCase", 1)
    if case:
        case[0].Activate()
    rel = app.GetCalcRelevantObjects("*.ElmRelay") or []
    fus = app.GetCalcRelevantObjects("*.RelFuse") or []
    sym = app.GetCalcRelevantObjects("*.ElmSym") or []
    allrel = app.GetProjectFolder("netdat").GetContents("*.ElmRelay", 1) or []
    allsym = app.GetProjectFolder("netdat").GetContents("*.ElmSym", 1) or []
    allfus = app.GetProjectFolder("netdat").GetContents("*.RelFuse", 1) or []
    out_rel = [o.loc_name for o in allrel if o.GetAttribute("outserv")]
    events = case[0].GetContents("*.IntEvt")[0].GetContents() if case and case[0].GetContents("*.IntEvt") else []
    var = [v.loc_name for v in (app.GetActiveNetworkVariations() or [])]
    print("%-36s relays %d (out of service %d), fuses %d, machines %d (out of service %d), events %d, variations %s" % (
        name, len(allrel), len(out_rel), len(allfus), len(allsym),
        len([o for o in allsym if o.GetAttribute("outserv")]), len(events), var or "none"))
    if out_rel:
        print("    relays out of service:", out_rel)
    prj.Deactivate()
    if mode == "export":
        path = os.path.join(OUT, fname)
        if os.path.exists(path):
            os.remove(path)
        exp = user.CreateObject("CompfdExport", "export")
        exp.SetAttribute("g_objects", [prj])
        exp.SetAttribute("e:g_file", path)
        exp.Execute()
        exp.Delete()
        print("    %s" % (("exported: %s (%d KB)" % (path, os.path.getsize(path) // 1024)) if os.path.exists(path) else "EXPORT FAILED"))
