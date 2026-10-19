"""
Runs the EMT simulation of one Fig. 10 project and leaves the project active with the page "Curve plot"
in front, so PowerFactory opens on the filled plot (PowerFactory closed).

    python open_plot.py            -> "DG in"
    python open_plot.py "DG out"
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "DSDR_Study"))
from pf_setup import get_app, STUDY_CASE          # noqa: E402

tag = sys.argv[1] if len(sys.argv) > 1 else "DG in"
VARS = ["m:I:bus2:A", "m:I:bus2:C"]

app = get_app()
ow = app.GetOutputWindow()
user = app.GetCurrentUser()
prj = user.GetContents("IEEE13 Fig10 EMT - %s.IntPrj" % tag)[0]
prj.Activate()
case = app.GetProjectFolder("study").GetContents(STUDY_CASE + ".IntCase", 1)[0]
case.Activate()
res = case.GetContents("Fig10 EMT.ElmRes")[0]
line = app.GetCalcRelevantObjects("LOHL650-632.ElmLne")[0]

print("events of the study case:")
for e in case.GetContents("*.IntEvt")[0].GetContents():
    print("   %-28s %-10s t = %s s  out of service = %s" % (e.loc_name, e.GetClassName(), e.GetAttribute("time"),
                                                             e.GetAttribute("outserv")))

inc, sim = app.GetFromStudyCase("ComInc"), app.GetFromStudyCase("ComSim")
inc.SetAttribute("iopt_sim", "ins")
inc.SetAttribute("dtemt", 1e-4)
inc.SetAttribute("p_resvar", res)
sim.SetAttribute("tstop", 2.0)
ow.Clear()
e1 = inc.Execute()
e2 = sim.Execute() if not e1 else 1
print("initial conditions: %s, simulation: %s" % ("FAILED" if e1 else "ok", "FAILED" if e2 else "ok"))
for typ in (ow.MessageType.Error, ow.MessageType.Warn):
    for m in ow.GetContent(typ):
        print("   PF:", m)

res.Load()
print("result file rows:", res.GetNumberOfRows(), "columns:", [res.FindColumn(line, v) for v in VARS])
res.Release()

desk = case.GetContents("*.SetDesktop", 1)[0]
print("pages:", [p.loc_name + "." + p.GetClassName() for p in desk.GetContents()])
page = desk.GetContents("Curve plot.GrpPage")[0]
plot = page.GetContents("*.PltLinebarplot")[0]
ds = plot.GetDataSeries()
for key, val in (("curveTableElement", [line, line]), ("curveTableVariable", VARS),
                 ("curveTableResultFile", [res, res]), ("useIndividualResults", 1)):
    ds.SetAttribute(key, val)
for how in (lambda: desk.Show(page), page.Show, plot.DoAutoScale, lambda: plot.DoAutoScaleX(), lambda: plot.DoAutoScaleY()):
    try:
        how()
    except Exception as e:
        print("   note:", e)
# the project stays active: PowerFactory opens on it
print("left active:", app.GetActiveProject().loc_name)
