"""
Runs the whole replication from a clean start (about 5 minutes).  PowerFactory must be closed
(engine mode cannot start while its window is open).

  step1  build the protection system in the IEEE 13-node feeder          (PowerFactory)
  step2  load flows and short circuits                                      (PowerFactory)
  step3  design by the paper's method, Tables II-IV, Figs. 8, 9, 11-17      (Python)
         Tables I-IV into results/database (Table IV with fuse t_MMT); Figs. 1-6  (Python)
  step4  settings into PowerFactory + check of PowerFactory's trip times    (PowerFactory)
  step5  Fig. 10 in EMT                                                     (PowerFactory)
  load flow on all buses and branches; load-flow / short-circuit database   (PowerFactory)
  coordination diagrams                                                     (Python)
The model is left with the DSDR settings (Fig. 17).
(The report, presentation and comparison PDFs are delivered ready-made in the main folder; the
scripts that produced them are not part of this folder.)
"""

import subprocess
import sys

STEPS = [["step1_build_model.py"], ["step2_studies.py"], ["step3_design_and_evaluate.py"],
         ["make_tables.py"], ["make_figures_1_to_6.py"],
         ["step4_apply_settings.py", "conventional"], ["step5_fig10_emt.py"],
         ["step4_apply_settings.py", "dsdr"],
         ["loadflow_all_buses.py"], ["database_study.py"],
         ["make_coordination_diagrams.py"]]

for step in STEPS:
    print("\n" + "=" * 90 + "\n" + " ".join(step) + "\n" + "=" * 90, flush=True)
    rc = subprocess.call([sys.executable] + step)
    if rc:
        sys.exit("%s failed (exit code %d)" % (step[0], rc))
