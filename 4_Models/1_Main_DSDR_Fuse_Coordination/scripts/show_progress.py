"""
Script behind the PowerFactory script object "Final(1)".  The report appears in the Output Window.

First (always)     load flow on all buses and branches, "From node -> To node", DG disconnected
                   and connected                                          loadflow_all_buses.py

Stage 1 (RUN_DATABASE)  load-flow and short-circuit database, DG disconnected and connected, with the
                   current through R1 and R2 and its direction, If,max, If,min and a validation
                   checklist                                                  database_study.py
                   -> results/database/  (no relay or fuse setting is touched)

Stage 2 (only when RUN_COORDINATION = True, i.e. after the database has been checked)
                   design by the paper's method: Tables II, III, IV, Figs. 14, 17;
                   settings written into the model and PowerFactory's trip times checked;
                   Tables I-IV (Table IV with the fuse t_MMT) -> results/database/   make_tables.py
                                                    step2_studies.py, step3_..., step4_...

While it runs, PowerFactory fills the Output Window with its own messages (a fault on a phase a
bus does not have is reported as "Short-circuit calculation not possible"; that is normal).  At the
end the window is cleared and only the report is printed.  The report is also saved as
results/Show_Progress_output.txt.

Replaces the old Show_Progress.py, which needs relays named "R1" and "R2"; in this model they are
"R1 Fast", "R1 Delayed", "R2 Fast", "R2 Delayed", "R2 Rev Fast", "R2 Rev Delayed".

Run: Python Script (ComPython) -> Execute.  The model is left in the study case
"Study with Substation Transformer".
"""

import contextlib
import csv
import gc
import io
import os
import runpy
import subprocess
import sys
import traceback



def _find_dir():
    """Folder of the scripts: C:\\DSDR\\1_Main_DSDR_Fuse_Coordination\\scripts (the folder copied as in the guide),
    or the folder of this file."""
    cands = [r"C:\DSDR\1_Main_DSDR_Fuse_Coordination\scripts"]
    try:
        cands.append(os.path.dirname(os.path.abspath(__file__)))
    except NameError:
        pass
    for c in cands:
        if os.path.isfile(os.path.join(c, "pf_setup.py")):
            return c
    raise RuntimeError("Scripts folder not found. Copy the folder 1_Main_DSDR_Fuse_Coordination to C:\\DSDR "
                       "(so that C:\\DSDR\\1_Main_DSDR_Fuse_Coordination\\scripts\\pf_setup.py exists).")


DIR = _find_dir()
RES = os.path.join(DIR, "results")
OUT_TXT = os.path.join(RES, "Show_Progress_output.txt")
RUN_DATABASE = True           # False: only the load flow on all buses and branches
RUN_COORDINATION = True       # stage 2 after the database; switched on 2026-10-01 (database accepted)
OWN = ("pf_setup", "protection_data", "curves", "step3_design_and_evaluate")


def forget():
    """PowerFactory keeps its Python session between runs: drop this project's modules (and with
    them the Application object of an earlier run) so every run starts clean."""
    for m in OWN:
        sys.modules.pop(m, None)
    gc.collect()


forget()
if DIR not in sys.path:
    sys.path.insert(0, DIR)
import pf_setup

app = pf_setup.get_app()
report = []
pf_setup.out = lambda msg="": report.append(str(msg))      # the steps' messages go into the report


def banner(text):
    report.extend(["", "#" * 100, "#  " + text, "#" * 100])


def step(script, *args):
    """Run one step of the pipeline; what it prints goes into the report."""
    argv = getattr(sys, "argv", None)
    sys.argv = [script] + list(args)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            runpy.run_path(os.path.join(DIR, script), run_name="__main__")
    finally:
        report.extend(buf.getvalue().splitlines())
        if argv is None:
            del sys.argv
        else:
            sys.argv = argv
        sys.modules.pop("step3_design_and_evaluate", None)   # step 4 must read the new results


def external(script):
    """Run a step that needs no PowerFactory with the normal python.exe: PowerFactory's built-in
    interpreter is some 50 times slower on pure calculation (step 3: 13 minutes instead of 15 s)."""
    exe = os.path.join(os.path.dirname(os.path.dirname(os.__file__)), "python.exe")
    if not os.path.isfile(exe):
        return step(script)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run([exe, os.path.join(DIR, script)], cwd=DIR, env=env, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    report.extend(p.stdout.decode("utf-8", "replace").splitlines())
    if p.returncode:
        raise RuntimeError("%s failed (exit code %d)" % (script, p.returncode))


def grid(title, column):
    """Fig. 14 / 17 as text: one symbol per faulted node and fault type."""
    rows = list(csv.DictReader(open(os.path.join(RES, "Fig14_Fig17_classification.csv"))))
    nodes = []
    for r in rows:
        if r["node"] not in nodes:
            nodes.append(r["node"])
    sym = {"held": "v", "lost": "x", "n/a": "-"}
    report.extend(["", "   " + title, "   (v) exists   (x) doesn't exist   (-) not applicable"])
    for ft in ("LG", "LL", "LLG", "LLL"):
        cells = {r["node"]: sym[r[column]] for r in rows if r["fault"] == ft}
        report.append("   %-4s |" % ft + "".join("  (%s) " % cells[n] for n in nodes))
    report.append("        +" + "-" * (6 * len(nodes)) + "> faulted node")
    report.append("         " + "".join(" %-5s" % n for n in nodes))


def run():
    app.PrintPlain("Running. PowerFactory's messages below are replaced by the report at the end.")
    app.EchoOff()
    banner("LOAD FLOW ON ALL BUSES AND BRANCHES  (From node -> To node; no setting is changed)")
    step("loadflow_all_buses.py")
    if not RUN_DATABASE:
        report.extend(["", "Short-circuit database and relay coordination not run: RUN_DATABASE = False in show_progress.py."])
        return
    banner("STAGE 1 - LOAD-FLOW AND SHORT-CIRCUIT DATABASE  (no relay or fuse setting is changed)")
    step("database_study.py")
    if not RUN_COORDINATION:
        report.extend(["", "Relay coordination (pickup, fast / delayed operation, TDS, TCC, CTI) has NOT been run:",
                       "RUN_COORDINATION = False in show_progress.py. Set it to True once the database is accepted."])
        return
    banner("STAGE 2 - RELAY COORDINATION")
    banner("1. LOAD FLOWS AND SHORT CIRCUITS  (PowerFactory, complete method, unbalanced)")
    step("step2_studies.py")
    banner("2. DESIGN BY THE PAPER'S METHOD  -  Tables II, III, IV; Figs. 14, 17")
    external("step3_design_and_evaluate.py")
    banner("FIG. 14 AND FIG. 17  -  recloser-fuse coordination, DG 4.05 MVA at 692")
    grid("Fig. 14: without the DSDR", "without DSDR (Fig14)")
    grid("Fig. 17: with the DSDR", "with DSDR (Fig17)")
    banner("3. DSDR SETTINGS IN THE MODEL  -  PowerFactory's trip times against the calculation")
    step("step4_apply_settings.py", "dsdr")
    banner("4. TABLES I-IV OF THE PAPER  (Table IV with the fuse t_MMT and t_TCT)  -> results/database/")
    external("make_tables.py")
    external("make_figures_1_to_6.py")
    report.extend(["", "Figures: " + os.path.join(RES, "figures") + "  (Fig01 ... Fig17)",
                   "Tables:  " + os.path.join(RES, "database") + "  (Table_I ... Table_IV csv, Tables_I_to_IV.txt)"])


try:
    try:
        run()
    except Exception:
        report.extend(["", "SCRIPT STOPPED WITH AN ERROR:"] + ["  " + s for s in traceback.format_exc().splitlines()])
        raise
    finally:
        try:
            app.EchoOn()
            app.GetOutputWindow().Clear()
        except Exception:
            pass
        for line in report:
            app.PrintPlain(line)
        with open(OUT_TXT, "w", encoding="utf-8") as fh:
            fh.write("\n".join(report) + "\n")
        app.PrintPlain("Report saved: " + OUT_TXT)
finally:
    del app
    forget()
