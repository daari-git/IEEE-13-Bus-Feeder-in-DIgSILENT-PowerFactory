"""Sets the variable and the result file of the two curves explicitly and reads them back (PowerFactory closed)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "DSDR_Study"))
from pf_setup import get_app, attr, STUDY_CASE          # noqa: E402

app = get_app()
user = app.GetCurrentUser()
VARS = ["m:I:bus2:A", "m:I:bus2:C"]


def show(ds, keys):
    for key in keys:
        try:
            v = ds.GetAttribute(key)
        except Exception as e:
            v = "ERR %s" % type(e).__name__
        if isinstance(v, list):
            v = [getattr(x, "loc_name", x) for x in v]
        else:
            v = getattr(v, "loc_name", v)
        print("      %-24s %s" % (key, v))


for tag in ("DG in", "DG out"):
    prj = user.GetContents("IEEE13 Fig10 EMT - %s.IntPrj" % tag)[0]
    prj.Activate()
    case = app.GetProjectFolder("study").GetContents(STUDY_CASE + ".IntCase", 1)[0]
    case.Activate()
    res = case.GetContents("Fig10 EMT.ElmRes")[0]
    line = app.GetCalcRelevantObjects("LOHL650-632.ElmLne")[0]
    page = case.GetContents("*.SetDesktop", 1)[0].GetContents("Curve plot.GrpPage")[0]
    ds = page.GetContents("*.PltDataseries", 1)[0]
    print(tag)
    for key, val in (("curveTableElement", [line, line]), ("curveTableVariable", VARS),
                     ("curveTableResultFile", [res, res]), ("useIndividualResults", 1)):
        try:
            ds.SetAttribute(key, val)
        except Exception as e:
            print("   could not set %s: %s" % (key, e))
    show(ds, ["curveTableElement", "curveTableVariable", "curveTableResultFile", "useIndividualResults",
              "curveTableVisible", "curveTableColor", "curveTableLabel"])
    # the variables must also be in the result file's variable set
    res.Load()
    print("      columns found in 'Fig10 EMT':", [res.FindColumn(line, v) for v in VARS], "rows", res.GetNumberOfRows())
    res.Release()
    try:
        page.GetContents("*.PltLinebarplot")[0].DoAutoScale()
    except Exception:
        pass
    prj.Deactivate()
