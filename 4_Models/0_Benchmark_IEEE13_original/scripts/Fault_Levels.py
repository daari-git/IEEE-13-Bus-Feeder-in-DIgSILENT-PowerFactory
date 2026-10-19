"""
Fault levels per feeder section (From -> To) with the DG in service: Table II of the paper
recalculated by IEEE13_Tables.py with DG_IN_SERVICE = True.

  I_f,max : bolted 3-phase fault at the downstream node, maximum short-circuit currents
            (LL / LG where the node has fewer phases), current through the From end   [kA]
  I_f,min : line-to-ground fault through 3 ohm at the farthest downstream node(s),
            minimum short-circuit currents                                          [kA]

Saved as Result/Table_II_DG_in.csv (and Table_III_DG_in.csv); the DG-out Table_II.csv is
left untouched. The DG in-service state is restored at the end.

Run: inside PowerFactory as a Python Script (ComPython) -> Execute,
     or from a terminal with PowerFactory closed:  py -3.9 Fault_Levels.py
"""

import os
import runpy
import sys

sys.path.append(r"C:\Program Files\DIgSILENT\PowerFactory 2021 SP2\Python\3.9")
import powerfactory as pf

DIR = r"C:\Users\Rabin\Desktop\Digsilent_project"
PROJECT = "IEEE 13 Node Feeder"
DG_IN_SERVICE = True

try:
    app
except NameError:
    app = pf.GetApplication()
if app is None:
    sys.exit("Could not start PowerFactory: close the PowerFactory window and try again.")
if app.GetActiveProject() is None and app.ActivateProject(PROJECT) != 0:
    raise RuntimeError("Could not activate project '%s'" % PROJECT)

g = runpy.run_path(os.path.join(DIR, "IEEE13_Tables.py"), run_name="fault_levels",
                   init_globals={"app": app})
g = g["main"].__globals__                 # run_path returns a copy; main() reads this one
g["DG_IN_SERVICE"] = DG_IN_SERVICE
tag = "_DG_in" if DG_IN_SERVICE else "_DG_out"
save_csv = g["save_csv"]
g["save_csv"] = lambda name, *a: save_csv(name.replace(".csv", tag + ".csv"), *a)
g["main"]()
