"""
Progress demo: everything in one run, in the PowerFactory Output Window.

  1. Table II  (maximum / minimum / rated branch current)       IEEE13_Tables.py
     Table III (fuse coefficients b_i)
  2. Table IV  (R1, R2 and fuse operating times), model and paper Table_IV.py
  3. Fig. 14   (coordination without the DSDR), model and paper  Fig14_Coordination.py
  4. Fig. 17   (coordination with the DSDR),    model and paper
  5. Figs. 8, 9, 11, 12, 13, 16: time-overcurrent plot pages     Figure_Plots.py

Each script can still be run on its own. Tables II and III are also saved in the Result folder.

PowerFactory keeps its Python session between runs. Application objects left over from an
earlier run are destroyed before connecting, and this run's are released at the end, so a
late clean-up can never disconnect a running script ("Application already deleted").

Run: Python Script (ComPython) in the study case -> Execute, with the single-line diagram
open (needed for the plot pages).
"""

import gc
import os
import runpy

import powerfactory as pf

DIR = r"D:\Protection and co-ordination"
SHOW_FIG17 = True
MAKE_PLOTS = True          # draw the plot pages Fig 8 ... Fig 16 (Figure_Plots.py)
OUT_TXT = os.path.join(DIR, "Result", "Show_Progress_output.txt")

gc.collect()               # destroy Application objects left over from earlier runs
app = pf.GetApplication()
loaded = []                # namespaces of the scripts used in this run


def banner(text):
    app.PrintPlain("")
    app.PrintPlain("#" * 90)
    app.PrintPlain("#  " + text)
    app.PrintPlain("#" * 90)


def load(name):
    """Functions of a script, without running it. The script gets this script's
    Application object: calling GetApplication() again invalidates the first one."""
    g = runpy.run_path(os.path.join(DIR, name), run_name="progress",
                       init_globals={"app": app})
    loaded.append(g)
    return g


def run():
    try:
        app.GetOutputWindow().Clear()
    except Exception:
        pass

    banner("1. TABLES II AND III  -  IEEE 13-node feeder (Yousaf et al. 2022)")
    load("IEEE13_Tables.py")["main"]()

    banner("2. TABLE IV  -  operating times of R1, R2 and the fuses, model and paper")
    load("Table_IV.py")["main"](clear=False)

    fig = load("Fig14_Coordination.py")
    banner("3. FIG. 14  -  recloser-fuse coordination WITHOUT the DSDR")
    fig["main"](clear=False, dsdr=False)
    if SHOW_FIG17:
        banner("4. FIG. 17  -  recloser-fuse coordination WITH the DSDR")
        fig["main"](clear=False, dsdr=True)

    if MAKE_PLOTS:
        banner("5. FIGS. 8, 9, 11, 12, 13, 16  -  time-overcurrent plots (pages 'Fig 8' ...)")
        load("Figure_Plots.py")["main"](clear=False)


try:
    run()
finally:
    try:
        app.EchoOn()
        app.GetOutputWindow().Save(OUT_TXT)
        app.PrintPlain("Output Window saved: " + OUT_TXT)
    except Exception as e:
        try:
            app.PrintWarn("Could not save the Output Window: %s" % e)
        except Exception:
            pass
    for g in loaded:       # break the script namespaces' reference cycles now,
        g.clear()          # so no Application object outlives this run
    loaded.clear()
    del app
    gc.collect()
