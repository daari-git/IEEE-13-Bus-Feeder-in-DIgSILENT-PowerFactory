"""Exports the page "Curve plot" of the EMT projects as a picture (PowerFactory closed)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "DSDR_Study"))
from pf_setup import get_app, STUDY_CASE          # noqa: E402

app = get_app()
user = app.GetCurrentUser()
for tag in ("DG in", "DG out"):
    prj = user.GetContents("IEEE13 Fig10 EMT - %s.IntPrj" % tag)[0]
    prj.Activate()
    case = app.GetProjectFolder("study").GetContents(STUDY_CASE + ".IntCase", 1)[0]
    case.Activate()
    desk = case.GetContents("*.SetDesktop", 1)[0]
    page = desk.GetContents("Curve plot.GrpPage")[0]
    plot = page.GetContents("*.PltLinebarplot")[0]
    out = os.path.join(HERE, "results", "plot_check_%s.png" % tag.replace(" ", "_"))
    if os.path.exists(out):
        os.remove(out)
    for how in ("desk.Show(page)", "page.Show()"):
        try:
            eval(how)
            print(tag, how, "ok")
        except Exception as e:
            print(tag, how, "failed:", e)
    try:
        plot.DoAutoScale()
    except Exception as e:
        print("   autoscale:", e)
    wr = app.GetFromStudyCase("ComWr")
    wr.SetAttribute("iopt_rd", "png")
    wr.SetAttribute("f", out)
    print("   export:", wr.Execute(), os.path.exists(out))
    prj.Deactivate()
