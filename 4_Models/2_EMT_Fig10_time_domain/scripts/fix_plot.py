"""
Repairs the plot of the two EMT projects ("IEEE13 Fig10 EMT - DG out" / "- DG in"):

  * the page "Curve plot" shows phase currents a and c of line LOHL650-632 (632 end) from the result
    file "Fig10 EMT";
  * empty pages created by mistake ("Curve plot(1)", ...) are removed;
  * the title block no longer points to a picture file of another computer;
  * the EMT simulation is run once, so the plot is filled when the project is opened.

PowerFactory must be closed.  Nothing else in the projects is changed.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "DSDR_Study"))
from pf_setup import get_app, attr, STUDY_CASE          # noqa: E402

app = get_app()
user = app.GetCurrentUser()
VARS = ("m:I:bus2:A", "m:I:bus2:C")


def curves_of(ds):
    try:
        objs, names = ds.GetAttribute("curveTableElement"), ds.GetAttribute("curveTableVariable")
        return [(o.loc_name if o else None, v) for o, v in zip(objs or [], names or [])]
    except Exception:
        return None


for tag in ("DG out", "DG in"):
    name = "IEEE13 Fig10 EMT - %s" % tag
    prj = user.GetContents(name + ".IntPrj")
    if not prj:
        print("%s: project not found" % name)
        continue
    prj[0].Activate()
    case = app.GetProjectFolder("study").GetContents(STUDY_CASE + ".IntCase", 1)[0]
    case.Activate()
    res = case.GetContents("Fig10 EMT.ElmRes")[0]
    line = app.GetCalcRelevantObjects("LOHL650-632.ElmLne")[0]
    desk = case.GetContents("*.SetDesktop", 1)[0]
    pages = desk.GetContents("*.GrpPage")
    print("%s: plot pages before: %s" % (name, [p.loc_name for p in pages]))

    # 1. remove the empty pages made by mistake
    for p in pages:
        if p.loc_name != "Curve plot":
            series = p.GetContents("*.PltDataseries", 1)
            if not series or not any(curves_of(s) for s in series):
                print("   removed empty page '%s'" % p.loc_name)
                p.Delete()

    # 2. the page "Curve plot" with the two curves
    page = desk.GetContents("Curve plot.GrpPage")
    page = page[0] if page else desk.GetPage("Curve plot", 1, "GrpPage")
    plots = page.GetContents("*.PltLinebarplot")
    plot = plots[0] if plots else page.GetOrInsertCurvePlot("Current at node 632")
    ds = plot.GetDataSeries()
    have = curves_of(ds)
    want = [(line.loc_name, v) for v in VARS]
    if have != want:
        ds.ClearCurves()
        for v in VARS:
            ds.AddCurve(line, v)
        print("   curves set (were: %s)" % have)
    else:
        print("   curves already correct: %s" % have)
    for key, val in (("useIndividualResults", 0), ("autoSearchResultFile", 0), ("userDefinedResultFile", res)):
        try:
            ds.SetAttribute(key, val)
        except Exception:
            pass
    print("   result file of the plot: %s" % attr(attr(ds, "userDefinedResultFile"), "loc_name", "(automatic)"))

    # 3. title block: no picture file from another computer
    for t in desk.GetContents("*.SetTitm", 1) + case.GetContents("*.SetTitm", 1):
        for key in ("sLogo", "logoFile", "f_name"):
            v = attr(t, key)
            if isinstance(v, str) and v.lower().endswith((".png", ".jpg", ".bmp", ".wmf")) and not os.path.exists(v):
                t.SetAttribute(key, "")
                print("   title block '%s': removed missing picture %s" % (t.loc_name, v))

    # 4. run the simulation, so the plot is filled
    inc, sim = app.GetFromStudyCase("ComInc"), app.GetFromStudyCase("ComSim")
    inc.SetAttribute("iopt_sim", "ins")
    inc.SetAttribute("dtemt", 1e-4)
    inc.SetAttribute("p_resvar", res)
    sim.SetAttribute("tstop", 2.0)
    err = inc.Execute() or sim.Execute()
    res.Load()
    n = res.GetNumberOfRows()
    ca, cc = res.FindColumn(line, VARS[0]), res.FindColumn(line, VARS[1])
    peak = max(max(abs(res.GetValue(i, ca)[1]), abs(res.GetValue(i, cc)[1])) for i in range(0, n, 5)) if n and ca >= 0 else 0
    res.Release()
    print("   simulation %s: %d samples, peak current %.0f A" % ("FAILED" if err else "ok", n, peak))
    try:
        page.Show()
        plot.DoAutoScale()
    except Exception:
        pass
    print("   plot pages now: %s" % [p.loc_name for p in desk.GetContents("*.GrpPage")])
    prj[0].Deactivate()
print("done")
